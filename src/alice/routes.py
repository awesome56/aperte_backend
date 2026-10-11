"""ALICE Flask routes (unified — chat SSE + conversations + confirmed writes + MCP)."""

import json
import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify, Response, stream_with_context
from flask_jwt_extended import jwt_required, get_jwt_identity

from src.alice.agent import run_agent_stream
from src.alice.models import AliceConversation
from src.alice.tools import (
    TOOL_DEFINITIONS, SAFE_TOOLS, WRITE_TOOLS, ALL_EXECUTORS, execute_tool,
)
from src.database import db

alice = Blueprint('alice', __name__, url_prefix='/api/v1/alice')
mcp = Blueprint('mcp', __name__, url_prefix='/api/v1/mcp')


def _clean_messages(raw):
    out = []
    for m in raw or []:
        role = m.get('role')
        if role not in ('user', 'assistant'):
            continue
        content = m.get('content') or ''
        if isinstance(content, str) and not content.strip():
            continue
        out.append({'role': role,
                    'content': content if isinstance(content, str) else json.dumps(content)})
    return out


@alice.get('/health')
def health():
    from src.alice.agent import DEEPSEEK_API_KEY, DEEPSEEK_MODEL
    return jsonify({'success': True, 'service': 'alice',
                    'model_configured': bool(DEEPSEEK_API_KEY),
                    'model': DEEPSEEK_MODEL,
                    'tools': len(TOOL_DEFINITIONS)})


@alice.post('/chat')
@jwt_required()
def chat():
    user_id = int(get_jwt_identity())
    data = request.get_json(force=True, silent=True) or {}
    prompt = (data.get('prompt') or '').strip()
    if not prompt:
        return jsonify({'error': 'prompt is required'}), 400
    session_id = data.get('session_id') or 'conv-{}-{}'.format(
        int(datetime.now().timestamp() * 1000), uuid.uuid4().hex[:6])
    page_context = data.get('page_context') or {}
    incognito = bool(data.get('incognito'))

    def generate():
        for event in run_agent_stream(user_id, session_id, prompt, page_context, incognito):
            yield json.dumps(event, ensure_ascii=False) + '\n'

    headers = {'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache',
               'Connection': 'keep-alive', 'X-Accel-Buffering': 'no'}
    return Response(stream_with_context(generate()), headers=headers)


@alice.post('/execute')
@jwt_required()
def execute():
    """Execute a previously permission-gated WRITE tool after user confirmation."""
    user_id = int(get_jwt_identity())
    data = request.get_json(force=True, silent=True) or {}
    name = data.get('name')
    args = data.get('args') or {}
    if name not in WRITE_TOOLS:
        return jsonify({'success': False, 'message': 'Only confirmable write tools can run here.'}), 400
    result = execute_tool(name, args, user_id)
    return jsonify({'success': True, 'name': name, 'result': result})


@alice.post('/permission')
@jwt_required()
def permission():
    # Compat shim (HRMS used cache-backed allow/deny). Unified flow uses /execute instead.
    return jsonify({'success': True})


@alice.get('/conversations')
@jwt_required()
def conversations():
    user_id = int(get_jwt_identity())
    load_session = request.args.get('load')
    if load_session:
        conv = AliceConversation.query.filter_by(user_id=user_id, session_id=load_session).first()
        if not conv:
            return jsonify({'success': False, 'message': 'Conversation not found.'}), 404
        try:
            raw = json.loads(conv.messages_json or '[]')
        except ValueError:
            raw = []
        return jsonify({'success': True, 'messages': _clean_messages(raw)})
    convs = AliceConversation.query.filter_by(user_id=user_id)\
        .order_by(AliceConversation.updated_at.desc()).all()
    out = []
    for c in convs:
        try:
            count = len(json.loads(c.messages_json or '[]'))
        except ValueError:
            count = 0
        out.append({'session_id': c.session_id, 'title': c.title or 'Conversation',
                    'messages': count,
                    'updated_at': int(c.updated_at.timestamp()) if c.updated_at else 0})
    return jsonify({'success': True, 'conversations': out})


@alice.delete('/conversations/<session_id>')
@jwt_required()
def delete_conversation(session_id):
    user_id = int(get_jwt_identity())
    conv = AliceConversation.query.filter_by(user_id=user_id, session_id=session_id).first()
    if not conv:
        return jsonify({'success': False, 'message': 'Conversation not found.'}), 404
    db.session.delete(conv)
    db.session.commit()
    return jsonify({'success': True})


@alice.delete('/conversations')
@jwt_required()
def delete_all_conversations():
    user_id = int(get_jwt_identity())
    n = AliceConversation.query.filter_by(user_id=user_id).delete()
    db.session.commit()
    return jsonify({'success': True, 'message': '{} conversation(s) deleted.'.format(n)})


@alice.post('/conversations/<session_id>/rename')
@jwt_required()
def rename_conversation(session_id):
    user_id = int(get_jwt_identity())
    data = request.get_json(force=True, silent=True) or {}
    conv = AliceConversation.query.filter_by(user_id=user_id, session_id=session_id).first()
    if not conv:
        return jsonify({'success': False, 'message': 'Conversation not found.'}), 404
    conv.title = (data.get('title') or '')[:255] or conv.title
    conv.updated_at = datetime.now()
    db.session.commit()
    return jsonify({'success': True})


@alice.get('/conversations/<session_id>/export')
@jwt_required()
def export_conversation(session_id):
    user_id = int(get_jwt_identity())
    conv = AliceConversation.query.filter_by(user_id=user_id, session_id=session_id).first()
    if not conv:
        return jsonify({'success': False, 'message': 'Conversation not found.'}), 404
    try:
        raw = json.loads(conv.messages_json or '[]')
    except ValueError:
        raw = []
    clean = _clean_messages(raw)
    title = ''.join(c for c in (conv.title or 'conversation') if c.isalnum() or c in ' _-')[:50] or 'conversation'
    fmt = request.args.get('format', 'json')
    if fmt == 'txt':
        body = ''.join('## {}\n\n{}\n\n'.format('You' if m['role'] == 'user' else 'ALICE', m['content']) for m in clean)
        return Response(body, headers={'Content-Type': 'text/plain; charset=utf-8',
                                       'Content-Disposition': 'attachment; filename="{}.txt"'.format(title)})
    return Response(json.dumps(clean, ensure_ascii=False, indent=2),
                    headers={'Content-Type': 'application/json; charset=utf-8',
                             'Content-Disposition': 'attachment; filename="{}.json"'.format(title)})


# ---------------------------------------------------------------------------
# MCP endpoint (collapses the old Node mcp-server): standard JSON-RPC over HTTP.
# POST /api/v1/mcp  {jsonrpc, method: tools/list|tools/call, params:{name, arguments}, id}
# ---------------------------------------------------------------------------

def _mcp_tool_list():
    return [{'name': t['function']['name'],
             'description': t['function']['description'],
             'inputSchema': t['function']['parameters']} for t in TOOL_DEFINITIONS]


@mcp.post('')
@mcp.post('/')
@jwt_required()
def mcp_endpoint():
    user_id = int(get_jwt_identity())
    data = request.get_json(force=True, silent=True) or {}
    method = data.get('method')
    req_id = data.get('id', 1)
    if method == 'tools/list':
        return jsonify({'jsonrpc': '2.0', 'id': req_id, 'result': {'tools': _mcp_tool_list()}})
    if method == 'tools/call':
        params = data.get('params') or {}
        name = params.get('name')
        args = params.get('arguments') or {}
        if name in WRITE_TOOLS:
            return jsonify({'jsonrpc': '2.0', 'id': req_id,
                            'result': {'content': [{'type': 'text',
                                                    'text': json.dumps({'success': False, 'message': 'Write tools need confirmation via /api/v1/alice/execute.'})}]}})
        if name not in ALL_EXECUTORS:
            return jsonify({'jsonrpc': '2.0', 'id': req_id,
                            'error': {'code': -32601, 'message': 'Unknown tool {}'.format(name)}})
        result = execute_tool(name, args, user_id)
        return jsonify({'jsonrpc': '2.0', 'id': req_id,
                        'result': {'content': [{'type': 'text',
                                                'text': json.dumps(result, ensure_ascii=False, default=str)}]}})
    return jsonify({'jsonrpc': '2.0', 'id': req_id,
                    'error': {'code': -32600, 'message': 'Use method tools/list or tools/call.'}}), 400

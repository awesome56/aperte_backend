"""ALICE orchestration loop (unified — replaces HRMS agent_daemon + agent_runner).

Synchronous Flask-friendly streaming using httpx sync client against a
DeepSeek/OpenAI-compatible Chat Completions API. Yields JSON-serialisable
event dicts: session_start, content, tool_start, tool_end, request_permission,
action, done, error.

Fixes vs HRMS daemon:
- user_id is passed per-call (no global MCP_USER).
- provider error bodies are logged server-side with a correlation id; the user
  only sees a safe message.
- conversations persist in DB (AliceConversation), not JSON files.
- WRITE tools are never auto-executed: the loop emits request_permission and
  stops, waiting for frontend confirmation via POST /execute.
"""

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone

log = logging.getLogger('alice')

DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '').strip()
DEEPSEEK_MODEL = os.environ.get('DEEPSEEK_MODEL', 'deepseek-chat').strip()
DEEPSEEK_BASE_URL = os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com/v1').strip()
MAX_AGENT_ITERATIONS = 10

from src.alice.prompts import SYSTEM_INSTRUCTIONS
from src.alice.tools import TOOL_DEFINITIONS, SAFE_TOOLS, WRITE_TOOLS, execute_tool


def _headers():
    return {'Authorization': 'Bearer {}'.format(DEEPSEEK_API_KEY),
            'Content-Type': 'application/json'}


def _load_conversation(user_id, session_id):
    from src.alice.models import AliceConversation
    conv = AliceConversation.query.filter_by(user_id=user_id, session_id=session_id).first()
    if conv and conv.messages_json:
        try:
            msgs = json.loads(conv.messages_json)
            if isinstance(msgs, list):
                return conv, msgs
        except Exception:
            pass
    return conv, []


def _save_conversation(user_id, session_id, messages, in_tok=0, out_tok=0, title=None):
    from src.alice.models import AliceConversation
    from src.database import db
    conv = AliceConversation.query.filter_by(user_id=user_id, session_id=session_id).first()
    if not conv:
        first_user = next((m.get('content', '') for m in messages if m.get('role') == 'user'), '')
        conv = AliceConversation(user_id=user_id, session_id=session_id,
                                 title=(title or first_user[:80] or 'Conversation'),
                                 created_at=datetime.now(), updated_at=datetime.now())
        db.session.add(conv)
    conv.messages_json = json.dumps(messages, ensure_ascii=False, default=str)
    conv.input_tokens = (conv.input_tokens or 0) + (in_tok or 0)
    conv.output_tokens = (conv.output_tokens or 0) + (out_tok or 0)
    conv.updated_at = datetime.now()
    if title:
        conv.title = title[:255]
    elif not conv.title:
        first_user = next((m.get('content', '') for m in messages if m.get('role') == 'user'), '')
        conv.title = (first_user[:80] or 'Conversation')
    db.session.commit()
    return conv


def _system_message(page_context=None):
    today = datetime.now(timezone.utc).strftime('%A, %B %d, %Y')
    msg = ('## CURRENT DATE\nToday is {} (UTC). ALWAYS use this for date math. Never guess dates.\n\n'.format(today))
    if page_context and isinstance(page_context, dict):
        parts = ['## CURRENT PAGE CONTEXT']
        for key in ('path', 'title', 'heading'):
            if page_context.get(key):
                parts.append('- {}: {}'.format(key, page_context[key]))
        if parts:
            msg += '\n'.join(parts) + '\nUse this to answer questions about what the user is looking at.\n\n'
    msg += SYSTEM_INSTRUCTIONS
    return msg


def run_agent_stream(user_id, session_id, prompt, page_context=None, incognito=False):
    """Generator yielding event dicts for SSE (JSON lines)."""
    import httpx

    if not DEEPSEEK_API_KEY:
        yield {'type': 'error', 'content': "I'm not configured yet — please try again in a little while."}
        return

    _conv, history = _load_conversation(user_id, session_id)
    messages = [{'role': 'system', 'content': _system_message(page_context)}]
    # keep recent history (avoid unbounded growth)
    for m in history[-30:]:
        if m.get('role') in ('user', 'assistant', 'tool') and m.get('content') is not None:
            messages.append({k: m[k] for k in ('role', 'content', 'tool_calls', 'tool_call_id', 'name') if k in m})
    messages.append({'role': 'user', 'content': prompt})

    yield {'type': 'session_start', 'session_id': session_id}

    total_in, total_out = 0, 0
    try:
        with httpx.Client(timeout=120.0) as client:
            for _iteration in range(1, MAX_AGENT_ITERATIONS + 1):
                payload = {'model': DEEPSEEK_MODEL, 'messages': messages,
                           'tools': TOOL_DEFINITIONS, 'stream': True}
                full_content = ''
                tool_calls = []
                try:
                    with client.stream('POST', DEEPSEEK_BASE_URL + '/chat/completions',
                                       headers=_headers(), json=payload) as resp:
                        if resp.status_code != 200:
                            body = resp.read().decode(errors='replace')[:500]
                            cid = uuid.uuid4().hex[:8]
                            log.error('ALICE provider %s cid=%s body=%s', resp.status_code, cid, body)
                            yield {'type': 'error',
                                   'content': "I'm having trouble reaching my brain right now (ref {}). Please try again in a moment.".format(cid)}
                            return
                        for line in resp.iter_lines():
                            if not line or not line.startswith('data:'):
                                continue
                            data_str = line[5:].strip()
                            if data_str == '[DONE]':
                                break
                            try:
                                chunk = json.loads(data_str)
                            except ValueError:
                                continue
                            # token usage (some providers send at end)
                            usage = chunk.get('usage')
                            if usage:
                                total_in += usage.get('prompt_tokens') or 0
                                total_out += usage.get('completion_tokens') or 0
                            delta = (chunk.get('choices') or [{}])[0].get('delta', {})
                            if delta.get('content'):
                                full_content += delta['content']
                                yield {'type': 'content', 'content': delta['content']}
                            for tc in delta.get('tool_calls', []):
                                idx = tc.get('index', 0)
                                while len(tool_calls) <= idx:
                                    tool_calls.append({'id': '', 'type': 'function',
                                                       'function': {'name': '', 'arguments': ''}})
                                if tc.get('id'):
                                    tool_calls[idx]['id'] = tc['id']
                                if tc.get('type'):
                                    tool_calls[idx]['type'] = tc['type']
                                fn = tc.get('function', {})
                                if fn.get('name'):
                                    tool_calls[idx]['function']['name'] = fn['name']
                                if fn.get('arguments'):
                                    tool_calls[idx]['function']['arguments'] += fn['arguments']
                except Exception as e:
                    cid = uuid.uuid4().hex[:8]
                    log.exception('ALICE stream failed cid=%s', cid)
                    yield {'type': 'error',
                           'content': "Something went wrong on my end (ref {}). Please try again.".format(cid)}
                    return

                if not tool_calls:
                    if full_content:
                        messages.append({'role': 'assistant', 'content': full_content})
                    break

                messages.append({'role': 'assistant', 'content': full_content or None,
                                 'tool_calls': tool_calls})

                # execute tool calls — writes need confirmation
                for tc in tool_calls:
                    name = (tc.get('function') or {}).get('name', '')
                    try:
                        args = json.loads((tc.get('function') or {}).get('arguments') or '{}')
                    except ValueError:
                        args = {}
                    if not name:
                        continue
                    if name in WRITE_TOOLS:
                        req_id = uuid.uuid4().hex[:12]
                        yield {'type': 'request_permission', 'request_id': req_id,
                               'name': name, 'args': args}
                        # record pending confirmation as assistant text so history makes sense
                        messages.append({'role': 'assistant',
                                         'content': 'Needs confirmation: {} {}'.format(name, json.dumps(args)[:300])})
                        if not incognito:
                            _save_conversation(user_id, session_id, messages, total_in, total_out)
                            total_in, total_out = 0, 0
                        yield {'type': 'done'}
                        return
                    if name not in SAFE_TOOLS:
                        result = {'success': False, 'message': "I can't do that here."}
                        yield {'type': 'tool_end', 'name': name, 'result': json.dumps(result)}
                        messages.append({'role': 'tool', 'tool_call_id': tc.get('id'),
                                         'content': json.dumps(result)})
                        continue
                    yield {'type': 'tool_start', 'name': name, 'args': args}
                    try:
                        result = execute_tool(name, args, user_id)
                    except Exception as e:
                        cid = uuid.uuid4().hex[:8]
                        log.exception('ALICE tool %s failed cid=%s', name, cid)
                        result = {'success': False, 'message': 'Tool error (ref {}).'.format(cid)}
                    yield {'type': 'tool_end', 'name': name,
                           'result': json.dumps(result, ensure_ascii=False, default=str)}
                    messages.append({'role': 'tool', 'tool_call_id': tc.get('id'),
                                     'content': json.dumps(result, ensure_ascii=False, default=str)})
    finally:
        pass

    if not incognito:
        try:
            _save_conversation(user_id, session_id, messages, total_in, total_out)
        except Exception:
            log.exception('ALICE save failed')
    yield {'type': 'done'}

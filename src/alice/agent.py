"""ALICE orchestration loop (unified — replaces HRMS agent_daemon + agent_runner).

Synchronous Flask-friendly streaming using httpx sync client against an
OpenAI-compatible Chat Completions API. Main brain is OpenCode Zen
(AI_API_KEY/AI_BASE_URL/AI_MODEL); DeepSeek env vars remain as fallback and
NVIDIA NIM as last-resort fallback. Yields JSON-serialisable event dicts:
session_start, content, tool_start, tool_end, request_permission, action,
done, error.

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

MAX_AGENT_ITERATIONS = 10
# HTTP statuses worth retrying on the next provider in the chain.
RETRYABLE_STATUSES = (401, 402, 409, 429, 500, 502, 503, 504)

from src.alice.prompts import SYSTEM_INSTRUCTIONS
from src.alice.tools import TOOL_DEFINITIONS, SAFE_TOOLS, WRITE_TOOLS, execute_tool


def provider_chain():
    """Ordered LLM providers: OpenCode Zen → DeepSeek → NVIDIA NIM (keys present only)."""
    chain = []
    ai_key = os.environ.get('AI_API_KEY', '').strip()
    if ai_key:
        chain.append({
            'label': 'zen',
            'key': ai_key,
            'base': (os.environ.get('AI_BASE_URL', '').strip()
                     or 'https://opencode.ai/zen/go/v1').rstrip('/'),
            'model': os.environ.get('AI_MODEL', '').strip() or 'deepseek-v4-flash-vision-exp',
        })
    ds_key = os.environ.get('DEEPSEEK_API_KEY', '').strip()
    if ds_key:
        chain.append({
            'label': 'deepseek',
            'key': ds_key,
            'base': (os.environ.get('DEEPSEEK_BASE_URL', '').strip()
                     or 'https://api.deepseek.com/v1').rstrip('/'),
            'model': os.environ.get('DEEPSEEK_MODEL', '').strip() or 'deepseek-chat',
        })
    nv_key = os.environ.get('NVIDIA_API_KEY', '').strip()
    if nv_key:
        chain.append({
            'label': 'nvidia',
            'key': nv_key,
            'base': (os.environ.get('NVIDIA_BASE_URL', '').strip()
                     or 'https://integrate.api.nvidia.com/v1').rstrip('/'),
            # Set NVIDIA_MODEL to a hosted id to enable this fallback.
            'model': os.environ.get('NVIDIA_MODEL', '').strip()
                     or os.environ.get('AI_MODEL', '').strip(),
        })
    return chain


def provider_info():
    chain = provider_chain()
    return {'providers': [p['label'] for p in chain],
            'model': chain[0]['model'] if chain else None,
            'model_configured': bool(chain)}


def _headers(provider, session_id=''):
    headers = {'Authorization': 'Bearer {}'.format(provider['key']),
               'Content-Type': 'application/json'}
    raw = os.environ.get('AI_EXTRA_HEADERS_JSON', '').strip()
    if raw:
        try:
            extra = json.loads(raw.replace('{session_id}', session_id or ''))
            for k, v in extra.items():
                headers[str(k)] = str(v)
        except ValueError:
            log.warning('ALICE ignoring malformed AI_EXTRA_HEADERS_JSON')
    return headers


def sanitize_history(history, limit=30):
    """Rebuild a provider-safe message window (fixes Zen/DeepSeek 400s).

    - keeps the last ``limit`` messages, allowed roles/keys only
    - drops leading orphan ``tool`` messages (window sliced mid-exchange)
    - backfills empty tool_call ids and pairs them positionally
    - drops ``tool`` messages with no matching id (strict gateways reject these)
    - drops assistant ``tool_calls`` blocks with no following tool response
      (e.g. the confirmation-path summary already carries the context)
    """
    msgs = []
    for m in history[-limit:]:
        r = m.get('role')
        if r not in ('user', 'assistant', 'tool'):
            continue
        keep = ('role', 'content', 'tool_calls') if r == 'assistant' else ('role', 'content', 'tool_call_id')
        msgs.append({k: m[k] for k in keep if k in m})
    while msgs and msgs[0].get('role') == 'tool':
        msgs.pop(0)

    out, pending, i = [], [], 0
    while i < len(msgs):
        m = msgs[i]
        if m.get('role') == 'assistant' and m.get('tool_calls'):
            fixed = []
            for tc in m['tool_calls']:
                tc = dict(tc)
                fn = dict(tc.get('function') or {})
                if not tc.get('id'):
                    tc['id'] = 'call_' + uuid.uuid4().hex[:8]
                fn['arguments'] = fn.get('arguments') or '{}'
                tc['function'] = fn
                fixed.append(tc)
            m = dict(m)
            m['tool_calls'] = fixed
            pending = [tc['id'] for tc in fixed]
            out.append(m)
        elif m.get('role') == 'tool':
            tid = m.get('tool_call_id') or ''
            if not tid and len(pending) == 1:
                tid = pending[0]
            if tid and tid in pending:
                m = dict(m)
                m['tool_call_id'] = tid
                pending.remove(tid)
                out.append(m)
            # else: orphan tool message — drop it (strict gateways 400 on these)
        else:
            pending = []
            out.append(m)
        i += 1

    # drop dangling assistant tool_calls blocks with no tool response after them
    final = []
    for j, m in enumerate(out):
        if m.get('role') == 'assistant' and m.get('tool_calls'):
            nxt = out[j + 1] if j + 1 < len(out) else None
            if not nxt or nxt.get('role') != 'tool':
                continue
        final.append(m)
    return final


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

    chain = provider_chain()
    if not chain:
        yield {'type': 'error', 'content': "I'm not configured yet — please try again in a little while."}
        return
    provider_idx = 0

    def _try_next_provider(status=None):
        nonlocal provider_idx
        if provider_idx + 1 < len(chain):
            provider_idx += 1
            log.warning('ALICE switching provider to %s (after %s)',
                        chain[provider_idx]['label'], status)
            return True
        return False

    _conv, history = _load_conversation(user_id, session_id)
    system_msg = {'role': 'system', 'content': _system_message(page_context)}
    user_msg = {'role': 'user', 'content': prompt}
    # recent history, rebuilt provider-safe (drops orphans strict gateways 400 on)
    messages = [system_msg] + sanitize_history(history) + [user_msg]
    history_dropped_retry = False

    yield {'type': 'session_start', 'session_id': session_id}

    total_in, total_out = 0, 0
    try:
        with httpx.Client(timeout=120.0) as client:
            for _iteration in range(1, MAX_AGENT_ITERATIONS + 1):
                provider = chain[provider_idx]
                payload = {'model': provider['model'], 'messages': messages,
                           'tools': TOOL_DEFINITIONS, 'stream': True}
                full_content = ''
                tool_calls = []
                try:
                    with client.stream('POST', provider['base'] + '/chat/completions',
                                       headers=_headers(provider, session_id), json=payload) as resp:
                        if resp.status_code != 200:
                            body = resp.read().decode(errors='replace')[:500]
                            cid = uuid.uuid4().hex[:8]
                            log.error('ALICE provider %s status=%s cid=%s body=%s',
                                      provider['label'], resp.status_code, cid, body)
                            if (resp.status_code in RETRYABLE_STATUSES
                                    and _try_next_provider(resp.status_code)):
                                continue  # retry same iteration on next provider
                            if resp.status_code == 400 and not history_dropped_retry and len(messages) > 2:
                                # shape rejected (often a history edge case): retry once
                                # history-free so the user still gets an answer
                                history_dropped_retry = True
                                log.warning('ALICE retrying history-free cid=%s', cid)
                                del messages[1:-1]
                                continue
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
                    # Network-level failure before any content → try next provider.
                    if not full_content and not tool_calls and _try_next_provider('connection-error'):
                        continue
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

"""ALICE voice: Amazon Polly (primary, Generative engine) with xAI Grok fallback.

Mirrors the HRMS ALICE TTS order: Polly first, Grok on failure. boto3 is used
for Polly (SigV4 handled by the SDK); httpx for the xAI REST call.
"""

import logging
import os
import re

log = logging.getLogger('alice')

MAX_TTS_CHARS = 2000


def clean_text(text):
    """Strip emoji/markdown so TTS doesn't read markup aloud (same as HRMS)."""
    text = re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF'
                  r'\U0001F1E0-\U0001F1FF\u2600-\u26FF\u2700-\u27BF\uFE00-\uFE0F\u200d]', '', text)
    text = re.sub(r'[*_~`#]', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'\s+', ' ', text.strip())
    return text[:MAX_TTS_CHARS]


def tts_status():
    return {'polly_configured': bool(os.environ.get('AWS_ACCESS_KEY_ID', '').strip()
                                    and os.environ.get('AWS_SECRET_ACCESS_KEY', '').strip()),
            'polly_voice': os.environ.get('POLLY_VOICE', 'Ruth').strip() or 'Ruth',
            'grok_configured': bool(os.environ.get('XAI_API_KEY', '').strip())}


def _polly(text):
    access = os.environ.get('AWS_ACCESS_KEY_ID', '').strip()
    secret = os.environ.get('AWS_SECRET_ACCESS_KEY', '').strip()
    if not access or not secret:
        return None
    try:
        import boto3
    except ImportError:
        log.error('ALICE TTS boto3 not installed')
        return None
    region = os.environ.get('AWS_REGION', 'us-east-1').strip() or 'us-east-1'
    voice = os.environ.get('POLLY_VOICE', 'Ruth').strip() or 'Ruth'
    try:
        client = boto3.client('polly', region_name=region,
                              aws_access_key_id=access,
                              aws_secret_access_key=secret)
        resp = client.synthesize_speech(Text=text, VoiceId=voice,
                                        OutputFormat='mp3', Engine='generative')
        audio = resp['AudioStream'].read()
        log.info('ALICE TTS polly ok voice=%s chars=%d bytes=%d', voice, len(text), len(audio))
        return audio
    except Exception:
        log.exception('ALICE TTS polly failed')
        return None


def _grok(text):
    key = os.environ.get('XAI_API_KEY', '').strip()
    if not key:
        return None
    import httpx
    voice = os.environ.get('TTS_VOICE', 'eve').strip() or 'eve'
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post('https://api.x.ai/v1/tts',
                               headers={'Authorization': 'Bearer {}'.format(key),
                                        'Content-Type': 'application/json'},
                               json={'text': text, 'voice_id': voice, 'language': 'en'})
            if resp.status_code != 200:
                log.error('ALICE TTS grok status=%s body=%s',
                          resp.status_code, resp.text[:300])
                return None
            log.info('ALICE TTS grok ok voice=%s chars=%d bytes=%d',
                     voice, len(text), len(resp.content))
            return resp.content
    except Exception:
        log.exception('ALICE TTS grok failed')
        return None


def synthesize(text):
    """Return (audio_bytes, 'audio/mpeg') or (None, safe_error_message)."""
    cleaned = clean_text(text or '')
    if not cleaned:
        return None, 'Nothing speakable in that message.'
    audio = _polly(cleaned)
    if audio:
        return audio, 'audio/mpeg'
    audio = _grok(cleaned)
    if audio:
        return audio, 'audio/mpeg'
    return None, "Voice isn't available right now."

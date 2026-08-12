from src.constants.http_status_codes import HTTP_200_OK
from src.constants.http_status_codes import HTTP_400_BAD_REQUEST
from flask import Blueprint, request, jsonify
from src.database import VisitorSession, AnalyticsEvent, Property, db
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
import json
import re

tracking = Blueprint("tracking", __name__, url_prefix="/api/v1/tracking")

MAX_BATCH = 50
SESSION_TIMEOUT_MIN = 30
INTERNAL_HOSTS = ('aparte.awesometech.com.ng', 'localhost', '127.0.0.1')

SEARCH_HOSTS = ('google.', 'bing.com', 'yahoo.', 'duckduckgo', 'yandex.', 'baidu.com', 'ask.com')
SOCIAL_HOSTS = ('facebook.', 'fb.com', 'twitter.', 'x.com', 'instagram.', 'linkedin.',
                'youtube.', 'whatsapp.', 'tiktok.', 'pinterest.', 'reddit.')


# ---------- classification helpers ----------

def classify_device(ua):
    if not ua:
        return 'desktop'
    ua = ua.lower()
    if 'ipad' in ua or 'tablet' in ua or ('kindle' in ua) or 'playbook' in ua:
        return 'tablet'
    if 'mobi' in ua or 'iphone' in ua or 'android' in ua or 'blackberry' in ua or 'windows phone' in ua:
        return 'mobile'
    return 'desktop'


def classify_browser(ua):
    if not ua:
        return None
    ua = ua.lower()
    if 'edg/' in ua or 'edge/' in ua:
        return 'Edge'
    if 'opr/' in ua or 'opera' in ua:
        return 'Opera'
    if 'chrome' in ua or 'crios' in ua:
        return 'Chrome'
    if 'firefox' in ua or 'fxios' in ua:
        return 'Firefox'
    if 'safari' in ua:
        return 'Safari'
    if 'samsungbrowser' in ua:
        return 'Samsung Internet'
    if 'msie' in ua or 'trident' in ua:
        return 'Internet Explorer'
    return 'Other'


def classify_os(ua):
    if not ua:
        return None
    ua = ua.lower()
    if 'android' in ua:
        return 'Android'
    if 'iphone' in ua or 'ipad' in ua or 'ipod' in ua or 'ios' in ua:
        return 'iOS'
    if 'windows' in ua:
        return 'Windows'
    if 'mac os' in ua or 'macintosh' in ua:
        return 'macOS'
    if 'linux' in ua:
        return 'Linux'
    if 'cros' in ua:
        return 'Chrome OS'
    return 'Other'


def classify_source(referrer, host, utm_source, utm_medium):
    if utm_source or utm_medium:
        return 'campaign'
    if not referrer:
        return 'direct'
    if host and any(h in host for h in INTERNAL_HOSTS):
        return 'internal'
    rl = referrer.lower()
    if any(h in rl for h in SEARCH_HOSTS):
        return 'search'
    if any(h in rl for h in SOCIAL_HOSTS):
        return 'social'
    return 'referral'


def trunc(value, limit):
    if not value:
        return value
    return str(value)[:limit]


def parse_host(referrer):
    if not referrer:
        return None
    m = re.match(r'^https?://([^/]+)', referrer)
    return m.group(1) if m else None


# ---------- ingestion ----------

def ingest_batch(items, ua, country, identity):
    """Persist a batch of analytics events + upsert their sessions.

    Sessions are updated in place so a session's landing/exit page, page view
    count and last activity stay current without background jobs.
    """
    user_id = identity if identity else None
    device_type = classify_device(ua)
    browser = classify_browser(ua)
    os = classify_os(ua)

    # collect unique sessions first so we can resolve them once
    session_ids = {i.get('session_id') for i in items if i.get('session_id')}
    sessions = {}
    if session_ids:
        for s in VisitorSession.query.filter(VisitorSession.id.in_(session_ids)).all():
            sessions[s.id] = s

    for item in items:
        event_type = item.get('type') or 'pageview'
        if event_type not in ('pageview', 'event', 'performance', 'error'):
            continue

        session_id = trunc(item.get('session_id'), 64)
        visitor_id = trunc(item.get('visitor_id'), 64)
        path = trunc(item.get('path'), 255)
        if not session_id or not visitor_id or not path:
            continue

        now = datetime.now()
        referrer = trunc(item.get('referrer'), 255)
        host = parse_host(referrer)
        utm_source = trunc(item.get('utm_source'), 100)
        utm_medium = trunc(item.get('utm_medium'), 100)
        source_type = classify_source(referrer, host, utm_source, utm_medium)

        property_id = item.get('property_id')
        if property_id is not None:
            try:
                property_id = int(property_id)
            except (ValueError, TypeError):
                property_id = None

        # ---- upsert session ----
        session = sessions.get(session_id)
        is_new_session = session is None
        if session is None:
            session = VisitorSession(
                id=session_id,
                visitor_id=visitor_id,
                user_id=user_id,
                started_at=now,
                last_activity_at=now,
                page_views=0,
                landing_path=path,
                landing_title=trunc(item.get('title'), 255),
                referrer=referrer,
                source_type=source_type,
                utm_source=utm_source,
                utm_medium=utm_medium,
                utm_campaign=trunc(item.get('utm_campaign'), 100),
                utm_term=trunc(item.get('utm_term'), 100),
                utm_content=trunc(item.get('utm_content'), 100),
                device_type=device_type,
                browser=browser,
                os=os,
                screen_size=trunc(item.get('screen_size'), 30),
                country=country,
            )
            db.session.add(session)
            sessions[session_id] = session
        else:
            session.last_activity_at = now
            session.exit_path = path
            session.user_id = user_id
            session.country = country
            if not session.screen_size:
                session.screen_size = trunc(item.get('screen_size'), 30)

        if event_type == 'pageview':
            session.page_views += 1

        # ---- insert event ----
        event = AnalyticsEvent(
            session_id=session_id,
            visitor_id=visitor_id,
            user_id=user_id,
            event_type=event_type,
            name=trunc(item.get('name'), 100),
            category=trunc(item.get('category'), 50),
            properties=json.dumps(item.get('properties')) if item.get('properties') else None,
            path=path,
            title=trunc(item.get('title'), 255),
            referrer=referrer,
            property_id=property_id,
            time_on_page_ms=item.get('time_on_page_ms'),
            device_type=device_type,
            browser=browser,
            os=os,
            screen_size=trunc(item.get('screen_size'), 30),
            country=country,
            source_type=source_type,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=trunc(item.get('utm_campaign'), 100),
            utm_term=trunc(item.get('utm_term'), 100),
            utm_content=trunc(item.get('utm_content'), 100),
            ttfb=item.get('ttfb'),
            dom_loaded=item.get('dom_loaded'),
            load_time=item.get('load_time'),
            fcp=item.get('fcp'),
            lcp=item.get('lcp'),
            cls=item.get('cls'),
            js_errors=item.get('js_errors') or 0,
            failed_requests=item.get('failed_requests') or 0,
            created_at=now,
        )
        db.session.add(event)

    # close out stale sessions for these visitors (30 min inactivity)
    if session_ids:
        for sid in session_ids:
            session = sessions.get(sid)
            if session is None:
                continue
            session.duration_seconds = max(0, int((datetime.now() - session.started_at).total_seconds()))
            session.is_bounce = session.page_views <= 1

    db.session.commit()


@tracking.post('/batch')
def track_batch():

    data = request.get_json(silent=True) or {}

    items = data.get('events')
    if not isinstance(items, list) or not items:
        return jsonify({'error': "Events must be a non-empty array"}), HTTP_400_BAD_REQUEST

    items = items[:MAX_BATCH]

    ua = request.headers.get('User-Agent', '')
    country = request.headers.get('CF-IPCountry') or request.headers.get('X-Country-Code') or None
    if country and len(country) != 2:
        country = None

    identity = None
    from flask_jwt_extended import verify_jwt_in_request
    try:
        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
    except Exception:
        identity = None

    try:
        ingest_batch(items, ua, country, identity)
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': "Failed to record events: {}".format(e)}), HTTP_400_BAD_REQUEST

    return jsonify({'message': "Events recorded"}), HTTP_200_OK


# Backward-compatible single pageview endpoint (used by older clients).
@tracking.post('/pageview')
@jwt_required(optional=True)
def track_pageview():

    data = request.get_json(silent=True) or {}

    path = (data.get('path') or '').strip()
    visitor_id = (data.get('visitor_id') or request.headers.get('X-Visitor-Id') or '').strip()

    if not path:
        return jsonify({'error': "Path must not be empty"}), HTTP_400_BAD_REQUEST
    if not visitor_id:
        return jsonify({'error': "Visitor id must not be empty"}), HTTP_400_BAD_REQUEST

    property_id = data.get('property_id')
    if property_id is not None:
        try:
            property_id = int(property_id)
        except (ValueError, TypeError):
            property_id = None

    item = {
        'type': 'pageview',
        'session_id': data.get('session_id') or visitor_id,
        'visitor_id': visitor_id,
        'path': path,
        'title': data.get('title'),
        'referrer': data.get('referrer'),
        'property_id': property_id,
        'screen_size': data.get('screen_size'),
        'utm_source': data.get('utm_source'),
        'utm_medium': data.get('utm_medium'),
        'utm_campaign': data.get('utm_campaign'),
        'utm_term': data.get('utm_term'),
        'utm_content': data.get('utm_content'),
        'time_on_page_ms': data.get('time_on_page_ms'),
    }

    ua = request.headers.get('User-Agent', '')
    country = request.headers.get('CF-IPCountry') or None

    ingest_batch([item], ua, country, get_jwt_identity())

    return jsonify({'message': "Page view recorded"}), HTTP_200_OK

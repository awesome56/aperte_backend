from src.constants.http_status_codes import HTTP_200_OK
from src.constants.http_status_codes import HTTP_400_BAD_REQUEST
from flask import Blueprint, request, jsonify, Response
from src.database import db, VisitorSession, AnalyticsEvent, Property, PropertyImage, PageVisit
from src.constants.permissions import permission_required
from datetime import datetime, timedelta
from sqlalchemy import case, text
import csv
import io

analytics_bp = Blueprint("admin_analytics", __name__, url_prefix="/api/v1/admin/analytics")

SESSION_TIMEOUT = timedelta(minutes=30)

PAGEVIEW = 'pageview'
PERF = 'performance'


# ---------- helpers ----------

def parse_dates():
    """Return (start_dt, end_dt) inclusive, defaulting to the last 30 days."""
    today = datetime.now().date()
    start_s = request.args.get('start')
    end_s = request.args.get('end')
    if start_s:
        try:
            start_dt = datetime.strptime(start_s[:10], '%Y-%m-%d')
        except ValueError:
            raise ValueError("start must be YYYY-MM-DD")
    else:
        start_dt = datetime(today.year, today.month, today.day) - timedelta(days=29)
    if end_s:
        try:
            end_dt = datetime.strptime(end_s[:10], '%Y-%m-%d')
        except ValueError:
            raise ValueError("end must be YYYY-MM-DD")
    else:
        end_dt = datetime(today.year, today.month, today.day)
    end_dt = end_dt + timedelta(days=1) - timedelta(microseconds=1)
    return start_dt, end_dt


def previous_period(start_dt, end_dt):
    length = end_dt - start_dt
    return start_dt - length - timedelta(microseconds=1), start_dt - timedelta(microseconds=1)


def pct_change(current, previous):
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return round(((current - previous) / previous) * 100, 1)


def get_pageviews(start_dt, end_dt):
    return AnalyticsEvent.query.filter(
        AnalyticsEvent.event_type == PAGEVIEW,
        AnalyticsEvent.created_at >= start_dt,
        AnalyticsEvent.created_at <= end_dt,
    )


def kpis(start_dt, end_dt):
    pv = get_pageviews(start_dt, end_dt)
    page_views = pv.count()
    unique_visitors = db.session.query(func_count_distinct(AnalyticsEvent.visitor_id)).filter(
        AnalyticsEvent.event_type == PAGEVIEW,
        AnalyticsEvent.created_at >= start_dt,
        AnalyticsEvent.created_at <= end_dt,
    ).scalar() or 0
    sessions = db.session.query(func_count_distinct(AnalyticsEvent.session_id)).filter(
        AnalyticsEvent.created_at >= start_dt,
        AnalyticsEvent.created_at <= end_dt,
    ).scalar() or 0

    # new visitors: first-ever event inside the window
    first_seen = db.session.execute(text("""
        SELECT COUNT(*) FROM (
            SELECT visitor_id, MIN(created_at) AS first_seen
            FROM analytics_event
            GROUP BY visitor_id
        ) t WHERE t.first_seen >= :start AND t.first_seen <= :end
    """), {'start': start_dt, 'end': end_dt}).scalar() or 0

    returning = max(0, unique_visitors - first_seen)

    sess_rows = VisitorSession.query.filter(
        VisitorSession.started_at >= start_dt,
        VisitorSession.started_at <= end_dt,
    )
    total_sessions = sess_rows.count()
    bounced = sess_rows.filter(VisitorSession.is_bounce.is_(True)).count()
    bounce_rate = round((bounced / total_sessions * 100), 1) if total_sessions else 0.0
    avg_duration = sess_rows.with_entities(db.func.avg(VisitorSession.duration_seconds)).scalar()
    avg_duration = round(avg_duration or 0)

    avg_time_on_page = pv.with_entities(db.func.avg(AnalyticsEvent.time_on_page_ms)).scalar()
    avg_time_on_page = round(avg_time_on_page or 0)

    interactions = AnalyticsEvent.query.filter(
        AnalyticsEvent.event_type == 'event',
        AnalyticsEvent.created_at >= start_dt,
        AnalyticsEvent.created_at <= end_dt,
    ).count()
    conversions = AnalyticsEvent.query.filter(
        AnalyticsEvent.event_type == 'event',
        AnalyticsEvent.category == 'conversion',
        AnalyticsEvent.created_at >= start_dt,
        AnalyticsEvent.created_at <= end_dt,
    ).count()

    return {
        'page_views': page_views,
        'unique_visitors': unique_visitors,
        'new_visitors': first_seen,
        'returning_visitors': returning,
        'sessions': sessions,
        'total_sessions': total_sessions,
        'bounce_rate': bounce_rate,
        'avg_session_duration': avg_duration,
        'avg_time_on_page': avg_time_on_page,
        'engagement_rate': round(100 - bounce_rate, 1),
        'events': interactions,
        'conversions': conversions,
    }


def func_count_distinct(col):
    return db.func.count(db.func.distinct(col))


def traffic_over_time(start_dt, end_dt, group='day'):
    """Per-day (or hour) page views, unique visitors and sessions."""
    if group == 'hour':
        key = db.func.date_trunc('hour', AnalyticsEvent.created_at)
    else:
        key = db.func.date(AnalyticsEvent.created_at)
    rows = db.session.query(
        key.label('bucket'),
        db.func.count(AnalyticsEvent.id).label('views'),
        func_count_distinct(AnalyticsEvent.visitor_id).label('visitors'),
        func_count_distinct(AnalyticsEvent.session_id).label('sessions'),
    ).filter(
        AnalyticsEvent.event_type == PAGEVIEW,
        AnalyticsEvent.created_at >= start_dt,
        AnalyticsEvent.created_at <= end_dt,
    ).group_by('bucket').order_by('bucket').all()

    result = []
    for r in rows:
        bucket = r.bucket
        if hasattr(bucket, 'strftime'):
            bucket = bucket.strftime('%Y-%m-%d') if group == 'day' else bucket.strftime('%Y-%m-%d %H:00')
        result.append({
            'date': bucket,
            'views': r.views,
            'visitors': r.visitors,
            'sessions': r.sessions,
        })
    return result


def traffic_sources(start_dt, end_dt):
    rows = db.session.query(
        AnalyticsEvent.source_type,
        func_count_distinct(AnalyticsEvent.visitor_id).label('visitors'),
        func_count_distinct(AnalyticsEvent.session_id).label('sessions'),
        db.func.count(AnalyticsEvent.id).label('views'),
    ).filter(
        AnalyticsEvent.event_type == PAGEVIEW,
        AnalyticsEvent.created_at >= start_dt,
        AnalyticsEvent.created_at <= end_dt,
    ).group_by(AnalyticsEvent.source_type).all()

    sources = {}
    for r in rows:
        src = r.source_type or 'direct'
        sources[src] = {'visitors': r.visitors, 'sessions': r.sessions, 'views': r.views}

    # bounce per source (from sessions)
    bounce_rows = db.session.query(
        VisitorSession.source_type,
        db.func.count(VisitorSession.id).label('total'),
        db.func.sum(case((VisitorSession.is_bounce.is_(True), 1), else_=0)).label('bounced'),
    ).filter(
        VisitorSession.started_at >= start_dt,
        VisitorSession.started_at <= end_dt,
    ).group_by(VisitorSession.source_type).all()

    order = ['direct', 'search', 'social', 'referral', 'campaign', 'internal']
    out = []
    for src in order:
        if src not in sources:
            continue
        bounced = 0
        total = 0
        for br in bounce_rows:
            if (br.source_type or 'direct') == src:
                total = br.total
                bounced = br.bounced or 0
        out.append({
            'source': src,
            'visitors': sources[src]['visitors'],
            'sessions': sources[src]['sessions'],
            'views': sources[src]['views'],
            'bounce_rate': round((bounced / total * 100), 1) if total else 0.0,
        })
    return out


def utm_rows(start_dt, end_dt):
    rows = db.session.query(
        AnalyticsEvent.utm_source,
        AnalyticsEvent.utm_medium,
        AnalyticsEvent.utm_campaign,
        func_count_distinct(AnalyticsEvent.visitor_id).label('visitors'),
        db.func.count(AnalyticsEvent.id).label('views'),
    ).filter(
        AnalyticsEvent.event_type == PAGEVIEW,
        AnalyticsEvent.utm_source.isnot(None),
        AnalyticsEvent.created_at >= start_dt,
        AnalyticsEvent.created_at <= end_dt,
    ).group_by(
        AnalyticsEvent.utm_source, AnalyticsEvent.utm_medium, AnalyticsEvent.utm_campaign
    ).order_by(db.func.count(AnalyticsEvent.id).desc()).limit(20).all()

    return [{
        'source': r.utm_source,
        'medium': r.utm_medium,
        'campaign': r.utm_campaign,
        'visitors': r.visitors,
        'views': r.views,
    } for r in rows]


def content_rows(start_dt, end_dt, limit=20):
    rows = db.session.query(
        AnalyticsEvent.path,
        AnalyticsEvent.title,
        db.func.count(AnalyticsEvent.id).label('views'),
        func_count_distinct(AnalyticsEvent.visitor_id).label('visitors'),
        func_count_distinct(AnalyticsEvent.session_id).label('sessions'),
        db.func.avg(AnalyticsEvent.time_on_page_ms).label('avg_time'),
    ).filter(
        AnalyticsEvent.event_type == PAGEVIEW,
        AnalyticsEvent.created_at >= start_dt,
        AnalyticsEvent.created_at <= end_dt,
    ).group_by(AnalyticsEvent.path, AnalyticsEvent.title).order_by(
        db.func.count(AnalyticsEvent.id).desc()
    ).limit(limit).all()

    # landings / exits per path
    landings = dict(db.session.query(
        VisitorSession.landing_path, db.func.count(VisitorSession.id)
    ).filter(
        VisitorSession.started_at >= start_dt,
        VisitorSession.started_at <= end_dt,
    ).group_by(VisitorSession.landing_path).all())
    exits = dict(db.session.query(
        VisitorSession.exit_path, db.func.count(VisitorSession.id)
    ).filter(
        VisitorSession.started_at >= start_dt,
        VisitorSession.started_at <= end_dt,
        VisitorSession.exit_path.isnot(None),
    ).group_by(VisitorSession.exit_path).all())

    out = []
    for r in rows:
        path = r.path
        landing = landings.get(path, 0)
        exit_ = exits.get(path, 0)
        exit_rate = round((exit_ / (r.views or 1)) * 100, 1)
        out.append({
            'path': path,
            'title': r.title,
            'views': r.views,
            'visitors': r.visitors,
            'sessions': r.sessions,
            'avg_time_on_page': round(r.avg_time or 0),
            'landings': landing,
            'exits': exit_,
            'exit_rate': exit_rate,
            'bounce_rate': round((landing / (r.sessions or 1)) * 100, 1) if landing else 0.0,
        })
    return out


def property_rows(start_dt, end_dt, limit=20, property_id=None):
    q = db.session.query(
        AnalyticsEvent.property_id,
        db.func.count(AnalyticsEvent.id).label('views'),
        func_count_distinct(AnalyticsEvent.visitor_id).label('visitors'),
        func_count_distinct(AnalyticsEvent.session_id).label('sessions'),
        db.func.avg(AnalyticsEvent.time_on_page_ms).label('avg_time'),
    ).filter(
        AnalyticsEvent.event_type == PAGEVIEW,
        AnalyticsEvent.property_id.isnot(None),
        AnalyticsEvent.created_at >= start_dt,
        AnalyticsEvent.created_at <= end_dt,
    )
    if property_id:
        q = q.filter(AnalyticsEvent.property_id == property_id)
    q = q.group_by(AnalyticsEvent.property_id).order_by(db.func.count(AnalyticsEvent.id).desc())
    if not property_id:
        q = q.limit(limit)
    rows = q.all()

    props = {p.id: p for p in Property.query.filter(Property.id.in_([r.property_id for r in rows])).all()} if rows else {}
    dps = {}
    if rows:
        for p in PropertyImage.query.filter(PropertyImage.dp == 1, PropertyImage.property_id.in_(list(props.keys()))).all():
            if p.property_id not in dps:
                dps[p.property_id] = p.image_url

    sessions = set(r.property_id for r in rows) if rows else set()
    bounce_map = {}
    if sessions:
        # bounce per property from sessions whose landing is the property page
        landing_rows = db.session.query(
            VisitorSession.landing_path, VisitorSession.is_bounce
        ).filter(
            VisitorSession.started_at >= start_dt,
            VisitorSession.started_at <= end_dt,
        ).all()
        for lp, bounced in landing_rows:
            if lp and lp.startswith('/properties/'):
                try:
                    pid = int(lp.split('/')[2])
                except (ValueError, IndexError):
                    continue
                bounce_map.setdefault(pid, [0, 0])
                bounce_map[pid][0] += 1
                if bounced:
                    bounce_map[pid][1] += 1

    out = []
    for r in rows:
        p = props.get(r.property_id)
        b = bounce_map.get(r.property_id, [0, 0])
        out.append({
            'id': r.property_id,
            'title': p.title if p else 'Property #{}'.format(r.property_id),
            'views': r.views,
            'visitors': r.visitors,
            'sessions': r.sessions,
            'avg_time_on_page': round(r.avg_time or 0),
            'bounce_rate': round((b[1] / b[0] * 100), 1) if b[0] else 0.0,
            'dp': dps.get(r.property_id, ''),
        })
    return out


def property_detail(start_dt, end_dt, property_id):
    """Full per-property analytics including sources + devices."""
    q = AnalyticsEvent.query.filter(
        AnalyticsEvent.event_type == PAGEVIEW,
        AnalyticsEvent.property_id == property_id,
        AnalyticsEvent.created_at >= start_dt,
        AnalyticsEvent.created_at <= end_dt,
    )
    views = q.count()
    visitors = q.with_entities(func_count_distinct(AnalyticsEvent.visitor_id)).scalar() or 0
    sessions = q.with_entities(func_count_distinct(AnalyticsEvent.session_id)).scalar() or 0
    avg_time = q.with_entities(db.func.avg(AnalyticsEvent.time_on_page_ms)).scalar()
    avg_time = round(avg_time or 0)

    sources = db.session.query(
        AnalyticsEvent.source_type,
        func_count_distinct(AnalyticsEvent.visitor_id),
    ).filter(
        AnalyticsEvent.event_type == PAGEVIEW,
        AnalyticsEvent.property_id == property_id,
        AnalyticsEvent.created_at >= start_dt,
        AnalyticsEvent.created_at <= end_dt,
    ).group_by(AnalyticsEvent.source_type).all()

    devices = db.session.query(
        AnalyticsEvent.device_type,
        func_count_distinct(AnalyticsEvent.visitor_id),
    ).filter(
        AnalyticsEvent.event_type == PAGEVIEW,
        AnalyticsEvent.property_id == property_id,
        AnalyticsEvent.created_at >= start_dt,
        AnalyticsEvent.created_at <= end_dt,
    ).group_by(AnalyticsEvent.device_type).all()

    over_time = db.session.query(
        db.func.date(AnalyticsEvent.created_at).label('day'),
        db.func.count(AnalyticsEvent.id),
    ).filter(
        AnalyticsEvent.event_type == PAGEVIEW,
        AnalyticsEvent.property_id == property_id,
        AnalyticsEvent.created_at >= start_dt,
        AnalyticsEvent.created_at <= end_dt,
    ).group_by('day').order_by('day').all()

    p = Property.query.filter_by(id=property_id).first()

    def fmt_day(d):
        return d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d)

    return {
        'id': property_id,
        'title': p.title if p else 'Property #{}'.format(property_id),
        'views': views,
        'visitors': visitors,
        'sessions': sessions,
        'avg_time_on_page': avg_time,
        'sources': [{'source': s[0] or 'direct', 'visitors': s[1]} for s in sources],
        'devices': [{'device': d[0] or 'desktop', 'visitors': d[1]} for d in devices],
        'views_over_time': [{'date': fmt_day(d[0]), 'views': d[1]} for d in over_time],
    }


def audience_rows(start_dt, end_dt):
    def breakdown(column):
        rows = db.session.query(
            column.label('key'),
            func_count_distinct(AnalyticsEvent.visitor_id).label('visitors'),
            db.func.count(AnalyticsEvent.id).label('views'),
        ).filter(
            AnalyticsEvent.event_type == PAGEVIEW,
            AnalyticsEvent.created_at >= start_dt,
            AnalyticsEvent.created_at <= end_dt,
        ).group_by('key').order_by(db.func.count(AnalyticsEvent.id).desc()).all()
        return [{'key': r.key or 'Unknown', 'visitors': r.visitors, 'views': r.views} for r in rows]

    return {
        'devices': breakdown(AnalyticsEvent.device_type),
        'browsers': breakdown(AnalyticsEvent.browser),
        'os': breakdown(AnalyticsEvent.os),
        'countries': breakdown(AnalyticsEvent.country),
        'screen_sizes': breakdown(AnalyticsEvent.screen_size),
    }


def performance_rows(start_dt, end_dt):
    q = AnalyticsEvent.query.filter(
        AnalyticsEvent.event_type == PERF,
        AnalyticsEvent.created_at >= start_dt,
        AnalyticsEvent.created_at <= end_dt,
    )
    totals = q.with_entities(
        db.func.avg(AnalyticsEvent.ttfb).label('ttfb'),
        db.func.avg(AnalyticsEvent.dom_loaded).label('dom'),
        db.func.avg(AnalyticsEvent.load_time).label('load'),
        db.func.avg(AnalyticsEvent.fcp).label('fcp'),
        db.func.avg(AnalyticsEvent.lcp).label('lcp'),
        db.func.avg(AnalyticsEvent.cls).label('cls'),
        db.func.sum(AnalyticsEvent.js_errors).label('js_errors'),
        db.func.sum(AnalyticsEvent.failed_requests).label('failed'),
        db.func.count(AnalyticsEvent.id).label('samples'),
    ).first()

    slow = db.session.query(
        AnalyticsEvent.path,
        db.func.avg(AnalyticsEvent.load_time).label('load'),
        db.func.avg(AnalyticsEvent.lcp).label('lcp'),
        db.func.avg(AnalyticsEvent.ttfb).label('ttfb'),
        db.func.avg(AnalyticsEvent.cls).label('cls'),
        db.func.count(AnalyticsEvent.id).label('samples'),
    ).filter(
        AnalyticsEvent.event_type == PERF,
        AnalyticsEvent.created_at >= start_dt,
        AnalyticsEvent.created_at <= end_dt,
    ).group_by(AnalyticsEvent.path).order_by(
        db.func.avg(AnalyticsEvent.load_time).desc()
    ).limit(15).all()

    errors = AnalyticsEvent.query.filter(
        AnalyticsEvent.event_type == 'error',
        AnalyticsEvent.created_at >= start_dt,
        AnalyticsEvent.created_at <= end_dt,
    ).count()

    def rnd(v):
        return round(v, 2) if v is not None else None

    return {
        'averages': {
            'ttfb': rnd(totals.ttfb),
            'dom_loaded': rnd(totals.dom),
            'load_time': rnd(totals.load),
            'fcp': rnd(totals.fcp),
            'lcp': rnd(totals.lcp),
            'cls': rnd(totals.cls),
            'js_errors': totals.js_errors or 0,
            'failed_requests': totals.failed or 0,
            'samples': totals.samples,
        },
        'slowest_pages': [{
            'path': r.path,
            'load_time': rnd(r.load),
            'lcp': rnd(r.lcp),
            'ttfb': rnd(r.ttfb),
            'cls': rnd(r.cls),
            'samples': r.samples,
        } for r in slow],
        'error_count': errors,
    }


def event_rows(start_dt, end_dt):
    rows = db.session.query(
        AnalyticsEvent.name,
        AnalyticsEvent.category,
        db.func.count(AnalyticsEvent.id).label('count'),
        func_count_distinct(AnalyticsEvent.visitor_id).label('visitors'),
    ).filter(
        AnalyticsEvent.event_type == 'event',
        AnalyticsEvent.created_at >= start_dt,
        AnalyticsEvent.created_at <= end_dt,
    ).group_by(AnalyticsEvent.name, AnalyticsEvent.category).order_by(
        db.func.count(AnalyticsEvent.id).desc()
    ).limit(50).all()

    search = db.session.query(
        AnalyticsEvent.name,
        db.func.count(AnalyticsEvent.id),
    ).filter(
        AnalyticsEvent.event_type == 'event',
        AnalyticsEvent.category == 'search',
        AnalyticsEvent.created_at >= start_dt,
        AnalyticsEvent.created_at <= end_dt,
    ).group_by(AnalyticsEvent.name).order_by(db.func.count(AnalyticsEvent.id).desc()).limit(25).all()

    return {
        'events': [{
            'name': r.name or '(unnamed)',
            'category': r.category or 'event',
            'count': r.count,
            'visitors': r.visitors,
        } for r in rows],
        'search_terms': [{'term': r[0], 'count': r[1]} for r in search],
    }


# ---------- routes ----------

@analytics_bp.get('/overview')
@permission_required('stats.view')
def overview():
    try:
        start_dt, end_dt = parse_dates()
    except ValueError as e:
        return jsonify({'error': str(e)}), HTTP_400_BAD_REQUEST

    prev_start, prev_end = previous_period(start_dt, end_dt)

    current = kpis(start_dt, end_dt)
    previous = kpis(prev_start, prev_end)

    comparisons = {}
    for key in ('page_views', 'unique_visitors', 'new_visitors', 'returning_visitors', 'sessions', 'conversions'):
        comparisons[key] = pct_change(current[key], previous.get(key, 0))

    return jsonify({
        'range': {'start': start_dt.strftime('%Y-%m-%d'), 'end': end_dt.strftime('%Y-%m-%d')},
        'current': current,
        'previous': previous,
        'change': comparisons,
        'over_time': traffic_over_time(start_dt, end_dt, 'day'),
        'sources': traffic_sources(start_dt, end_dt),
        'utm': utm_rows(start_dt, end_dt),
        'top_properties': property_rows(start_dt, end_dt, 5),
    }), HTTP_200_OK


@analytics_bp.get('/traffic')
@permission_required('stats.view')
def traffic():
    try:
        start_dt, end_dt = parse_dates()
    except ValueError as e:
        return jsonify({'error': str(e)}), HTTP_400_BAD_REQUEST
    group = request.args.get('group', 'day')
    if group not in ('day', 'hour'):
        group = 'day'
    return jsonify({
        'over_time': traffic_over_time(start_dt, end_dt, group),
        'sources': traffic_sources(start_dt, end_dt),
        'utm': utm_rows(start_dt, end_dt),
    }), HTTP_200_OK


@analytics_bp.get('/content')
@permission_required('stats.view')
def content():
    try:
        start_dt, end_dt = parse_dates()
    except ValueError as e:
        return jsonify({'error': str(e)}), HTTP_400_BAD_REQUEST

    pages = content_rows(start_dt, end_dt, 50)
    # least visited: flip ordering
    least = sorted(pages, key=lambda r: r['views'])[:10]

    # landing pages (by session landing)
    landings = db.session.query(
        VisitorSession.landing_path,
        db.func.count(VisitorSession.id).label('sessions'),
        db.func.avg(VisitorSession.duration_seconds).label('avg_duration'),
    ).filter(
        VisitorSession.started_at >= start_dt,
        VisitorSession.started_at <= end_dt,
    ).group_by(VisitorSession.landing_path).order_by(
        db.func.count(VisitorSession.id).desc()
    ).limit(15).all()

    exits = db.session.query(
        VisitorSession.exit_path,
        db.func.count(VisitorSession.id).label('count'),
    ).filter(
        VisitorSession.started_at >= start_dt,
        VisitorSession.started_at <= end_dt,
        VisitorSession.exit_path.isnot(None),
    ).group_by(VisitorSession.exit_path).order_by(
        db.func.count(VisitorSession.id).desc()
    ).limit(15).all()

    return jsonify({
        'pages': pages,
        'least_visited': least,
        'landing_pages': [{'path': r[0], 'sessions': r[1], 'avg_duration': round(r[2] or 0)} for r in landings],
        'exit_pages': [{'path': r[0], 'count': r[1]} for r in exits],
        'properties': property_rows(start_dt, end_dt, 20),
    }), HTTP_200_OK


@analytics_bp.get('/properties')
@permission_required('stats.view')
def properties():
    try:
        start_dt, end_dt = parse_dates()
    except ValueError as e:
        return jsonify({'error': str(e)}), HTTP_400_BAD_REQUEST
    property_id = request.args.get('property_id', type=int)
    if property_id:
        return jsonify(property_detail(start_dt, end_dt, property_id)), HTTP_200_OK
    return jsonify({'properties': property_rows(start_dt, end_dt, 50)}), HTTP_200_OK


@analytics_bp.get('/audience')
@permission_required('stats.view')
def audience():
    try:
        start_dt, end_dt = parse_dates()
    except ValueError as e:
        return jsonify({'error': str(e)}), HTTP_400_BAD_REQUEST
    return jsonify(audience_rows(start_dt, end_dt)), HTTP_200_OK


@analytics_bp.get('/performance')
@permission_required('stats.view')
def performance():
    try:
        start_dt, end_dt = parse_dates()
    except ValueError as e:
        return jsonify({'error': str(e)}), HTTP_400_BAD_REQUEST
    return jsonify(performance_rows(start_dt, end_dt)), HTTP_200_OK


@analytics_bp.get('/events')
@permission_required('stats.view')
def events():
    try:
        start_dt, end_dt = parse_dates()
    except ValueError as e:
        return jsonify({'error': str(e)}), HTTP_400_BAD_REQUEST
    return jsonify(event_rows(start_dt, end_dt)), HTTP_200_OK


@analytics_bp.get('/realtime')
@permission_required('stats.view')
def realtime():
    cutoff = datetime.now() - SESSION_TIMEOUT
    active = VisitorSession.query.filter(VisitorSession.last_activity_at >= cutoff)
    total_active = active.count()

    # page currently being viewed = last pageview per active session
    pages = db.session.query(
        AnalyticsEvent.path,
        db.func.count(db.func.distinct(AnalyticsEvent.session_id)).label('visitors'),
    ).filter(
        AnalyticsEvent.event_type == PAGEVIEW,
        AnalyticsEvent.created_at >= cutoff,
    ).group_by(AnalyticsEvent.path).order_by(db.func.count(db.func.distinct(AnalyticsEvent.session_id)).desc()).limit(10).all()

    recent = AnalyticsEvent.query.filter(
        AnalyticsEvent.created_at >= cutoff,
    ).order_by(AnalyticsEvent.created_at.desc()).limit(20).all()

    return jsonify({
        'active_sessions': total_active,
        'active_visitors': active.with_entities(db.func.count(db.func.distinct(VisitorSession.visitor_id))).scalar() or 0,
        'pages': [{'path': r[0], 'active_visitors': r[1]} for r in pages],
        'recent': [{
            'path': e.path,
            'event_type': e.event_type,
            'device_type': e.device_type,
            'source_type': e.source_type,
            'country': e.country,
            'created_at': e.created_at.strftime('%H:%M:%S'),
        } for e in recent],
    }), HTTP_200_OK


@analytics_bp.get('/export')
@permission_required('stats.view')
def export():
    try:
        start_dt, end_dt = parse_dates()
    except ValueError as e:
        return jsonify({'error': str(e)}), HTTP_400_BAD_REQUEST

    fmt = request.args.get('format', 'csv')
    if fmt != 'csv':
        return jsonify({'error': "Only CSV export is currently supported"}), HTTP_400_BAD_REQUEST

    rows = AnalyticsEvent.query.filter(
        AnalyticsEvent.created_at >= start_dt,
        AnalyticsEvent.created_at <= end_dt,
    ).order_by(AnalyticsEvent.created_at.desc()).limit(20000).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        'created_at', 'event_type', 'name', 'category', 'path', 'title', 'visitor_id',
        'session_id', 'referrer', 'source_type', 'utm_source', 'utm_medium', 'utm_campaign',
        'property_id', 'device_type', 'browser', 'os', 'screen_size', 'country',
        'time_on_page_ms', 'ttfb', 'dom_loaded', 'load_time', 'fcp', 'lcp', 'cls',
        'js_errors', 'failed_requests',
    ])
    for e in rows:
        writer.writerow([
            e.created_at.strftime('%Y-%m-%d %H:%M:%S') if e.created_at else '',
            e.event_type, e.name or '', e.category or '', e.path, e.title or '',
            e.visitor_id, e.session_id, e.referrer or '', e.source_type or '',
            e.utm_source or '', e.utm_medium or '', e.utm_campaign or '',
            e.property_id or '', e.device_type or '', e.browser or '', e.os or '',
            e.screen_size or '', e.country or '', e.time_on_page_ms or '',
            e.ttfb or '', e.dom_loaded or '', e.load_time or '', e.fcp or '',
            e.lcp or '', e.cls or '', e.js_errors or 0, e.failed_requests or 0,
        ])

    filename = 'aperte-analytics-{}-{}.csv'.format(start_dt.strftime('%Y%m%d'), end_dt.strftime('%Y%m%d'))
    return Response(
        buf.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename={}'.format(filename)},
    )


@analytics_bp.post('/prune')
@permission_required('stats.view')
def prune():
    days = request.args.get('days', type=int)
    if not days or days < 1:
        return jsonify({'error': "days must be a positive integer"}), HTTP_400_BAD_REQUEST

    cutoff = datetime.now() - timedelta(days=days)

    ev = AnalyticsEvent.query.filter(AnalyticsEvent.created_at < cutoff).delete()
    se = VisitorSession.query.filter(VisitorSession.last_activity_at < cutoff).delete()

    from src.database import PageVisit
    pv = PageVisit.query.filter(PageVisit.created_at < cutoff).delete()
    db.session.commit()

    return jsonify({
        'message': 'Deleted analytics older than {} days'.format(days),
        'events_deleted': ev,
        'sessions_deleted': se,
        'page_visits_deleted': pv,
    }), HTTP_200_OK

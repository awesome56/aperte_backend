"""ALICE tool definitions + implementations for Aperte (unified, no MCP bridge/server split).

Every tool takes an explicit ``user_id`` (request-scoped — fixes the HRMS global
MCP_USER concurrency bug) and talks to SQLAlchemy models directly. AuthZ uses the
existing role/permission system (admin implies all; otherwise role permissions).
"""

import json
from datetime import datetime
from sqlalchemy import func, or_

from src.database import (
    db, User, Property, PropertyImage, PropertyVideo, Favorite, Request,
    Booking, Message, Room, RoomImage, Slot, Review, PropertyClaim,
    PropertyUnavailability,
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _clean_website(url):
    if not url:
        return url
    if 'propertypro' in url.lower():
        return None
    return url


def _dp(prop_id):
    img = PropertyImage.query.filter_by(property_id=prop_id, dp=1).first()
    if img:
        return img.image_url
    first = PropertyImage.query.filter_by(property_id=prop_id).first()
    return first.image_url if first else ''


def _brief(p):
    return {
        'id': p.id,
        'title': p.title,
        'price': p.price,
        'currency': p.currency,
        'city': p.city,
        'location': p.location,
        'state': p.state,
        'category': p.category,
        'property_type': p.property_type,
        'purpose': p.purpose,
        'bedrooms': p.bedrooms,
        'bathrooms': p.bathrooms,
        'available': p.available,
        'approved': p.approved,
        'views': p.views,
        'dp': _dp(p.id),
        'favorites_count': Favorite.query.filter_by(property_id=p.id).count(),
    }


def _is_admin(user_id):
    u = User.query.filter_by(id=user_id).first()
    return bool(u and u.role == 'admin')


# ---------------------------------------------------------------------------
# READ tools (safe — run freely)
# ---------------------------------------------------------------------------

def search_properties(user_id, q=None, search=None, city=None, category=None,
                      purpose=None, property_type=None, min_price=None,
                      max_price=None, bedrooms=None, bathrooms=None,
                      available=None, sort='newest', page=1, per_page=6):
    """Natural-language + structured property search (approved, enabled only)."""
    # Try AI interpretation for natural queries (reuse existing DeepSeek helper)
    query_text = q or search or ''
    if query_text and not any([city, category, purpose, property_type,
                               min_price, max_price, bedrooms, bathrooms]):
        try:
            from src.ai_search import ai_interpret
            parsed = ai_interpret(query_text)
            if parsed:
                category = category or parsed.get('category')
                purpose = purpose or parsed.get('purpose')
                property_type = property_type or parsed.get('property_type')
                bedrooms = bedrooms if bedrooms is not None else parsed.get('bedrooms')
                bathrooms = bathrooms if bathrooms is not None else parsed.get('bathrooms')
                min_price = min_price if min_price is not None else parsed.get('min_price')
                max_price = max_price if max_price is not None else parsed.get('max_price')
                city = city or parsed.get('city')
                loc = parsed.get('location')
                kws = parsed.get('keywords') or []
                if not search and not q:
                    search = ' '.join(kws) if kws else None
                elif loc and not search and not q:
                    search = loc
                if loc and not city:
                    # location-level search (e.g. Bodija) — search covers it
                    if not search:
                        search = loc
        except Exception:
            pass

    query = Property.query.filter(Property.disabled == 0, Property.approved == 1)
    if search or q:
        s = '%{}%'.format((search or q or '').strip())
        query = query.filter(
            Property.title.ilike(s) | Property.city.ilike(s)
            | Property.location.ilike(s) | Property.description.ilike(s)
        )
    if category:
        query = query.filter_by(category=category)
    if purpose:
        query = query.filter_by(purpose=purpose)
    if property_type:
        query = query.filter_by(property_type=property_type)
    if city:
        query = query.filter(Property.city.ilike('%{}%'.format(city.strip())))
    if bedrooms is not None:
        try:
            query = query.filter(Property.bedrooms >= int(bedrooms))
        except (TypeError, ValueError):
            pass
    if bathrooms is not None:
        try:
            query = query.filter(Property.bathrooms >= int(bathrooms))
        except (TypeError, ValueError):
            pass
    if min_price is not None:
        try:
            query = query.filter(Property.price >= float(min_price))
        except (TypeError, ValueError):
            pass
    if max_price is not None:
        try:
            query = query.filter(Property.price <= float(max_price))
        except (TypeError, ValueError):
            pass
    if available is not None:
        try:
            query = query.filter_by(available=int(available))
        except (TypeError, ValueError):
            pass

    if sort == 'popular':
        query = query.order_by(Property.views.desc(), Property.created_at.desc())
    elif sort == 'favorites':
        query = query.outerjoin(Favorite, Favorite.property_id == Property.id)\
            .group_by(Property.id)\
            .order_by(func.count(Favorite.id).desc(), Property.created_at.desc())
    elif sort == 'price_asc':
        query = query.order_by(Property.price.asc())
    elif sort == 'price_desc':
        query = query.order_by(Property.price.desc())
    else:
        query = query.order_by(Property.created_at.desc())

    try:
        page = max(1, int(page or 1))
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = min(20, max(1, int(per_page or 6)))
    except (TypeError, ValueError):
        per_page = 6
    pag = query.paginate(page=page, per_page=per_page, error_out=False)
    return {
        'success': True,
        'data': [_brief(p) for p in pag.items],
        'meta': {'page': pag.page, 'pages': pag.pages, 'total_count': pag.total,
                 'has_next': pag.has_next, 'has_prev': pag.has_prev},
    }


def get_property_details(user_id, property_id):
    p = Property.query.filter_by(id=int(property_id)).first()
    if not p or p.disabled:
        return {'success': False, 'message': 'Property not found.'}
    owner = User.query.filter_by(id=p.user_id).first()
    images = [{'id': i.id, 'image_url': i.image_url, 'dp': i.dp}
              for i in PropertyImage.query.filter_by(property_id=p.id).all()]
    videos = [{'id': v.id, 'video_url': v.video_url}
              for v in PropertyVideo.query.filter_by(property_id=p.id).all()]
    try:
        attrs = json.loads(p.attributes) if p.attributes else {}
    except Exception:
        attrs = {}
    try:
        amenities = json.loads(p.amenities) if p.amenities else {}
    except Exception:
        amenities = {}
    phones = []
    try:
        phones = json.loads(p.contact_phones) if p.contact_phones else []
    except Exception:
        phones = []
    emails = []
    try:
        emails = json.loads(p.contact_emails) if p.contact_emails else []
    except Exception:
        emails = []
    return {
        'success': True,
        'property': {
            'id': p.id, 'title': p.title, 'description': p.description,
            'category': p.category, 'property_type': p.property_type,
            'purpose': p.purpose, 'price': p.price, 'currency': p.currency,
            'location': p.location, 'city': p.city, 'state': p.state,
            'country': p.country, 'bedrooms': p.bedrooms, 'bathrooms': p.bathrooms,
            'area': p.area, 'available': p.available, 'approved': p.approved,
            'views': p.views, 'negotiable': p.negotiable,
            'attributes': attrs, 'amenities': amenities,
            'images': images, 'videos': videos, 'dp': _dp(p.id),
            'owner_full_name': owner.full_name if owner else None,
            'username': owner.username if owner else None,
            'owner_is_admin': bool(owner and owner.role == 'admin'),
            'contact_phones': [x for x in phones if x],
            'contact_emails': [x for x in emails if x],
            'contact_website': _clean_website(p.contact_website),
            'favorites_count': Favorite.query.filter_by(property_id=p.id).count(),
        },
    }


def similar_properties(user_id, property_id, per_page=3):
    p = Property.query.filter_by(id=int(property_id)).first()
    if not p:
        return {'success': False, 'message': 'Property not found.'}
    items = Property.query.filter(
        Property.disabled == 0, Property.approved == 1,
        Property.category == p.category, Property.id != p.id,
    ).order_by(Property.created_at.desc()).limit(int(per_page or 3)).all()
    return {'success': True, 'data': [_brief(x) for x in items]}


def market_stats(user_id):
    base = Property.query.filter(Property.disabled == 0, Property.approved == 1)
    total = base.count()
    by_cat = dict(base.with_entities(Property.category, func.count(Property.id))
                  .group_by(Property.category).all())
    top_cities = base.with_entities(Property.city, func.count(Property.id))\
        .group_by(Property.city).order_by(func.count(Property.id).desc()).limit(6).all()
    return {'success': True,
            'total_listings': total,
            'by_category': by_cat,
            'top_cities': [{'city': c, 'count': n} for c, n in top_cities]}


def my_properties(user_id, page=1, per_page=10, category=None,
                    purpose=None, city=None, available=None):
    query = Property.query.filter_by(user_id=int(user_id))
    if category:
        query = query.filter_by(category=category)
    if purpose:
        query = query.filter_by(purpose=purpose)
    if city:
        query = query.filter(Property.city.ilike('%{}%'.format(city.strip())))
    if available is not None:
        try:
            query = query.filter_by(available=int(available))
        except (TypeError, ValueError):
            pass
    pag = query.order_by(Property.created_at.desc())\
        .paginate(page=int(page or 1), per_page=min(20, int(per_page or 10)), error_out=False)
    return {'success': True, 'data': [_brief(p) for p in pag.items],
            'meta': {'page': pag.page, 'pages': pag.pages, 'total_count': pag.total}}


def my_property_stats(user_id):
    """Instant breakdown of the current user's listings (no paging needed)."""
    uid = int(user_id)
    total = Property.query.filter_by(user_id=uid).count()
    by_cat = dict(Property.query.filter_by(user_id=uid)
                  .with_entities(Property.category, func.count(Property.id))
                  .group_by(Property.category).all())
    by_purpose = dict(Property.query.filter_by(user_id=uid)
                      .with_entities(Property.purpose, func.count(Property.id))
                      .group_by(Property.purpose).all())
    top_cities = Property.query.filter_by(user_id=uid)\
        .with_entities(Property.city, func.count(Property.id))\
        .group_by(Property.city).order_by(func.count(Property.id).desc()).limit(6).all()
    return {'success': True, 'total_count': total,
            'by_category': by_cat, 'by_purpose': by_purpose,
            'top_cities': [{'city': c, 'count': n} for c, n in top_cities]}


def my_favorites_list(user_id, page=1, per_page=12):
    favs = Favorite.query.filter_by(user_id=int(user_id)).order_by(Favorite.created_at.desc())
    pag = favs.paginate(page=int(page or 1), per_page=min(50, int(per_page or 12)), error_out=False)
    out = []
    for f in pag.items:
        p = Property.query.filter_by(id=f.property_id).first()
        if p:
            out.append(_brief(p))
    return {'success': True, 'data': out,
            'meta': {'page': pag.page, 'pages': pag.pages, 'total_count': pag.total}}


def browse_requests(user_id, city=None, property_type=None, search=None, page=1, per_page=10):
    query = Request.query
    if city:
        query = query.filter(Request.city.ilike('%{}%'.format(city.strip())))
    if property_type:
        query = query.filter_by(property_type=property_type)
    if search:
        s = '%{}%'.format(search.strip())
        query = query.filter(Request.title.ilike(s) | Request.description.ilike(s)
                             | Request.location.ilike(s))
    pag = query.order_by(Request.created_at.desc())\
        .paginate(page=int(page or 1), per_page=min(20, int(per_page or 10)), error_out=False)
    data = [{'id': r.id, 'title': r.title, 'description': r.description,
             'property_type': r.property_type, 'city': r.city, 'location': r.location,
             'min_price': r.min_price, 'max_price': r.max_price,
             'bedrooms': r.bedrooms, 'created_at': str(r.created_at)} for r in pag.items]
    return {'success': True, 'data': data,
            'meta': {'page': pag.page, 'pages': pag.pages, 'total_count': pag.total}}


def my_requests(user_id):
    items = Request.query.filter_by(user_id=int(user_id))\
        .order_by(Request.created_at.desc()).all()
    return {'success': True, 'data': [
        {'id': r.id, 'title': r.title, 'property_type': r.property_type,
         'city': r.city, 'min_price': r.min_price, 'max_price': r.max_price,
         'created_at': str(r.created_at)} for r in items]}


def my_bookings(user_id):
    from src.database import Booking
    items = Booking.query.filter_by(customer_id=int(user_id))\
        .order_by(Booking.created_at.desc()).limit(20).all()
    out = []
    for b in items:
        p = Property.query.filter_by(id=b.property_id).first()
        out.append({'id': b.id, 'property_id': b.property_id,
                    'property_title': p.title if p else None,
                    'status': b.status, 'total': b.total,
                    'check_in': str(b.check_in), 'check_out': str(b.check_out),
                    'guests': b.guests})
    return {'success': True, 'data': out}


def check_availability(user_id, property_id, check_in=None, check_out=None):
    from src.database import Booking
    p = Property.query.filter_by(id=int(property_id)).first()
    if not p:
        return {'success': False, 'message': 'Property not found.'}
    if p.category not in ('hotel', 'hall', 'event_center', 'shortlet'):
        return {'success': True, 'bookable': False,
                'message': 'This property is not bookable — contact the owner directly.'}
    blocked = PropertyUnavailability.query.filter_by(property_id=p.id).all()
    return {'success': True, 'bookable': True, 'available': p.available == 1,
            'blocked_periods': [{'start': str(b.start_date), 'end': str(b.end_date)} for b in blocked],
            'message': 'Available for booking.' if p.available == 1 else 'Currently unavailable.'}


def get_rooms(user_id, property_id):
    rooms = Room.query.filter_by(property_id=int(property_id)).all()
    out = []
    for r in rooms:
        imgs = [{'id': i.id, 'image_url': i.image_url, 'dp': i.dp} for i in r.images.all()]
        out.append({'id': r.id, 'room_type': r.room_type, 'beds': r.beds,
                    'price': r.price, 'available': r.available, 'images': imgs})
    return {'success': True, 'data': out}


def get_slots(user_id, property_id):
    slots = Slot.query.filter_by(property_id=int(property_id))\
        .order_by(Slot.date.asc()).limit(20).all()
    return {'success': True, 'data': [
        {'id': s.id, 'date': str(s.date), 'start_time': str(s.start_time),
         'end_time': str(s.end_time), 'price': s.price, 'status': s.status} for s in slots]}


def my_conversations(user_id):
    rows = Message.query.filter(
        or_(Message.sender_id == int(user_id), Message.receiver_id == int(user_id))
    ).order_by(Message.created_at.desc()).limit(50).all()
    seen, out = set(), []
    for m in rows:
        other = m.receiver_id if m.sender_id == int(user_id) else m.sender_id
        key = (other, m.property_id, m.request_id)
        if key in seen:
            continue
        seen.add(key)
        u = User.query.filter_by(id=other).first()
        out.append({'with_user_id': other,
                    'with_name': u.full_name if u else None,
                    'property_id': m.property_id, 'request_id': m.request_id,
                    'last_body': (m.body or '')[:120],
                    'created_at': str(m.created_at)})
        if len(out) >= 10:
            break
    return {'success': True, 'data': out}


def get_profile(user_id):
    u = User.query.filter_by(id=int(user_id)).first()
    if not u:
        return {'success': False, 'message': 'User not found.'}
    return {'success': True, 'profile': {
        'id': u.id, 'username': u.username, 'full_name': u.full_name,
        'email': u.email, 'phone_number': u.phone_number, 'role': u.role,
        'properties': Property.query.filter_by(user_id=u.id).count(),
        'favorites': Favorite.query.filter_by(user_id=u.id).count(),
        'requests': Request.query.filter_by(user_id=u.id).count()}}


def admin_stats(user_id):
    if not _is_admin(user_id):
        return {'restricted': 'This data is not available for your account.'}
    return {'success': True,
            'users': User.query.count(),
            'properties': Property.query.count(),
            'approved': Property.query.filter_by(approved=1).count(),
            'pending': Property.query.filter_by(approved=0).count(),
            'bookings': Booking.query.count()}


# ---------------------------------------------------------------------------
# WRITE tools (need explicit confirmation — never auto-run)
# ---------------------------------------------------------------------------

def toggle_favorite(user_id, property_id):
    p = Property.query.filter_by(id=int(property_id)).first()
    if not p:
        return {'success': False, 'message': 'Property not found.'}
    existing = Favorite.query.filter_by(user_id=int(user_id), property_id=p.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return {'success': True, 'favorited': False,
                'message': 'Removed "{}" from your favorites.'.format(p.title[:60])}
    db.session.add(Favorite(user_id=int(user_id), property_id=p.id,
                            created_at=datetime.now(), updated_at=datetime.now()))
    db.session.commit()
    return {'success': True, 'favorited': True,
            'message': 'Saved "{}" to your favorites.'.format(p.title[:60])}


def create_request(user_id, title, description, property_type, city=None,
                   location=None, state=None, country=None, min_price=0,
                   max_price=0, bedrooms=None, bathrooms=None):
    if not title or not description or not property_type:
        return {'success': False, 'message': 'Title, description and property type are required.'}
    existing = Request.query.filter(
        Request.user_id == int(user_id),
        func.lower(Request.title) == func.lower(title.strip()),
        Request.property_type == property_type).first()
    if existing:
        return {'success': False, 'message': 'You already have a request with this title.'}
    r = Request(user_id=int(user_id), title=title.strip(), description=description.strip(),
                property_type=property_type, sub_category=None,
                min_price=min_price or 0, max_price=max_price or 0,
                area=None, bedrooms=bedrooms, bathrooms=bathrooms,
                location=location or '', city=city or '', state=state or '',
                country=country or '', year_built=None, amenities=json.dumps({}),
                created_at=datetime.now(), updated_at=datetime.now())
    db.session.add(r)
    db.session.commit()
    return {'success': True, 'id': r.id,
            'message': 'Posted your request "{}". Owners can now respond.'.format(title[:60])}


def create_booking(user_id, property_id, check_in=None, check_out=None,
                   guests=1, room_id=None, slot_id=None):
    from src.database import Booking
    from datetime import date as date_cls
    p = Property.query.filter_by(id=int(property_id)).first()
    if not p:
        return {'success': False, 'message': 'Property not found.'}
    if p.category not in ('hotel', 'hall', 'event_center', 'shortlet'):
        return {'success': False, 'message': 'This property cannot be booked online.'}
    if p.user_id == int(user_id):
        return {'success': False, 'message': 'You cannot book your own property.'}
    if p.available != 1:
        return {'success': False, 'message': 'Property is currently unavailable.'}
    try:
        guests = int(guests or 1)
    except (TypeError, ValueError):
        guests = 1
    room = slot = None
    total, nights = p.price, 1
    if p.category == 'hotel':
        if not room_id:
            return {'success': False, 'message': 'Please choose a room first.'}
        room = Room.query.filter_by(id=int(room_id), property_id=p.id).first()
        if not room or room.available != 1:
            return {'success': False, 'message': 'That room is not available.'}
        if not check_in or not check_out:
            return {'success': False, 'message': 'Check-in and check-out dates are required.'}
        try:
            ci = date_cls.fromisoformat(str(check_in)[:10])
            co = date_cls.fromisoformat(str(check_out)[:10])
        except ValueError:
            return {'success': False, 'message': 'Use YYYY-MM-DD dates.'}
        nights = (co - ci).days
        if nights < 1:
            return {'success': False, 'message': 'Check-out must be after check-in.'}
        total = room.price * nights
    elif p.category in ('hall', 'event_center'):
        if not slot_id:
            return {'success': False, 'message': 'Please choose a slot first.'}
        slot = Slot.query.filter_by(id=int(slot_id), property_id=p.id).first()
        if not slot or slot.status != 'available':
            return {'success': False, 'message': 'That slot is not available.'}
        ci = co = slot.date
        total = slot.price
    else:
        if not check_in or not check_out:
            return {'success': False, 'message': 'Check-in and check-out dates are required.'}
        try:
            ci = date_cls.fromisoformat(str(check_in)[:10])
            co = date_cls.fromisoformat(str(check_out)[:10])
        except ValueError:
            return {'success': False, 'message': 'Use YYYY-MM-DD dates.'}
        nights = (co - ci).days
        if nights < 1:
            return {'success': False, 'message': 'Check-out must be after check-in.'}
        total = p.price * nights
    b = Booking(property_id=p.id, room_id=room.id if room else None,
                slot_id=slot.id if slot else None, customer_id=int(user_id),
                check_in=ci, check_out=co, guests=guests, nights=nights,
                total=total, status='pending',
                created_at=datetime.now(), updated_at=datetime.now())
    db.session.add(b)
    if slot:
        slot.status = 'pending'
        slot.booked_by = int(user_id)
    db.session.commit()
    return {'success': True, 'id': b.id, 'total': total,
            'message': 'Booking requested ({} night(s), total {} {}). Status: pending.'.format(
                nights, p.currency, total)}


def send_message(user_id, body, receiver_id=None, property_id=None, request_id=None):
    if not body or not body.strip():
        return {'success': False, 'message': 'Message body is required.'}
    if receiver_id:
        other = User.query.filter_by(id=int(receiver_id)).first()
        if not other:
            return {'success': False, 'message': 'Recipient not found.'}
        to_id = other.id
    elif property_id:
        p = Property.query.filter_by(id=int(property_id)).first()
        if not p:
            return {'success': False, 'message': 'Property not found.'}
        if p.user_id == int(user_id):
            return {'success': False, 'message': 'This is your own listing.'}
        to_id = p.user_id
    elif request_id:
        r = Request.query.filter_by(id=int(request_id)).first()
        if not r:
            return {'success': False, 'message': 'Request not found.'}
        to_id = r.user_id
    else:
        return {'success': False, 'message': 'Provide a property, request, or recipient.'}
    m = Message(sender_id=int(user_id), receiver_id=to_id,
                property_id=int(property_id) if property_id else None,
                request_id=int(request_id) if request_id else None,
                body=body.strip(), created_at=datetime.now(), updated_at=datetime.now())
    db.session.add(m)
    db.session.commit()
    return {'success': True, 'id': m.id, 'message': 'Message sent.'}


def claim_property(user_id, property_id):
    p = Property.query.filter_by(id=int(property_id)).first()
    if not p:
        return {'success': False, 'message': 'Property not found.'}
    owner = User.query.filter_by(id=p.user_id).first()
    if not owner or owner.role != 'admin':
        return {'success': False, 'message': 'Only admin-listed properties can be claimed here.'}
    existing = PropertyClaim.query.filter_by(
        property_id=p.id, user_id=int(user_id)).order_by(
        PropertyClaim.created_at.desc()).first()
    if existing and existing.status in ('pending', 'pending_verification'):
        return {'success': False, 'message': 'You already have a pending claim for this property.'}
    claim = PropertyClaim(property_id=p.id, user_id=int(user_id), status='pending',
                          created_at=datetime.now(), updated_at=datetime.now())
    db.session.add(claim)
    db.session.commit()
    return {'success': True, 'id': claim.id,
            'message': 'Claim submitted for "{}". The admin will review it.'.format(p.title[:60])}


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------

READ_EXECUTORS = {
    'search_properties': search_properties,
    'get_property_details': get_property_details,
    'similar_properties': similar_properties,
    'market_stats': market_stats,
    'my_properties': my_properties,
    'my_property_stats': my_property_stats,
    'my_favorites_list': my_favorites_list,
    'browse_requests': browse_requests,
    'my_requests': my_requests,
    'my_bookings': my_bookings,
    'check_availability': check_availability,
    'get_rooms': get_rooms,
    'get_slots': get_slots,
    'my_conversations': my_conversations,
    'get_profile': get_profile,
    'admin_stats': admin_stats,
}

WRITE_EXECUTORS = {
    'toggle_favorite': toggle_favorite,
    'create_request': create_request,
    'create_booking': create_booking,
    'send_message': send_message,
    'claim_property': claim_property,
}

ALL_EXECUTORS = {**READ_EXECUTORS, **WRITE_EXECUTORS}
SAFE_TOOLS = set(READ_EXECUTORS.keys())
WRITE_TOOLS = set(WRITE_EXECUTORS.keys())


def execute_tool(name, args, user_id):
    fn = ALL_EXECUTORS.get(name)
    if not fn:
        return {'success': False, 'message': "Unknown tool '{}'.".format(name)}
    try:
        clean = {k: v for k, v in (args or {}).items() if v is not None}
        return fn(user_id, **clean)
    except TypeError as e:
        return {'success': False, 'message': 'Invalid arguments for {}: {}'.format(name, e)}
    except Exception as e:
        return {'success': False, 'message': 'Tool error: {}'.format(e)}


TOOL_DEFINITIONS = [
    {"type": "function", "function": {
        "name": "search_properties",
        "description": "Search approved Aperte listings. Pass natural queries ('2 bedroom flat in Bodija under 3m') straight through via q, or use structured filters. AFTER calling: present each as one emoji-prefixed line '🏠 <title> — <price> · <city> (id: N)'. NO markdown tables.",
        "parameters": {"type": "object", "properties": {
            "q": {"type": "string", "description": "Natural-language query, e.g. '2 bedroom flat in Bodija under 3m'."},
            "search": {"type": "string", "description": "Keyword search (title/city/location)."},
            "city": {"type": "string", "description": "City filter, e.g. 'Ibadan'."},
            "category": {"type": "string", "description": "property|land|hotel|hall|event_center|shortlet."},
            "purpose": {"type": "string", "description": "rent|sale."},
            "property_type": {"type": "string", "description": "Flat / Apartment|House|Duplex|Land|Shop|Office|Hotel|etc."},
            "min_price": {"type": "number", "description": "Minimum price in Naira."},
            "max_price": {"type": "number", "description": "Maximum price in Naira."},
            "bedrooms": {"type": "integer", "description": "Minimum bedrooms."},
            "bathrooms": {"type": "integer", "description": "Minimum bathrooms."},
            "sort": {"type": "string", "description": "newest|popular|favorites|price_asc|price_desc."},
            "page": {"type": "integer", "description": "Page number (default 1)."},
            "per_page": {"type": "integer", "description": "Results per page, max 20 (default 6)."}}, "required": []}}},
    {"type": "function", "function": {
        "name": "get_property_details",
        "description": "Full details for one listing: price, location, beds/baths, images, owner, contact phone, availability. AFTER calling: short emoji-prefixed lines, never a table.",
        "parameters": {"type": "object", "properties": {
            "property_id": {"type": "integer", "description": "Listing id."}}, "required": ["property_id"]}}},
    {"type": "function", "function": {
        "name": "similar_properties",
        "description": "More listings in the same category (discovery).",
        "parameters": {"type": "object", "properties": {
            "property_id": {"type": "integer", "description": "Reference listing id."},
            "per_page": {"type": "integer", "description": "How many (default 3)."}}, "required": ["property_id"]}}},
    {"type": "function", "function": {
        "name": "market_stats",
        "description": "Live marketplace counts: total listings, by category, top cities.",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "my_properties",
        "description": "Current user's own listings, filterable by category/purpose/city. Use this for 'show my shortlets/houses/land' — pass category directly instead of paging the full list. AFTER calling: one emoji-prefixed line per listing with id. Counts come ONLY from meta.total_count.",
        "parameters": {"type": "object", "properties": {
            "page": {"type": "integer"}, "per_page": {"type": "integer"},
            "category": {"type": "string", "description": "property|land|hotel|hall|event_center|shortlet."},
            "purpose": {"type": "string", "description": "rent|sale."},
            "city": {"type": "string", "description": "City filter."},
            "available": {"type": "integer", "description": "1 available, 0 unavailable."}}, "required": []}}},
    {"type": "function", "function": {
        "name": "my_property_stats",
        "description": "Instant breakdown of the current user's listings: total_count plus counts by category, by purpose, and top cities. Use this FIRST for 'how many of my X', 'break down my listings', 'how many shortlets do I have' — then optionally pull examples with my_properties. Never page the full list to tally categories yourself.",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "my_favorites_list",
        "description": "Properties the user saved.",
        "parameters": {"type": "object", "properties": {
            "page": {"type": "integer"}, "per_page": {"type": "integer"}}, "required": []}}},
    {"type": "function", "function": {
        "name": "toggle_favorite",
        "description": "Save or unsave a listing. CONFIRM with the user first: state the exact title/id and wait for a clear yes. Never auto-call.",
        "parameters": {"type": "object", "properties": {
            "property_id": {"type": "integer", "description": "Listing id."}}, "required": ["property_id"]}}},
    {"type": "function", "function": {
        "name": "browse_requests",
        "description": "Browse 'looking for' property requests from seekers.",
        "parameters": {"type": "object", "properties": {
            "city": {"type": "string"}, "property_type": {"type": "string"},
            "search": {"type": "string"}, "page": {"type": "integer"},
            "per_page": {"type": "integer"}}, "required": []}}},
    {"type": "function", "function": {
        "name": "my_requests",
        "description": "Current user's posted requests.",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "create_request",
        "description": "Post a 'looking for' request. CONFIRM first: title, property type, city/budget. Ask for any missing required field (title, description, property_type) — never guess.",
        "parameters": {"type": "object", "properties": {
            "title": {"type": "string"}, "description": {"type": "string"},
            "property_type": {"type": "string"}, "city": {"type": "string"},
            "location": {"type": "string"}, "state": {"type": "string"},
            "country": {"type": "string"}, "min_price": {"type": "number"},
            "max_price": {"type": "number"}, "bedrooms": {"type": "integer"},
            "bathrooms": {"type": "integer"}},
            "required": ["title", "description", "property_type"]}}},
    {"type": "function", "function": {
        "name": "my_bookings",
        "description": "Current user's bookings with status and totals.",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "check_availability",
        "description": "Check whether a hotel/shortlet/venue is bookable and blocked periods.",
        "parameters": {"type": "object", "properties": {
            "property_id": {"type": "integer"}, "check_in": {"type": "string"},
            "check_out": {"type": "string"}}, "required": ["property_id"]}}},
    {"type": "function", "function": {
        "name": "get_rooms",
        "description": "Rooms for a hotel listing.",
        "parameters": {"type": "object", "properties": {
            "property_id": {"type": "integer"}}, "required": ["property_id"]}}},
    {"type": "function", "function": {
        "name": "get_slots",
        "description": "Available slots for a hall/event-centre listing.",
        "parameters": {"type": "object", "properties": {
            "property_id": {"type": "integer"}}, "required": ["property_id"]}}},
    {"type": "function", "function": {
        "name": "create_booking",
        "description": "Request a booking. CONFIRM first: property, dates, guests, room/slot, total. For hotels need room_id + dates; venues need slot_id. Never guess dates.",
        "parameters": {"type": "object", "properties": {
            "property_id": {"type": "integer"}, "check_in": {"type": "string"},
            "check_out": {"type": "string"}, "guests": {"type": "integer"},
            "room_id": {"type": "integer"}, "slot_id": {"type": "integer"}},
            "required": ["property_id"]}}},
    {"type": "function", "function": {
        "name": "my_conversations",
        "description": "Recent message threads for the user.",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "send_message",
        "description": "Message an owner about a property/request. CONFIRM first: recipient/property and exact text. Never send without a clear yes.",
        "parameters": {"type": "object", "properties": {
            "body": {"type": "string"}, "receiver_id": {"type": "integer"},
            "property_id": {"type": "integer"}, "request_id": {"type": "integer"}},
            "required": ["body"]}}},
    {"type": "function", "function": {
        "name": "claim_property",
        "description": "Claim an admin-listed property. CONFIRM first: state the exact title/id. Only admin listings qualify.",
        "parameters": {"type": "object", "properties": {
            "property_id": {"type": "integer"}}, "required": ["property_id"]}}},
    {"type": "function", "function": {
        "name": "get_profile",
        "description": "Current user's profile with counts (listings, favorites, requests).",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "admin_stats",
        "description": "Admin-only marketplace totals (users, properties, pending, bookings).",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
]

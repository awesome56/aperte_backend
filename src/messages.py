from src.constants.http_status_codes import HTTP_400_BAD_REQUEST
from src.constants.http_status_codes import HTTP_401_UNAUTHORIZED
from src.constants.http_status_codes import HTTP_404_NOT_FOUND
from src.constants.http_status_codes import HTTP_200_OK
from src.constants.http_status_codes import HTTP_201_CREATED
from src.constants.http_status_codes import HTTP_204_NO_CONTENT
from flask import Blueprint, request, jsonify
from src.database import db, User, Message, Property, Request, PropertyImage
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from sqlalchemy import or_, and_, func
from flasgger import swag_from

messages = Blueprint("messages", __name__, url_prefix="/api/v1/messages")

# A user is considered online if their last heartbeat is within this window.
ONLINE_WINDOW = timedelta(minutes=2)


def presence(user):
    """Online status helper: online + last_seen (for 'last seen X ago')."""
    if user is None or user.last_seen is None:
        return {'online': False, 'last_seen': None}
    return {
        'online': datetime.now() - user.last_seen <= ONLINE_WINDOW,
        'last_seen': user.last_seen,
    }


def message_context(m):
    """Attach the quoted property/request so receivers see where the message
    originated from."""
    ctx = {}
    if m.property_id:
        p = Property.query.filter_by(id=m.property_id).first()
        if p:
            dp = PropertyImage.query.filter_by(property_id=p.id, dp=1).first()
            ctx['property'] = {
                'id': p.id,
                'title': p.title,
                'property_type': p.property_type,
                'price': p.price,
                'currency': p.currency,
                'location': p.location,
                'city': p.city,
                'state': p.state,
                'dp': dp.image_url if dp else "",
            }
    if m.request_id:
        r = Request.query.filter_by(id=m.request_id).first()
        if r:
            ctx['request'] = {
                'id': r.id,
                'title': r.title,
                'property_type': r.property_type,
                'min_price': r.min_price,
                'max_price': r.max_price,
                'city': r.city,
                'state': r.state,
            }
    return ctx


def serialize_message(m):
    return {
        'id': m.id,
        'sender_id': m.sender_id,
        'receiver_id': m.receiver_id,
        'body': m.body,
        'read': m.read,
        'delivered': m.delivered,
        'property_id': m.property_id,
        'request_id': m.request_id,
        'created_at': m.created_at,
        'updated_at': m.updated_at,
        **message_context(m),
    }


@messages.post("/")
@jwt_required()
@swag_from('./docs/messages/sendmessage.yml')
def send_message():
    me = get_jwt_identity()

    data = request.get_json(silent=True) or {}

    body = (data.get('body') or '').strip()
    receiver_id = data.get('receiver_id')
    property_id = data.get('property_id')
    request_id = data.get('request_id')

    if not body:
        return jsonify({'error': "Message body must not be empty"}), HTTP_400_BAD_REQUEST

    if len(body) > 5000:
        return jsonify({'error': "Message is too long (max 5000 characters)"}), HTTP_400_BAD_REQUEST

    if property_id is not None:
        try:
            property_id = int(property_id)
        except (ValueError, TypeError):
            return jsonify({'error': "Invalid property id"}), HTTP_400_BAD_REQUEST

    if request_id is not None:
        try:
            request_id = int(request_id)
        except (ValueError, TypeError):
            return jsonify({'error': "Invalid request id"}), HTTP_400_BAD_REQUEST

    if property_id and request_id:
        return jsonify({'error': "A message can quote a property OR a request, not both"}), HTTP_400_BAD_REQUEST

    # Resolve the receiver: explicit user, or the owner of the quoted
    # property/request so the context always makes sense.
    receiver = None
    if receiver_id:
        try:
            receiver = User.query.filter_by(id=int(receiver_id)).first()
        except (ValueError, TypeError):
            receiver = None
        if not receiver:
            return jsonify({'error': "Receiver not found"}), HTTP_404_NOT_FOUND

    if property_id:
        p = Property.query.filter_by(id=property_id).first()
        if not p:
            return jsonify({'error': "Property not found"}), HTTP_404_NOT_FOUND
        if receiver is None:
            receiver = User.query.filter_by(id=p.user_id).first()

    if request_id:
        r = Request.query.filter_by(id=request_id).first()
        if not r:
            return jsonify({'error': "Request not found"}), HTTP_404_NOT_FOUND
        if receiver is None:
            receiver = User.query.filter_by(id=r.user_id).first()

    if not receiver:
        return jsonify({'error': "Receiver not found"}), HTTP_404_NOT_FOUND

    if receiver.id == me:
        return jsonify({'error': "You cannot message yourself"}), HTTP_400_BAD_REQUEST

    msg = Message(
        sender_id=me,
        receiver_id=receiver.id,
        body=body,
        property_id=property_id,
        request_id=request_id,
        read=0,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    db.session.add(msg)
    db.session.commit()

    return jsonify(serialize_message(msg)), HTTP_201_CREATED


@messages.get("/conversations")
@jwt_required()
@swag_from('./docs/messages/conversations.yml')
def conversations():
    me = get_jwt_identity()

    property_id = request.args.get('property_id', type=int)
    request_id = request.args.get('request_id', type=int)

    q = Message.query.filter(or_(Message.sender_id == me, Message.receiver_id == me))
    if property_id:
        q = q.filter(Message.property_id == property_id)
    if request_id:
        q = q.filter(Message.request_id == request_id)

    recent = q.order_by(Message.created_at.desc()).limit(500).all()

    unread = dict(db.session.query(
        Message.sender_id, func.count(Message.id)
    ).filter(
        Message.receiver_id == me, Message.read == 0
    ).group_by(Message.sender_id).all())

    # latest message per counterpart
    convos = {}
    for m in recent:
        other = m.receiver_id if m.sender_id == me else m.sender_id
        if other not in convos:
            convos[other] = m

    data = []
    for other_id, last in sorted(convos.items(), key=lambda kv: kv[1].created_at, reverse=True):
        u = User.query.filter_by(id=other_id).first()
        if not u:
            continue
        data.append({
            'user': {
                'id': u.id,
                'username': u.username,
                'full_name': u.full_name,
                'profile_picture': u.profile_picture,
                **presence(u),
            },
            'last_message': serialize_message(last),
            'unread_count': unread.get(other_id, 0),
            'last_activity': last.created_at,
        })

    return jsonify({'data': data}), HTTP_200_OK


@messages.get("/conversation/<int:user_id>")
@jwt_required()
@swag_from('./docs/messages/conversation.yml')
def conversation(user_id):
    me = get_jwt_identity()

    if user_id == me:
        return jsonify({'error': "Invalid conversation"}), HTTP_400_BAD_REQUEST

    other = User.query.filter_by(id=user_id).first()
    if not other:
        return jsonify({'error': "User not found"}), HTTP_404_NOT_FOUND

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)

    q = Message.query.filter(
        or_(
            and_(Message.sender_id == me, Message.receiver_id == user_id),
            and_(Message.sender_id == user_id, Message.receiver_id == me),
        )
    )

    msgs = q.order_by(Message.created_at.desc()).paginate(page=page, per_page=per_page)

    # Mark incoming messages as delivered and read (thread is open)
    incoming = Message.query.filter(
        Message.sender_id == user_id, Message.receiver_id == me
    ).all()
    for m in incoming:
        m.delivered = 1
        m.read = 1
    db.session.commit()

    data = [serialize_message(m) for m in reversed(msgs.items)]

    meta = {
        "page": msgs.page,
        "pages": msgs.pages,
        "total_count": msgs.total,
        "prev_page": msgs.prev_num,
        "next_page": msgs.next_num,
        "has_next": msgs.has_next,
        "has_prev": msgs.has_prev,
    }

    return jsonify({
        'messages': data,
        'user': {
            'id': other.id,
            'username': other.username,
            'full_name': other.full_name,
            'profile_picture': other.profile_picture,
            **presence(other),
        },
        'meta': meta,
    }), HTTP_200_OK


@messages.get("/unread-count")
@jwt_required()
def unread_count():
    me = get_jwt_identity()
    n = Message.query.filter(Message.receiver_id == me, Message.read == 0).count()
    return jsonify({'unread_count': n}), HTTP_200_OK


@messages.delete("/<int:id>")
@jwt_required()
@swag_from('./docs/messages/deletemessage.yml')
def delete_message(id):
    me = get_jwt_identity()

    m = Message.query.filter_by(id=id).first()
    if not m:
        return jsonify({'error': "Message not found"}), HTTP_404_NOT_FOUND

    if m.sender_id != me and m.receiver_id != me:
        return jsonify({'error': "Unauthorized"}), HTTP_401_UNAUTHORIZED

    db.session.delete(m)
    db.session.commit()

    return jsonify({}), HTTP_204_NO_CONTENT

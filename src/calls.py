from src.constants.http_status_codes import HTTP_400_BAD_REQUEST
from src.constants.http_status_codes import HTTP_404_NOT_FOUND
from src.constants.http_status_codes import HTTP_200_OK
from src.constants.http_status_codes import HTTP_201_CREATED
from flask import Blueprint, request, jsonify
from src.database import db, User, Call, CallSignal
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
import uuid

calls = Blueprint("calls", __name__, url_prefix="/api/v1/calls")

# Ringing calls that were never answered expire after this long (seconds).
RING_TIMEOUT = 60

# A user is considered online if their last heartbeat is within this window.
ONLINE_WINDOW = timedelta(minutes=2)


def call_user(u):
    if not u:
        return None
    online = u.last_seen is not None and (datetime.now() - u.last_seen <= ONLINE_WINDOW)
    return {
        'id': u.id,
        'username': u.username,
        'full_name': u.full_name,
        'profile_picture': u.profile_picture,
        'online': online,
        'last_seen': u.last_seen,
    }


def serialize_call(c):
    return {
        'id': c.id,
        'caller': call_user(User.query.filter_by(id=c.caller_id).first()),
        'callee': call_user(User.query.filter_by(id=c.callee_id).first()),
        'call_type': c.call_type,
        'status': c.status,
        'started_at': c.started_at,
        'ended_at': c.ended_at,
        'ended_by': c.ended_by,
        'created_at': c.created_at,
    }


@calls.post("/")
@jwt_required()
def create_call():
    me = get_jwt_identity()

    data = request.get_json(silent=True) or {}
    receiver_id = data.get('receiver_id')
    call_type = data.get('call_type', 'audio')

    if call_type not in ('audio', 'video'):
        return jsonify({'error': "call_type must be 'audio' or 'video'"}), HTTP_400_BAD_REQUEST

    try:
        receiver_id = int(receiver_id)
    except (ValueError, TypeError):
        return jsonify({'error': "receiver_id is required"}), HTTP_400_BAD_REQUEST

    if receiver_id == me:
        return jsonify({'error': "You cannot call yourself"}), HTTP_400_BAD_REQUEST

    if not User.query.filter_by(id=receiver_id).first():
        return jsonify({'error': "Receiver not found"}), HTTP_404_NOT_FOUND

    # Don't stack ringing calls between the same pair
    existing = Call.query.filter(
        Call.caller_id == me, Call.callee_id == receiver_id, Call.status == 'ringing'
    ).first()
    if existing:
        return jsonify(serialize_call(existing)), HTTP_200_OK

    call = Call(
        id=str(uuid.uuid4()),
        caller_id=me,
        callee_id=receiver_id,
        call_type=call_type,
        status='ringing',
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    db.session.add(call)
    db.session.commit()

    return jsonify(serialize_call(call)), HTTP_201_CREATED


@calls.get("/<call_id>")
@jwt_required()
def get_call(call_id):
    me = get_jwt_identity()

    call = Call.query.filter_by(id=call_id).first()
    if not call:
        return jsonify({'error': "Call not found"}), HTTP_404_NOT_FOUND

    if me not in (call.caller_id, call.callee_id):
        return jsonify({'error': "Unauthorized"}), HTTP_401_UNAUTHORIZED

    return jsonify(serialize_call(call)), HTTP_200_OK


@calls.post("/<call_id>/answer")
@jwt_required()
def answer_call(call_id):
    me = get_jwt_identity()

    call = Call.query.filter_by(id=call_id).first()
    if not call:
        return jsonify({'error': "Call not found"}), HTTP_404_NOT_FOUND

    if me != call.callee_id:
        return jsonify({'error': "Only the callee can answer this call"}), HTTP_400_BAD_REQUEST

    data = request.get_json(silent=True) or {}
    accepted = data.get('accepted', True)

    if call.status != 'ringing':
        return jsonify(serialize_call(call)), HTTP_200_OK

    if not accepted:
        call.status = 'declined'
        call.ended_at = datetime.now()
        call.ended_by = me
    else:
        call.status = 'active'
        call.started_at = datetime.now()
    call.updated_at = datetime.now()
    db.session.commit()

    return jsonify(serialize_call(call)), HTTP_200_OK


@calls.post("/<call_id>/signal")
@jwt_required()
def send_signal(call_id):
    me = get_jwt_identity()

    call = Call.query.filter_by(id=call_id).first()
    if not call:
        return jsonify({'error': "Call not found"}), HTTP_404_NOT_FOUND

    if me not in (call.caller_id, call.callee_id):
        return jsonify({'error': "Unauthorized"}), HTTP_401_UNAUTHORIZED

    data = request.get_json(silent=True) or {}
    signal_type = data.get('type')
    payload = data.get('payload')

    if signal_type not in ('offer', 'answer', 'ice'):
        return jsonify({'error': "signal type must be offer, answer or ice"}), HTTP_400_BAD_REQUEST
    if not payload:
        return jsonify({'error': "payload is required"}), HTTP_400_BAD_REQUEST

    import json as _json
    signal = CallSignal(
        call_id=call.id,
        sender_id=me,
        signal_type=signal_type,
        payload=_json.dumps(payload),
        created_at=datetime.now(),
    )
    db.session.add(signal)
    db.session.commit()

    return jsonify({'message': "Signal stored"}), HTTP_200_OK


@calls.get("/<call_id>/signals")
@jwt_required()
def list_signals(call_id):
    me = get_jwt_identity()

    call = Call.query.filter_by(id=call_id).first()
    if not call:
        return jsonify({'error': "Call not found"}), HTTP_404_NOT_FOUND

    if me not in (call.caller_id, call.callee_id):
        return jsonify({'error': "Unauthorized"}), HTTP_401_UNAUTHORIZED

    after = request.args.get('after', 0, type=int)

    import json as _json
    signals = CallSignal.query.filter(
        CallSignal.call_id == call_id,
        CallSignal.id > after,
        CallSignal.sender_id != me,
    ).order_by(CallSignal.id.asc()).limit(100).all()

    return jsonify({
        'signals': [{
            'id': s.id,
            'type': s.signal_type,
            'payload': _json.loads(s.payload),
            'created_at': s.created_at,
        } for s in signals],
    }), HTTP_200_OK


@calls.post("/<call_id>/end")
@jwt_required()
def end_call(call_id):
    me = get_jwt_identity()

    call = Call.query.filter_by(id=call_id).first()
    if not call:
        return jsonify({'error': "Call not found"}), HTTP_404_NOT_FOUND

    if me not in (call.caller_id, call.callee_id):
        return jsonify({'error': "Unauthorized"}), HTTP_401_UNAUTHORIZED

    if call.status in ('ringing', 'active'):
        data = request.get_json(silent=True) or {}
        reason = data.get('status')
        call.status = reason if reason in ('declined', 'missed') else 'ended'
        call.ended_at = datetime.now()
        call.ended_by = me
        call.updated_at = datetime.now()
        db.session.commit()

    return jsonify(serialize_call(call)), HTTP_200_OK

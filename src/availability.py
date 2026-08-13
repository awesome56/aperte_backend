from src.constants.http_status_codes import HTTP_400_BAD_REQUEST
from src.constants.http_status_codes import HTTP_404_NOT_FOUND
from src.constants.http_status_codes import HTTP_200_OK
from src.constants.http_status_codes import HTTP_201_CREATED
from src.constants.http_status_codes import HTTP_204_NO_CONTENT
from flask import Blueprint, request, jsonify
from src.database import db, Property, Booking, Room, Slot, PropertyUnavailability
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta

availability = Blueprint("availability", __name__, url_prefix="/api/v1")

BOOKABLE = ('hotel', 'shortlet', 'hall', 'event_center')


def parse_date(value, label):
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        raise ValueError("{} must be a valid date (YYYY-MM-DD)".format(label))


@availability.get("/properties/<int:property_id>/availability")
@jwt_required(optional=True)
def get_availability(property_id):
    """Calendar data for a bookable property.

    Returns booked date ranges (from active bookings, per room for hotels),
    owner-blocked ranges, and slot details for halls/event centers.
    """
    property_ = Property.query.filter_by(id=property_id).first()
    if not property_:
        return jsonify({'error': "Property not found"}), HTTP_404_NOT_FOUND

    if property_.category not in BOOKABLE:
        return jsonify({'error': "This property is not bookable"}), HTTP_400_BAD_REQUEST

    # active bookings (pending/confirmed count as taken)
    bookings = Booking.query.filter(
        Booking.property_id == property_id,
        Booking.status.in_(['pending', 'confirmed']),
    ).all()

    booked = []
    for b in bookings:
        booked.append({
            'id': b.id,
            'room_id': b.room_id,
            'slot_id': b.slot_id,
            'start': b.check_in.isoformat() if b.check_in else None,
            'end': b.check_out.isoformat() if b.check_out else None,
            'date': b.check_in.isoformat() if (b.slot_id is not None and b.check_in) else None,
            'status': b.status,
        })

    blocked = [{
        'id': u.id,
        'start': u.start_date.isoformat(),
        'end': u.end_date.isoformat(),
    } for u in PropertyUnavailability.query.filter_by(property_id=property_id).order_by(PropertyUnavailability.start_date).all()]

    rooms = [{
        'id': r.id,
        'room_type': r.room_type,
        'available': r.available,
    } for r in Room.query.filter_by(property_id=property_id).all()] if property_.category == 'hotel' else []

    slots = [{
        'id': s.id,
        'date': s.date.isoformat(),
        'start_time': s.start_time,
        'end_time': s.end_time,
        'price': s.price,
        'status': s.status,
        'booked_by': s.booked_by,
    } for s in Slot.query.filter_by(property_id=property_id).order_by(Slot.date).all()] if property_.category in ('hall', 'event_center') else []

    return jsonify({
        'category': property_.category,
        'booked': booked,
        'blocked': blocked,
        'rooms': rooms,
        'slots': slots,
    }), HTTP_200_OK


@availability.post("/properties/<int:property_id>/unavailability")
@jwt_required()
def block_dates(property_id):
    me = get_jwt_identity()

    property_ = Property.query.filter_by(id=property_id).first()
    if not property_:
        return jsonify({'error': "Property not found"}), HTTP_404_NOT_FOUND

    if property_.user_id != me:
        return jsonify({'error': "Only the property owner can manage availability"}), HTTP_404_NOT_FOUND

    if property_.category not in ('hotel', 'shortlet'):
        return jsonify({'error': "Only hotels and shortlets support date blocking"}), HTTP_400_BAD_REQUEST

    data = request.get_json(silent=True) or {}
    start = data.get('start_date')
    end = data.get('end_date')

    try:
        start_date = parse_date(start, "Start date")
        end_date = parse_date(end, "End date")
    except ValueError as e:
        return jsonify({'error': str(e)}), HTTP_400_BAD_REQUEST

    if end_date < start_date:
        return jsonify({'error': "End date must be on or after the start date"}), HTTP_400_BAD_REQUEST

    block = PropertyUnavailability(
        property_id=property_id,
        start_date=start_date,
        end_date=end_date,
        created_at=datetime.now(),
    )
    db.session.add(block)
    db.session.commit()

    return jsonify({
        'message': "Dates blocked",
        'block': {'id': block.id, 'start': block.start_date.isoformat(), 'end': block.end_date.isoformat()},
    }), HTTP_201_CREATED


@availability.delete("/unavailability/<int:block_id>")
@jwt_required()
def unblock_dates(block_id):
    me = get_jwt_identity()

    block = PropertyUnavailability.query.filter_by(id=block_id).first()
    if not block:
        return jsonify({'error': "Block not found"}), HTTP_404_NOT_FOUND

    property_ = Property.query.filter_by(id=block.property_id).first()
    if not property_ or property_.user_id != me:
        return jsonify({'error': "Only the property owner can manage availability"}), HTTP_404_NOT_FOUND

    db.session.delete(block)
    db.session.commit()

    return jsonify({}), HTTP_204_NO_CONTENT

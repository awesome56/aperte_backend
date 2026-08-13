from src.constants.http_status_codes import HTTP_400_BAD_REQUEST
from src.constants.http_status_codes import HTTP_401_UNAUTHORIZED
from src.constants.http_status_codes import HTTP_404_NOT_FOUND
from src.constants.http_status_codes import HTTP_409_CONFLICT
from src.constants.http_status_codes import HTTP_200_OK
from src.constants.http_status_codes import HTTP_201_CREATED
from src.constants.http_status_codes import HTTP_204_NO_CONTENT
from flask import Blueprint, request, jsonify
from src.database import db, Property, Room, Slot, Booking
from src.constants.property_meta import BOOKING_CATEGORIES, BOOKING_STATUSES
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from flasgger import swag_from


bookings = Blueprint("booking", __name__, url_prefix="/api/v1/bookings")


def to_int(value, label):
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (ValueError, TypeError):
        raise ValueError("{} must be an whole number".format(label))


def parse_date(value, label):
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        raise ValueError("{} must be a valid date (YYYY-MM-DD)".format(label))


def serialize_booking(booking):
    return {
        'id': booking.id,
        'property_id': booking.property_id,
        'room_id': booking.room_id,
        'slot_id': booking.slot_id,
        'customer_id': booking.customer_id,
        'check_in': booking.check_in.isoformat() if booking.check_in else None,
        'check_out': booking.check_out.isoformat() if booking.check_out else None,
        'guests': booking.guests,
        'nights': booking.nights,
        'total': booking.total,
        'status': booking.status,
        'created_at': booking.created_at,
        'updated_at': booking.updated_at,
    }


def has_blocked_period(property_id, check_in, check_out):
    return PropertyUnavailability.query.filter(
        PropertyUnavailability.property_id == property_id,
        PropertyUnavailability.end_date >= check_in,
        PropertyUnavailability.start_date <= check_out,
    ).first() is not None


def has_overlap(property_id, room_id, check_in, check_out):
    query = Booking.query.filter(
        Booking.property_id == property_id,
        Booking.status.in_(['pending', 'confirmed']),
        Booking.check_out > check_in,
        Booking.check_in < check_out,
    )

    if room_id is not None:
        query = query.filter(Booking.room_id == room_id)
    else:
        query = query.filter(Booking.room_id.is_(None))

    return query.first() is not None


@bookings.post('/property/<int:property_id>')
@jwt_required()
@swag_from('./docs/bookings/createbooking.yml')
def create_booking(property_id):
    current_user = get_jwt_identity()

    property_ = Property.query.filter_by(id=property_id).first()

    if not property_:
        return jsonify({'error': "Property not found"}), HTTP_404_NOT_FOUND

    if property_.category not in BOOKING_CATEGORIES:
        return jsonify({'error': "This property category cannot be booked"}), HTTP_400_BAD_REQUEST

    if property_.user_id == current_user:
        return jsonify({'error': "You cannot book your own property"}), HTTP_400_BAD_REQUEST

    if property_.available != 1:
        return jsonify({'error': "Property is not available"}), HTTP_400_BAD_REQUEST

    room_id = request.get_json().get('room_id')
    slot_id = request.get_json().get('slot_id')
    guests = request.get_json().get('guests', 1)
    check_in = request.get_json().get('check_in')
    check_out = request.get_json().get('check_out')

    try:
        guests = to_int(guests, "Guests")
    except ValueError as e:
        return jsonify({'error': str(e)}), HTTP_400_BAD_REQUEST

    if guests is not None and guests < 1:
        return jsonify({'error': "Guests must be at least 1"}), HTTP_400_BAD_REQUEST

    nights = 1
    room = None
    slot = None

    if property_.category == 'hotel':
        if not room_id:
            return jsonify({'error': "Room id is required for hotel bookings"}), HTTP_400_BAD_REQUEST

        room = Room.query.filter_by(id=room_id, property_id=property_id).first()

        if not room:
            return jsonify({'error': "Room not found for this property"}), HTTP_404_NOT_FOUND

        if room.available != 1:
            return jsonify({'error': "Room is not available"}), HTTP_400_BAD_REQUEST

        if not check_in or not check_out:
            return jsonify({'error': "Check in and check out dates are required"}), HTTP_400_BAD_REQUEST

        try:
            check_in_date = parse_date(check_in, "Check in date")
            check_out_date = parse_date(check_out, "Check out date")
        except ValueError as e:
            return jsonify({'error': str(e)}), HTTP_400_BAD_REQUEST

        nights = (check_out_date - check_in_date).days

        if nights < 1:
            return jsonify({'error': "Check out date must be after check in date"}), HTTP_400_BAD_REQUEST

        if has_blocked_period(property_id, check_in_date, check_out_date):
            return jsonify({'error': "Property is blocked for the selected dates"}), HTTP_409_CONFLICT

        if has_overlap(property_id, room_id, check_in_date, check_out_date):
            return jsonify({'error': "Room is already booked for the selected dates"}), HTTP_409_CONFLICT

        total = room.price * nights

    elif property_.category in ('hall', 'event_center'):
        if not slot_id:
            return jsonify({'error': "Slot id is required for {} bookings".format(property_.category)}), HTTP_400_BAD_REQUEST

        slot = Slot.query.filter_by(id=slot_id, property_id=property_id).first()

        if not slot:
            return jsonify({'error': "Slot not found for this property"}), HTTP_404_NOT_FOUND

        if slot.status != 'available':
            return jsonify({'error': "Slot is not available"}), HTTP_409_CONFLICT

        check_in_date = slot.date
        check_out_date = slot.date
        nights = 1
        total = slot.price

    else:
        if not check_in or not check_out:
            return jsonify({'error': "Check in and check out dates are required"}), HTTP_400_BAD_REQUEST

        try:
            check_in_date = parse_date(check_in, "Check in date")
            check_out_date = parse_date(check_out, "Check out date")
        except ValueError as e:
            return jsonify({'error': str(e)}), HTTP_400_BAD_REQUEST

        nights = (check_out_date - check_in_date).days

        if nights < 1:
            return jsonify({'error': "Check out date must be after check in date"}), HTTP_400_BAD_REQUEST

        if has_blocked_period(property_id, check_in_date, check_out_date):
            return jsonify({'error': "Property is blocked for the selected dates"}), HTTP_409_CONFLICT

        if has_overlap(property_id, None, check_in_date, check_out_date):
            return jsonify({'error': "Property is already booked for the selected dates"}), HTTP_409_CONFLICT

        total = property_.price * nights

    booking = Booking(property_id=property_id, room_id=room.id if room else None, slot_id=slot.id if slot else None, customer_id=current_user, check_in=check_in_date, check_out=check_out_date, guests=guests, nights=nights, total=total, status='pending', created_at=datetime.now(), updated_at=datetime.now())

    db.session.add(booking)

    if slot:
        slot.status = 'pending'
        slot.booked_by = current_user

    db.session.commit()

    return jsonify(serialize_booking(booking)), HTTP_201_CREATED


@bookings.get('/<int:id>')
@swag_from('./docs/bookings/getbooking.yml')
def get_booking(id):
    booking = Booking.query.filter_by(id=id).first()

    if not booking:
        return jsonify({'error': "Booking not found"}), HTTP_404_NOT_FOUND

    return jsonify(serialize_booking(booking)), HTTP_200_OK


@bookings.get('/property/<int:property_id>')
@jwt_required()
@swag_from('./docs/bookings/getpropertybookings.yml')
def get_property_bookings(property_id):
    current_user = get_jwt_identity()

    property_ = Property.query.filter_by(id=property_id).first()

    if not property_:
        return jsonify({'error': "Property not found"}), HTTP_404_NOT_FOUND

    if not property_.user_id == current_user:
        return jsonify({'error': "Unauthorized"}), HTTP_401_UNAUTHORIZED

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')

    query = Booking.query.filter_by(property_id=property_id)

    if status:
        if status not in BOOKING_STATUSES:
            return jsonify({'error': "Status must be one of: pending, confirmed, cancelled, completed"}), HTTP_400_BAD_REQUEST
        query = query.filter_by(status=status)

    bookings_ = query.order_by(Booking.created_at.desc()).paginate(page=page, per_page=per_page)

    data = [serialize_booking(booking) for booking in bookings_.items]

    meta = {
        "page": bookings_.page,
        "pages": bookings_.pages,
        "total_count": bookings_.total,
        "prev_page": bookings_.prev_num,
        "next_page": bookings_.next_num,
        "has_next": bookings_.has_next,
        "has_prev": bookings_.has_prev
    }

    return jsonify({'data': data, 'meta': meta}), HTTP_200_OK


@bookings.get('/user/<int:user_id>/')
@swag_from('./docs/bookings/getuserbookings.yml')
def get_user_bookings(user_id):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')

    query = Booking.query.filter_by(customer_id=user_id)

    if status:
        if status not in BOOKING_STATUSES:
            return jsonify({'error': "Status must be one of: pending, confirmed, cancelled, completed"}), HTTP_400_BAD_REQUEST
        query = query.filter_by(status=status)

    bookings_ = query.order_by(Booking.created_at.desc()).paginate(page=page, per_page=per_page)

    data = [serialize_booking(booking) for booking in bookings_.items]

    meta = {
        "page": bookings_.page,
        "pages": bookings_.pages,
        "total_count": bookings_.total,
        "prev_page": bookings_.prev_num,
        "next_page": bookings_.next_num,
        "has_next": bookings_.has_next,
        "has_prev": bookings_.has_prev
    }

    return jsonify({'data': data, 'meta': meta}), HTTP_200_OK


@bookings.put('/<int:id>')
@bookings.patch('/<int:id>')
@jwt_required()
@swag_from('./docs/bookings/editbooking.yml')
def edit_booking(id):
    current_user = get_jwt_identity()

    booking = Booking.query.filter_by(id=id).first()

    if not booking:
        return jsonify({'error': "Booking not found"}), HTTP_404_NOT_FOUND

    property_ = Property.query.filter_by(id=booking.property_id).first()

    is_owner = property_ is not None and property_.user_id == current_user
    is_customer = booking.customer_id == current_user

    status = request.get_json().get('status', '')

    if status not in BOOKING_STATUSES:
        return jsonify({'error': "Status must be one of: pending, confirmed, cancelled, completed"}), HTTP_400_BAD_REQUEST

    if status == 'confirmed':
        if not is_owner:
            return jsonify({'error': "Only the property owner can confirm a booking"}), HTTP_401_UNAUTHORIZED
        if booking.status == 'cancelled':
            return jsonify({'error': "Cancelled booking cannot be confirmed"}), HTTP_400_BAD_REQUEST
        booking.status = 'confirmed'
        if booking.slot_id:
            slot = Slot.query.filter_by(id=booking.slot_id).first()
            if slot:
                slot.status = 'booked'
                slot.booked_by = booking.customer_id
    elif status == 'completed':
        if not is_owner:
            return jsonify({'error': "Only the property owner can complete a booking"}), HTTP_401_UNAUTHORIZED
        if booking.status != 'confirmed':
            return jsonify({'error': "Only confirmed bookings can be completed"}), HTTP_400_BAD_REQUEST
        booking.status = 'completed'
    elif status == 'cancelled':
        if not (is_owner or is_customer):
            return jsonify({'error': "Unauthorized"}), HTTP_401_UNAUTHORIZED
        booking.status = 'cancelled'
        if booking.slot_id:
            slot = Slot.query.filter_by(id=booking.slot_id).first()
            if slot:
                slot.status = 'available'
                slot.booked_by = None
    elif status == 'pending':
        if not is_owner:
            return jsonify({'error': "Unauthorized"}), HTTP_401_UNAUTHORIZED
        if booking.status not in ('cancelled', 'confirmed'):
            return jsonify({'error': "Booking is already pending"}), HTTP_400_BAD_REQUEST
        booking.status = 'pending'
        if booking.slot_id:
            slot = Slot.query.filter_by(id=booking.slot_id).first()
            if slot:
                slot.status = 'pending'
                slot.booked_by = booking.customer_id

    booking.updated_at = datetime.now()

    db.session.commit()

    return jsonify(serialize_booking(booking)), HTTP_200_OK


@bookings.delete('/<int:id>')
@jwt_required()
@swag_from('./docs/bookings/deletebooking.yml')
def delete_booking(id):
    current_user = get_jwt_identity()

    booking = Booking.query.filter_by(id=id).first()

    if not booking:
        return jsonify({'error': "Booking not found"}), HTTP_404_NOT_FOUND

    property_ = Property.query.filter_by(id=booking.property_id).first()

    if not (booking.customer_id == current_user or (property_ is not None and property_.user_id == current_user)):
        return jsonify({'error': "Unauthorized"}), HTTP_401_UNAUTHORIZED

    if booking.slot_id:
        slot = Slot.query.filter_by(id=booking.slot_id).first()
        if slot:
            slot.status = 'available'
            slot.booked_by = None

    db.session.delete(booking)
    db.session.commit()

    return jsonify({}), HTTP_204_NO_CONTENT

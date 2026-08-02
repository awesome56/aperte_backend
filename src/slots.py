from src.constants.http_status_codes import HTTP_400_BAD_REQUEST
from src.constants.http_status_codes import HTTP_401_UNAUTHORIZED
from src.constants.http_status_codes import HTTP_404_NOT_FOUND
from src.constants.http_status_codes import HTTP_409_CONFLICT
from src.constants.http_status_codes import HTTP_200_OK
from src.constants.http_status_codes import HTTP_201_CREATED
from src.constants.http_status_codes import HTTP_204_NO_CONTENT
from flask import Blueprint, request, jsonify
from src.database import db, Property, Slot
from src.constants.property_meta import SLOT_CATEGORIES, SLOT_STATUSES
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
import re
from flasgger import swag_from


slots = Blueprint("slot", __name__, url_prefix="/api/v1/slots")


def to_float(value, label):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (ValueError, TypeError):
        raise ValueError("{} must be a valid number".format(label))


def parse_date(value, label):
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        raise ValueError("{} must be a valid date (YYYY-MM-DD)".format(label))


def parse_time(value, label):
    if not re.match(r'^\d{2}:\d{2}$', value):
        raise ValueError("{} must be in HH:MM 24-hour format".format(label))
    hours, minutes = int(value[:2]), int(value[3:])
    if hours > 23 or minutes > 59:
        raise ValueError("{} must be in HH:MM 24-hour format".format(label))
    return value


def serialize_slot(slot):
    return {
        'id': slot.id,
        'property_id': slot.property_id,
        'date': slot.date.isoformat(),
        'start_time': slot.start_time,
        'end_time': slot.end_time,
        'price': slot.price,
        'status': slot.status,
        'booked_by': slot.booked_by,
        'created_at': slot.created_at,
        'updated_at': slot.updated_at,
    }


def time_overlaps(start_a, end_a, start_b, end_b):
    return start_a < end_b and end_a > start_b


@slots.post('/property/<int:property_id>')
@jwt_required()
@swag_from('./docs/slots/createslot.yml')
def create_slot(property_id):
    current_user = get_jwt_identity()

    property_ = Property.query.filter_by(id=property_id).first()

    if not property_:
        return jsonify({'error': "Property not found"}), HTTP_404_NOT_FOUND

    if not property_.user_id == current_user:
        return jsonify({'error': "Unauthorized"}), HTTP_401_UNAUTHORIZED

    if property_.category not in SLOT_CATEGORIES:
        return jsonify({'error': "Slots can only be added to hall or event_center properties"}), HTTP_400_BAD_REQUEST

    date = request.get_json().get('date')
    start_time = request.get_json().get('start_time', '')
    end_time = request.get_json().get('end_time', '')
    price = request.get_json().get('price')

    if not date or not start_time or not end_time or price is None:
        return jsonify({'error': "Date, start time, end time and price must not be empty"}), HTTP_400_BAD_REQUEST

    try:
        slot_date = parse_date(date, "Date")
        start_time = parse_time(start_time, "Start time")
        end_time = parse_time(end_time, "End time")
        price = to_float(price, "Price")
    except ValueError as e:
        return jsonify({'error': str(e)}), HTTP_400_BAD_REQUEST

    if start_time >= end_time:
        return jsonify({'error': "End time must be after start time"}), HTTP_400_BAD_REQUEST

    conflict = Slot.query.filter(
        Slot.property_id == property_id,
        Slot.date == slot_date,
        Slot.status.in_(['available', 'pending', 'booked'])
    ).all()

    for existing in conflict:
        if time_overlaps(start_time, end_time, existing.start_time, existing.end_time):
            return jsonify({'error': "Slot overlaps with an existing slot on this date"}), HTTP_409_CONFLICT

    slot = Slot(property_id=property_id, date=slot_date, start_time=start_time, end_time=end_time, price=price, status='available', created_at=datetime.now(), updated_at=datetime.now())

    db.session.add(slot)
    db.session.commit()

    return jsonify(serialize_slot(slot)), HTTP_201_CREATED


@slots.get('/property/<int:property_id>')
@swag_from('./docs/slots/getpropertyslots.yml')
def get_property_slots(property_id):
    if not Property.query.filter_by(id=property_id).first():
        return jsonify({'error': "Property not found"}), HTTP_404_NOT_FOUND

    date = request.args.get('date')
    status = request.args.get('status')

    query = Slot.query.filter_by(property_id=property_id)

    if date:
        try:
            slot_date = parse_date(date, "Date")
        except ValueError as e:
            return jsonify({'error': str(e)}), HTTP_400_BAD_REQUEST
        query = query.filter_by(date=slot_date)

    if status:
        if status not in SLOT_STATUSES:
            return jsonify({'error': "Status must be one of: available, pending, booked"}), HTTP_400_BAD_REQUEST
        query = query.filter_by(status=status)

    slots_ = query.order_by(Slot.date.asc(), Slot.start_time.asc()).all()

    data = [serialize_slot(slot) for slot in slots_]

    return jsonify({'data': data}), HTTP_200_OK


@slots.get('/<int:id>')
@swag_from('./docs/slots/getslot.yml')
def get_slot(id):
    slot = Slot.query.filter_by(id=id).first()

    if not slot:
        return jsonify({'error': "Slot not found"}), HTTP_404_NOT_FOUND

    return jsonify(serialize_slot(slot)), HTTP_200_OK


@slots.put('/<int:id>')
@slots.patch('/<int:id>')
@jwt_required()
@swag_from('./docs/slots/editslot.yml')
def edit_slot(id):
    current_user = get_jwt_identity()

    slot = Slot.query.filter_by(id=id).first()

    if not slot:
        return jsonify({'error': "Slot not found"}), HTTP_404_NOT_FOUND

    property_ = Property.query.filter_by(id=slot.property_id).first()

    if not property_ or not property_.user_id == current_user:
        return jsonify({'error': "Unauthorized"}), HTTP_401_UNAUTHORIZED

    if slot.status in ('pending', 'booked'):
        return jsonify({'error': "Slot cannot be edited while it is pending or booked"}), HTTP_409_CONFLICT

    date = request.get_json().get('date', slot.date)
    start_time = request.get_json().get('start_time', slot.start_time)
    end_time = request.get_json().get('end_time', slot.end_time)
    price = request.get_json().get('price', slot.price)

    try:
        if not isinstance(date, str):
            slot_date = date
        else:
            slot_date = parse_date(date, "Date")
        start_time = parse_time(start_time, "Start time")
        end_time = parse_time(end_time, "End time")
        price = to_float(price, "Price")
    except ValueError as e:
        return jsonify({'error': str(e)}), HTTP_400_BAD_REQUEST

    if start_time >= end_time:
        return jsonify({'error': "End time must be after start time"}), HTTP_400_BAD_REQUEST

    conflict = Slot.query.filter(
        Slot.id != slot.id,
        Slot.property_id == slot.property_id,
        Slot.date == slot_date,
        Slot.status.in_(['available', 'pending', 'booked'])
    ).all()

    for existing in conflict:
        if time_overlaps(start_time, end_time, existing.start_time, existing.end_time):
            return jsonify({'error': "Slot overlaps with an existing slot on this date"}), HTTP_409_CONFLICT

    slot.date = slot_date
    slot.start_time = start_time
    slot.end_time = end_time
    slot.price = price
    slot.updated_at = datetime.now()

    db.session.commit()

    return jsonify(serialize_slot(slot)), HTTP_200_OK


@slots.delete('/<int:id>')
@jwt_required()
@swag_from('./docs/slots/deleteslot.yml')
def delete_slot(id):
    current_user = get_jwt_identity()

    slot = Slot.query.filter_by(id=id).first()

    if not slot:
        return jsonify({'error': "Slot not found"}), HTTP_404_NOT_FOUND

    property_ = Property.query.filter_by(id=slot.property_id).first()

    if not property_ or not property_.user_id == current_user:
        return jsonify({'error': "Unauthorized"}), HTTP_401_UNAUTHORIZED

    if slot.status in ('pending', 'booked'):
        return jsonify({'error': "Slot cannot be deleted while it is pending or booked"}), HTTP_409_CONFLICT

    db.session.delete(slot)
    db.session.commit()

    return jsonify({}), HTTP_204_NO_CONTENT

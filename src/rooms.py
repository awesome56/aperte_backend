from src.constants.http_status_codes import HTTP_400_BAD_REQUEST
from src.constants.http_status_codes import HTTP_401_UNAUTHORIZED
from src.constants.http_status_codes import HTTP_404_NOT_FOUND
from src.constants.http_status_codes import HTTP_409_CONFLICT
from src.constants.http_status_codes import HTTP_200_OK
from src.constants.http_status_codes import HTTP_201_CREATED
from src.constants.http_status_codes import HTTP_204_NO_CONTENT
from flask import Blueprint, request, jsonify
from src.database import db, Property, Room, RoomImage, Booking
from src.constants.property_meta import ROOM_CATEGORIES
from src.constants.storage import upload_file, delete_file
from src.constants.http_status_codes import HTTP_500_INTERNAL_SERVER_ERROR
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
import json
from flasgger import swag_from


rooms = Blueprint("room", __name__, url_prefix="/api/v1/rooms")


def to_float(value, label):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (ValueError, TypeError):
        raise ValueError("{} must be a valid number".format(label))


def to_int(value, label):
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (ValueError, TypeError):
        raise ValueError("{} must be an whole number".format(label))


def serialize_room(room):
    room_images = RoomImage.query.filter_by(room_id=room.id)
    images = []
    for img in room_images:
        images.append({
            'id': img.id,
            'image_url': img.image_url,
            'dp': img.dp,
            'created_at': img.created_at,
            'updated_at': img.updated_at,
        })

    return {
        'id': room.id,
        'property_id': room.property_id,
        'room_type': room.room_type,
        'beds': room.beds,
        'price': room.price,
        'amenities': json.loads(room.amenities) if room.amenities else {},
        'available': room.available,
        'images': images,
        'created_at': room.created_at,
        'updated_at': room.updated_at,
    }


def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'heif', 'png', 'jpg', 'jpeg'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def allowed_file_size(file):
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    return len(file.read()) <= MAX_CONTENT_LENGTH


def has_active_bookings(room_id):
    return Booking.query.filter(
        Booking.room_id == room_id,
        Booking.status.in_(['pending', 'confirmed'])
    ).first() is not None


@rooms.post('/property/<int:property_id>')
@jwt_required()
@swag_from('./docs/rooms/createroom.yml')
def create_room(property_id):
    current_user = get_jwt_identity()

    property_ = Property.query.filter_by(id=property_id).first()

    if not property_:
        return jsonify({'error': "Property not found"}), HTTP_404_NOT_FOUND

    if not property_.user_id == current_user:
        return jsonify({'error': "Unauthorized"}), HTTP_401_UNAUTHORIZED

    if property_.category not in ROOM_CATEGORIES:
        return jsonify({'error': "Rooms can only be added to hotel properties"}), HTTP_400_BAD_REQUEST

    room_type = request.get_json().get('room_type', '')
    beds = request.get_json().get('beds', 1)
    price = request.get_json().get('price')
    amenities = request.get_json().get('amenities')
    available = request.get_json().get('available', 1)

    if not room_type or price is None:
        return jsonify({'error': "Room type and price must not be empty"}), HTTP_400_BAD_REQUEST

    if len(room_type) < 2:
        return jsonify({'error': "Room type must be more than 1 character"}), HTTP_400_BAD_REQUEST

    try:
        beds = to_int(beds, "Beds")
        price = to_float(price, "Price")
    except ValueError as e:
        return jsonify({'error': str(e)}), HTTP_400_BAD_REQUEST

    if beds is not None and beds < 1:
        return jsonify({'error': "Beds must be at least 1"}), HTTP_400_BAD_REQUEST

    if isinstance(amenities, dict):
        amenities_str = json.dumps(amenities)
    else:
        return jsonify({'error': "Amenities must be in json format"}), HTTP_400_BAD_REQUEST

    if isinstance(available, int) and (available == 0 or available == 1):
        pass
    else:
        return jsonify({'error': "Available must be either 0 or 1"}), HTTP_400_BAD_REQUEST

    room = Room(property_id=property_id, room_type=room_type, beds=beds, price=price, amenities=amenities_str, available=available, created_at=datetime.now(), updated_at=datetime.now())

    db.session.add(room)
    db.session.commit()

    return jsonify(serialize_room(room)), HTTP_201_CREATED


@rooms.get('/property/<int:property_id>')
@swag_from('./docs/rooms/getpropertyrooms.yml')
def get_property_rooms(property_id):
    if not Property.query.filter_by(id=property_id).first():
        return jsonify({'error': "Property not found"}), HTTP_404_NOT_FOUND

    rooms_ = Room.query.filter_by(property_id=property_id).order_by(Room.created_at.asc()).all()

    data = [serialize_room(room) for room in rooms_]

    return jsonify({'data': data}), HTTP_200_OK


@rooms.get('/<int:id>')
@swag_from('./docs/rooms/getroom.yml')
def get_room(id):
    room = Room.query.filter_by(id=id).first()

    if not room:
        return jsonify({'error': "Room not found"}), HTTP_404_NOT_FOUND

    return jsonify(serialize_room(room)), HTTP_200_OK


@rooms.put('/<int:id>')
@rooms.patch('/<int:id>')
@jwt_required()
@swag_from('./docs/rooms/editroom.yml')
def edit_room(id):
    current_user = get_jwt_identity()

    room = Room.query.filter_by(id=id).first()

    if not room:
        return jsonify({'error': "Room not found"}), HTTP_404_NOT_FOUND

    property_ = Property.query.filter_by(id=room.property_id).first()

    if not property_ or not property_.user_id == current_user:
        return jsonify({'error': "Unauthorized"}), HTTP_401_UNAUTHORIZED

    room_type = request.get_json().get('room_type', room.room_type)
    beds = request.get_json().get('beds', room.beds)
    price = request.get_json().get('price', room.price)
    amenities = request.get_json().get('amenities', json.loads(room.amenities) if room.amenities else {})
    available = request.get_json().get('available', room.available)

    if not room_type or price is None:
        return jsonify({'error': "Room type and price must not be empty"}), HTTP_400_BAD_REQUEST

    if len(room_type) < 2:
        return jsonify({'error': "Room type must be more than 1 character"}), HTTP_400_BAD_REQUEST

    try:
        beds = to_int(beds, "Beds")
        price = to_float(price, "Price")
    except ValueError as e:
        return jsonify({'error': str(e)}), HTTP_400_BAD_REQUEST

    if beds is not None and beds < 1:
        return jsonify({'error': "Beds must be at least 1"}), HTTP_400_BAD_REQUEST

    if isinstance(amenities, dict):
        amenities_str = json.dumps(amenities)
    else:
        return jsonify({'error': "Amenities must be in json format"}), HTTP_400_BAD_REQUEST

    if isinstance(available, int) and (available == 0 or available == 1):
        pass
    else:
        return jsonify({'error': "Available must be either 0 or 1"}), HTTP_400_BAD_REQUEST

    room.room_type = room_type
    room.beds = beds
    room.price = price
    room.amenities = amenities_str
    room.available = available
    room.updated_at = datetime.now()

    db.session.commit()

    return jsonify(serialize_room(room)), HTTP_200_OK


@rooms.delete('/<int:id>')
@jwt_required()
@swag_from('./docs/rooms/deleteroom.yml')
def delete_room(id):
    current_user = get_jwt_identity()

    room = Room.query.filter_by(id=id).first()

    if not room:
        return jsonify({'error': "Room not found"}), HTTP_404_NOT_FOUND

    property_ = Property.query.filter_by(id=room.property_id).first()

    if not property_ or not property_.user_id == current_user:
        return jsonify({'error': "Unauthorized"}), HTTP_401_UNAUTHORIZED

    if has_active_bookings(room.id):
        return jsonify({'error': "Room cannot be deleted while it has pending or confirmed bookings"}), HTTP_409_CONFLICT

    db.session.delete(room)
    db.session.commit()

    return jsonify({}), HTTP_204_NO_CONTENT


@rooms.post('/<int:id>/images')
@jwt_required()
@swag_from('./docs/rooms/addroomimage.yml')
def add_room_images(id):
    current_user = get_jwt_identity()

    room = Room.query.filter_by(id=id).first()
    if not room:
        return jsonify({'error': "Room not found"}), HTTP_404_NOT_FOUND

    property_ = Property.query.filter_by(id=room.property_id).first()
    if not property_ or not property_.user_id == current_user:
        return jsonify({'error': "Unauthorized"}), HTTP_401_UNAUTHORIZED

    files = request.files.getlist('file')
    if not files:
        return jsonify({'error': "No file added"}), HTTP_400_BAD_REQUEST

    if len(files) > 3:
        return jsonify({'error': "Maximum of 3 images per room"}), HTTP_400_BAD_REQUEST

    current_count = RoomImage.query.filter_by(room_id=room.id).count()
    if current_count + len(files) > 3:
        return jsonify({'error': "Room can only have a maximum of 3 images"}), HTTP_400_BAD_REQUEST

    for file in files:
        if file:
            if not allowed_file(file.filename):
                return jsonify({'error': "Invalid file extension"}), HTTP_400_BAD_REQUEST
            if not allowed_file_size(file):
                return jsonify({'error': "File size is too large"}), HTTP_400_BAD_REQUEST
            file.seek(0)

    dp_exists = RoomImage.query.filter_by(room_id=room.id, dp=1).first() is not None
    attachments = []

    for idx, file in enumerate(files):
        file.seek(0)
        dp_value = 1 if idx == 0 and not dp_exists else 0
        try:
            image_url = upload_file(file, 'properties/{}/rooms/{}/images'.format(current_user, room.id))
        except Exception as e:
            return jsonify({'error': str(e)}), HTTP_500_INTERNAL_SERVER_ERROR

        room_image = RoomImage(room_id=room.id, image_url=image_url, dp=dp_value, created_at=datetime.now(), updated_at=datetime.now())
        db.session.add(room_image)
        db.session.commit()

        attachments.append({
            'id': room_image.id,
            'image_url': room_image.image_url,
            'dp': room_image.dp,
            'created_at': room_image.created_at,
            'updated_at': room_image.updated_at,
        })

    return jsonify(attachments), HTTP_201_CREATED


@rooms.delete('/images/<int:id>')
@jwt_required()
@swag_from('./docs/rooms/deleteroomimage.yml')
def delete_room_image(id):
    current_user = get_jwt_identity()

    room_image = RoomImage.query.filter_by(id=id).first()
    if not room_image:
        return jsonify({'error': "Image not found"}), HTTP_404_NOT_FOUND

    room = Room.query.filter_by(id=room_image.room_id).first()
    property_ = Property.query.filter_by(id=room.property_id).first()
    if not property_ or not property_.user_id == current_user:
        return jsonify({'error': "Unauthorized"}), HTTP_401_UNAUTHORIZED

    oldfile = room_image.image_url
    db.session.delete(room_image)
    db.session.commit()

    try:
        delete_file(oldfile)
    except Exception as e:
        return jsonify({'error': str(e)}), HTTP_500_INTERNAL_SERVER_ERROR

    return jsonify({}), HTTP_204_NO_CONTENT


@rooms.put('/images/<int:id>/dp')
@rooms.patch('/images/<int:id>/dp')
@jwt_required()
@swag_from('./docs/rooms/setroomimage_dp.yml')
def set_room_image_dp(id):
    current_user = get_jwt_identity()

    room_image = RoomImage.query.filter_by(id=id).first()
    if not room_image:
        return jsonify({'error': "Image not found"}), HTTP_404_NOT_FOUND

    room = Room.query.filter_by(id=room_image.room_id).first()
    property_ = Property.query.filter_by(id=room.property_id).first()
    if not property_ or not property_.user_id == current_user:
        return jsonify({'error': "Unauthorized"}), HTTP_401_UNAUTHORIZED

    RoomImage.query.filter_by(room_id=room.id, dp=1).update({'dp': 0})
    room_image.dp = 1
    db.session.commit()

    return jsonify({
        'id': room_image.id,
        'image_url': room_image.image_url,
        'dp': room_image.dp,
    }), HTTP_200_OK

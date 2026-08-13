from src.constants.http_status_codes import HTTP_400_BAD_REQUEST
from src.constants.http_status_codes import HTTP_401_UNAUTHORIZED
from src.constants.http_status_codes import HTTP_404_NOT_FOUND
from src.constants.http_status_codes import HTTP_409_CONFLICT
from src.constants.http_status_codes import HTTP_200_OK
from src.constants.http_status_codes import HTTP_201_CREATED
from src.constants.http_status_codes import HTTP_202_ACCEPTED
from src.constants.http_status_codes import HTTP_204_NO_CONTENT
from src.constants.http_status_codes import HTTP_500_INTERNAL_SERVER_ERROR
from flask import Blueprint, request
from src.database import User, Property, Message, PropertyImage, PropertyVideo, Request, Review, Favorite, PropertyClaim, db
from flask import Blueprint, request, jsonify
from src.constants.functions import adjust_url
from src.constants.property_meta import is_valid_category, is_valid_purpose
from src.constants.storage import upload_file, delete_file
import validators
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import json
from sqlalchemy import func
from flasgger import swag_from


properties = Blueprint("property", __name__, url_prefix="/api/v1/properties")


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


def serialize_property(property):
    property_images = PropertyImage.query.filter_by(property_id=property.id)
    attachments = []
    for property_image in property_images:
        attachments.append({
            'id': property_image.id,
            'image_url': property_image.image_url,
            'dp': property_image.dp,
            'created_at': property_image.created_at,
            'updated_at': property_image.updated_at,
        })

    property_videos = PropertyVideo.query.filter_by(property_id=property.id)
    videos = []
    for property_video in property_videos:
        videos.append({
            'id': property_video.id,
            'video_url': property_video.video_url,
            'created_at': property_video.created_at,
            'updated_at': property_video.updated_at,
        })

    average_rating = db.session.query(func.avg(Review.rating)).filter(Review.property_id == property.id).scalar()

    user = User.query.filter_by(id=property.user_id).first()

    return {
        'id': property.id,
        'user_id': property.user_id,
        'title': property.title,
        'description': property.description,
        'category': property.category,
        'property_type': property.property_type,
        'purpose': property.purpose,
        'attributes': json.loads(property.attributes) if property.attributes else {},
        'price': property.price,
        'currency': property.currency,
        'area': property.area,
        'bedrooms': property.bedrooms,
        'bathrooms': property.bathrooms,
        'location': property.location,
        'city': property.city,
        'state': property.state,
        'country': property.country,
        'latitude': property.latitude,
        'logitude': property.longitude,
        'year_built': property.year_built,
        'amenities': json.loads(property.amenities) if property.amenities else {},
        'images': attachments,
        'videos': videos,
        'negotiable': property.negotiable,
        'available': property.available,
        'approved': property.approved,
        'disabled': property.disabled,
        'views': property.views,
        'favorites_count': Favorite.query.filter_by(property_id=property.id).count(),
        'created_at': property.created_at,
        'updated_at': property.updated_at,
        'average_rating': average_rating,
        'username': user.username,
        'owner_full_name': user.full_name,
        'owner_email': user.email,
        'owner_phone_number': user.phone_number,
        'owner_is_admin': user.role == 'admin',
        'contact_phone': property.contact_phone,
        'contact_email': property.contact_email,
        'contact_website': property.contact_website,
        'contact_phones': json.loads(property.contact_phones) if property.contact_phones else [],
        'contact_emails': json.loads(property.contact_emails) if property.contact_emails else [],
    }


@properties.post("/")
@jwt_required()
@swag_from('./docs/properties/createproperty.yml')
def create_property():
    current_user = get_jwt_identity()

    title = request.get_json().get('title','')
    description = request.get_json().get('description','')
    category = request.get_json().get('category', 'property')
    property_type = request.get_json().get('property_type','')
    purpose = request.get_json().get('purpose', 'rent')
    attributes = request.get_json().get('attributes')
    price = request.get_json().get('price')
    currency = request.get_json().get('currency', 'USD')
    area = request.get_json().get('area')
    bedrooms = request.get_json().get('bedrooms')
    bathrooms = request.get_json().get('bathrooms')
    location = request.get_json().get('location','')
    city = request.get_json().get('city','')
    state = request.get_json().get('state','')
    country = request.get_json().get('country','')
    latitude = request.get_json().get('latitude')
    longitude = request.get_json().get('longitude')
    year_built = request.get_json().get('year_built')
    contact_phone = request.get_json().get('contact_phone')
    contact_email = request.get_json().get('contact_email')
    contact_website = request.get_json().get('contact_website')
    contact_phones = request.get_json().get('contact_phones') or []
    contact_emails = request.get_json().get('contact_emails') or []
    amenities = request.get_json().get('amenities')
    negotiable = request.get_json().get('negotiable', 0)

    if not title or not description or not property_type or price is None or not location or not city or not state or not country:
        return jsonify({'error': "Property title, description, property type, price, location, city, state, country must not be empty"}), HTTP_400_BAD_REQUEST 
    
    if not is_valid_category(category):
        return jsonify({'error': "Category must be one of: property, land, hotel, hall, event_center, shortlet, other"}), HTTP_400_BAD_REQUEST
    
    if not is_valid_purpose(purpose):
        return jsonify({'error': "Purpose must be one of: rent, sale, both"}), HTTP_400_BAD_REQUEST
    
    if attributes is not None and not isinstance(attributes, dict):
        return jsonify({'error': "Attributes must be in json format"}), HTTP_400_BAD_REQUEST
    
    if len(title) < 3:
        return jsonify({'error': "Property title must be more than 2 characters"}), HTTP_400_BAD_REQUEST
    
    if Property.query.filter_by(user_id=current_user, title=title).first():
        return jsonify({'error': "Property title already exists for user"}), HTTP_409_CONFLICT
    
    if len(description) < 3:
        return jsonify({'error': "Property description must be more than 2 characters"}), HTTP_400_BAD_REQUEST
    
    if isinstance(price, (int, float)):
        # price is already a number (integer or float)
        pass
    else:
        # price is a string, let's try to convert it to a number
        try:
            price = float(price)
        except ValueError:
            return jsonify({'error': "Price must be a valid number"}), HTTP_400_BAD_REQUEST
        
    try:
        area = to_float(area, "Area")
        bedrooms = to_int(bedrooms, "Bedroom")
        bathrooms = to_int(bathrooms, "Bathroom")
        latitude = to_float(latitude, "Latitude")
        longitude = to_float(longitude, "Longitude")
        year_built = to_int(year_built, "Year built")
    except ValueError as e:
        return jsonify({'error': str(e)}), HTTP_400_BAD_REQUEST

    if isinstance(negotiable, int) and (negotiable == 0 or negotiable == 1):
        # year_built is an integer
        pass
    else:
        return jsonify({'error': "Negotiable must be either 0 or 1"}), HTTP_400_BAD_REQUEST
        
    if isinstance(amenities, dict):
        # amenities is a JSON object (dictionary)
        # Convert amenities to a JSON string
        amenities_str = json.dumps(amenities)
        # amenities_str = str(amenities)
    else:
        return jsonify({'error': "Amenities must be in json format"}), HTTP_400_BAD_REQUEST

    attributes_str = json.dumps(attributes) if attributes else None
    
    property = Property(user_id=current_user, title=title, description=description, category=category, property_type=property_type, purpose=purpose, attributes=attributes_str, price=price, currency=currency, area=area, bedrooms=bedrooms, bathrooms=bathrooms, location=location, city=city, state=state, country=country, negotiable=negotiable, latitude=latitude, longitude=longitude, year_built=year_built, amenities=amenities_str, contact_phone=contact_phone, contact_email=contact_email, contact_website=contact_website, contact_phones=json.dumps(contact_phones) if contact_phones else None, contact_emails=json.dumps(contact_emails) if contact_emails else None, created_at=datetime.now(), updated_at=datetime.now())

    db.session.add(property)
    db.session.commit()

    return jsonify(serialize_property(property)), HTTP_201_CREATED


@properties.post('/images/<int:id>')
@jwt_required()
@swag_from('./docs/properties/addpropertyimage.yml')
def add_property_image(id):
    current_user = get_jwt_identity()

    property = Property.query.filter_by(id=id).first()

    if not property:
        return jsonify({'error': "Property not found"}), HTTP_404_NOT_FOUND
    
    if not property.user_id == current_user:
        return jsonify({'error': "Unathorized"}), HTTP_401_UNAUTHORIZED

    files = request.files.getlist('file')

    if not files:
        return jsonify({'error': "No file added"}),HTTP_400_BAD_REQUEST

    if len(files) > 5:
        return jsonify({'error': "Maximum of 5 images per property"}), HTTP_400_BAD_REQUEST

    current_count = PropertyImage.query.filter_by(property_id=property.id).count()

    if current_count + len(files) > 5:
        return jsonify({'error': "Property can only have a maximum of 5 images"}), HTTP_400_BAD_REQUEST

    for file in files:
        if file:
            # Check the file extension
            if not allowed_file(file.filename):
                return jsonify({'error': "Invalid file extension"}), HTTP_400_BAD_REQUEST

            # Check the file size
            if not allowed_file_size(file):
                return jsonify({'error': "File size is too large"}), HTTP_400_BAD_REQUEST
            
            # Reset the pointer to the beginning of the file
            file.seek(0)
    attachments = []

    # Check if any row with property_id and dp=1 exists
    dp_exists = PropertyImage.query.filter_by(property_id=property.id, dp=1).first() is not None

    for idx, file in enumerate(files):

        file_size = len(file.read())
        file.seek(0)

        # dp_value = 1 if idx == 0 else 0
        # Set dp=1 for the first image if no dp=1 row exists in the database, otherwise set dp=0 for all
        dp_value = 1 if idx == 0 and not dp_exists else 0

        try:
            image_url = upload_file(file, 'properties/{}/images'.format(current_user))
        except Exception as e:
            return jsonify({'error': str(e)}), HTTP_500_INTERNAL_SERVER_ERROR

        property_image = PropertyImage(property_id= property.id, image_url=image_url, dp=dp_value, created_at=datetime.now(), updated_at=datetime.now())
        db.session.add(property_image)
        db.session.commit()

        attachments.append({
            'id': property_image.id,
            'image_url': property_image.image_url,
            'dp': property_image.dp,
            'created_at' : property_image.created_at,
            'updated_at' : property_image.updated_at,
        })

    return jsonify(attachments), HTTP_201_CREATED

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'heif', 'png', 'jpg', 'jpeg'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_file_size(file):
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    return len(file.read()) <= MAX_CONTENT_LENGTH


@properties.route('/images/<int:id>', methods=['DELETE'])
@jwt_required()
@swag_from('./docs/properties/deletepropertyimage.yml')
def delete_image(id):
    current_user = get_jwt_identity()

    property_image = PropertyImage.query.filter_by(id=id).first()
    if not property_image:
        return jsonify({'message': "Image not found"}), HTTP_404_NOT_FOUND
    
    property = Property.query.filter_by(id=property_image.property_id).first()
    if not property.user_id == current_user:
        return jsonify({'error': "Unauthorized"}), HTTP_401_UNAUTHORIZED

    oldfile = property_image.image_url

    db.session.delete(property_image)
    db.session.commit()

    try:
        delete_file(oldfile)
    except Exception as e:
        return jsonify({'error': str(e)}), HTTP_500_INTERNAL_SERVER_ERROR

    return jsonify({}), HTTP_204_NO_CONTENT


@properties.put('/images/<int:id>/dp')
@properties.patch('/images/<int:id>/dp')
@jwt_required()
@swag_from('./docs/properties/setpropertyimage_dp.yml')
def set_property_image_dp(id):
    current_user = get_jwt_identity()

    property_image = PropertyImage.query.filter_by(id=id).first()
    if not property_image:
        return jsonify({'error': "Image not found"}), HTTP_404_NOT_FOUND

    property = Property.query.filter_by(id=property_image.property_id).first()
    if not property.user_id == current_user:
        return jsonify({'error': "Unauthorized"}), HTTP_401_UNAUTHORIZED

    # Clear existing dp flags for this property, then set this image as the display picture.
    PropertyImage.query.filter_by(property_id=property.id, dp=1).update({'dp': 0})
    property_image.dp = 1
    db.session.commit()

    return jsonify({
        'id': property_image.id,
        'image_url': property_image.image_url,
        'dp': property_image.dp,
    }), HTTP_200_OK


@properties.post('/videos/<int:id>')
@jwt_required()
@swag_from('./docs/properties/addpropertyvideo.yml')
def add_property_video(id):
    current_user = get_jwt_identity()

    property = Property.query.filter_by(id=id).first()

    if not property:
        return jsonify({'error': "Property not found"}), HTTP_404_NOT_FOUND
    
    if not property.user_id == current_user:
        return jsonify({'error': "Unathorized"}), HTTP_401_UNAUTHORIZED

    files = request.files.getlist('file')

    if not files:
        return jsonify({'error': "No file added"}),HTTP_400_BAD_REQUEST

    for file in files:
        if file:
            if not allowed_video_file(file.filename):
                return jsonify({'error': "Invalid file extension"}), HTTP_400_BAD_REQUEST

            if not allowed_video_file_size(file):
                return jsonify({'error': "File size is too large"}), HTTP_400_BAD_REQUEST
            
            file.seek(0)

    attachments = []

    for idx, file in enumerate(files):

        file_size = len(file.read())
        file.seek(0)

        try:
            video_url = upload_file(file, 'properties/{}/videos'.format(current_user))
        except Exception as e:
            return jsonify({'error': str(e)}), HTTP_500_INTERNAL_SERVER_ERROR

        property_video = PropertyVideo(property_id=property.id, video_url=video_url, created_at=datetime.now(), updated_at=datetime.now())
        db.session.add(property_video)
        db.session.commit()

        attachments.append({
            'id': property_video.id,
            'video_url': property_video.video_url,
            'created_at': property_video.created_at,
            'updated_at': property_video.updated_at,
        })

    return jsonify(attachments), HTTP_201_CREATED


def allowed_video_file(filename):
    ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'mov', 'm4v', 'webm', 'avi', 'mkv'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_VIDEO_EXTENSIONS


def allowed_video_file_size(file):
    MAX_VIDEO_CONTENT_LENGTH = 100 * 1024 * 1024
    return len(file.read()) <= MAX_VIDEO_CONTENT_LENGTH


@properties.route('/videos/<int:id>', methods=['DELETE'])
@jwt_required()
@swag_from('./docs/properties/deletepropertyvideo.yml')
def delete_video(id):
    current_user = get_jwt_identity()

    property_video = PropertyVideo.query.filter_by(id=id).first()
    if not property_video:
        return jsonify({'message': "Video not found"}), HTTP_404_NOT_FOUND
    
    property = Property.query.filter_by(id=property_video.property_id).first()
    if not property.user_id == current_user:
        return jsonify({'error': "Unauthorized"}), HTTP_401_UNAUTHORIZED

    oldfile = property_video.video_url

    db.session.delete(property_video)
    db.session.commit()

    try:
        delete_file(oldfile)
    except Exception as e:
        return jsonify({'error': str(e)}), HTTP_500_INTERNAL_SERVER_ERROR

    return jsonify({}), HTTP_204_NO_CONTENT


@properties.get("/analytics/mine")
@jwt_required()
def my_analytics():
    """Personal analytics for the current user's listings and requests."""
    me = get_jwt_identity()

    from src.database import Booking, Request, Message

    props = Property.query.filter_by(user_id=me).all()

    per_property = []
    total_views = 0
    total_favorites = 0
    for p in props:
        dp = PropertyImage.query.filter_by(property_id=p.id, dp=1).first()
        bookings = Booking.query.filter_by(property_id=p.id).all()
        b_counts = {'total': len(bookings), 'pending': 0, 'confirmed': 0, 'completed': 0, 'cancelled': 0}
        for b in bookings:
            if b.status in b_counts:
                b_counts[b.status] += 1
        total_views += p.views or 0
        total_favorites += Favorite.query.filter_by(property_id=p.id).count()
        per_property.append({
            'id': p.id,
            'title': p.title,
            'dp': dp.image_url if dp else "",
            'views': p.views or 0,
            'favorites': Favorite.query.filter_by(property_id=p.id).count(),
            'bookings': b_counts,
            'created_at': p.created_at,
        })

    reqs = Request.query.filter_by(user_id=me).all()
    requests_out = []
    for r in reqs:
        responses = Message.query.filter(
            Message.request_id == r.id, Message.receiver_id == me
        ).count()
        requests_out.append({
            'id': r.id,
            'title': r.title,
            'responses': responses,
            'created_at': r.created_at,
        })

    return jsonify({
        'totals': {
            'properties': len(props),
            'views': total_views,
            'favorites': total_favorites,
            'requests': len(reqs),
            'request_responses': sum(r['responses'] for r in requests_out),
            'messages_received': Message.query.filter(Message.receiver_id == me).count(),
            'messages_sent': Message.query.filter(Message.sender_id == me).count(),
        },
        'properties': per_property,
        'requests': requests_out,
    }), HTTP_200_OK


@properties.get("/<int:id>/stats")
@jwt_required()
def property_stats(id):
    """Owner-only management stats for a single property."""
    me = get_jwt_identity()

    from src.database import Booking, Room, Slot, Review

    property_ = Property.query.filter_by(id=id).first()
    if not property_:
        return jsonify({'error': "Property not found"}), HTTP_404_NOT_FOUND

    if property_.user_id != me:
        admin_check = User.query.filter_by(id=me).first()
        if not admin_check or admin_check.role != 'admin':
            return jsonify({'error': "Only the property owner can view stats"}), HTTP_404_NOT_FOUND

    bookings = Booking.query.filter_by(property_id=id).all()
    b_counts = {'total': len(bookings), 'pending': 0, 'confirmed': 0, 'completed': 0, 'cancelled': 0}
    revenue = 0
    for b in bookings:
        if b.status in b_counts:
            b_counts[b.status] += 1
        if b.status in ('confirmed', 'completed'):
            revenue += b.total or 0

    dp = PropertyImage.query.filter_by(property_id=id, dp=1).first()

    rooms = []
    if property_.category == 'hotel':
        for r in Room.query.filter_by(property_id=id).all():
            room_bookings = [b for b in bookings if b.room_id == r.id]
            room_revenue = sum((b.total or 0) for b in room_bookings if b.status in ('confirmed', 'completed'))
            rooms.append({
                'id': r.id,
                'room_type': r.room_type,
                'beds': r.beds,
                'price': r.price,
                'available': r.available,
                'bookings': len(room_bookings),
                'active_bookings': len([b for b in room_bookings if b.status in ('pending', 'confirmed')]),
                'revenue': room_revenue,
            })

    slot_count = Slot.query.filter_by(property_id=id).count() if property_.category in ('hall', 'event_center') else 0

    reviews = []
    for rv in Review.query.filter_by(property_id=id).order_by(Review.created_at.desc()).limit(50).all():
        u = User.query.filter_by(id=rv.user_id).first()
        reviews.append({
            'id': rv.id,
            'user_id': rv.user_id,
            'username': u.username if u else None,
            'full_name': u.full_name if u else None,
            'rating': rv.rating,
            'title': rv.title,
            'content': rv.content,
            'created_at': rv.created_at,
        })

    avg_rating = db.session.query(func.avg(Review.rating)).filter(Review.property_id == id).scalar()

    return jsonify({
        'property': {
            'id': property_.id,
            'title': property_.title,
            'category': property_.category,
            'approved': property_.approved,
            'available': property_.available,
            'disabled': property_.disabled,
            'views': property_.views or 0,
            'favorites': Favorite.query.filter_by(property_id=id).count(),
            'dp': dp.image_url if dp else "",
            'created_at': property_.created_at,
        },
        'bookings': b_counts,
        'revenue': revenue,
        'rooms': rooms,
        'slot_count': slot_count,
        'reviews': reviews,
        'average_rating': avg_rating,
        'review_count': len(reviews),
    }), HTTP_200_OK


@properties.get("/<int:id>")
@jwt_required(optional=True)
@swag_from('./docs/properties/getproperty.yml')
def get_property(id):

    property = Property.query.filter_by(id=id).first()

    if not property:
        return jsonify({'message': "Property not found"}),HTTP_404_NOT_FOUND

    # disabled listings are hidden from the site (owner/admin can still view)
    if property.disabled:
        viewer = get_jwt_identity()
        if viewer is None or (viewer != property.user_id and User.query.filter_by(id=viewer).first().role != 'admin'):
            return jsonify({'message': "Property not found"}),HTTP_404_NOT_FOUND

    property.views = (property.views or 0) + 1

    # Record a server-side analytics pageview for this property so property
    # analytics work even if client-side tracking is blocked/disabled.
    try:
        from src.tracking import ingest_batch
        visitor_id = request.headers.get('X-Visitor-Id') or 'anonymous'
        session_id = request.headers.get('X-Session-Id') or visitor_id
        item = {
            'type': 'pageview',
            'session_id': session_id,
            'visitor_id': visitor_id,
            'path': '/properties/{}'.format(property.id),
            'title': property.title,
            'referrer': request.headers.get('Referer') or '',
            'property_id': property.id,
            'screen_size': request.headers.get('X-Screen-Size'),
        }
        ingest_batch([item], request.headers.get('User-Agent', ''), request.headers.get('CF-IPCountry'), get_jwt_identity())
    except Exception:
        db.session.rollback()
        property.views = (property.views or 0) + 1
        db.session.commit()

    data = serialize_property(property)

    # claim status for the current user (optional auth)
    current_user = get_jwt_identity()
    if current_user is not None:
        claim = PropertyClaim.query.filter_by(
            property_id=property.id, user_id=current_user
        ).order_by(PropertyClaim.created_at.desc()).first()
        data['claim_status'] = claim.status if claim else None

    return jsonify(data), HTTP_200_OK


@properties.post("/<int:id>/claim")
@jwt_required()
def claim_property(id):
    current_user = get_jwt_identity()

    property = Property.query.filter_by(id=id).first()

    if not property:
        return jsonify({'error': "Property not found"}), HTTP_404_NOT_FOUND

    owner = User.query.filter_by(id=property.user_id).first()
    if not owner or owner.role != 'admin':
        return jsonify({'error': "This property is not claimable"}), HTTP_400_BAD_REQUEST

    if property.user_id == current_user:
        return jsonify({'error': "You already own this property"}), HTTP_400_BAD_REQUEST

    # one pending claim at a time keeps things clean
    existing_pending = PropertyClaim.query.filter(
        PropertyClaim.property_id == id,
        PropertyClaim.status.in_(('pending_verification', 'pending')),
    ).first()
    if existing_pending:
        return jsonify({'error': "A claim for this property is already in progress"}), HTTP_400_BAD_REQUEST

    mine = PropertyClaim.query.filter_by(property_id=id, user_id=current_user).first()
    if mine:
        if mine.status == 'approved':
            return jsonify({'error': "You already own this property"}), HTTP_400_BAD_REQUEST
        if mine.status == 'rejected':
            # allow a rejected user to try again — restarts the process
            mine.status = None
            mine.updated_at = datetime.now()
            claim = mine
            db.session.commit()
        else:
            return jsonify({'error': "A claim for this property is already in progress"}), HTTP_400_BAD_REQUEST
    else:
        claim = PropertyClaim(
            property_id=id,
            user_id=current_user,
            status=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db.session.add(claim)
        db.session.flush()

    # ---- verification method (claimant's choice) ----
    # 'email'    -> verify ownership with a code sent to the claimant's email
    # 'document' -> upload supporting documents, reviewed by the admin
    # 'phone'    -> reserved for future phone/SMS verification
    if request.files and 'document' in request.files:
        method = 'document'
    else:
        data = request.get_json(silent=True) or {}
        method = (data.get('method') or 'email').lower()

    if method not in ('email', 'document'):
        db.session.delete(claim)
        db.session.commit()
        return jsonify({'error': "Verification method must be 'email' or 'document'"}), HTTP_400_BAD_REQUEST

    if method == 'email':
        claim.status = 'pending_verification'
        claim.updated_at = datetime.now()
        db.session.commit()

        claimant = User.query.filter_by(id=current_user).first()
        target_email = claimant.email if claimant else None
        if not target_email:
            db.session.delete(claim)
            db.session.commit()
            return jsonify({'error': "No email on your account to verify with"}), HTTP_400_BAD_REQUEST

        _send_claim_code(claim, property, target_email)

        return jsonify({
            'message': "Claim started — a verification code was sent to {}".format(target_email),
            'claim': {'id': claim.id, 'status': claim.status},
            'verification_email': target_email,
        }), HTTP_201_CREATED

    # ---- document submission path ----
    file = request.files.get('document')
    if not file or not file.filename:
        db.session.delete(claim)
        db.session.commit()
        return jsonify({'error': "Upload a supporting document to submit your claim"}), HTTP_400_BAD_REQUEST

    filename = (file.filename or '').lower()
    if not filename.endswith(('.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx', '.webp')):
        db.session.delete(claim)
        db.session.commit()
        return jsonify({'error': "Document must be a PDF, image or Word file"}), HTTP_400_BAD_REQUEST

    # basic size guard (~15MB)
    try:
        file.stream.seek(0, 2)
        size = file.stream.tell()
        file.stream.seek(0)
    except Exception:
        size = 0
    if size > 15 * 1024 * 1024:
        db.session.delete(claim)
        db.session.commit()
        return jsonify({'error': "Document is too large (max 15MB)"}), HTTP_400_BAD_REQUEST

    try:
        from src.constants.storage import upload_file
        document_url = upload_file(file, 'property_claims/{}'.format(current_user))
    except Exception as e:
        db.session.delete(claim)
        db.session.commit()
        return jsonify({'error': "Failed to upload document: {}".format(e)}), HTTP_400_BAD_REQUEST

    claim.status = 'pending'
    claim.document_url = document_url
    claim.updated_at = datetime.now()
    db.session.commit()

    return jsonify({
        'message': "Claim submitted — your document will be reviewed by the admin",
        'claim': {'id': claim.id, 'status': claim.status},
        'document_url': document_url,
    }), HTTP_201_CREATED


def _send_claim_code(claim, property, email):
    """Generate + email a 6-digit verification code for a property claim."""
    from src.constants.functions import generate_random_string
    from src.database import Verification
    from flask_mail import Message
    from src.auth import mail

    code = generate_random_string(6)
    purpose = "claim_property"
    expiration = 10

    code_hash = generate_password_hash(code)

    old = Verification.query.filter_by(user_id=claim.user_id, purpose=purpose, property_id=property.id)
    for v in old:
        db.session.delete(v)
    db.session.flush()

    verification = Verification(
        user_id=claim.user_id,
        property_id=property.id,
        code=code_hash,
        purpose=purpose,
        expiration=expiration,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    db.session.add(verification)
    db.session.commit()

    message = (
        "You requested to claim the property \"{}\".\n\n"
        "Your verification code is: {}\n\n"
        "This code expires in {} minutes."
    ).format(property.title, code, expiration)

    msg = Message(subject='Property Claim Verification', recipients=[email])
    msg.body = message

    try:
        mail.send(msg)
    except Exception as e:
        print('Failed to send claim verification email to {}: {}'.format(email, e))


@properties.post("/<int:id>/claim/verify")
@jwt_required()
def verify_claim(id):
    current_user = get_jwt_identity()

    property = Property.query.filter_by(id=id).first()
    if not property:
        return jsonify({'error': "Property not found"}), HTTP_404_NOT_FOUND

    claim = PropertyClaim.query.filter_by(
        property_id=id, user_id=current_user, status='pending_verification'
    ).first()
    if not claim:
        return jsonify({'error': "No claim is waiting for verification"}), HTTP_400_BAD_REQUEST

    data = request.get_json(silent=True) or {}
    code = data.get('code')

    from src.database import Verification
    verification = Verification.query.filter_by(
        user_id=current_user, purpose='claim_property', property_id=id
    ).first()

    if not verification:
        return jsonify({'error': "No verification code found. Request a new one."}), HTTP_400_BAD_REQUEST

    if not check_password_hash(verification.code, code):
        return jsonify({'error': "Invalid verification code"}), HTTP_400_BAD_REQUEST

    if datetime.now() - verification.created_at >= timedelta(minutes=verification.expiration):
        db.session.delete(verification)
        db.session.commit()
        return jsonify({'error': "Verification code expired. Request a new one."}), HTTP_400_BAD_REQUEST

    claim.status = 'pending'
    claim.updated_at = datetime.now()
    db.session.delete(verification)
    db.session.commit()

    return jsonify({
        'message': "Verification successful — claim submitted for admin review",
        'claim': {'id': claim.id, 'status': claim.status},
    }), HTTP_200_OK


@properties.get("/<int:id>/claim/resend")
@jwt_required()
def resend_claim_code(id):
    current_user = get_jwt_identity()

    property = Property.query.filter_by(id=id).first()
    if not property:
        return jsonify({'error': "Property not found"}), HTTP_404_NOT_FOUND

    claim = PropertyClaim.query.filter_by(
        property_id=id, user_id=current_user, status='pending_verification'
    ).first()
    if not claim:
        return jsonify({'error': "No claim is waiting for verification"}), HTTP_400_BAD_REQUEST

    claimant = User.query.filter_by(id=current_user).first()
    target_email = claimant.email if claimant else None
    if not target_email:
        return jsonify({'error': "No email on your account to verify with"}), HTTP_400_BAD_REQUEST

    _send_claim_code(claim, property, target_email)

    return jsonify({'message': "A new verification code was sent to {}".format(target_email)}), HTTP_200_OK


@properties.route('/user/<int:id>/', methods=['GET'])
@swag_from('./docs/properties/getuserproperties.yml')
def get_properties(id):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    category = request.args.get('category')
    purpose = request.args.get('purpose')
    property_type = request.args.get('property_type')
    search = request.args.get('search')

    if not User.query.filter_by(id=id).first():
        return jsonify({'error': "User not found"}), HTTP_404_NOT_FOUND

    query = Property.query.filter_by(user_id=id)
    if category:
        query = query.filter_by(category=category)
    if purpose:
        query = query.filter_by(purpose=purpose)
    if property_type:
        query = query.filter_by(property_type=property_type)
    if search:
        query = query.filter(Property.title.ilike('%{}%'.format(search)))

    properties = query.order_by(Property.created_at.desc()).paginate(page=page, per_page=per_page)

    data = []

    for property in properties.items:
        dp = PropertyImage.query.filter_by(property_id=property.id, dp=1).first()
        if dp is None:  # Check if dp is None
            dp_url = ""
        else:
            dp_url = dp.image_url

        average_rating = db.session.query(func.avg(Review.rating)).filter(Review.property_id == property.id).scalar()

        user = User.query.filter_by(id=property.user_id).first()

        data.append({
            'id': property.id,
            'title': property.title,
            'category': property.category,
            'property_type': property.property_type,
            'purpose': property.purpose,
            'price': property.price,
            'currency': property.currency,
            'location': property.location,
            'city': property.city,
            'state': property.state,
            'country': property.country,
            'dp': dp_url,  # Use dp_url to access the image_url
            'image_count': PropertyImage.query.filter_by(property_id=property.id).count(),
            'video_count': PropertyVideo.query.filter_by(property_id=property.id).count(),
            'approved': property.approved,
            'available': property.available,
            'disabled': property.disabled,
            'views': property.views,
            'favorites_count': Favorite.query.filter_by(property_id=property.id).count(),
            'created_at': property.created_at,
            'updated_at': property.updated_at,
            'average_rating' : average_rating,
            'username' : user.username,
            'owner_full_name': user.full_name,
            'owner_email': user.email,
            'owner_phone_number': user.phone_number,
            'contact_phone': property.contact_phone,
            'contact_email': property.contact_email,
            'contact_website': property.contact_website,
            'contact_phones': json.loads(property.contact_phones) if property.contact_phones else [],
            'contact_emails': json.loads(property.contact_emails) if property.contact_emails else [],
        })

    meta={
        "page": properties.page,
        "pages": properties.pages,
        "total_count": properties.total,
        "prev_page": properties.prev_num,
        "next_page": properties.next_num,
        "has_next": properties.has_next,
        "has_prev": properties.has_prev
    }

    return jsonify({'data': data, 'meta':meta}), HTTP_200_OK


@properties.get("/")
@swag_from('./docs/properties/browseproperties.yml')
def browse_properties():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    category = request.args.get('category')
    purpose = request.args.get('purpose')
    property_type = request.args.get('property_type')
    city = request.args.get('city')
    state = request.args.get('state')
    country = request.args.get('country')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    sort = request.args.get('sort')
    bedrooms = request.args.get('bedrooms', type=int)
    bathrooms = request.args.get('bathrooms', type=int)
    available = request.args.get('available', type=int)

    query = Property.query.filter(Property.disabled == 0)

    if category:
        query = query.filter_by(category=category)
    if purpose:
        query = query.filter_by(purpose=purpose)
    if property_type:
        query = query.filter_by(property_type=property_type)
    if city:
        query = query.filter(Property.city.ilike('%{}%'.format(city)))
    if state:
        query = query.filter(Property.state.ilike('%{}%'.format(state)))
    if country:
        query = query.filter(Property.country.ilike('%{}%'.format(country)))
    if min_price is not None:
        query = query.filter(Property.price >= min_price)
    if max_price is not None:
        query = query.filter(Property.price <= max_price)

    if bedrooms is not None:
        query = query.filter(Property.bedrooms >= bedrooms)

    if bathrooms is not None:
        query = query.filter(Property.bathrooms >= bathrooms)

    if available is not None:
        query = query.filter(Property.available == available)

    if sort == 'views':
        query = query.order_by(Property.views.desc(), Property.created_at.desc())
    elif sort == 'popular':
        query = query.order_by(Property.views.desc(), Property.created_at.desc())
    elif sort == 'price_asc':
        query = query.order_by(Property.price.asc())
    elif sort == 'price_desc':
        query = query.order_by(Property.price.desc())
    else:
        query = query.order_by(Property.created_at.desc())
    properties = query.paginate(page=page, per_page=per_page, error_out=False)

    data = []

    for property in properties.items:
        dp = PropertyImage.query.filter_by(property_id=property.id, dp=1).first()
        dp_url = dp.image_url if dp else ""

        average_rating = db.session.query(func.avg(Review.rating)).filter(Review.property_id == property.id).scalar()

        user = User.query.filter_by(id=property.user_id).first()

        data.append({
            'id': property.id,
            'user_id': property.user_id,
            'title': property.title,
            'category': property.category,
            'property_type': property.property_type,
            'purpose': property.purpose,
            'price': property.price,
            'currency': property.currency,
            'location': property.location,
            'city': property.city,
            'state': property.state,
            'country': property.country,
            'dp': dp_url,
            'image_count': PropertyImage.query.filter_by(property_id=property.id).count(),
            'video_count': PropertyVideo.query.filter_by(property_id=property.id).count(),
            'approved': property.approved,
            'available': property.available,
            'views': property.views,
            'favorites_count': Favorite.query.filter_by(property_id=property.id).count(),
            'created_at': property.created_at,
            'updated_at': property.updated_at,
            'average_rating': average_rating,
            'username': user.username,
            'owner_full_name': user.full_name,
            'owner_email': user.email,
            'owner_phone_number': user.phone_number,
            'contact_phone': property.contact_phone,
            'contact_email': property.contact_email,
            'contact_website': property.contact_website,
            'contact_phones': json.loads(property.contact_phones) if property.contact_phones else [],
            'contact_emails': json.loads(property.contact_emails) if property.contact_emails else [],
        })

    meta={
        "page": properties.page,
        "pages": properties.pages,
        "total_count": properties.total,
        "prev_page": properties.prev_num,
        "next_page": properties.next_num,
        "has_next": properties.has_next,
        "has_prev": properties.has_prev
    }

    return jsonify({'data': data, 'meta':meta}), HTTP_200_OK


@properties.put('/<int:id>')
@properties.patch('/<int:id>')
@jwt_required()
@swag_from('./docs/properties/editproperty.yml')
def edit_property(id):

    current_user = get_jwt_identity()

    if not Property.query.filter_by(id=id).first():
        return jsonify({'message': "Property not found"}), HTTP_404_NOT_FOUND

    property = Property.query.filter_by(user_id=current_user, id=id).first()

    if not property:
        return jsonify({'error': "Unauthorized User"}), HTTP_401_UNAUTHORIZED

    title = request.get_json().get('title','')
    description = request.get_json().get('description','')
    category = request.get_json().get('category', property.category)
    property_type = request.get_json().get('property_type','')
    purpose = request.get_json().get('purpose', property.purpose)
    attributes = request.get_json().get('attributes')
    price = request.get_json().get('price')
    currency = request.get_json().get('currency', property.currency)
    area = request.get_json().get('area')
    bedrooms = request.get_json().get('bedrooms')
    bathrooms = request.get_json().get('bathrooms')
    location = request.get_json().get('location','')
    city = request.get_json().get('city','')
    state = request.get_json().get('state','')
    country = request.get_json().get('country','')
    latitude = request.get_json().get('latitude')
    longitude = request.get_json().get('longitude')
    year_built = request.get_json().get('year_built')
    contact_phone = request.get_json().get('contact_phone', property.contact_phone)
    contact_email = request.get_json().get('contact_email', property.contact_email)
    contact_website = request.get_json().get('contact_website', property.contact_website)
    contact_phones = request.get_json().get('contact_phones') or []
    contact_emails = request.get_json().get('contact_emails') or []
    amenities = request.get_json().get('amenities')
    negotiable = request.get_json().get('negotiable', 0)
    available = request.get_json().get('available', property.available)
    disabled = request.get_json().get('disabled', property.disabled)

    if not title or not description or not property_type or price is None or not location or not city or not state or not country:
        return jsonify({'error': "Title, Description, Property type, Price, Location, City, State, Country must not be empty"}), HTTP_400_BAD_REQUEST 
    
    if not is_valid_category(category):
        return jsonify({'error': "Category must be one of: property, land, hotel, hall, event_center, shortlet, other"}), HTTP_400_BAD_REQUEST
    
    if not is_valid_purpose(purpose):
        return jsonify({'error': "Purpose must be one of: rent, sale, both"}), HTTP_400_BAD_REQUEST
    
    if attributes is not None and not isinstance(attributes, dict):
        return jsonify({'error': "Attributes must be in json format"}), HTTP_400_BAD_REQUEST
    
    if len(title) < 3:
        return jsonify({'error': "Title must be more than 2 characters"}), HTTP_400_BAD_REQUEST
    
    if not property.title == title and Property.query.filter_by(user_id=current_user, title=title).first():
        return jsonify({'error': "Property title already exists for user"}), HTTP_409_CONFLICT
    
    if len(description) < 3:
        return jsonify({'error': "Description must be more than 2 characters"}), HTTP_400_BAD_REQUEST
    
    if isinstance(price, (int, float)):
        # price is already a number (integer or float)
        pass
    else:
        # price is a string, let's try to convert it to a number
        try:
            price = float(price)
        except ValueError:
            return jsonify({'error': "Price must be a valid number"}), HTTP_400_BAD_REQUEST
        
    try:
        area = to_float(area, "Area")
        bedrooms = to_int(bedrooms, "Bedroom")
        bathrooms = to_int(bathrooms, "Bathroom")
        latitude = to_float(latitude, "Latitude")
        longitude = to_float(longitude, "Longitude")
        year_built = to_int(year_built, "Year built")
    except ValueError as e:
        return jsonify({'error': str(e)}), HTTP_400_BAD_REQUEST

    if isinstance(available, int) and (available == 0 or available == 1):
        # year_built is an integer
        pass
    else:
        return jsonify({'error': "Available must be either 0 or 1"}), HTTP_400_BAD_REQUEST
    
    if isinstance(negotiable, int) and (negotiable == 0 or negotiable == 1):
        # year_built is an integer
        pass
    else:
        return jsonify({'error': "Negotiable must be either 0 or 1"}), HTTP_400_BAD_REQUEST
        
    if isinstance(amenities, dict):
        # amenities is a JSON object (dictionary)
        # Convert amenities to a JSON string
        amenities_str = json.dumps(amenities)
        # amenities_str = str(amenities)
    else:
        return jsonify({'error': "Amenities must be in json format"}), HTTP_400_BAD_REQUEST

    attributes_str = json.dumps(attributes) if attributes else None
    
    property.title=title
    property.description=description
    property.category=category
    property.property_type=property_type
    property.purpose=purpose
    if attributes_str is not None:
        property.attributes=attributes_str
    property.price=price
    property.currency=currency
    property.area=area
    property.bedrooms=bedrooms
    property.bathrooms=bathrooms
    property.location=location
    property.city=city
    property.state=state
    property.country=country
    property.negotiable=negotiable
    property.latitude=latitude
    property.longitude=longitude
    property.year_built=year_built
    property.amenities=amenities_str 
    property.available=available
    property.disabled=disabled
    property.contact_phone=contact_phone
    property.contact_email=contact_email
    property.contact_website=contact_website
    property.contact_phones=json.dumps(contact_phones) if contact_phones else None
    property.contact_emails=json.dumps(contact_emails) if contact_emails else None
    property.updated_at=datetime.now()

    db.session.commit()

    return jsonify(serialize_property(property)), HTTP_200_OK
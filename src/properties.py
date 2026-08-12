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
from src.database import User, Property, Message, PropertyImage, PropertyVideo, Request, Review, Favorite, db
from flask import Blueprint, request, jsonify
from src.constants.functions import adjust_url
from src.constants.property_meta import is_valid_category, is_valid_purpose
from src.constants.storage import upload_file, delete_file
import validators
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
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
    amenities = request.get_json().get('amenities')
    negotiable = request.get_json().get('negotiable', 0)

    if not title or not description or not property_type or not price or not location or not city or not state or not country:
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
    
    property = Property(user_id=current_user, title=title, description=description, category=category, property_type=property_type, purpose=purpose, attributes=attributes_str, price=price, currency=currency, area=area, bedrooms=bedrooms, bathrooms=bathrooms, location=location, city=city, state=state, country=country, negotiable=negotiable, latitude=latitude, longitude=longitude, year_built=year_built, amenities=amenities_str, contact_phone=contact_phone, contact_email=contact_email, contact_website=contact_website, created_at=datetime.now(), updated_at=datetime.now())

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


@properties.get("/<int:id>")
@swag_from('./docs/properties/getproperty.yml')
def get_property(id):

    property = Property.query.filter_by(id=id).first()

    if not property:
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
        ingest_batch([item], request.headers.get('User-Agent', ''), request.headers.get('CF-IPCountry'), None)
    except Exception:
        db.session.rollback()
        property.views = (property.views or 0) + 1
        db.session.commit()

    return jsonify(serialize_property(property)), HTTP_200_OK


@properties.route('/user/<int:id>/', methods=['GET'])
@swag_from('./docs/properties/getuserproperties.yml')
def get_properties(id):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    category = request.args.get('category')
    purpose = request.args.get('purpose')
    property_type = request.args.get('property_type')

    if not User.query.filter_by(id=id).first():
        return jsonify({'error': "User not found"}), HTTP_404_NOT_FOUND

    query = Property.query.filter_by(user_id=id)
    if category:
        query = query.filter_by(category=category)
    if purpose:
        query = query.filter_by(purpose=purpose)
    if property_type:
        query = query.filter_by(property_type=property_type)

    properties = query.paginate(page=page, per_page=per_page)

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
            'approved': property.approved,
            'available': property.available,
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

    query = Property.query

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
    amenities = request.get_json().get('amenities')
    negotiable = request.get_json().get('negotiable', 0)
    available = request.get_json().get('available', property.available)

    if not title or not description or not property_type or not price or not location or not city or not state or not country:
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
    property.contact_phone=contact_phone
    property.contact_email=contact_email
    property.contact_website=contact_website
    property.updated_at=datetime.now()

    db.session.commit()

    return jsonify(serialize_property(property)), HTTP_200_OK
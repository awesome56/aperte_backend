from src.constants.http_status_codes import HTTP_400_BAD_REQUEST
from src.constants.http_status_codes import HTTP_401_UNAUTHORIZED
from src.constants.http_status_codes import HTTP_404_NOT_FOUND
from src.constants.http_status_codes import HTTP_409_CONFLICT
from src.constants.http_status_codes import HTTP_200_OK
from src.constants.http_status_codes import HTTP_201_CREATED
from src.constants.http_status_codes import HTTP_202_ACCEPTED
from src.constants.http_status_codes import HTTP_204_NO_CONTENT
from flask import Blueprint, request
from src.database import User, Property, Message, PropertyImage, Request, Review, db
from flask import Blueprint, request, jsonify
from src.constants.functions import adjust_url
import validators
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
import os
import time
from datetime import datetime
import json
from sqlalchemy import func


properties = Blueprint("property", __name__, url_prefix="/api/v1/properties")


@properties.post("/")
@jwt_required()
def create_property():
    current_user = get_jwt_identity()

    title = request.get_json().get('title','')
    description = request.get_json().get('description','')
    property_type = request.get_json().get('property_type','')
    price = request.get_json().get('price')
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
    amenities = request.get_json().get('amenities')
    negotiable = request.get_json().get('negotiable', 0)

    if not title or not description or not property_type or not price or not location or not city or not state or not country:
        return jsonify({'error': "Property title, description, property type, price, location, city, state, country must not be empty"}), HTTP_400_BAD_REQUEST 
    
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
        
    if isinstance(area, (int, float)):
        # area is already a number (integer or float)
        pass
    else:
        # area is a string, let's try to convert it to a number
        try:
            area = float(area)
        except ValueError:
            return jsonify({'error': "Area must be a valid number"}), HTTP_400_BAD_REQUEST
        
    if isinstance(bedrooms, int):
        # bedrooms is an integer
        pass
    else:
        try:
            bedrooms = int(bedrooms)
        except ValueError:
            return jsonify({'error': "Bedroom must be an whole number"}), HTTP_400_BAD_REQUEST
        
    if isinstance(bathrooms, int):
        # bathrooms is an integer
        pass
    else:
        try:
            bathrooms = int(bathrooms)
        except ValueError:
            return jsonify({'error': "Bathroom must be an whole number"}), HTTP_400_BAD_REQUEST
        
    if isinstance(latitude, (int, float)):
        # latitude is already a number (integer or float)
        pass
    else:
        # latitude is a string, let's try to convert it to a number
        try:
            latitude = float(latitude)
        except ValueError:
            return jsonify({'error': "Latitude must be a valid number"}), HTTP_400_BAD_REQUEST
        
    if isinstance(longitude, (int, float)):
        # longitude is already a number (integer or float)
        pass
    else:
        # longitude is a string, let's try to convert it to a number
        try:
            longitude = float(longitude)
        except ValueError:
            return jsonify({'error': "Longitude must be a valid number"}), HTTP_400_BAD_REQUEST
        
    if isinstance(year_built, int):
        # year_built is an integer
        pass
    else:
        try:
            year_built = int(year_built)
        except ValueError:
            return jsonify({'error': "Year built must be an whole number"}), HTTP_400_BAD_REQUEST
        
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
    
    
    property = Property(user_id=current_user, title=title, description=description, property_type=property_type, price=price, area=area, bedrooms=bedrooms, bathrooms=bathrooms, location=location, city=city, state=state, country=country, negotiable=negotiable, latitude=latitude, longitude=longitude, year_built=year_built, amenities=amenities_str, created_at=datetime.now(), updated_at=datetime.now())

    db.session.add(property)
    db.session.commit()

    property_images = PropertyImage.query.filter_by(property_id=property.id)
    attachments = []
    for property_image in property_images:
        attachments.append({
                    'id': property_image.id,
                    'image_url': property_image.image_url,
                    'created_at' : property_image.created_at,
                    'updated_at' : property_image.updated_at,
                })
        
    average_rating = db.session.query(func.avg(Review.rating)).filter(Review.property_id == property.id).scalar()

    user = User.query.filter_by(id=current_user).first()

    return jsonify({
        'id': property.id,
        'user_id': property.user_id,
        'title': property.title,
        'description': property.description,
        'property_type': property.property_type,
        'price': property.price,
        'area' : property.area,
        'bedrooms' : property.bedrooms,
        'bathrooms' : property.bathrooms,
        'location' : property.location,
        'city' : property.city,
        'state' : property.state,
        'country' : property.country,
        'latitude' : property.latitude,
        'logitude': property.longitude,
        'year_built': property.year_built,
        'amenities': json.loads(property.amenities),
        'images' : attachments,
        'negotiable' : property.negotiable,
        'available' : property.available,
        'approved': property.approved,
        'created_at': property.created_at,
        'updated_at': property.updated_at,
        'average_rating' : average_rating,
        'username' : user.username
    }), HTTP_201_CREATED


@properties.post('/images/<int:id>')
@jwt_required()
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

    for file in files:
        if file:
            # Check the file extension
            if not allowed_file(file.filename):
                return 'Invalid file extension'

            # Check the file size
            if not allowed_file_size(file):
                return 'File size is too large'
            
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
        
        # Append a unique micro timestamp to the filename
        timestamp = int(time.time() * 1000000)

        # Get the absolute path of the current working directory
        app_root = os.path.dirname(os.path.abspath(__file__))

        user_directory = os.path.join(app_root, 'static', 'files', str(current_user),'properties')
        os.makedirs(user_directory, exist_ok=True)
        
        file_path = os.path.join(user_directory, f'{timestamp}_{secure_filename(file.filename)}')

        # Save the file to disk
        file.save(file_path)

        property_image = PropertyImage(property_id= property.id, image_url=file_path, dp=dp_value, created_at=datetime.now(), updated_at=datetime.now())
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

    if os.path.exists(oldfile):
        os.remove(oldfile)

    return jsonify({}), HTTP_204_NO_CONTENT


@properties.get("/<int:id>")
def get_property(id):

    property = Property.query.filter_by(id=id).first()

    if not property:
        return jsonify({'message': "Property not found"}),HTTP_404_NOT_FOUND
    
    property_images = PropertyImage.query.filter_by(property_id=property.id)
    attachments = []
    for property_image in property_images:
        attachments.append({
                    'id': property_image.id,
                    'image_url': property_image.image_url,
                    'created_at' : property_image.created_at,
                    'updated_at' : property_image.updated_at,
                })
        
    average_rating = db.session.query(func.avg(Review.rating)).filter(Review.property_id == property.id).scalar()

    user = User.query.filter_by(id=property.user_id).first()

    return jsonify({
        'id': property.id,
        'user_id': property.user_id,
        'title': property.title,
        'description': property.description,
        'property_type': property.property_type,
        'price': property.price,
        'area' : property.area,
        'bedrooms' : property.bedrooms,
        'bathrooms' : property.bathrooms,
        'location' : property.location,
        'city' : property.city,
        'state' : property.state,
        'country' : property.country,
        'latitude' : property.latitude,
        'logitude': property.longitude,
        'year_built': property.year_built,
        'amenities': json.loads(property.amenities),
        'images' : attachments,
        'negotiable' : property.negotiable,
        'available' : property.available,
        'approved': property.approved,
        'created_at': property.created_at,
        'updated_at': property.updated_at,
        'average_rating' : average_rating,
        'username' : user.username
    }), HTTP_200_OK


@properties.route('/user/<int:id>/', methods=['GET'])
def get_properties(id):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    if not User.query.filter_by(id=id).first():
        return jsonify({'error': "User not found"}), HTTP_404_NOT_FOUND

    properties=Property.query.filter_by(user_id=id).paginate(page=page, per_page=per_page)

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
            'property_type': property.property_type,
            'price': property.price,
            'location': property.location,
            'dp': dp_url,  # Use dp_url to access the image_url
            'approved': property.approved,
            'available': property.available,
            'created_at': property.created_at,
            'updated_at': property.updated_at,
            'average_rating' : average_rating,
            'username' : user.username
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
def edit_property(id):

    current_user = get_jwt_identity()

    if not Property.query.filter_by(id=id).first():
        return jsonify({'message': "Property not found"}), HTTP_404_NOT_FOUND

    property = Property.query.filter_by(user_id=current_user, id=id).first()

    if not property:
        return jsonify({'error': "Unauthorized User"}), HTTP_401_UNAUTHORIZED

    title = request.get_json().get('title','')
    description = request.get_json().get('description','')
    property_type = request.get_json().get('property_type','')
    price = request.get_json().get('price')
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
    amenities = request.get_json().get('amenities')
    negotiable = request.get_json().get('negotiable', 0)
    available = request.get_json().get('negotiable', 1)

    if not title or not description or not property_type or not price or not location or not city or not state or not country:
        return jsonify({'error': "Title, Description, Property type, Price, Location, City, State, Country must not be empty"}), HTTP_400_BAD_REQUEST 
    
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
        
    if isinstance(area, (int, float)):
        # area is already a number (integer or float)
        pass
    else:
        # area is a string, let's try to convert it to a number
        try:
            area = float(area)
        except ValueError:
            return jsonify({'error': "Area must be a valid number"}), HTTP_400_BAD_REQUEST
        
    if isinstance(bedrooms, int):
        # bedrooms is an integer
        pass
    else:
        try:
            bedrooms = int(bedrooms)
        except ValueError:
            return jsonify({'error': "Bedroom must be an whole number"}), HTTP_400_BAD_REQUEST
        
    if isinstance(bathrooms, int):
        # bathrooms is an integer
        pass
    else:
        try:
            bathrooms = int(bathrooms)
        except ValueError:
            return jsonify({'error': "Bathroom must be an whole number"}), HTTP_400_BAD_REQUEST
        
    if isinstance(latitude, (int, float)):
        # latitude is already a number (integer or float)
        pass
    else:
        # latitude is a string, let's try to convert it to a number
        try:
            latitude = float(latitude)
        except ValueError:
            return jsonify({'error': "Latitude must be a valid number"}), HTTP_400_BAD_REQUEST
        
    if isinstance(longitude, (int, float)):
        # longitude is already a number (integer or float)
        pass
    else:
        # longitude is a string, let's try to convert it to a number
        try:
            longitude = float(longitude)
        except ValueError:
            return jsonify({'error': "Longitude must be a valid number"}), HTTP_400_BAD_REQUEST
        
    if isinstance(year_built, int):
        # year_built is an integer
        pass
    else:
        try:
            year_built = int(year_built)
        except ValueError:
            return jsonify({'error': "Year built must be an whole number"}), HTTP_400_BAD_REQUEST
        
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
    
    property.title=title
    property.description=description
    property.property_type=property_type
    property.price=price
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
    property.updated_at=datetime.now()

    db.session.commit()

    property_images = PropertyImage.query.filter_by(property_id=property.id)
    attachments = []
    for property_image in property_images:
        attachments.append({
                    'id': property_image.id,
                    'image_url': property_image.image_url,
                    'created_at' : property_image.created_at,
                    'updated_at' : property_image.updated_at,
                })
        
    average_rating = db.session.query(func.avg(Review.rating)).filter(Review.property_id == property.id).scalar()

    user = User.query.filter_by(id=property.user_id).first()

    return jsonify({
        'id': property.id,
        'user_id': property.user_id,
        'title': property.title,
        'description': property.description,
        'property_type': property.property_type,
        'price': property.price,
        'area' : property.area,
        'bedrooms' : property.bedrooms,
        'bathrooms' : property.bathrooms,
        'location' : property.location,
        'city' : property.city,
        'state' : property.state,
        'country' : property.country,
        'latitude' : property.latitude,
        'logitude': property.longitude,
        'year_built': property.year_built,
        'amenities': json.loads(property.amenities),
        'images' : attachments,
        'negotiable' : property.negotiable,
        'available' : property.available,
        'approved': property.approved,
        'created_at': property.created_at,
        'updated_at': property.updated_at,
        'average_rating' : average_rating,
        'username' : user.username
    }), HTTP_200_OK
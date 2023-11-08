from src.constants.http_status_codes import HTTP_400_BAD_REQUEST
from src.constants.http_status_codes import HTTP_401_UNAUTHORIZED
from src.constants.http_status_codes import HTTP_404_NOT_FOUND
from src.constants.http_status_codes import HTTP_409_CONFLICT
from src.constants.http_status_codes import HTTP_200_OK
from src.constants.http_status_codes import HTTP_201_CREATED
from src.constants.http_status_codes import HTTP_202_ACCEPTED
from src.constants.http_status_codes import HTTP_204_NO_CONTENT
from flask import Blueprint, request
from src.database import User, Request, db
from flask import Blueprint, request, jsonify
from src.constants.functions import adjust_url
import validators
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
import os
import time
from sqlalchemy import func
from datetime import datetime
import json


requests = Blueprint("request", __name__, url_prefix="/api/v1/requests")


@requests.post("/")
@jwt_required()
def create_requests():
    current_user = get_jwt_identity()

    title = request.get_json().get('title','')
    property_type = request.get_json().get('property_type','')
    sub_category = request.get_json().get('sub_category',None)
    bedrooms = request.get_json().get('bedrooms', None)
    bathrooms = request.get_json().get('bathrooms', None)
    location = request.get_json().get('location', '')
    city = request.get_json().get('city','')
    state = request.get_json().get('state','')
    country = request.get_json().get('country','')
    amenities = request.get_json().get('amenities')
    description = request.get_json().get('description','')
    min_price = request.get_json().get('min_price', 0)
    max_price = request.get_json().get('max_price', 0)
    area = request.get_json().get('area', None)
    year_built = request.get_json().get('year_built', None)

    if not title or not description or not property_type:
        return jsonify({'error': "Title, Description and Property type must not be empty"}), HTTP_400_BAD_REQUEST 
    
    if len(title) < 3:
        return jsonify({'error': "Title must be more than 2 characters"}), HTTP_400_BAD_REQUEST
    
    existing_request = Request.query.filter(Request.user_id == current_user, func.lower(Request.title) == func.lower(title), Request.property_type == property_type).first()

    if existing_request:
        return jsonify({'error': "Request title already exists for the user"}), HTTP_409_CONFLICT
    
    if len(description) < 3:
        return jsonify({'error': "Description must be more than 2 characters"}), HTTP_400_BAD_REQUEST
    
    if isinstance(min_price, (int, float)):
        # price is already a number (integer or float)
        pass
    else:
        # price is a string, let's try to convert it to a number
        try:
            min_price = float(min_price)
        except ValueError:
            return jsonify({'error': "Min price must be a valid number"}), HTTP_400_BAD_REQUEST
        
    if isinstance(max_price, (int, float)):
        # price is already a number (integer or float)
        pass
    else:
        # price is a string, let's try to convert it to a number
        try:
            max_price = float(max_price)
        except ValueError:
            return jsonify({'error': "Max price must be a valid number"}), HTTP_400_BAD_REQUEST
        
    if area is not None:    
        if isinstance(area, (int, float)):
            # area is already a number (integer or float)
            pass
        else:
            # area is a string, let's try to convert it to a number
            try:
                area = float(area)
            except ValueError:
                return jsonify({'error': "Area must be a valid number"}), HTTP_400_BAD_REQUEST

    if bedrooms is not None: 
        if isinstance(bedrooms, int):
            # bedrooms is an integer
            pass
        else:
            try:
                bedrooms = int(bedrooms)
            except ValueError:
                return jsonify({'error': "Bedroom must be an whole number"}), HTTP_400_BAD_REQUEST
        
    if bathrooms is not None:
        if isinstance(bathrooms, int):
            # bathrooms is an integer
            pass
        else:
            try:
                bathrooms = int(bathrooms)
            except ValueError:
                return jsonify({'error': "Bathroom must be an whole number"}), HTTP_400_BAD_REQUEST
        
    if year_built is not None:
        if isinstance(year_built, int):
            # year_built is an integer
            pass
        else:
            try:
                year_built = int(year_built)
            except ValueError:
                return jsonify({'error': "Year built must be an whole number"}), HTTP_400_BAD_REQUEST
        
    if isinstance(amenities, dict):
        # amenities is a JSON object (dictionary)
        # Convert amenities to a JSON string
        amenities_str = json.dumps(amenities)
        # amenities_str = str(amenities)
    else:
        return jsonify({'error': "Amenities must be in json format"}), HTTP_400_BAD_REQUEST
    
    
    request_ = Request(user_id=current_user, title=title, description=description, property_type=property_type, sub_category=sub_category, min_price=min_price, max_price=max_price, area=area, bedrooms=bedrooms, bathrooms=bathrooms, location=location, city=city, state=state, country=country, year_built=year_built, amenities=amenities_str, created_at=datetime.now(), updated_at=datetime.now())

    db.session.add(request_)
    db.session.commit()

    return jsonify({
        'id': request_.id,
        'user_id': request_.user_id,
        'title': request_.title,
        'description': request_.description,
        'property_type': request_.property_type,
        'sub_category': request_.sub_category,
        'min_price': request_.min_price,
        'max_price': request_.max_price,
        'area' : request_.area,
        'bedrooms' : request_.bedrooms,
        'bathrooms' : request_.bathrooms,
        'location' : request_.location,
        'city' : request_.city,
        'state' : request_.state,
        'country' : request_.country,
        'year_built': request_.year_built,
        'amenities': json.loads(request_.amenities),
        'created_at': request_.created_at,
        'updated_at': request_.updated_at,
    }), HTTP_201_CREATED


@requests.get("/<int:id>")
def get_property(id):

    request_ = Request.query.filter_by(id=id).first()

    if not request_:
        return jsonify({'message': "Request not found"}),HTTP_404_NOT_FOUND

    return jsonify({
        'id': request_.id,
        'user_id': request_.user_id,
        'title': request_.title,
        'description': request_.description,
        'property_type': request_.property_type,
        'sub_category': request_.sub_category,
        'min_price': request_.min_price,
        'max_price': request_.max_price,
        'area' : request_.area,
        'bedrooms' : request_.bedrooms,
        'bathrooms' : request_.bathrooms,
        'location' : request_.location,
        'city' : request_.city,
        'state' : request_.state,
        'country' : request_.country,
        'year_built': request_.year_built,
        'amenities': json.loads(request_.amenities),
        'created_at': request_.created_at,
        'updated_at': request_.updated_at,
    }), HTTP_200_OK


@requests.put('/<int:id>')
@requests.patch('/<int:id>')
@jwt_required()
def edit_request(id):

    current_user = get_jwt_identity()

    if not Request.query.filter_by(id=id).first():
        return jsonify({'message': "Request not found"}), HTTP_404_NOT_FOUND

    request_ = Request.query.filter_by(user_id=current_user, id=id).first()

    if not request_:
        return jsonify({'error': "Unauthorized User"}), HTTP_401_UNAUTHORIZED

    title = request.get_json().get('title','')
    property_type = request.get_json().get('property_type','')
    sub_category = request.get_json().get('sub_category',None)
    bedrooms = request.get_json().get('bedrooms', None)
    bathrooms = request.get_json().get('bathrooms', None)
    location = request.get_json().get('location', '')
    city = request.get_json().get('city','')
    state = request.get_json().get('state','')
    country = request.get_json().get('country','')
    amenities = request.get_json().get('amenities')
    description = request.get_json().get('description','')
    min_price = request.get_json().get('min_price', 0)
    max_price = request.get_json().get('max_price', 0)
    area = request.get_json().get('area', None)
    year_built = request.get_json().get('year_built', None)

    if not title or not description or not property_type:
        return jsonify({'error': "Title, Description and Property type must not be empty"}), HTTP_400_BAD_REQUEST 
    
    if len(title) < 3:
        return jsonify({'error': "Title must be more than 2 characters"}), HTTP_400_BAD_REQUEST
    
    if not request_.title == title:
        if Request.query.filter_by(user_id=current_user, title=title, property_type=property_type).first():
            return jsonify({'error': "Request title already exists for user"}), HTTP_409_CONFLICT
    
    if len(description) < 3:
        return jsonify({'error': "Description must be more than 2 characters"}), HTTP_400_BAD_REQUEST
    
    if isinstance(min_price, (int, float)):
        # price is already a number (integer or float)
        pass
    else:
        # price is a string, let's try to convert it to a number
        try:
            min_price = float(min_price)
        except ValueError:
            return jsonify({'error': "Min price must be a valid number"}), HTTP_400_BAD_REQUEST
        
    if isinstance(max_price, (int, float)):
        # price is already a number (integer or float)
        pass
    else:
        # price is a string, let's try to convert it to a number
        try:
            max_price = float(max_price)
        except ValueError:
            return jsonify({'error': "Max price must be a valid number"}), HTTP_400_BAD_REQUEST
        
    if area is not None:    
        if isinstance(area, (int, float)):
            # area is already a number (integer or float)
            pass
        else:
            # area is a string, let's try to convert it to a number
            try:
                area = float(area)
            except ValueError:
                return jsonify({'error': "Area must be a valid number"}), HTTP_400_BAD_REQUEST

    if bedrooms is not None: 
        if isinstance(bedrooms, int):
            # bedrooms is an integer
            pass
        else:
            try:
                bedrooms = int(bedrooms)
            except ValueError:
                return jsonify({'error': "Bedroom must be an whole number"}), HTTP_400_BAD_REQUEST
        
    if bathrooms is not None:
        if isinstance(bathrooms, int):
            # bathrooms is an integer
            pass
        else:
            try:
                bathrooms = int(bathrooms)
            except ValueError:
                return jsonify({'error': "Bathroom must be an whole number"}), HTTP_400_BAD_REQUEST
        
    if year_built is not None:
        if isinstance(year_built, int):
            # year_built is an integer
            pass
        else:
            try:
                year_built = int(year_built)
            except ValueError:
                return jsonify({'error': "Year built must be an whole number"}), HTTP_400_BAD_REQUEST
        
    if isinstance(amenities, dict):
        # amenities is a JSON object (dictionary)
        # Convert amenities to a JSON string
        amenities_str = json.dumps(amenities)
        # amenities_str = str(amenities)
    else:
        return jsonify({'error': "Amenities must be in json format"}), HTTP_400_BAD_REQUEST
    
    request_.title=title
    request_.description=description
    request_.sub_category=sub_category
    request_.property_type=property_type
    request_.min_price=min_price
    request_.max_price=max_price
    request_.area=area
    request_.bedrooms=bedrooms
    request_.bathrooms=bathrooms
    request_.location=location
    request_.city=city
    request_.state=state
    request_.country=country
    request_.year_built=year_built
    request_.amenities=amenities_str 
    request_.updated_at=datetime.now()

    db.session.commit()

    return jsonify({
        'id': request_.id,
        'user_id': request_.user_id,
        'title': request_.title,
        'description': request_.description,
        'property_type': request_.property_type,
        'sub_category': request_.sub_category,
        'min_price': request_.min_price,
        'max_price': request_.max_price,
        'area' : request_.area,
        'bedrooms' : request_.bedrooms,
        'bathrooms' : request_.bathrooms,
        'location' : request_.location,
        'city' : request_.city,
        'state' : request_.state,
        'country' : request_.country,
        'year_built': request_.year_built,
        'amenities': json.loads(request_.amenities),
        'created_at': request_.created_at,
        'updated_at': request_.updated_at,
    }), HTTP_200_OK


@requests.route('/user/<int:id>/', methods=['GET'])
def get_user_requests(id):
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    if not User.query.filter_by(id=id).first():
        return jsonify({'error': "User not found"}), HTTP_404_NOT_FOUND

    requests=Request.query.filter_by(user_id=id).paginate(page=page, per_page=per_page)

    data = []

    for request_ in requests.items:
        data.append({
            'id': request_.id,
            'user_id': request_.user_id,
            'title': request_.title,
            'property_type': request_.property_type,
            'location' : request_.location,
            'city' : request_.city,
            'state' : request_.state,
            'country' : request_.country,
            'created_at': request_.created_at,
            'updated_at': request_.updated_at,
        })

    meta={
        "page": requests.page,
        "pages": requests.pages,
        "total_count": requests.total,
        "prev_page": requests.prev_num,
        "next_page": requests.next_num,
        "has_next": requests.has_next,
        "has_prev": requests.has_prev
    }

    return jsonify({'data': data, 'meta':meta}), HTTP_200_OK


@requests.route('/<int:id>', methods=['DELETE'])
@jwt_required()
def delete_request(id):
    current_user = get_jwt_identity()

    request_ = Request.query.filter_by(id =id).first()

    if not request_:
        return jsonify({'msg': "Request not found"}), HTTP_404_NOT_FOUND
    
    if not request_.user_id == current_user:
        return jsonify({'error': "Unauthorized User"}), HTTP_401_UNAUTHORIZED

    db.session.delete(request_)
    db.session.commit()

    return jsonify({}), HTTP_204_NO_CONTENT
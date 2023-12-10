from src.constants.http_status_codes import HTTP_400_BAD_REQUEST
from src.constants.http_status_codes import HTTP_401_UNAUTHORIZED
from src.constants.http_status_codes import HTTP_404_NOT_FOUND
from src.constants.http_status_codes import HTTP_409_CONFLICT
from src.constants.http_status_codes import HTTP_200_OK
from src.constants.http_status_codes import HTTP_201_CREATED
from src.constants.http_status_codes import HTTP_202_ACCEPTED
from src.constants.http_status_codes import HTTP_204_NO_CONTENT
from flask import Blueprint, request
from src.database import Favorite, PropertyImage, Review,User, Property, db
from flask import Blueprint, request, jsonify
import validators
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
import os
import time
from datetime import datetime
from typing import Union
from sqlalchemy import func

favorites = Blueprint("favorite", __name__, url_prefix="/api/v1/favorites")

@favorites.post('/<int:id>')
@jwt_required()
def favorite_property(id):
    current_user = get_jwt_identity()

    if not Property.query.filter_by(id = id).first():
        return jsonify({'error': "Property not found"}), HTTP_404_NOT_FOUND
    
    # Check if the property is already favorited by the user
    existing_favorite = Favorite.query.filter_by(user_id=current_user, property_id=id).first()

    if existing_favorite:

        db.session.delete(existing_favorite )
        db.session.commit()

        return jsonify({'messsage': "Property unfavorited successfully"}), HTTP_200_OK
    
    favorite = Favorite(user_id=current_user, property_id=id, created_at=datetime.now(), updated_at=datetime.now())
    db.session.add(favorite)
    db.session.commit()

    return jsonify({'messsage': "Property favorited successfully"}), HTTP_200_OK


@favorites.route('/', methods=['GET'])
@jwt_required()
def get_user_favorites():
    current_user = get_jwt_identity()

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    favorites = Favorite.query.filter_by(user_id=current_user).paginate(page=page, per_page=per_page)

    if not favorites:
        return jsonify({}), HTTP_204_NO_CONTENT

    data = []

    for favorite in favorites.items:
        property = Favorite.query.filter_by(id=favorite.property_id).first()

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
        "page": favorites.page,
        "pages": favorites.pages,
        "total_count": favorites.total,
        "prev_page": favorites.prev_num,
        "next_page": favorites.next_num,
        "has_next": favorites.has_next,
        "has_prev": favorites.has_prev
    }

    return jsonify({'data': data, 'meta':meta}), HTTP_200_OK


@favorites.route('/properties/<int:id>', methods=['GET'])
@jwt_required()
def get_property_reviews(id):

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    property=Property.query.filter_by(id=id).first()

    reviews = Review.query.filter_by(property_id=id).paginate(page=page, per_page=per_page)

    data = []

    for review in reviews.items:
        user = User.query.filter_by(id = review.user_id).first()
        data.append({
            'id': review.id,
            'property_id': review.property_id,
            'user_id': review.user_id,
            'username' : user.username,
            'title': review.title,
            'content': review.content,
            'rating': review.rating,
            'created_at': review.created_at,
            'updated_at': review.updated_at
        })

    meta={
        "page": reviews.page,
        "pages": reviews.pages,
        "total_count": reviews.total,
        "prev_page": reviews.prev_num,
        "next_page": reviews.next_num,
        "has_next": reviews.has_next,
        "has_prev": reviews.has_prev
    }

    return jsonify({'data': data, 'meta':meta}), HTTP_200_OK
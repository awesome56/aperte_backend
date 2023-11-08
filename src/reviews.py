from src.constants.http_status_codes import HTTP_400_BAD_REQUEST
from src.constants.http_status_codes import HTTP_401_UNAUTHORIZED
from src.constants.http_status_codes import HTTP_404_NOT_FOUND
from src.constants.http_status_codes import HTTP_409_CONFLICT
from src.constants.http_status_codes import HTTP_200_OK
from src.constants.http_status_codes import HTTP_201_CREATED
from src.constants.http_status_codes import HTTP_202_ACCEPTED
from src.constants.http_status_codes import HTTP_204_NO_CONTENT
from flask import Blueprint, request
from src.database import Review, User, Property, db
from flask import Blueprint, request, jsonify
import validators
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
import os
import time
from datetime import datetime
from typing import Union

reviews = Blueprint("review", __name__, url_prefix="/api/v1/reviews")

@reviews.post('/<int:id>')
@jwt_required()
def create_review(id):
    current_user = get_jwt_identity()

    if not Property.query.filter_by(id = id).first():
        return jsonify({'error': "Property not found"}), HTTP_404_NOT_FOUND

    title: str
    content: str
    rating: Union[int, None]


    if request.is_json:
        title = request.json.get('title', '')
        content = request.json.get('content', '')
        rating = request.json.get('rating', None)
    else:
        title = request.form.get('title', '')
        content = request.form.get('content', '')
        rating = request.form.get('rating', None)

    if not title or not content:
        return jsonify({'error': "Title and Content must not be empty"}), HTTP_400_BAD_REQUEST 
    
    if rating is not None:
        if isinstance(rating, (int, float)):
            if 0 <= rating <= 5:
                pass
            else:
                return jsonify({'error': "Rating must be between 0 and 5"}), HTTP_400_BAD_REQUEST
        else:
            return jsonify({'error': "Rating must be a valid number and not greater than 5"}), HTTP_400_BAD_REQUEST

    review = Review(property_id=id, user_id=current_user, title=title, content=content, rating=rating, created_at=datetime.now(), updated_at=datetime.now())

    db.session.add(review)
    db.session.commit()

    user = User.query.filter_by(id = id).first()

    return jsonify({
        'id': review.id,
        'property_id': review.property_id,
        'user_id': review.user_id,
        'username' : user.username,
        'title': review.title,
        'content': review.content,
        'rating': review.rating,
        'created_at': review.created_at,
        'updated_at': review.updated_at
    }), HTTP_201_CREATED


@reviews.get("/<int:id>")
def get_review(id):

    review = Review.query.filter_by(id=id).first()

    if not review:
        return jsonify({'error': "Review not found"}),HTTP_404_NOT_FOUND
    
    user = User.query.filter_by(id = review.user_id).first()

    return jsonify({
        'id': review.id,
        'property_id': review.property_id,
        'user_id': review.user_id,
        'username' : user.username,
        'title': review.title,
        'content': review.content,
        'rating': review.rating,
        'created_at': review.created_at,
        'updated_at': review.updated_at
    }), HTTP_200_OK


@reviews.route('/properties/<int:id>', methods=['GET'])
def get_branch_reviews(id):

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


@reviews.route('/', methods=['GET'])
@jwt_required()
def get_user_reviews():
    current_user = get_jwt_identity()

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    reviews = Review.query.filter_by(user_id=current_user).paginate(page=page, per_page=per_page)

    if not reviews:
        return jsonify({'error': "Error getting reviews"}), HTTP_400_BAD_REQUEST

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


@reviews.route('/<int:id>', methods=['DELETE'])
@jwt_required()
def delete_review(id):
    current_user = get_jwt_identity()

    review = Review.query.filter_by(id =id).first()

    if not review:
        return jsonify({'msg': "Review not found"}), HTTP_404_NOT_FOUND
    
    if not review.user_id == current_user:
        return jsonify({'error': "Unauthorized User"}), HTTP_401_UNAUTHORIZED

    db.session.delete(review)
    db.session.commit()

    return jsonify({}), HTTP_204_NO_CONTENT
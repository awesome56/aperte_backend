from src.constants.http_status_codes import HTTP_400_BAD_REQUEST
from src.constants.http_status_codes import HTTP_404_NOT_FOUND
from src.constants.http_status_codes import HTTP_200_OK
from src.constants.http_status_codes import HTTP_204_NO_CONTENT
from flask import Blueprint, request, jsonify
from src.database import Favorite, PropertyImage, Review, User, Property, db
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
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

        db.session.delete(existing_favorite)
        db.session.commit()

        return jsonify({'message': "Property unfavorited successfully"}), HTTP_200_OK
    
    favorite = Favorite(user_id=current_user, property_id=id, created_at=datetime.now(), updated_at=datetime.now())
    db.session.add(favorite)
    db.session.commit()

    return jsonify({'message': "Property favorited successfully"}), HTTP_200_OK


@favorites.get('/check/<int:id>')
@jwt_required(optional=True)
def check_favorite(id):

    if not Property.query.filter_by(id=id).first():
        return jsonify({'error': "Property not found"}), HTTP_404_NOT_FOUND

    current_user = get_jwt_identity()

    if current_user is None:
        return jsonify({'favorited': False}), HTTP_200_OK

    existing_favorite = Favorite.query.filter_by(user_id=current_user, property_id=id).first()

    return jsonify({'favorited': existing_favorite is not None}), HTTP_200_OK


@favorites.route('/', methods=['GET'])
@jwt_required()
def get_user_favorites():
    current_user = get_jwt_identity()

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    favorites = Favorite.query.filter_by(user_id=current_user).order_by(Favorite.created_at.desc()).paginate(page=page, per_page=per_page)

    if not favorites.items:
        return jsonify({'data': [], 'meta': {}}), HTTP_200_OK

    data = []

    for favorite in favorites.items:
        property = Property.query.filter_by(id=favorite.property_id).first()

        if not property:
            continue

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
            'created_at': property.created_at,
            'updated_at': property.updated_at,
            'average_rating': average_rating,
            'username': user.username if user else None,
            'owner_full_name': user.full_name if user else None,
            'contact_phone': property.contact_phone,
            'contact_email': property.contact_email,
            'contact_website': property.contact_website,
            'favorited': True,
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

    return jsonify({'data': data, 'meta': meta}), HTTP_200_OK

from src.constants.http_status_codes import HTTP_400_BAD_REQUEST
from src.constants.http_status_codes import HTTP_401_UNAUTHORIZED
from src.constants.http_status_codes import HTTP_403_FORBIDDEN
from src.constants.http_status_codes import HTTP_404_NOT_FOUND
from src.constants.http_status_codes import HTTP_200_OK
from src.constants.http_status_codes import HTTP_201_CREATED
from src.constants.http_status_codes import HTTP_204_NO_CONTENT
from flask import Blueprint, request, jsonify
from src.database import db, User, Property, Booking, Room, PropertyImage
from src.constants.permissions import admin_required
from flask_jwt_extended import get_jwt_identity
from datetime import datetime
import json
from sqlalchemy import func
from flasgger import swag_from


admin = Blueprint("admin", __name__, url_prefix="/api/v1/admin")


def user_summary(u):
    return {
        'id': u.id,
        'username': u.username,
        'email': u.email,
        'full_name': u.full_name,
        'phone_number': u.phone_number,
        'profile_picture': u.profile_picture,
        'email_verified': u.email_verified,
        'role': u.role,
        'created_at': u.created_at,
        'updated_at': u.updated_at,
    }


@admin.get("/stats")
@admin_required
@swag_from('./docs/admin/stats.yml')
def get_stats():
    total_users = User.query.count()
    total_properties = Property.query.count()
    pending_properties = Property.query.filter_by(approved=0).count()
    approved_properties = Property.query.filter_by(approved=1).count()
    total_bookings = Booking.query.count()
    total_rooms = Room.query.count()
    hotels = Property.query.filter_by(category='hotel').count()
    shortlets = Property.query.filter_by(category='shortlet').count()

    return jsonify({
        'total_users': total_users,
        'total_properties': total_properties,
        'pending_properties': pending_properties,
        'approved_properties': approved_properties,
        'total_bookings': total_bookings,
        'total_rooms': total_rooms,
        'hotels': hotels,
        'shortlets': shortlets,
    }), HTTP_200_OK


@admin.get("/users")
@admin_required
@swag_from('./docs/admin/users.yml')
def get_users():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search')

    query = User.query

    if search:
        query = query.filter(
            func.lower(User.username).like('%{}%'.format(search.lower())) |
            func.lower(User.email).like('%{}%'.format(search.lower())) |
            func.lower(User.full_name).like('%{}%'.format(search.lower()))
        )

    users = query.order_by(User.created_at.desc()).paginate(page=page, per_page=per_page)

    data = [user_summary(u) for u in users.items]

    meta = {
        "page": users.page,
        "pages": users.pages,
        "total_count": users.total,
        "prev_page": users.prev_num,
        "next_page": users.next_num,
        "has_next": users.has_next,
        "has_prev": users.has_prev
    }

    return jsonify({'data': data, 'meta': meta}), HTTP_200_OK


@admin.put("/users/<int:id>/role")
@admin_required
@swag_from('./docs/admin/userrole.yml')
def update_user_role(id):
    current_admin = get_jwt_identity()
    user = User.query.filter_by(id=id).first()

    if not user:
        return jsonify({'error': "User not found"}), HTTP_404_NOT_FOUND

    if user.id == current_admin:
        return jsonify({'error': "You cannot change your own role"}), HTTP_400_BAD_REQUEST

    role = request.get_json().get('role', '')
    if role not in ('user', 'admin'):
        return jsonify({'error': "Role must be one of: user, admin"}), HTTP_400_BAD_REQUEST

    user.role = role
    user.updated_at = datetime.now()
    db.session.commit()

    return jsonify(user_summary(user)), HTTP_200_OK


@admin.delete("/users/<int:id>")
@admin_required
@swag_from('./docs/admin/deleteuser.yml')
def delete_user(id):
    current_admin = get_jwt_identity()
    user = User.query.filter_by(id=id).first()

    if not user:
        return jsonify({'error': "User not found"}), HTTP_404_NOT_FOUND

    if user.id == current_admin:
        return jsonify({'error': "You cannot delete your own account"}), HTTP_400_BAD_REQUEST

    db.session.delete(user)
    db.session.commit()

    return jsonify({}), HTTP_204_NO_CONTENT


@admin.get("/properties")
@admin_required
@swag_from('./docs/admin/properties.yml')
def get_all_properties():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')  # approved / pending / all
    category = request.args.get('category')
    search = request.args.get('search')

    query = Property.query

    if status == 'approved':
        query = query.filter_by(approved=1)
    elif status == 'pending':
        query = query.filter_by(approved=0)

    if category:
        query = query.filter_by(category=category)

    if search:
        query = query.filter(
            func.lower(Property.title).like('%{}%'.format(search.lower())) |
            func.lower(Property.city).like('%{}%'.format(search.lower()))
        )

    properties = query.order_by(Property.created_at.desc()).paginate(page=page, per_page=per_page)

    data = []
    for p in properties.items:
        user = User.query.filter_by(id=p.user_id).first()
        dp = PropertyImage.query.filter_by(property_id=p.id, dp=1).first()
        data.append({
            'id': p.id,
            'user_id': p.user_id,
            'title': p.title,
            'category': p.category,
            'property_type': p.property_type,
            'purpose': p.purpose,
            'price': p.price,
            'currency': p.currency,
            'city': p.city,
            'state': p.state,
            'country': p.country,
            'dp': dp.image_url if dp else "",
            'approved': p.approved,
            'available': p.available,
            'username': user.username if user else None,
            'created_at': p.created_at,
        })

    meta = {
        "page": properties.page,
        "pages": properties.pages,
        "total_count": properties.total,
        "prev_page": properties.prev_num,
        "next_page": properties.next_num,
        "has_next": properties.has_next,
        "has_prev": properties.has_prev
    }

    return jsonify({'data': data, 'meta': meta}), HTTP_200_OK


@admin.put("/properties/<int:id>/approve")
@admin_required
@swag_from('./docs/admin/approveproperty.yml')
def approve_property(id):
    property = Property.query.filter_by(id=id).first()

    if not property:
        return jsonify({'error': "Property not found"}), HTTP_404_NOT_FOUND

    property.approved = 1
    property.updated_at = datetime.now()
    db.session.commit()

    return jsonify({'id': property.id, 'approved': property.approved}), HTTP_200_OK


@admin.put("/properties/<int:id>/reject")
@admin_required
@swag_from('./docs/admin/rejectproperty.yml')
def reject_property(id):
    property = Property.query.filter_by(id=id).first()

    if not property:
        return jsonify({'error': "Property not found"}), HTTP_404_NOT_FOUND

    property.approved = 0
    property.updated_at = datetime.now()
    db.session.commit()

    return jsonify({'id': property.id, 'approved': property.approved}), HTTP_200_OK


@admin.delete("/properties/<int:id>")
@admin_required
@swag_from('./docs/admin/deleteproperty.yml')
def delete_property(id):
    property = Property.query.filter_by(id=id).first()

    if not property:
        return jsonify({'error': "Property not found"}), HTTP_404_NOT_FOUND

    db.session.delete(property)
    db.session.commit()

    return jsonify({}), HTTP_204_NO_CONTENT

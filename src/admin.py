from src.constants.http_status_codes import HTTP_400_BAD_REQUEST
from src.constants.http_status_codes import HTTP_401_UNAUTHORIZED
from src.constants.http_status_codes import HTTP_403_FORBIDDEN
from src.constants.http_status_codes import HTTP_404_NOT_FOUND
from src.constants.http_status_codes import HTTP_200_OK
from src.constants.http_status_codes import HTTP_201_CREATED
from src.constants.http_status_codes import HTTP_204_NO_CONTENT
from flask import Blueprint, request, jsonify
from src.database import db, User, Property, Booking, Room, PropertyImage, Role, Permission, role_permissions, Favorite, PageVisit, PropertyClaim
from src.constants.permissions import permission_required, PERMISSION_CATALOG
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
        'role_id': u.role_id,
        'created_at': u.created_at,
        'updated_at': u.updated_at,
    }


def role_summary(r):
    return {
        'id': r.id,
        'name': r.name,
        'description': r.description,
        'permissions': sorted([p.name for p in r.permissions.all()]),
        'created_at': r.created_at,
    }


# ---------- Permissions ----------

@admin.get("/permissions")
@permission_required('roles.view')
@swag_from('./docs/admin/permissions.yml')
def get_permissions():
    perms = Permission.query.order_by(Permission.name.asc()).all()
    return jsonify({'data': [{'id': p.id, 'name': p.name, 'description': p.description} for p in perms]}), HTTP_200_OK


@admin.post("/permissions/seed")
@permission_required('permissions.manage')
def seed_permissions():
    """Insert any permissions from the catalog that are missing (idempotent)."""
    added = 0
    for p in PERMISSION_CATALOG:
        if not Permission.query.filter_by(name=p['name']).first():
            db.session.add(Permission(name=p['name'], description=p['description']))
            added += 1
    db.session.commit()
    return jsonify({'added': added}), HTTP_200_OK


# ---------- Roles ----------

@admin.get("/roles")
@permission_required('roles.view')
@swag_from('./docs/admin/roles.yml')
def get_roles():
    roles = Role.query.order_by(Role.name.asc()).all()
    return jsonify({'data': [role_summary(r) for r in roles]}), HTTP_200_OK


@admin.post("/roles")
@permission_required('roles.manage')
@swag_from('./docs/admin/createrole.yml')
def create_role():
    name = request.get_json().get('name', '').strip()
    description = request.get_json().get('description', '').strip()

    if not name:
        return jsonify({'error': "Role name is required"}), HTTP_400_BAD_REQUEST

    if Role.query.filter_by(name=name).first():
        return jsonify({'error': "Role already exists"}), HTTP_400_BAD_REQUEST

    role = Role(name=name, description=description, created_at=datetime.now())
    db.session.add(role)
    db.session.commit()

    return jsonify(role_summary(role)), HTTP_201_CREATED


@admin.put("/roles/<int:id>")
@permission_required('roles.manage')
@swag_from('./docs/admin/editrole.yml')
def edit_role(id):
    role = Role.query.filter_by(id=id).first()
    if not role:
        return jsonify({'error': "Role not found"}), HTTP_404_NOT_FOUND

    name = request.get_json().get('name', role.name).strip()
    description = request.get_json().get('description', role.description)

    if not name:
        return jsonify({'error': "Role name is required"}), HTTP_400_BAD_REQUEST

    existing = Role.query.filter(Role.name == name, Role.id != role.id).first()
    if existing:
        return jsonify({'error': "Role already exists"}), HTTP_400_BAD_REQUEST

    role.name = name
    role.description = description
    db.session.commit()

    return jsonify(role_summary(role)), HTTP_200_OK


@admin.delete("/roles/<int:id>")
@permission_required('roles.manage')
@swag_from('./docs/admin/deleterole.yml')
def delete_role(id):
    role = Role.query.filter_by(id=id).first()
    if not role:
        return jsonify({'error': "Role not found"}), HTTP_404_NOT_FOUND

    if role.name in ('user', 'admin'):
        return jsonify({'error': "The built-in '{}' role cannot be deleted".format(role.name)}), HTTP_400_BAD_REQUEST

    # Users with this role fall back to their legacy role string
    User.query.filter_by(role_id=role.id).update({'role_id': None})
    db.session.delete(role)
    db.session.commit()

    return jsonify({}), HTTP_204_NO_CONTENT


@admin.put("/roles/<int:id>/permissions")
@permission_required('permissions.manage')
@swag_from('./docs/admin/rolepermissions.yml')
def set_role_permissions(id):
    """Replace the full permission set of a role."""
    role = Role.query.filter_by(id=id).first()
    if not role:
        return jsonify({'error': "Role not found"}), HTTP_404_NOT_FOUND

    permission_names = request.get_json().get('permissions', [])
    if not isinstance(permission_names, list):
        return jsonify({'error': "Permissions must be a list of names"}), HTTP_400_BAD_REQUEST

    permissions = Permission.query.filter(Permission.name.in_(permission_names)).all()
    role.permissions = permissions
    db.session.commit()

    return jsonify(role_summary(role)), HTTP_200_OK


@admin.post("/roles/<int:id>/permissions/<permission_name>")
@permission_required('permissions.manage')
@swag_from('./docs/admin/addrolepermission.yml')
def add_role_permission(id, permission_name):
    role = Role.query.filter_by(id=id).first()
    if not role:
        return jsonify({'error': "Role not found"}), HTTP_404_NOT_FOUND

    permission = Permission.query.filter_by(name=permission_name).first()
    if not permission:
        return jsonify({'error': "Permission not found"}), HTTP_404_NOT_FOUND

    if permission not in role.permissions.all():
        role.permissions.append(permission)
        db.session.commit()

    return jsonify(role_summary(role)), HTTP_200_OK


@admin.delete("/roles/<int:id>/permissions/<permission_name>")
@permission_required('permissions.manage')
@swag_from('./docs/admin/removerolepermission.yml')
def remove_role_permission(id, permission_name):
    role = Role.query.filter_by(id=id).first()
    if not role:
        return jsonify({'error': "Role not found"}), HTTP_404_NOT_FOUND

    permission = Permission.query.filter_by(name=permission_name).first()
    if permission and permission in role.permissions.all():
        role.permissions.remove(permission)
        db.session.commit()

    return jsonify(role_summary(role)), HTTP_200_OK


@admin.get("/stats")
@permission_required('stats.view')
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


@admin.get("/analytics")
@permission_required('stats.view')
def get_analytics():
    from datetime import datetime as dt, timedelta
    today = dt.now().date()

    def start_of_day(days_ago=0):
        return dt(today.year, today.month, today.day) - timedelta(days=days_ago)

    total_page_views = PageVisit.query.count()
    unique_visitors = db.session.query(func.count(func.distinct(PageVisit.visitor_id))).scalar()
    views_today = PageVisit.query.filter(PageVisit.created_at >= start_of_day(0)).count()
    views_7d = PageVisit.query.filter(PageVisit.created_at >= start_of_day(6)).count()

    new_visitors_today = db.session.query(func.count(func.distinct(PageVisit.visitor_id))).filter(
        PageVisit.created_at >= start_of_day(0)).scalar()
    new_visitors_7d = db.session.query(func.count(func.distinct(PageVisit.visitor_id))).filter(
        PageVisit.created_at >= start_of_day(6)).scalar()

    # most viewed properties
    top_properties = Property.query.order_by(Property.views.desc()).limit(10).all()
    top_props = []
    for p in top_properties:
        dp = PropertyImage.query.filter_by(property_id=p.id, dp=1).first()
        top_props.append({
            'id': p.id,
            'title': p.title,
            'views': p.views,
            'dp': dp.image_url if dp else "",
            'price': p.price,
            'currency': p.currency,
            'location': p.location,
            'city': p.city,
            'state': p.state,
        })

    # most favorited properties
    fav_rows = db.session.query(
        Favorite.property_id,
        func.count(Favorite.id).label('cnt')
    ).group_by(Favorite.property_id).order_by(func.count(Favorite.id).desc()).limit(10).all()
    fav_props = []
    for row in fav_rows:
        p = Property.query.filter_by(id=row.property_id).first()
        if not p:
            continue
        dp = PropertyImage.query.filter_by(property_id=p.id, dp=1).first()
        fav_props.append({
            'id': p.id,
            'title': p.title,
            'favorites_count': row.cnt,
            'dp': dp.image_url if dp else "",
            'price': p.price,
            'currency': p.currency,
        })

    # top pages
    page_rows = db.session.query(
        PageVisit.path,
        func.count(PageVisit.id).label('cnt')
    ).group_by(PageVisit.path).order_by(func.count(PageVisit.id).desc()).limit(10).all()
    top_pages = [{'path': r.path, 'count': r.cnt} for r in page_rows]

    # views by day (last 14 days)
    since = start_of_day(13)
    day_rows = db.session.query(
        func.date(PageVisit.created_at).label('day'),
        func.count(PageVisit.id).label('cnt')
    ).filter(PageVisit.created_at >= since).group_by('day').all()
    counts_by_day = {str(r.day): r.cnt for r in day_rows}
    views_by_day = []
    for offset in range(13, -1, -1):
        day = today - timedelta(days=offset)
        views_by_day.append({'date': str(day), 'count': counts_by_day.get(str(day), 0)})

    total_favorites = Favorite.query.count()
    total_property_views = db.session.query(func.coalesce(func.sum(Property.views), 0)).scalar()

    return jsonify({
        'total_page_views': total_page_views,
        'unique_visitors': unique_visitors,
        'views_today': views_today,
        'views_7d': views_7d,
        'new_visitors_today': new_visitors_today,
        'new_visitors_7d': new_visitors_7d,
        'total_favorites': total_favorites,
        'total_property_views': total_property_views,
        'top_properties': top_props,
        'favorite_properties': fav_props,
        'top_pages': top_pages,
        'views_by_day': views_by_day,
    }), HTTP_200_OK


@admin.get("/users")
@permission_required('users.view')
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


@admin.get("/claims")
@permission_required('properties.approve')
def list_claims():
    status = request.args.get('status', 'pending')

    query = PropertyClaim.query
    if status == 'pending':
        # the Pending tab shows both verification-in-progress and submitted claims
        query = query.filter(PropertyClaim.status.in_(('pending_verification', 'pending')))
    elif status:
        query = query.filter(PropertyClaim.status == status)

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    claims = query.order_by(PropertyClaim.created_at.desc()).paginate(page=page, per_page=per_page)

    data = []
    for c in claims.items:
        p = Property.query.filter_by(id=c.property_id).first()
        u = User.query.filter_by(id=c.user_id).first()
        dp = PropertyImage.query.filter_by(property_id=c.property_id, dp=1).first()
        data.append({
            'id': c.id,
            'status': c.status,
            'created_at': c.created_at,
            'updated_at': c.updated_at,
            'property': {
                'id': c.property_id,
                'title': p.title if p else 'Property #{}'.format(c.property_id),
                'price': p.price if p else None,
                'currency': p.currency if p else None,
                'city': p.city if p else None,
                'state': p.state if p else None,
                'dp': dp.image_url if dp else "",
            },
            'user': {
                'id': c.user_id,
                'username': u.username if u else None,
                'full_name': u.full_name if u else None,
                'email': u.email if u else None,
            },
        })

    meta = {
        "page": claims.page,
        "pages": claims.pages,
        "total_count": claims.total,
        "prev_page": claims.prev_num,
        "next_page": claims.next_num,
        "has_next": claims.has_next,
        "has_prev": claims.has_prev,
    }

    return jsonify({'data': data, 'meta': meta}), HTTP_200_OK


@admin.put("/claims/<int:claim_id>")
@permission_required('properties.approve')
def decide_claim(claim_id):
    claim = PropertyClaim.query.filter_by(id=claim_id).first()

    if not claim:
        return jsonify({'error': "Claim not found"}), HTTP_404_NOT_FOUND

    if claim.status != 'pending':
        if claim.status == 'pending_verification':
            return jsonify({'error': "Claimant has not completed verification yet"}), HTTP_400_BAD_REQUEST
        return jsonify({'error': "Claim has already been decided"}), HTTP_400_BAD_REQUEST

    data = request.get_json(silent=True) or {}
    approved = data.get('approved', True)

    if approved:
        property_ = Property.query.filter_by(id=claim.property_id).first()
        if not property_:
            return jsonify({'error': "Property not found"}), HTTP_404_NOT_FOUND
        claimant = User.query.filter_by(id=claim.user_id).first()
        if not claimant:
            return jsonify({'error': "Claimant not found"}), HTTP_404_NOT_FOUND

        # transfer ownership to the claimant
        property_.user_id = claimant.id
        property_.updated_at = datetime.now()
        claim.status = 'approved'

        # any other pending claim on this property is now moot
        PropertyClaim.query.filter(
            PropertyClaim.property_id == claim.property_id,
            PropertyClaim.id != claim.id,
            PropertyClaim.status == 'pending',
        ).update({'status': 'rejected', 'updated_at': datetime.now()})
    else:
        claim.status = 'rejected'

    claim.updated_at = datetime.now()
    db.session.commit()

    return jsonify({'message': "Claim approved — ownership transferred" if approved else "Claim rejected"}), HTTP_200_OK


@admin.put("/users/<int:id>/verify")
@permission_required('users.verify')
def verify_user(id):
    user = User.query.filter_by(id=id).first()

    if not user:
        return jsonify({'error': "User not found"}), HTTP_404_NOT_FOUND

    data = request.get_json(silent=True) or {}
    verified = data.get('verified', True)

    user.email_verified = 1 if verified else 0
    user.updated_at = datetime.now()
    db.session.commit()

    return jsonify({
        'message': "User verified" if verified else "User unverified",
        'user': user_summary(user),
    }), HTTP_200_OK


@admin.put("/users/<int:id>/role")
@permission_required('users.assign_role')
@swag_from('./docs/admin/userrole.yml')
def update_user_role(id):
    current_admin = get_jwt_identity()
    user = User.query.filter_by(id=id).first()

    if not user:
        return jsonify({'error': "User not found"}), HTTP_404_NOT_FOUND

    if user.id == current_admin:
        return jsonify({'error': "You cannot change your own role"}), HTTP_400_BAD_REQUEST

    role_name = request.get_json().get('role', '').strip()
    role = Role.query.filter_by(name=role_name).first()

    if not role:
        return jsonify({'error': "Role not found. Available roles: {}".format(
            ', '.join(r.name for r in Role.query.order_by(Role.name).all())
        )}), HTTP_400_BAD_REQUEST

    # Keep the legacy `role` string in sync for JWT compatibility
    user.role = role.name
    user.role_id = role.id
    user.updated_at = datetime.now()
    db.session.commit()

    return jsonify(user_summary(user)), HTTP_200_OK


@admin.delete("/users/<int:id>")
@permission_required('users.manage')
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
@permission_required('properties.view')
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
@permission_required('properties.approve')
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
@permission_required('properties.approve')
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
@permission_required('properties.delete')
@swag_from('./docs/admin/deleteproperty.yml')
def delete_property(id):
    property = Property.query.filter_by(id=id).first()

    if not property:
        return jsonify({'error': "Property not found"}), HTTP_404_NOT_FOUND

    db.session.delete(property)
    db.session.commit()

    return jsonify({}), HTTP_204_NO_CONTENT

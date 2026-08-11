from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt, jwt_required, get_jwt_identity
from src.constants.http_status_codes import HTTP_401_UNAUTHORIZED
from src.constants.http_status_codes import HTTP_403_FORBIDDEN

# The full catalog of permissions in the system.
# Used to seed the `permission` table and to document available permissions.
PERMISSION_CATALOG = [
    # Properties
    {'name': 'properties.view', 'description': 'View all properties'},
    {'name': 'properties.create', 'description': 'Create property listings'},
    {'name': 'properties.edit', 'description': 'Edit any property'},
    {'name': 'properties.delete', 'description': 'Delete any property'},
    {'name': 'properties.approve', 'description': 'Approve or reject properties'},
    # Users
    {'name': 'users.view', 'description': 'View all users'},
    {'name': 'users.manage', 'description': 'Delete users'},
    # Roles & permissions
    {'name': 'roles.view', 'description': 'View roles and their permissions'},
    {'name': 'roles.manage', 'description': 'Create/edit/delete roles'},
    {'name': 'permissions.manage', 'description': 'Add/remove permissions on roles'},
    {'name': 'users.assign_role', 'description': 'Assign roles to users'},
    # Bookings
    {'name': 'bookings.view', 'description': 'View all bookings'},
    {'name': 'bookings.manage', 'description': 'Manage bookings'},
]

# Role hierarchy for the legacy `role` string field (admin > user)
ROLE_HIERARCHY = {
    'user': 1,
    'admin': 100,
}


def has_role(role, required):
    return ROLE_HIERARCHY.get(role, 0) >= ROLE_HIERARCHY.get(required, 0)


def role_required(*roles):
    """Decorator that requires the JWT subject's legacy role string to be one of `roles`."""
    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            claims = get_jwt()
            role = claims.get('role', 'user')
            if role not in roles:
                return jsonify({'error': "Insufficient permissions"}), HTTP_403_FORBIDDEN
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def admin_required(fn):
    """Shortcut for admin-only routes (legacy role check)."""
    return role_required('admin')(fn)


def get_user_permissions():
    """Resolve the set of permission names for the current JWT subject.

    Reads permissions from the user's Role object. Falls back to legacy
    behavior: role 'admin' implies all permissions, role 'user' implies none.
    """
    from src.database import db, User, Role, Permission, role_permissions

    user_id = get_jwt_identity()
    user = User.query.filter_by(id=user_id).first()
    if not user:
        return set()

    # Legacy admin -> everything
    if user.role == 'admin':
        return {p.name for p in Permission.query.all()}

    if user.role_id:
        role = Role.query.filter_by(id=user.role_id).first()
        if role:
            return {p.name for p in role.permissions.all()}

    return set()


def permission_required(permission_name):
    """Decorator that requires the current user to hold a specific permission."""
    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            perms = get_user_permissions()
            if permission_name not in perms:
                return jsonify({'error': "Insufficient permissions"}), HTTP_403_FORBIDDEN
            return fn(*args, **kwargs)
        return wrapper
    return decorator

from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt, jwt_required
from src.constants.http_status_codes import HTTP_401_UNAUTHORIZED
from src.constants.http_status_codes import HTTP_403_FORBIDDEN

# Role hierarchy: admin > user
ROLE_HIERARCHY = {
    'user': 1,
    'admin': 100,
}


def has_role(role, required):
    return ROLE_HIERARCHY.get(role, 0) >= ROLE_HIERARCHY.get(required, 0)


def role_required(*roles):
    """Decorator that requires the JWT subject's role to be one of `roles`."""
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
    """Shortcut for admin-only routes."""
    return role_required('admin')(fn)

from src.constants.http_status_codes import HTTP_200_OK
from src.constants.http_status_codes import HTTP_400_BAD_REQUEST
from flask import Blueprint, request, jsonify
from src.database import PageVisit, Property, db
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
import validators

tracking = Blueprint("tracking", __name__, url_prefix="/api/v1/tracking")


@tracking.post('/pageview')
@jwt_required(optional=True)
def track_pageview():

    data = request.get_json(silent=True) or {}

    path = (data.get('path') or '').strip()
    if not path:
        return jsonify({'error': "Path must not be empty"}), HTTP_400_BAD_REQUEST

    visitor_id = (data.get('visitor_id') or request.headers.get('X-Visitor-Id') or '').strip()
    if not visitor_id:
        return jsonify({'error': "Visitor id must not be empty"}), HTTP_400_BAD_REQUEST

    if not (1 <= len(visitor_id) <= 64):
        return jsonify({'error': "Visitor id must be between 1 and 64 characters"}), HTTP_400_BAD_REQUEST

    property_id = data.get('property_id')
    if property_id is not None:
        try:
            property_id = int(property_id)
        except (ValueError, TypeError):
            property_id = None
        if property_id is not None and not Property.query.filter_by(id=property_id).first():
            property_id = None

    referrer = (data.get('referrer') or '')
    if referrer and not validators.url(referrer):
        referrer = None

    user_agent = request.headers.get('User-Agent', '')[:255]

    visit = PageVisit(
        visitor_id=visitor_id[:64],
        user_id=get_jwt_identity(),
        property_id=property_id,
        path=path[:255],
        referrer=referrer[:255] if referrer else None,
        user_agent=user_agent or None,
        created_at=datetime.now(),
    )
    db.session.add(visit)
    db.session.commit()

    return jsonify({'message': "Page view recorded"}), HTTP_200_OK

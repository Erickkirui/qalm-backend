
from functools import wraps

from flask_jwt_extended import jwt_required, get_jwt_identity
from flask import jsonify

from app import db
from Server.Models.Users import Users


def check_role(*allowed_roles):
    """
    Protect an endpoint using JWT authentication and allowed user roles.

    Example:
        @check_role("admin")
        def get(self):
            ...
    """
    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            identity = get_jwt_identity()

            try:
                user = db.session.get(Users, int(identity))
            except (ValueError, TypeError):
                user = None

            if not user:
                return jsonify({
                    "message": "User account not found."
                }), 401

            if user.status != "active":
                return jsonify({
                    "message": "Your account is not active."
                }), 403

            if user.role not in allowed_roles:
                return jsonify({
                    "message": "You do not have permission to access this resource."
                }), 403

            return fn(*args, **kwargs)

        return wrapper

    return decorator

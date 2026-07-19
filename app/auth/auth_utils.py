from functools import wraps
from flask import session, jsonify

def auth_required(role=None):
    """
    Unified decorator to check:
    - If user is logged in
    - If user has the correct role (optional)
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check if user is logged in
            if 'email' not in session:
                return jsonify({"message": "Login required."}), 401

            # Check if role matches, if a role is specified
            if role and session.get('role') != role:
                return jsonify({"message": "Access denied. Role mismatch."}), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator

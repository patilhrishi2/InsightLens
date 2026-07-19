from flask import Blueprint, request, jsonify, session
from db import users_collection
from pymongo.errors import DuplicateKeyError
from flask import render_template
auth_bp = Blueprint('auth', __name__)


# ========================= Login Page ==========================
@auth_bp.route('/login', methods=['GET'])
def login_page():
    return render_template('loginPage.html')

# ===========================
# Signup Route
# ===========================
@auth_bp.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    role = data.get('role')  # 'candidate' or 'hr'

    if role not in ['candidate', 'hr']:
        return jsonify({"message": "Invalid role. Must be 'candidate' or 'hr'."}), 400

    try:
        users_collection.insert_one({
            'name': name,
            "email": email,
            "password": password,  # Plain text (as per your request)
            "role": role
        })
        return jsonify({"message": "User registered successfully."}), 201
    except DuplicateKeyError:
        return jsonify({"message": "Email already exists."}), 409
    
    except Exception as e:
        print(f"[ERROR] Registration failed: {e}")
        return jsonify({"message": "Registration failed."}), 500

# ===========================
# Login Route
# ===========================
@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()  # ✅ Correct: parentheses required
    email = data.get('emailID')
    password = data.get('password')
    role = data.get('role')

    if not email or not password or not role:
        return jsonify({"success": False, "message": "All fields are required."}), 400

    # ✅ Find user with matching email, password, and role
    user = users_collection.find_one({"email": email, "password": password, "role": role})

    if user:
        session.permanent = True  # Enable session expiry
        session['email'] = email
        session['role'] = role
        return jsonify({"success": True, "message": f"Login successful as {role}."}), 200
    else:
        return jsonify({"success": False, "message": "Invalid credentials or role mismatch."}), 401

# ===========================
# Logout Route
# ===========================
from flask import redirect, url_for

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing_page'))


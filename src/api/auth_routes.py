"""
Authentication Routes

This module defines the authentication endpoints for the API.
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    jwt_required, get_jwt_identity, get_jwt,
    create_access_token, set_access_cookies
)
import datetime
from .auth import hash_password, verify_password, generate_tokens, log_user_activity

# Create Blueprint
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Register a new user.
    
    Request body:
        username (str): Username
        email (str): Email address
        password (str): Password
        first_name (str): First name
        last_name (str): Last name
        role_id (int): Role ID (optional, defaults to lowest privilege)
        
    Returns:
        JSON: User information and tokens
    """
    from app import create_db_connection
    
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['username', 'email', 'password', 'first_name', 'last_name']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400
    
    connection = create_db_connection()
    if connection is None:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Check if username or email already exists
        cursor.execute(
            "SELECT * FROM users WHERE username = %s OR email = %s", 
            (data['username'], data['email'])
        )
        
        if cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({"error": "Username or email already exists"}), 409
        
        # Hash password
        hashed_password = hash_password(data['password'])
        
        # Default role to receptionist if not specified
        role_id = data.get('role_id', 4)  # 4 is receptionist in our default roles
        
        # Insert user
        insert_query = """
        INSERT INTO users (
            username, email, password_hash, first_name, last_name, role_id
        ) VALUES (%s, %s, %s, %s, %s, %s)
        """
        
        cursor.execute(
            insert_query, 
            (
                data['username'], 
                data['email'], 
                hashed_password, 
                data['first_name'], 
                data['last_name'], 
                role_id
            )
        )
        
        connection.commit()
        
        # Get the inserted user
        user_id = cursor.lastrowid
        
        # Get role name
        cursor.execute("SELECT role_name FROM roles WHERE role_id = %s", (role_id,))
        role = cursor.fetchone()
        role_name = role['role_name'] if role else 'unknown'
        
        # Generate tokens
        access_token, refresh_token = generate_tokens(
            user_id, data['username'], role_name
        )
        
        # Log activity
        log_user_activity(
            user_id, 
            "register", 
            f"User registered with username {data['username']}", 
            connection
        )
        
        cursor.close()
        connection.close()
        
        return jsonify({
            "message": "User registered successfully",
            "user_id": user_id,
            "username": data['username'],
            "role": role_name,
            "access_token": access_token,
            "refresh_token": refresh_token
        }), 201
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Login a user.
    
    Request body:
        username (str): Username or email
        password (str): Password
        
    Returns:
        JSON: User information and tokens
    """
    from app import create_db_connection
    
    data = request.get_json()
    
    # Validate required fields
    if 'username' not in data or 'password' not in data:
        return jsonify({"error": "Username and password are required"}), 400
    
    connection = create_db_connection()
    if connection is None:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Check if username is actually an email
        is_email = '@' in data['username']
        
        if is_email:
            cursor.execute(
                "SELECT * FROM users WHERE email = %s", 
                (data['username'],)
            )
        else:
            cursor.execute(
                "SELECT * FROM users WHERE username = %s", 
                (data['username'],)
            )
        
        user = cursor.fetchone()
        
        if not user or not verify_password(user['password_hash'], data['password']):
            cursor.close()
            connection.close()
            return jsonify({"error": "Invalid username or password"}), 401
        
        # Check if user is active
        if not user['is_active']:
            cursor.close()
            connection.close()
            return jsonify({"error": "Account is disabled"}), 403
        
        # Get role name
        cursor.execute(
            "SELECT role_name FROM roles WHERE role_id = %s", 
            (user['role_id'],)
        )
        role = cursor.fetchone()
        role_name = role['role_name'] if role else 'unknown'
        
        # Generate tokens
        access_token, refresh_token = generate_tokens(
            user['user_id'], user['username'], role_name
        )
        
        # Update last login
        cursor.execute(
            "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE user_id = %s", 
            (user['user_id'],)
        )
        
        # Create session
        session_id = access_token
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=30)
        
        cursor.execute(
            """
            INSERT INTO user_sessions (
                session_id, user_id, ip_address, user_agent, expires_at
            ) VALUES (%s, %s, %s, %s, %s)
            """,
            (
                session_id, 
                user['user_id'], 
                request.remote_addr, 
                request.user_agent.string, 
                expires_at
            )
        )
        
        connection.commit()
        
        # Log activity
        log_user_activity(
            user['user_id'], 
            "login", 
            f"User logged in from {request.remote_addr}", 
            connection
        )
        
        cursor.close()
        connection.close()
        
        return jsonify({
            "message": "Login successful",
            "user_id": user['user_id'],
            "username": user['username'],
            "first_name": user['first_name'],
            "last_name": user['last_name'],
            "role": role_name,
            "access_token": access_token,
            "refresh_token": refresh_token
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """
    Refresh access token using refresh token.
    
    Returns:
        JSON: New access token
    """
    identity = get_jwt_identity()
    claims = get_jwt()
    
    # Create new access token
    access_token = create_access_token(
        identity=identity,
        additional_claims={"role": claims.get("role", "unknown")}
    )
    
    return jsonify({
        "access_token": access_token
    }), 200

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """
    Logout a user by invalidating their session.
    
    Returns:
        JSON: Success message
    """
    from app import create_db_connection
    
    identity = get_jwt_identity()
    token = get_jwt()
    
    connection = create_db_connection()
    if connection is None:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cursor = connection.cursor()
        
        # Delete session
        cursor.execute(
            "DELETE FROM user_sessions WHERE user_id = %s", 
            (identity.get('user_id'),)
        )
        
        connection.commit()
        
        # Log activity
        log_user_activity(
            identity.get('user_id'), 
            "logout", 
            "User logged out", 
            connection
        )
        
        cursor.close()
        connection.close()
        
        return jsonify({
            "message": "Logout successful"
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """
    Get current user information.
    
    Returns:
        JSON: User information
    """
    from app import create_db_connection
    
    identity = get_jwt_identity()
    
    connection = create_db_connection()
    if connection is None:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        cursor.execute(
            "SELECT user_id, username, email, first_name, last_name, role_id, is_active, last_login FROM users WHERE user_id = %s", 
            (identity.get('user_id'),)
        )
        
        user = cursor.fetchone()
        
        if not user:
            cursor.close()
            connection.close()
            return jsonify({"error": "User not found"}), 404
        
        # Get role name
        cursor.execute(
            "SELECT role_name FROM roles WHERE role_id = %s", 
            (user['role_id'],)
        )
        role = cursor.fetchone()
        user['role'] = role['role_name'] if role else 'unknown'
        
        cursor.close()
        connection.close()
        
        return jsonify(user), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500 
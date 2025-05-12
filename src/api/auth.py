"""
Authentication and Authorization Module

This module handles user authentication, authorization, and session management
for the Hospital Patient Management System.
"""

import bcrypt
import datetime
from flask import request, jsonify
from flask_jwt_extended import (
    create_access_token, create_refresh_token, 
    jwt_required, get_jwt_identity, get_jwt
)
from functools import wraps

# Role-based access control decorator
def role_required(allowed_roles):
    """
    Decorator for role-based access control.
    
    Args:
        allowed_roles (list): List of role names allowed to access the endpoint
        
    Returns:
        Function: Decorated function with role check
    """
    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            # Get claims from JWT
            claims = get_jwt()
            
            # Check if user role is in allowed roles
            if claims.get("role") not in allowed_roles:
                return jsonify({"error": "Access denied: insufficient permissions"}), 403
            
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def hash_password(password):
    """
    Hash a password using bcrypt.
    
    Args:
        password (str): Plain text password
        
    Returns:
        str: Hashed password
    """
    # Generate salt and hash password
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(stored_hash, provided_password):
    """
    Verify a password against its hash.
    
    Args:
        stored_hash (str): Stored password hash
        provided_password (str): Password to verify
        
    Returns:
        bool: True if password matches, False otherwise
    """
    return bcrypt.checkpw(
        provided_password.encode('utf-8'), 
        stored_hash.encode('utf-8')
    )

def generate_tokens(user_id, username, role):
    """
    Generate access and refresh tokens for a user.
    
    Args:
        user_id (int): User ID
        username (str): Username
        role (str): User role name
        
    Returns:
        tuple: (access_token, refresh_token)
    """
    # Set token expiration times
    access_expires = datetime.timedelta(hours=1)
    refresh_expires = datetime.timedelta(days=30)
    
    # Create token identity and additional claims
    identity = {
        "user_id": user_id,
        "username": username
    }
    
    additional_claims = {
        "role": role
    }
    
    # Generate tokens
    access_token = create_access_token(
        identity=identity,
        additional_claims=additional_claims,
        expires_delta=access_expires
    )
    
    refresh_token = create_refresh_token(
        identity=identity,
        additional_claims=additional_claims,
        expires_delta=refresh_expires
    )
    
    return access_token, refresh_token

def log_user_activity(user_id, activity_type, details=None, connection=None):
    """
    Log user activity for audit purposes.
    
    Args:
        user_id (int): User ID
        activity_type (str): Type of activity (login, view, create, update, delete)
        details (str): Additional details about the activity
        connection: Database connection
        
    Returns:
        bool: True if logged successfully, False otherwise
    """
    if not connection:
        return False
        
    try:
        cursor = connection.cursor()
        
        query = """
        INSERT INTO user_activity_log (
            user_id, activity_type, details, ip_address
        ) VALUES (%s, %s, %s, %s)
        """
        
        ip_address = request.remote_addr
        
        cursor.execute(query, (user_id, activity_type, details, ip_address))
        connection.commit()
        
        cursor.close()
        return True
    except Exception as e:
        print(f"Error logging user activity: {e}")
        return False 
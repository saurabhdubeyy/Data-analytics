/**
 * Authentication module for the Hospital Patient Management System
 * Handles login, registration, token management, and session persistence
 */

// API base URL - change this to match your backend server
const API_BASE_URL = 'http://localhost:5000/api';

/**
 * Check if the user is authenticated
 * @returns {boolean} True if authenticated, false otherwise
 */
function isAuthenticated() {
    const token = getAccessToken();
    
    if (!token) {
        return false;
    }
    
    // Check if token is expired
    try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        const expiryTime = payload.exp * 1000; // Convert to milliseconds
        
        if (Date.now() >= expiryTime) {
            // Token expired - try to refresh
            const refreshToken = getRefreshToken();
            if (refreshToken) {
                // We have a refresh token, but we don't want to block the UI
                // Just return false and let the refresh happen asynchronously
                refreshAccessToken();
                return false;
            }
            
            // No refresh token, clear everything
            logout();
            return false;
        }
        
        // Token is valid
        return true;
    } catch (error) {
        console.error('Error validating token:', error);
        logout();
        return false;
    }
}

/**
 * Get the current user's information
 * @returns {Promise<Object>} User data
 */
async function getCurrentUser() {
    if (!isAuthenticated()) {
        return null;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/auth/me`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${getAccessToken()}`
            }
        });
        
        if (!response.ok) {
            throw new Error('Failed to get user data');
        }
        
        return await response.json();
    } catch (error) {
        console.error('Error getting user data:', error);
        return null;
    }
}

/**
 * Login user with username/email and password
 * @param {string} username Username or email
 * @param {string} password Password
 * @returns {Promise<Object>} Login response
 */
async function login(username, password) {
    try {
        const response = await fetch(`${API_BASE_URL}/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, password })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            return {
                success: false,
                message: data.error || 'Login failed'
            };
        }
        
        // Store tokens
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('refresh_token', data.refresh_token);
        
        // Store basic user info
        localStorage.setItem('user', JSON.stringify({
            id: data.user_id,
            username: data.username,
            firstName: data.first_name,
            lastName: data.last_name,
            role: data.role
        }));
        
        return {
            success: true,
            user: {
                id: data.user_id,
                username: data.username,
                firstName: data.first_name,
                lastName: data.last_name,
                role: data.role
            }
        };
    } catch (error) {
        console.error('Login error:', error);
        return {
            success: false,
            message: 'Network error. Please try again.'
        };
    }
}

/**
 * Register a new user
 * @param {Object} userData User registration data
 * @returns {Promise<Object>} Registration response
 */
async function register(userData) {
    try {
        const response = await fetch(`${API_BASE_URL}/auth/register`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(userData)
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            return {
                success: false,
                message: data.error || 'Registration failed'
            };
        }
        
        return {
            success: true,
            message: 'Registration successful'
        };
    } catch (error) {
        console.error('Registration error:', error);
        return {
            success: false,
            message: 'Network error. Please try again.'
        };
    }
}

/**
 * Logout the current user
 * @returns {Promise<boolean>} Success status
 */
async function logout() {
    const token = getAccessToken();
    
    if (token) {
        try {
            await fetch(`${API_BASE_URL}/auth/logout`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
        } catch (error) {
            console.error('Logout error:', error);
        }
    }
    
    // Clear local storage
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    
    return true;
}

/**
 * Refresh the access token using the refresh token
 * @returns {Promise<boolean>} Success status
 */
async function refreshAccessToken() {
    const refreshToken = getRefreshToken();
    
    if (!refreshToken) {
        return false;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${refreshToken}`
            }
        });
        
        if (!response.ok) {
            // If refresh fails, log out the user
            logout();
            return false;
        }
        
        const data = await response.json();
        
        // Store the new access token
        localStorage.setItem('access_token', data.access_token);
        
        return true;
    } catch (error) {
        console.error('Token refresh error:', error);
        logout();
        return false;
    }
}

/**
 * Get the stored access token
 * @returns {string|null} Access token or null if not found
 */
function getAccessToken() {
    return localStorage.getItem('access_token');
}

/**
 * Get the stored refresh token
 * @returns {string|null} Refresh token or null if not found
 */
function getRefreshToken() {
    return localStorage.getItem('refresh_token');
}

/**
 * Get the current user's basic info from localStorage
 * @returns {Object|null} User object or null if not logged in
 */
function getUser() {
    const userJson = localStorage.getItem('user');
    return userJson ? JSON.parse(userJson) : null;
}

/**
 * Check if the current user has a specific role
 * @param {string} role Role to check
 * @returns {boolean} True if user has the role, false otherwise
 */
function hasRole(role) {
    const user = getUser();
    return user && user.role === role;
}

/**
 * Add authorization header to fetch options
 * @param {Object} options Fetch options
 * @returns {Object} Options with authorization header
 */
function withAuth(options = {}) {
    const token = getAccessToken();
    
    if (!token) {
        return options;
    }
    
    return {
        ...options,
        headers: {
            ...options.headers,
            'Authorization': `Bearer ${token}`
        }
    };
}

/**
 * Make an authenticated fetch request
 * @param {string} url API endpoint URL
 * @param {Object} options Fetch options
 * @returns {Promise<Response>} Fetch response
 */
async function authFetch(url, options = {}) {
    const authOptions = withAuth(options);
    
    // First attempt with current token
    let response = await fetch(url, authOptions);
    
    // If unauthorized and we have a refresh token, try to refresh and retry
    if (response.status === 401 && getRefreshToken()) {
        const refreshed = await refreshAccessToken();
        
        if (refreshed) {
            // Retry with new token
            const newAuthOptions = withAuth(options);
            response = await fetch(url, newAuthOptions);
        }
    }
    
    return response;
} 
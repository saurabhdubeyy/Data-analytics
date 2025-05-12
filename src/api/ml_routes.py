"""
Machine Learning API Routes

This module defines the API endpoints for machine learning predictions.
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from ml_models import PregnancyRiskModel, FollowUpPredictionModel, VitalsPredictionModel
from auth import role_required

# Create Blueprint
ml_bp = Blueprint('ml', __name__)

# Initialize models
pregnancy_model = PregnancyRiskModel()
followup_model = FollowUpPredictionModel()
vitals_model = VitalsPredictionModel()

@ml_bp.route('/predict/pregnancy-risk', methods=['POST'])
@jwt_required()
@role_required(['admin', 'doctor', 'nurse'])
def predict_pregnancy_risk():
    """
    Predict pregnancy risk for a patient.
    
    Request body:
        patient_data (dict): Patient data including age, vitals, etc.
        
    Returns:
        JSON: Prediction results
    """
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    try:
        result = pregnancy_model.predict(data)
        
        if 'error' in result:
            return jsonify({"error": result['error']}), 500
        
        return jsonify({
            "success": True,
            "prediction": result
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@ml_bp.route('/predict/followup-miss', methods=['POST'])
@jwt_required()
@role_required(['admin', 'doctor', 'nurse', 'receptionist'])
def predict_followup_miss():
    """
    Predict likelihood of a patient missing a follow-up appointment.
    
    Request body:
        patient_data (dict): Patient data
        
    Returns:
        JSON: Prediction results
    """
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    try:
        result = followup_model.predict(data)
        
        if 'error' in result:
            return jsonify({"error": result['error']}), 500
        
        return jsonify({
            "success": True,
            "prediction": result
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@ml_bp.route('/predict/future-vitals', methods=['POST'])
@jwt_required()
@role_required(['admin', 'doctor', 'nurse', 'data_analyst'])
def predict_future_vitals():
    """
    Predict future vitals for a patient based on current data.
    
    Request body:
        patient_data (dict): Patient's current vitals and demographic data
        
    Returns:
        JSON: Prediction results
    """
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    try:
        result = vitals_model.predict(data)
        
        if 'error' in result:
            return jsonify({"error": result['error']}), 500
        
        return jsonify({
            "success": True,
            "prediction": result
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@ml_bp.route('/train/pregnancy-risk', methods=['POST'])
@jwt_required()
@role_required(['admin', 'data_analyst'])
def train_pregnancy_risk():
    """
    Trigger training for the pregnancy risk model.
    
    Returns:
        JSON: Training result
    """
    try:
        success = pregnancy_model.train()
        
        if success:
            return jsonify({
                "success": True,
                "message": "Pregnancy risk model trained successfully"
            }), 200
        else:
            return jsonify({
                "success": False,
                "message": "Failed to train pregnancy risk model"
            }), 500
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@ml_bp.route('/train/followup-miss', methods=['POST'])
@jwt_required()
@role_required(['admin', 'data_analyst'])
def train_followup_miss():
    """
    Trigger training for the follow-up prediction model.
    
    Returns:
        JSON: Training result
    """
    try:
        success = followup_model.train()
        
        if success:
            return jsonify({
                "success": True,
                "message": "Follow-up prediction model trained successfully"
            }), 200
        else:
            return jsonify({
                "success": False,
                "message": "Failed to train follow-up prediction model"
            }), 500
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@ml_bp.route('/train/future-vitals', methods=['POST'])
@jwt_required()
@role_required(['admin', 'data_analyst'])
def train_future_vitals():
    """
    Trigger training for the vitals prediction model.
    
    Returns:
        JSON: Training result
    """
    try:
        success = vitals_model.train()
        
        if success:
            return jsonify({
                "success": True,
                "message": "Vitals prediction model trained successfully"
            }), 200
        else:
            return jsonify({
                "success": False,
                "message": "Failed to train vitals prediction model"
            }), 500
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@ml_bp.route('/predict/patient/<patient_id>/pregnancy-risk', methods=['GET'])
@jwt_required()
@role_required(['admin', 'doctor', 'nurse'])
def get_patient_pregnancy_risk(patient_id):
    """
    Get pregnancy risk prediction for a specific patient.
    
    Parameters:
        patient_id (str): Patient ID
        
    Returns:
        JSON: Prediction results
    """
    from app import create_db_connection
    
    connection = create_db_connection()
    if connection is None:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Get patient data required for prediction
        query = """
        SELECT 
            TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) AS age,
            v.temperature,
            v.heart_rate,
            v.blood_pressure_systolic,
            v.blood_pressure_diastolic,
            v.respiratory_rate,
            v.oxygen_saturation,
            CASE WHEN m.condition_name LIKE '%hypertension%' THEN 1 ELSE 0 END AS has_hypertension,
            CASE WHEN m.condition_name LIKE '%diabetes%' THEN 1 ELSE 0 END AS has_diabetes,
            CASE WHEN m.condition_name LIKE '%asthma%' THEN 1 ELSE 0 END AS has_asthma
        FROM 
            patients p
        LEFT JOIN 
            vitals v ON p.patient_id = v.patient_id AND v.recorded_at = (
                SELECT MAX(recorded_at) FROM vitals WHERE patient_id = p.patient_id
            )
        LEFT JOIN 
            medical_history m ON p.patient_id = m.patient_id
        WHERE 
            p.patient_id = %s
        """
        
        cursor.execute(query, (patient_id,))
        data = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if not data:
            return jsonify({"error": "Patient not found"}), 404
        
        # Make prediction
        result = pregnancy_model.predict(data)
        
        if 'error' in result:
            return jsonify({"error": result['error']}), 500
        
        return jsonify({
            "success": True,
            "patient_id": patient_id,
            "prediction": result
        }), 200
        
    except Exception as e:
        if connection:
            connection.close()
        return jsonify({"error": str(e)}), 500

@ml_bp.route('/predict/patient/<patient_id>/followup-miss', methods=['GET'])
@jwt_required()
@role_required(['admin', 'doctor', 'nurse', 'receptionist'])
def get_patient_followup_miss(patient_id):
    """
    Get follow-up miss prediction for a specific patient.
    
    Parameters:
        patient_id (str): Patient ID
        
    Returns:
        JSON: Prediction results
    """
    from app import create_db_connection
    
    connection = create_db_connection()
    if connection is None:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Get patient data required for prediction
        query = """
        SELECT 
            TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) AS age,
            p.gender,
            CASE WHEN p.city IS NULL OR p.city = '' THEN 0 ELSE 1 END AS has_address,
            CASE WHEN p.phone IS NULL OR p.phone = '' THEN 0 ELSE 1 END AS has_phone,
            CASE WHEN p.email IS NULL OR p.email = '' THEN 0 ELSE 1 END AS has_email,
            CASE WHEN p.insurance_provider IS NULL OR p.insurance_provider = '' THEN 0 ELSE 1 END AS has_insurance,
            DATEDIFF(fv.follow_up_date, fv.visit_date) AS days_between_visits
        FROM 
            patients p
        LEFT JOIN 
            follow_up_visits fv ON p.patient_id = fv.patient_id AND fv.visit_date = (
                SELECT MAX(visit_date) FROM follow_up_visits WHERE patient_id = p.patient_id
            )
        WHERE 
            p.patient_id = %s
        """
        
        cursor.execute(query, (patient_id,))
        data = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if not data:
            return jsonify({"error": "Patient not found"}), 404
        
        # Make prediction
        result = followup_model.predict(data)
        
        if 'error' in result:
            return jsonify({"error": result['error']}), 500
        
        return jsonify({
            "success": True,
            "patient_id": patient_id,
            "prediction": result
        }), 200
        
    except Exception as e:
        if connection:
            connection.close()
        return jsonify({"error": str(e)}), 500

@ml_bp.route('/predict/patient/<patient_id>/future-vitals', methods=['GET'])
@jwt_required()
@role_required(['admin', 'doctor', 'nurse'])
def get_patient_future_vitals(patient_id):
    """
    Get future vitals prediction for a specific patient.
    
    Parameters:
        patient_id (str): Patient ID
        
    Returns:
        JSON: Prediction results
    """
    from app import create_db_connection
    
    connection = create_db_connection()
    if connection is None:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Get patient data required for prediction
        query = """
        SELECT 
            TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) AS age_at_recording,
            v.temperature AS prev_temperature,
            v.heart_rate AS prev_heart_rate,
            v.blood_pressure_systolic AS prev_bp_systolic,
            v.blood_pressure_diastolic AS prev_bp_diastolic,
            v.respiratory_rate AS prev_respiratory_rate,
            v.oxygen_saturation AS prev_oxygen_saturation
        FROM 
            patients p
        JOIN 
            vitals v ON p.patient_id = v.patient_id AND v.recorded_at = (
                SELECT MAX(recorded_at) FROM vitals WHERE patient_id = p.patient_id
            )
        WHERE 
            p.patient_id = %s
        """
        
        cursor.execute(query, (patient_id,))
        data = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        if not data:
            return jsonify({"error": "Patient not found or no vitals recorded"}), 404
        
        # Make prediction
        result = vitals_model.predict(data)
        
        if 'error' in result:
            return jsonify({"error": result['error']}), 500
        
        return jsonify({
            "success": True,
            "patient_id": patient_id,
            "prediction": result
        }), 200
        
    except Exception as e:
        if connection:
            connection.close()
        return jsonify({"error": str(e)}), 500 
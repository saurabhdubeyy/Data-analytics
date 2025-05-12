from flask import Flask, request, jsonify
import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv
from flask_cors import CORS
import json
from datetime import datetime, date
from flask_jwt_extended import JWTManager
from flasgger import Swagger

# Import auth routes
from auth_routes import auth_bp
# Import ML routes
from ml_routes import ml_bp

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configure Flask-JWT-Extended
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-me")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = 3600  # 1 hour
app.config["JWT_REFRESH_TOKEN_EXPIRES"] = 2592000  # 30 days
jwt = JWTManager(app)

# Configure Swagger
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/api/docs"
}

template = {
    "swagger": "2.0",
    "info": {
        "title": "Hospital Patient Management System API",
        "description": "API for the Hospital Patient Management System",
        "version": "1.0.0",
        "contact": {
            "name": "API Support",
            "email": "support@example.com"
        },
    },
    "securityDefinitions": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "JWT Authorization header using the Bearer scheme. Example: \"Bearer {token}\""
        }
    },
    "security": [
        {
            "Bearer": []
        }
    ]
}

swagger = Swagger(app, config=swagger_config, template=template)

# Database connection function
def create_db_connection():
    try:
        connection = mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "hospital_db")
        )
        return connection
    except Error as e:
        print(f"Error connecting to MySQL database: {e}")
        return None

# Custom JSON encoder to handle date/datetime objects
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)

app.json_encoder = CustomJSONEncoder

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(ml_bp, url_prefix='/api/ml')

# Import auth functions
from auth import role_required

# Health check endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    """
    Health check endpoint
    This endpoint checks if the API is running.
    ---
    responses:
      200:
        description: API is healthy
    """
    return jsonify({"status": "healthy", "message": "API is running"}), 200

# Get all patients
@app.route('/api/patients', methods=['GET'])
@role_required(['admin', 'doctor', 'nurse', 'receptionist', 'data_analyst'])
def get_patients():
    """
    Get all patients
    This endpoint returns a list of all patients.
    ---
    security:
      - Bearer: []
    responses:
      200:
        description: A list of patients
      500:
        description: Database connection error
    """
    connection = create_db_connection()
    if connection is None:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM patients")
        patients = cursor.fetchall()
        cursor.close()
        connection.close()
        return jsonify(patients), 200
    except Error as e:
        return jsonify({"error": str(e)}), 500

# Get patient by ID
@app.route('/api/patients/<patient_id>', methods=['GET'])
@role_required(['admin', 'doctor', 'nurse', 'receptionist'])
def get_patient(patient_id):
    """
    Get patient by ID
    This endpoint returns a specific patient's details.
    ---
    security:
      - Bearer: []
    parameters:
      - name: patient_id
        in: path
        type: string
        required: true
        description: The ID of the patient
    responses:
      200:
        description: Patient details
      404:
        description: Patient not found
      500:
        description: Database connection error
    """
    connection = create_db_connection()
    if connection is None:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM patients WHERE patient_id = %s", (patient_id,))
        patient = cursor.fetchone()
        
        if not patient:
            cursor.close()
            connection.close()
            return jsonify({"error": "Patient not found"}), 404
        
        # Get medical history
        cursor.execute("SELECT * FROM medical_history WHERE patient_id = %s", (patient_id,))
        medical_history = cursor.fetchall()
        patient['medical_history'] = medical_history
        
        # Get vitals
        cursor.execute("SELECT * FROM vitals WHERE patient_id = %s ORDER BY recorded_at DESC", (patient_id,))
        vitals = cursor.fetchall()
        patient['vitals'] = vitals
        
        # Get medications
        cursor.execute("SELECT * FROM medications WHERE patient_id = %s", (patient_id,))
        medications = cursor.fetchall()
        patient['medications'] = medications
        
        # Get appointments
        cursor.execute("SELECT * FROM appointments WHERE patient_id = %s ORDER BY appointment_date DESC", (patient_id,))
        appointments = cursor.fetchall()
        patient['appointments'] = appointments
        
        # Get delivery information if available
        cursor.execute("SELECT * FROM delivery_information WHERE patient_id = %s", (patient_id,))
        delivery_info = cursor.fetchall()
        patient['delivery_information'] = delivery_info
        
        cursor.close()
        connection.close()
        return jsonify(patient), 200
    except Error as e:
        return jsonify({"error": str(e)}), 500

# Add new patient
@app.route('/api/patients', methods=['POST'])
@role_required(['admin', 'doctor', 'nurse', 'receptionist'])
def add_patient():
    """
    Add a new patient
    This endpoint adds a new patient to the database.
    ---
    security:
      - Bearer: []
    parameters:
      - name: patient
        in: body
        required: true
        schema:
          type: object
          required:
            - first_name
            - last_name
            - date_of_birth
          properties:
            first_name:
              type: string
            last_name:
              type: string
            date_of_birth:
              type: string
              format: date
            gender:
              type: string
            email:
              type: string
            phone:
              type: string
            address:
              type: string
            city:
              type: string
            state:
              type: string
            zip_code:
              type: string
            insurance_provider:
              type: string
            insurance_id:
              type: string
            emergency_contact_name:
              type: string
            emergency_contact_phone:
              type: string
    responses:
      201:
        description: Patient created successfully
      400:
        description: Invalid request data
      500:
        description: Database connection error
    """
    connection = create_db_connection()
    if connection is None:
        return jsonify({"error": "Database connection failed"}), 500
    
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['first_name', 'last_name', 'date_of_birth']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400
    
    # Sanitize and validate inputs
    if not isinstance(data['first_name'], str) or len(data['first_name']) > 100:
        return jsonify({"error": "Invalid first_name"}), 400
    
    if not isinstance(data['last_name'], str) or len(data['last_name']) > 100:
        return jsonify({"error": "Invalid last_name"}), 400
    
    # Validate date format
    try:
        datetime.strptime(data['date_of_birth'], '%Y-%m-%d')
    except ValueError:
        return jsonify({"error": "Invalid date_of_birth format. Use YYYY-MM-DD"}), 400
    
    try:
        cursor = connection.cursor()
        
        # Generate patient_id (in a real system, you might have a different approach)
        import uuid
        patient_id = f"P{uuid.uuid4().hex[:8].upper()}"
        
        # Insert into patients table
        query = """
        INSERT INTO patients (
            patient_id, first_name, last_name, date_of_birth, gender, email, 
            phone, address, city, state, zip_code, insurance_provider, insurance_id, 
            emergency_contact_name, emergency_contact_phone
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (
            patient_id, data['first_name'], data['last_name'], data['date_of_birth'],
            data.get('gender'), data.get('email'), data.get('phone'),
            data.get('address'), data.get('city'), data.get('state'),
            data.get('zip_code'), data.get('insurance_provider'), data.get('insurance_id'),
            data.get('emergency_contact_name'), data.get('emergency_contact_phone')
        )
        
        cursor.execute(query, values)
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({
            "message": "Patient added successfully",
            "patient_id": patient_id
        }), 201
    except Error as e:
        return jsonify({"error": str(e)}), 500

# Update patient
@app.route('/api/patients/<patient_id>', methods=['PUT'])
@role_required(['admin', 'doctor', 'nurse'])
def update_patient(patient_id):
    """
    Update a patient
    This endpoint updates a patient's information.
    ---
    security:
      - Bearer: []
    parameters:
      - name: patient_id
        in: path
        type: string
        required: true
        description: The ID of the patient
      - name: patient
        in: body
        required: true
        schema:
          type: object
          properties:
            first_name:
              type: string
            last_name:
              type: string
            date_of_birth:
              type: string
              format: date
            gender:
              type: string
            email:
              type: string
            phone:
              type: string
            address:
              type: string
            city:
              type: string
            state:
              type: string
            zip_code:
              type: string
            insurance_provider:
              type: string
            insurance_id:
              type: string
            emergency_contact_name:
              type: string
            emergency_contact_phone:
              type: string
    responses:
      200:
        description: Patient updated successfully
      400:
        description: Invalid request data
      404:
        description: Patient not found
      500:
        description: Database connection error
    """
    connection = create_db_connection()
    if connection is None:
        return jsonify({"error": "Database connection failed"}), 500
    
    data = request.get_json()
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Check if patient exists
        cursor.execute("SELECT * FROM patients WHERE patient_id = %s", (patient_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({"error": "Patient not found"}), 404
        
        # Sanitize and validate inputs
        if 'first_name' in data and (not isinstance(data['first_name'], str) or len(data['first_name']) > 100):
            return jsonify({"error": "Invalid first_name"}), 400
        
        if 'last_name' in data and (not isinstance(data['last_name'], str) or len(data['last_name']) > 100):
            return jsonify({"error": "Invalid last_name"}), 400
        
        if 'date_of_birth' in data:
            try:
                datetime.strptime(data['date_of_birth'], '%Y-%m-%d')
            except ValueError:
                return jsonify({"error": "Invalid date_of_birth format. Use YYYY-MM-DD"}), 400
        
        # Build update query dynamically based on provided fields
        update_fields = []
        values = []
        
        for key, value in data.items():
            if key != 'patient_id':  # Don't update the primary key
                update_fields.append(f"{key} = %s")
                values.append(value)
        
        if not update_fields:
            cursor.close()
            connection.close()
            return jsonify({"error": "No fields to update"}), 400
        
        # Add patient_id to values for WHERE clause
        values.append(patient_id)
        
        query = f"UPDATE patients SET {', '.join(update_fields)} WHERE patient_id = %s"
        cursor.execute(query, values)
        connection.commit()
        
        cursor.close()
        connection.close()
        
        return jsonify({"message": "Patient updated successfully"}), 200
    except Error as e:
        return jsonify({"error": str(e)}), 500

# Add vitals for a patient
@app.route('/api/patients/<patient_id>/vitals', methods=['POST'])
@role_required(['admin', 'doctor', 'nurse'])
def add_vitals(patient_id):
    """
    Add vitals for a patient
    This endpoint adds vitals for a specific patient.
    ---
    security:
      - Bearer: []
    parameters:
      - name: patient_id
        in: path
        type: string
        required: true
        description: The ID of the patient
      - name: vitals
        in: body
        required: true
        schema:
          type: object
          properties:
            recorded_at:
              type: string
              format: date-time
            temperature:
              type: number
              format: float
            heart_rate:
              type: integer
            blood_pressure_systolic:
              type: integer
            blood_pressure_diastolic:
              type: integer
            respiratory_rate:
              type: integer
            oxygen_saturation:
              type: number
              format: float
            notes:
              type: string
    responses:
      201:
        description: Vitals added successfully
      404:
        description: Patient not found
      500:
        description: Database connection error
    """
    connection = create_db_connection()
    if connection is None:
        return jsonify({"error": "Database connection failed"}), 500
    
    data = request.get_json()
    
    # Validate inputs
    if 'temperature' in data and data['temperature'] is not None:
        try:
            data['temperature'] = float(data['temperature'])
            if data['temperature'] < 30 or data['temperature'] > 45:
                return jsonify({"error": "Temperature out of reasonable range (30-45°C)"}), 400
        except ValueError:
            return jsonify({"error": "Invalid temperature value"}), 400
    
    if 'heart_rate' in data and data['heart_rate'] is not None:
        try:
            data['heart_rate'] = int(data['heart_rate'])
            if data['heart_rate'] < 30 or data['heart_rate'] > 220:
                return jsonify({"error": "Heart rate out of reasonable range (30-220 bpm)"}), 400
        except ValueError:
            return jsonify({"error": "Invalid heart rate value"}), 400
    
    if 'blood_pressure_systolic' in data and data['blood_pressure_systolic'] is not None:
        try:
            data['blood_pressure_systolic'] = int(data['blood_pressure_systolic'])
            if data['blood_pressure_systolic'] < 70 or data['blood_pressure_systolic'] > 250:
                return jsonify({"error": "Systolic blood pressure out of reasonable range (70-250 mmHg)"}), 400
        except ValueError:
            return jsonify({"error": "Invalid systolic blood pressure value"}), 400
    
    if 'blood_pressure_diastolic' in data and data['blood_pressure_diastolic'] is not None:
        try:
            data['blood_pressure_diastolic'] = int(data['blood_pressure_diastolic'])
            if data['blood_pressure_diastolic'] < 40 or data['blood_pressure_diastolic'] > 150:
                return jsonify({"error": "Diastolic blood pressure out of reasonable range (40-150 mmHg)"}), 400
        except ValueError:
            return jsonify({"error": "Invalid diastolic blood pressure value"}), 400
    
    try:
        cursor = connection.cursor()
        
        # Check if patient exists
        cursor.execute("SELECT * FROM patients WHERE patient_id = %s", (patient_id,))
        if not cursor.fetchone():
            cursor.close()
            connection.close()
            return jsonify({"error": "Patient not found"}), 404
        
        # Insert vitals
        query = """
        INSERT INTO vitals (
            patient_id, recorded_at, temperature, heart_rate, 
            blood_pressure_systolic, blood_pressure_diastolic, 
            respiratory_rate, oxygen_saturation, notes
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        # Use current timestamp if not provided
        recorded_at = data.get('recorded_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        values = (
            patient_id, recorded_at, data.get('temperature'), data.get('heart_rate'),
            data.get('blood_pressure_systolic'), data.get('blood_pressure_diastolic'),
            data.get('respiratory_rate'), data.get('oxygen_saturation'),
            data.get('notes')
        )
        
        cursor.execute(query, values)
        connection.commit()
        
        vital_id = cursor.lastrowid
        
        cursor.close()
        connection.close()
        
        return jsonify({
            "message": "Vitals added successfully",
            "vital_id": vital_id
        }), 201
    except Error as e:
        return jsonify({"error": str(e)}), 500

# Get high-risk pregnancies
@app.route('/api/analytics/high-risk-pregnancies', methods=['GET'])
@role_required(['admin', 'doctor', 'nurse', 'data_analyst'])
def high_risk_pregnancies():
    """
    Get high-risk pregnancies
    This endpoint returns patients with high-risk pregnancies.
    ---
    security:
      - Bearer: []
    responses:
      200:
        description: List of high-risk pregnancies
      500:
        description: Database connection error
    """
    connection = create_db_connection()
    if connection is None:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        query = """
        SELECT 
            p.patient_id,
            CONCAT(p.first_name, ' ', p.last_name) AS patient_name,
            p.date_of_birth,
            TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) AS age,
            v.blood_pressure_systolic,
            v.blood_pressure_diastolic,
            d.complications,
            CASE
                WHEN TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) > 35 THEN 'Age Risk'
                WHEN v.blood_pressure_systolic > 140 OR v.blood_pressure_diastolic > 90 THEN 'Hypertension Risk'
                WHEN d.complications IS NOT NULL AND d.complications != '' THEN 'Previous Complications'
                ELSE 'Normal'
            END AS risk_category
        FROM 
            patients p
        LEFT JOIN 
            vitals v ON p.patient_id = v.patient_id AND v.recorded_at = (
                SELECT MAX(recorded_at) FROM vitals WHERE patient_id = p.patient_id
            )
        LEFT JOIN 
            delivery_information d ON p.patient_id = d.patient_id
        WHERE 
            (TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) > 35 OR
            v.blood_pressure_systolic > 140 OR 
            v.blood_pressure_diastolic > 90 OR
            (d.complications IS NOT NULL AND d.complications != ''))
        ORDER BY 
            CASE
                WHEN TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) > 35 AND 
                    (v.blood_pressure_systolic > 140 OR v.blood_pressure_diastolic > 90) THEN 1
                WHEN v.blood_pressure_systolic > 140 OR v.blood_pressure_diastolic > 90 THEN 2
                WHEN TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) > 35 THEN 3
                ELSE 4
            END
        """
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return jsonify(results), 200
    except Error as e:
        return jsonify({"error": str(e)}), 500

# Get missed follow-ups
@app.route('/api/analytics/missed-follow-ups', methods=['GET'])
@role_required(['admin', 'doctor', 'nurse', 'receptionist', 'data_analyst'])
def missed_follow_ups():
    """
    Get missed follow-ups
    This endpoint returns patients who missed their follow-up appointments.
    ---
    security:
      - Bearer: []
    responses:
      200:
        description: List of missed follow-ups
      500:
        description: Database connection error
    """
    connection = create_db_connection()
    if connection is None:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        query = """
        SELECT 
            p.patient_id,
            CONCAT(p.first_name, ' ', p.last_name) AS patient_name,
            p.phone,
            p.email,
            fv.visit_date AS last_visit_date,
            fv.follow_up_date AS scheduled_follow_up,
            DATEDIFF(CURDATE(), fv.follow_up_date) AS days_overdue
        FROM 
            patients p
        JOIN 
            follow_up_visits fv ON p.patient_id = fv.patient_id
        WHERE 
            fv.follow_up_required = TRUE 
            AND fv.follow_up_date < CURDATE()
            AND NOT EXISTS (
                SELECT 1 
                FROM follow_up_visits fv2 
                WHERE fv2.patient_id = p.patient_id 
                AND fv2.visit_date > fv.follow_up_date
            )
        ORDER BY 
            days_overdue DESC
        """
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return jsonify(results), 200
    except Error as e:
        return jsonify({"error": str(e)}), 500

# Get patient demographics
@app.route('/api/analytics/demographics', methods=['GET'])
@role_required(['admin', 'doctor', 'data_analyst'])
def patient_demographics():
    """
    Get patient demographics
    This endpoint returns patient demographic data.
    ---
    security:
      - Bearer: []
    responses:
      200:
        description: Patient demographic data
      500:
        description: Database connection error
    """
    connection = create_db_connection()
    if connection is None:
        return jsonify({"error": "Database connection failed"}), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        query = """
        SELECT 
            CASE 
                WHEN TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) < 18 THEN 'Under 18'
                WHEN TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) BETWEEN 18 AND 30 THEN '18-30'
                WHEN TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) BETWEEN 31 AND 45 THEN '31-45'
                WHEN TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) BETWEEN 46 AND 65 THEN '46-65'
                ELSE 'Over 65'
            END AS age_group,
            p.city,
            p.state,
            COUNT(*) AS patient_count,
            COUNT(DISTINCT m.condition_name) AS unique_conditions,
            COUNT(DISTINCT d.delivery_id) AS delivery_count
        FROM 
            patients p
        LEFT JOIN 
            medical_history m ON p.patient_id = m.patient_id
        LEFT JOIN 
            delivery_information d ON p.patient_id = d.patient_id
        GROUP BY 
            age_group, p.city, p.state
        ORDER BY 
            p.state, p.city, age_group
        """
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        cursor.close()
        connection.close()
        
        return jsonify(results), 200
    except Error as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 
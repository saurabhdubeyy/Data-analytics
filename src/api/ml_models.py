"""
Machine Learning Models for Hospital Patient Risk Prediction

This module implements machine learning models to predict:
1. High-risk pregnancies
2. Missed follow-up likelihood
3. Abnormal vitals prediction

These models add predictive capabilities to the existing analytics dashboard.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, mean_squared_error, roc_auc_score
import joblib
import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def create_db_connection():
    """
    Create a connection to the MySQL database.
    
    Returns:
        mysql.connector.connection_cext.CMySQLConnection: Database connection
    """
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

class PregnancyRiskModel:
    """
    Model to predict high-risk pregnancies based on patient data.
    """
    
    def __init__(self):
        """Initialize the pregnancy risk prediction model."""
        self.model = None
        self.model_path = os.path.join(os.path.dirname(__file__), 'models', 'pregnancy_risk_model.joblib')
        
        # Create models directory if it doesn't exist
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        
        # Load the model if it exists
        if os.path.exists(self.model_path):
            self.load_model()
    
    def get_training_data(self):
        """
        Fetch training data from the database.
        
        Returns:
            tuple: Features DataFrame (X) and target Series (y)
        """
        connection = create_db_connection()
        if not connection:
            return None, None
        
        try:
            # Query to get features and target for pregnancy risk model
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
                CASE WHEN m.condition_name LIKE '%asthma%' THEN 1 ELSE 0 END AS has_asthma,
                CASE
                    WHEN TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) > 35 
                        OR v.blood_pressure_systolic > 140 
                        OR v.blood_pressure_diastolic > 90 
                        OR d.complications IS NOT NULL AND d.complications != ''
                        OR m.condition_name LIKE '%hypertension%'
                        OR m.condition_name LIKE '%diabetes%'
                    THEN 1
                    ELSE 0
                END AS high_risk
            FROM 
                patients p
            LEFT JOIN 
                vitals v ON p.patient_id = v.patient_id AND v.recorded_at = (
                    SELECT MAX(recorded_at) FROM vitals WHERE patient_id = p.patient_id
                )
            LEFT JOIN 
                medical_history m ON p.patient_id = m.patient_id
            LEFT JOIN 
                delivery_information d ON p.patient_id = d.patient_id
            WHERE 
                p.gender = 'Female'
            """
            
            # Fetch data
            df = pd.read_sql(query, connection)
            
            # Close connection
            connection.close()
            
            # Handle missing values
            df = df.fillna({
                'temperature': df['temperature'].median(),
                'heart_rate': df['heart_rate'].median(),
                'blood_pressure_systolic': df['blood_pressure_systolic'].median(),
                'blood_pressure_diastolic': df['blood_pressure_diastolic'].median(),
                'respiratory_rate': df['respiratory_rate'].median(),
                'oxygen_saturation': df['oxygen_saturation'].median(),
                'has_hypertension': 0,
                'has_diabetes': 0,
                'has_asthma': 0
            })
            
            # Split features and target
            X = df.drop('high_risk', axis=1)
            y = df['high_risk']
            
            return X, y
            
        except Error as e:
            print(f"Error getting training data: {e}")
            if connection:
                connection.close()
            return None, None
    
    def train(self):
        """
        Train the pregnancy risk prediction model.
        
        Returns:
            bool: True if training was successful, False otherwise
        """
        # Get training data
        X, y = self.get_training_data()
        
        if X is None or len(X) < 10:  # Need at least some samples to train
            print("Not enough training data available.")
            return False
        
        try:
            # Define numeric features
            numeric_features = X.select_dtypes(include=['int64', 'float64']).columns.tolist()
            
            # Create preprocessing pipeline
            numeric_transformer = Pipeline(steps=[
                ('imputer', SimpleImputer(strategy='median')),
                ('scaler', StandardScaler())
            ])
            
            preprocessor = ColumnTransformer(
                transformers=[
                    ('num', numeric_transformer, numeric_features)
                ],
                remainder='passthrough'
            )
            
            # Create model pipeline
            self.model = Pipeline(steps=[
                ('preprocessor', preprocessor),
                ('classifier', RandomForestClassifier(n_estimators=100, random_state=42))
            ])
            
            # Split the data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            
            # Train the model
            self.model.fit(X_train, y_train)
            
            # Evaluate the model
            y_pred = self.model.predict(X_test)
            y_prob = self.model.predict_proba(X_test)[:, 1]
            
            print("Pregnancy Risk Model Evaluation:")
            print(classification_report(y_test, y_pred))
            print(f"ROC AUC Score: {roc_auc_score(y_test, y_prob):.4f}")
            
            # Save the model
            self.save_model()
            
            return True
            
        except Exception as e:
            print(f"Error training pregnancy risk model: {e}")
            return False
    
    def predict(self, patient_data):
        """
        Predict pregnancy risk for a patient.
        
        Args:
            patient_data (dict): Patient's data with features
            
        Returns:
            dict: Prediction results with risk probability and category
        """
        if self.model is None:
            if not os.path.exists(self.model_path):
                self.train()
            else:
                self.load_model()
                
        if self.model is None:
            return {
                'error': 'Model not available',
                'risk_probability': None,
                'risk_category': 'Unknown'
            }
        
        try:
            # Convert to DataFrame
            df = pd.DataFrame([patient_data])
            
            # Make prediction
            risk_prob = self.model.predict_proba(df)[0, 1]
            
            # Determine risk category
            if risk_prob < 0.3:
                risk_category = 'Low Risk'
            elif risk_prob < 0.7:
                risk_category = 'Medium Risk'
            else:
                risk_category = 'High Risk'
            
            return {
                'risk_probability': float(risk_prob),
                'risk_category': risk_category
            }
            
        except Exception as e:
            print(f"Error predicting pregnancy risk: {e}")
            return {
                'error': str(e),
                'risk_probability': None,
                'risk_category': 'Unknown'
            }
    
    def save_model(self):
        """Save the model to a file."""
        if self.model is not None:
            joblib.dump(self.model, self.model_path)
            print(f"Pregnancy risk model saved to {self.model_path}")
    
    def load_model(self):
        """Load the model from a file."""
        if os.path.exists(self.model_path):
            self.model = joblib.load(self.model_path)
            print(f"Pregnancy risk model loaded from {self.model_path}")

class FollowUpPredictionModel:
    """
    Model to predict the likelihood of a patient missing a follow-up appointment.
    """
    
    def __init__(self):
        """Initialize the follow-up prediction model."""
        self.model = None
        self.model_path = os.path.join(os.path.dirname(__file__), 'models', 'followup_model.joblib')
        
        # Create models directory if it doesn't exist
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        
        # Load the model if it exists
        if os.path.exists(self.model_path):
            self.load_model()
    
    def get_training_data(self):
        """
        Fetch training data from the database.
        
        Returns:
            tuple: Features DataFrame (X) and target Series (y)
        """
        connection = create_db_connection()
        if not connection:
            return None, None
        
        try:
            # Query to get features and target for follow-up prediction model
            query = """
            SELECT 
                TIMESTAMPDIFF(YEAR, p.date_of_birth, CURDATE()) AS age,
                p.gender,
                CASE WHEN p.city IS NULL OR p.city = '' THEN 0 ELSE 1 END AS has_address,
                CASE WHEN p.phone IS NULL OR p.phone = '' THEN 0 ELSE 1 END AS has_phone,
                CASE WHEN p.email IS NULL OR p.email = '' THEN 0 ELSE 1 END AS has_email,
                CASE WHEN p.insurance_provider IS NULL OR p.insurance_provider = '' THEN 0 ELSE 1 END AS has_insurance,
                DATEDIFF(fv.follow_up_date, fv.visit_date) AS days_between_visits,
                CASE 
                    WHEN fv.follow_up_required = TRUE 
                    AND fv.follow_up_date < CURDATE()
                    AND NOT EXISTS (
                        SELECT 1 
                        FROM follow_up_visits fv2 
                        WHERE fv2.patient_id = p.patient_id 
                        AND fv2.visit_date > fv.follow_up_date
                    ) THEN 1
                    ELSE 0
                END AS missed_followup
            FROM 
                patients p
            JOIN 
                follow_up_visits fv ON p.patient_id = fv.patient_id
            """
            
            # Fetch data
            df = pd.read_sql(query, connection)
            
            # Close connection
            connection.close()
            
            # Process categorical features
            df['gender'] = df['gender'].fillna('Unknown')
            
            # Split features and target
            X = df.drop('missed_followup', axis=1)
            y = df['missed_followup']
            
            return X, y
            
        except Error as e:
            print(f"Error getting training data: {e}")
            if connection:
                connection.close()
            return None, None
    
    def train(self):
        """
        Train the follow-up prediction model.
        
        Returns:
            bool: True if training was successful, False otherwise
        """
        # Get training data
        X, y = self.get_training_data()
        
        if X is None or len(X) < 10:  # Need at least some samples to train
            print("Not enough training data available.")
            return False
        
        try:
            # Define feature types
            numeric_features = X.select_dtypes(include=['int64', 'float64']).columns.tolist()
            categorical_features = ['gender']
            
            # Create preprocessing pipeline
            numeric_transformer = Pipeline(steps=[
                ('imputer', SimpleImputer(strategy='median')),
                ('scaler', StandardScaler())
            ])
            
            categorical_transformer = Pipeline(steps=[
                ('imputer', SimpleImputer(strategy='constant', fill_value='Unknown')),
                ('onehot', OneHotEncoder(handle_unknown='ignore'))
            ])
            
            preprocessor = ColumnTransformer(
                transformers=[
                    ('num', numeric_transformer, numeric_features),
                    ('cat', categorical_transformer, categorical_features)
                ]
            )
            
            # Create model pipeline
            self.model = Pipeline(steps=[
                ('preprocessor', preprocessor),
                ('classifier', RandomForestClassifier(n_estimators=100, random_state=42))
            ])
            
            # Split the data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            
            # Train the model
            self.model.fit(X_train, y_train)
            
            # Evaluate the model
            y_pred = self.model.predict(X_test)
            y_prob = self.model.predict_proba(X_test)[:, 1]
            
            print("Follow-up Prediction Model Evaluation:")
            print(classification_report(y_test, y_pred))
            print(f"ROC AUC Score: {roc_auc_score(y_test, y_prob):.4f}")
            
            # Save the model
            self.save_model()
            
            return True
            
        except Exception as e:
            print(f"Error training follow-up prediction model: {e}")
            return False
    
    def predict(self, patient_data):
        """
        Predict the likelihood of missing a follow-up appointment.
        
        Args:
            patient_data (dict): Patient's data with features
            
        Returns:
            dict: Prediction results with probability and compliance level
        """
        if self.model is None:
            if not os.path.exists(self.model_path):
                self.train()
            else:
                self.load_model()
                
        if self.model is None:
            return {
                'error': 'Model not available',
                'miss_probability': None,
                'compliance_level': 'Unknown'
            }
        
        try:
            # Convert to DataFrame
            df = pd.DataFrame([patient_data])
            
            # Make prediction
            miss_prob = self.model.predict_proba(df)[0, 1]
            
            # Determine compliance level
            if miss_prob < 0.3:
                compliance_level = 'High Compliance'
            elif miss_prob < 0.6:
                compliance_level = 'Medium Compliance'
            else:
                compliance_level = 'Low Compliance'
            
            return {
                'miss_probability': float(miss_prob),
                'compliance_level': compliance_level
            }
            
        except Exception as e:
            print(f"Error predicting follow-up compliance: {e}")
            return {
                'error': str(e),
                'miss_probability': None,
                'compliance_level': 'Unknown'
            }
    
    def save_model(self):
        """Save the model to a file."""
        if self.model is not None:
            joblib.dump(self.model, self.model_path)
            print(f"Follow-up prediction model saved to {self.model_path}")
    
    def load_model(self):
        """Load the model from a file."""
        if os.path.exists(self.model_path):
            self.model = joblib.load(self.model_path)
            print(f"Follow-up prediction model loaded from {self.model_path}")

class VitalsPredictionModel:
    """
    Model to predict future vital signs based on patient history.
    """
    
    def __init__(self):
        """Initialize the vitals prediction model."""
        self.model = None
        self.model_path = os.path.join(os.path.dirname(__file__), 'models', 'vitals_model.joblib')
        
        # Create models directory if it doesn't exist
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        
        # Load the model if it exists
        if os.path.exists(self.model_path):
            self.load_model()
    
    def get_training_data(self):
        """
        Fetch training data from the database.
        
        Returns:
            tuple: Features DataFrame (X) and target Series (y)
        """
        connection = create_db_connection()
        if not connection:
            return None, None
        
        try:
            # Query to get sequential vitals data for predictions
            query = """
            SELECT 
                p.patient_id,
                TIMESTAMPDIFF(YEAR, p.date_of_birth, v.recorded_at) AS age_at_recording,
                p.gender,
                v.recorded_at,
                v.temperature,
                v.heart_rate,
                v.blood_pressure_systolic,
                v.blood_pressure_diastolic,
                v.respiratory_rate,
                v.oxygen_saturation,
                LAG(v.temperature) OVER (PARTITION BY p.patient_id ORDER BY v.recorded_at) AS prev_temperature,
                LAG(v.heart_rate) OVER (PARTITION BY p.patient_id ORDER BY v.recorded_at) AS prev_heart_rate,
                LAG(v.blood_pressure_systolic) OVER (PARTITION BY p.patient_id ORDER BY v.recorded_at) AS prev_bp_systolic,
                LAG(v.blood_pressure_diastolic) OVER (PARTITION BY p.patient_id ORDER BY v.recorded_at) AS prev_bp_diastolic,
                LAG(v.respiratory_rate) OVER (PARTITION BY p.patient_id ORDER BY v.recorded_at) AS prev_respiratory_rate,
                LAG(v.oxygen_saturation) OVER (PARTITION BY p.patient_id ORDER BY v.recorded_at) AS prev_oxygen_saturation
            FROM 
                patients p
            JOIN 
                vitals v ON p.patient_id = v.patient_id
            ORDER BY 
                p.patient_id, v.recorded_at
            """
            
            # Fetch data
            df = pd.read_sql(query, connection)
            
            # Close connection
            connection.close()
            
            # Filter out rows with no previous vitals
            df = df.dropna(subset=['prev_temperature', 'prev_heart_rate', 
                                   'prev_bp_systolic', 'prev_bp_diastolic'])
            
            # Process categorical features
            df['gender'] = df['gender'].fillna('Unknown')
            
            # For simplicity, let's predict blood pressure systolic as a demonstration
            X = df[['age_at_recording', 'prev_temperature', 'prev_heart_rate', 
                   'prev_bp_systolic', 'prev_bp_diastolic', 
                   'prev_respiratory_rate', 'prev_oxygen_saturation']]
            
            y = df['blood_pressure_systolic']
            
            return X, y
            
        except Error as e:
            print(f"Error getting training data: {e}")
            if connection:
                connection.close()
            return None, None
    
    def train(self):
        """
        Train the vitals prediction model.
        
        Returns:
            bool: True if training was successful, False otherwise
        """
        # Get training data
        X, y = self.get_training_data()
        
        if X is None or len(X) < 10:  # Need at least some samples to train
            print("Not enough training data available.")
            return False
        
        try:
            # Create preprocessing pipeline
            preprocessor = Pipeline(steps=[
                ('imputer', SimpleImputer(strategy='median')),
                ('scaler', StandardScaler())
            ])
            
            # Create model pipeline
            self.model = Pipeline(steps=[
                ('preprocessor', preprocessor),
                ('regressor', GradientBoostingRegressor(n_estimators=100, random_state=42))
            ])
            
            # Split the data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42
            )
            
            # Train the model
            self.model.fit(X_train, y_train)
            
            # Evaluate the model
            y_pred = self.model.predict(X_test)
            mse = mean_squared_error(y_test, y_pred)
            rmse = np.sqrt(mse)
            
            print("Vitals Prediction Model Evaluation:")
            print(f"Root Mean Squared Error: {rmse:.2f}")
            
            # Save the model
            self.save_model()
            
            return True
            
        except Exception as e:
            print(f"Error training vitals prediction model: {e}")
            return False
    
    def predict(self, patient_data):
        """
        Predict future blood pressure based on current vitals.
        
        Args:
            patient_data (dict): Patient's current vitals and demographic data
            
        Returns:
            dict: Prediction results with predicted blood pressure and risk assessment
        """
        if self.model is None:
            if not os.path.exists(self.model_path):
                self.train()
            else:
                self.load_model()
                
        if self.model is None:
            return {
                'error': 'Model not available',
                'predicted_bp_systolic': None,
                'bp_status': 'Unknown'
            }
        
        try:
            # Convert to DataFrame
            df = pd.DataFrame([patient_data])
            
            # Make prediction
            predicted_bp = self.model.predict(df)[0]
            
            # Determine blood pressure status
            if predicted_bp < 120:
                bp_status = 'Normal'
            elif predicted_bp < 130:
                bp_status = 'Elevated'
            elif predicted_bp < 140:
                bp_status = 'Hypertension Stage 1'
            else:
                bp_status = 'Hypertension Stage 2'
            
            return {
                'predicted_bp_systolic': float(predicted_bp),
                'bp_status': bp_status
            }
            
        except Exception as e:
            print(f"Error predicting blood pressure: {e}")
            return {
                'error': str(e),
                'predicted_bp_systolic': None,
                'bp_status': 'Unknown'
            }
    
    def save_model(self):
        """Save the model to a file."""
        if self.model is not None:
            joblib.dump(self.model, self.model_path)
            print(f"Vitals prediction model saved to {self.model_path}")
    
    def load_model(self):
        """Load the model from a file."""
        if os.path.exists(self.model_path):
            self.model = joblib.load(self.model_path)
            print(f"Vitals prediction model loaded from {self.model_path}")

# Initialize and train models when the module is imported
def initialize_models():
    """Initialize and train all models if needed."""
    print("Initializing machine learning models...")
    
    # Initialize pregnancy risk model
    pregnancy_model = PregnancyRiskModel()
    if not os.path.exists(pregnancy_model.model_path):
        print("Training pregnancy risk model...")
        pregnancy_model.train()
    
    # Initialize follow-up prediction model
    followup_model = FollowUpPredictionModel()
    if not os.path.exists(followup_model.model_path):
        print("Training follow-up prediction model...")
        followup_model.train()
    
    # Initialize vitals prediction model
    vitals_model = VitalsPredictionModel()
    if not os.path.exists(vitals_model.model_path):
        print("Training vitals prediction model...")
        vitals_model.train()
    
    print("Model initialization complete.")

# Only run initialization if this module is run directly
if __name__ == "__main__":
    initialize_models() 
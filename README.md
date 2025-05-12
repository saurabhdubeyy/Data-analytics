# Hospital Patient Management System

A comprehensive hospital patient management system designed to help clinicians track patient information, identify high-risk cases, monitor follow-up compliance, and visualize healthcare analytics.

## Features

### Core Features
- Patient registration and management
- Vital signs tracking
- Medical history management
- Appointment scheduling
- Delivery information tracking
- Follow-up visit scheduling and monitoring
- Lab results storage and analysis

### Enhanced Security and Authentication
- User authentication with JWT
- Role-based access control (Admin, Doctor, Nurse, Receptionist, Data Analyst)
- Secure password handling with bcrypt
- User session management
- Activity logging

### Advanced Analytics
- Machine learning models for risk prediction
  - High-risk pregnancy prediction
  - Follow-up compliance prediction
  - Vitals trend prediction
- Interactive data visualization
- Patient demographic analysis
- Clinical outcome analysis

### Documentation
- API documentation with Swagger/OpenAPI
- Comprehensive code comments
- User guides

## Technical Architecture

### Database
- MySQL relational database
- Normalized schema design
- Optimized queries for analytical insights

### Backend
- Flask-based RESTful API
- Authentication with Flask-JWT-Extended
- Input validation and sanitization
- SQL injection prevention
- Machine learning models using scikit-learn

### Frontend
- HTML/CSS/JavaScript
- Bootstrap for responsive design
- Interactive charts with Chart.js
- Role-based UI components

## Getting Started

### Prerequisites
- Python 3.8+
- MySQL 8.0+
- Node.js (for development)
- AWS CLI (for deployment)

### Installation

1. Clone the repository
```bash
git clone https://github.com/yourusername/hospital-patient-management-system.git
cd hospital-patient-management-system
```

2. Set up the database
```bash
# Create a MySQL database
mysql -u root -p
CREATE DATABASE hospital_db;
exit;

# Import the schema
mysql -u root -p hospital_db < src/database/schema.sql
```

3. Configure environment variables
```bash
cd src/api
cp .env.example .env
# Edit .env with your database credentials and JWT secret
```

4. Install backend dependencies
```bash
cd src/api
pip install -r requirements.txt
```

5. Run the backend
```bash
cd src/api
python app.py
```

6. Access the frontend
```bash
# Open src/frontend/index.html in your browser
```

### Deployment

Use the deployment script to deploy to AWS:
```bash
./deploy.sh
```

For more detailed deployment options, refer to the deployment documentation.

## API Documentation

Once the application is running, access the API documentation at:
```
http://localhost:5000/api/docs
```

## Testing

Run the test suite:
```bash
cd src/api
pytest
```

## Security Features

- JWT authentication
- Password hashing with bcrypt
- Role-based access control
- Input validation and sanitization
- CSRF protection
- API rate limiting
- Secure password reset

## Machine Learning Models

The system includes three machine learning models:

1. **Pregnancy Risk Model**: Predicts high-risk pregnancies based on patient demographics, medical history, and vitals.
2. **Follow-up Prediction Model**: Predicts the likelihood of a patient missing follow-up appointments.
3. **Vitals Prediction Model**: Predicts future vital signs based on historical data.

Models are automatically trained when first needed or can be manually retrained through the API.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- This project was created as part of a junior data scientist assessment
- Special thanks to all contributors and reviewers
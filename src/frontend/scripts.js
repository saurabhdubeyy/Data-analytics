// API base URL - change this to match your backend server
const API_BASE_URL = 'http://localhost:5000/api';

// DOM Elements
document.addEventListener('DOMContentLoaded', function() {
    // Check authentication for protected pages
    checkAuthentication();
    
    // Add logout functionality
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async function(event) {
            event.preventDefault();
            await logout();
            window.location.href = 'login.html';
        });
    }
    
    // Update UI with user info
    updateUserUI();
    
    // Patient form handling
    const patientForm = document.getElementById('patientForm');
    if (patientForm) {
        patientForm.addEventListener('submit', handlePatientFormSubmit);
    }

    // Load patients list if on patients page
    const patientsList = document.getElementById('patientsList');
    if (patientsList) {
        loadPatients();
    }

    // Load analytics if on analytics page
    const analyticsContainer = document.getElementById('analyticsContainer');
    if (analyticsContainer) {
        loadAnalytics();
    }
});

// Check if user is authenticated for protected pages
function checkAuthentication() {
    // Skip check for login and register pages
    if (window.location.pathname.includes('login.html') || 
        window.location.pathname.includes('register.html')) {
        return;
    }
    
    if (!isAuthenticated()) {
        // Redirect to login
        window.location.href = 'login.html';
    }
}

// Update UI with user information
function updateUserUI() {
    const user = getUser();
    
    if (!user) {
        return;
    }
    
    // Update user name in navbar
    const userNameElement = document.getElementById('userName');
    if (userNameElement) {
        userNameElement.textContent = `${user.firstName} ${user.lastName}`;
    }
    
    // Update role badge
    const userRoleElement = document.getElementById('userRole');
    if (userRoleElement) {
        userRoleElement.textContent = user.role;
        
        // Set badge color based on role
        let badgeClass = 'bg-secondary';
        switch (user.role) {
            case 'admin':
                badgeClass = 'bg-danger';
                break;
            case 'doctor':
                badgeClass = 'bg-primary';
                break;
            case 'nurse':
                badgeClass = 'bg-success';
                break;
            case 'receptionist':
                badgeClass = 'bg-info';
                break;
            case 'data_analyst':
                badgeClass = 'bg-warning';
                break;
        }
        
        userRoleElement.className = `badge ${badgeClass}`;
    }
    
    // Show/hide elements based on role
    document.querySelectorAll('[data-role-access]').forEach(element => {
        const allowedRoles = element.dataset.roleAccess.split(',').map(r => r.trim());
        
        if (allowedRoles.includes(user.role)) {
            element.style.display = '';
        } else {
            element.style.display = 'none';
        }
    });
}

// Handle patient form submission
async function handlePatientFormSubmit(event) {
    event.preventDefault();
    
    // Show loading state
    const submitButton = event.target.querySelector('button[type="submit"]');
    const originalButtonText = submitButton.textContent;
    submitButton.disabled = true;
    submitButton.textContent = 'Submitting...';
    
    try {
        // Get form data
        const formData = new FormData(event.target);
        const patientData = {
            first_name: formData.get('firstName'),
            last_name: formData.get('lastName'),
            date_of_birth: formData.get('dateOfBirth'),
            gender: formData.get('gender'),
            email: formData.get('email'),
            phone: formData.get('phone'),
            address: formData.get('address'),
            city: formData.get('city'),
            state: formData.get('state'),
            zip_code: formData.get('zipCode'),
            insurance_provider: formData.get('insuranceProvider'),
            insurance_id: formData.get('insuranceId'),
            emergency_contact_name: formData.get('emergencyContactName'),
            emergency_contact_phone: formData.get('emergencyContactPhone')
        };
        
        // Validate required fields
        const requiredFields = ['first_name', 'last_name', 'date_of_birth'];
        for (const field of requiredFields) {
            if (!patientData[field]) {
                throw new Error(`${field.replace('_', ' ')} is required`);
            }
        }
        
        // Send data to API with authentication
        const response = await authFetch(`${API_BASE_URL}/patients`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(patientData)
        });
        
        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.error || 'Failed to register patient');
        }
        
        const data = await response.json();
        
        // Show success message
        showAlert('success', `Patient registered successfully with ID: ${data.patient_id}`);
        
        // Reset form
        event.target.reset();
    } catch (error) {
        console.error('Error:', error);
        showAlert('danger', error.message);
    } finally {
        // Restore button state
        submitButton.disabled = false;
        submitButton.textContent = originalButtonText;
    }
}

// Load patients list
async function loadPatients() {
    try {
        const patientsList = document.getElementById('patientsList');
        patientsList.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div></div>';
        
        // Use authFetch to make an authenticated request
        const response = await authFetch(`${API_BASE_URL}/patients`);
        
        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.error || 'Failed to load patients');
        }
        
        const patients = await response.json();
        
        // Display patients
        if (patients.length === 0) {
            patientsList.innerHTML = '<div class="alert alert-info">No patients found.</div>';
        } else {
            let html = '<div class="list-group">';
            patients.forEach(patient => {
                html += `
                    <a href="patient-details.html?id=${patient.patient_id}" class="list-group-item list-group-item-action">
                        <div class="d-flex w-100 justify-content-between">
                            <h5 class="mb-1">${patient.first_name} ${patient.last_name}</h5>
                            <small>ID: ${patient.patient_id}</small>
                        </div>
                        <p class="mb-1">Date of Birth: ${formatDate(patient.date_of_birth)}</p>
                        <small>${patient.email || 'No email provided'} | ${patient.phone || 'No phone provided'}</small>
                    </a>
                `;
            });
            html += '</div>';
            patientsList.innerHTML = html;
        }
    } catch (error) {
        console.error('Error:', error);
        document.getElementById('patientsList').innerHTML = `
            <div class="alert alert-danger">
                Failed to load patients: ${error.message}
            </div>
        `;
    }
}

// Load analytics data
async function loadAnalytics() {
    try {
        const analyticsContainer = document.getElementById('analyticsContainer');
        analyticsContainer.innerHTML = '<div class="text-center"><div class="spinner-border" role="status"><span class="visually-hidden">Loading...</span></div></div>';
        
        // Load high-risk pregnancies
        const highRiskResponse = await authFetch(`${API_BASE_URL}/analytics/high-risk-pregnancies`);
        if (!highRiskResponse.ok) {
            const data = await highRiskResponse.json();
            throw new Error(data.error || 'Failed to load high-risk data');
        }
        const highRiskData = await highRiskResponse.json();
        
        // Load missed follow-ups
        const followUpsResponse = await authFetch(`${API_BASE_URL}/analytics/missed-follow-ups`);
        if (!followUpsResponse.ok) {
            const data = await followUpsResponse.json();
            throw new Error(data.error || 'Failed to load follow-up data');
        }
        const followUpsData = await followUpsResponse.json();
        
        // Load demographics
        const demographicsResponse = await authFetch(`${API_BASE_URL}/analytics/demographics`);
        if (!demographicsResponse.ok) {
            const data = await demographicsResponse.json();
            throw new Error(data.error || 'Failed to load demographics data');
        }
        const demographicsData = await demographicsResponse.json();
        
        // Display analytics
        let html = `
            <div class="row">
                <div class="col-md-6 mb-4">
                    <div class="card">
                        <div class="card-header bg-danger text-white">
                            <h5>High-Risk Pregnancies (${highRiskData.length})</h5>
                        </div>
                        <div class="card-body">
                            ${renderHighRiskTable(highRiskData)}
                        </div>
                    </div>
                </div>
                
                <div class="col-md-6 mb-4">
                    <div class="card">
                        <div class="card-header bg-warning">
                            <h5>Missed Follow-ups (${followUpsData.length})</h5>
                        </div>
                        <div class="card-body">
                            ${renderFollowUpsTable(followUpsData)}
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="row">
                <div class="col-12 mb-4">
                    <div class="card">
                        <div class="card-header bg-info">
                            <h5>Patient Demographics</h5>
                        </div>
                        <div class="card-body">
                            ${renderDemographicsTable(demographicsData)}
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        analyticsContainer.innerHTML = html;
        
        // Initialize charts if Chart.js is available
        if (typeof Chart !== 'undefined') {
            createDemographicsChart(demographicsData);
        }
        
        // Update summary counts in dashboard cards
        document.getElementById('totalPatientsCount').textContent = demographicsData.reduce((sum, group) => sum + group.patient_count, 0);
        document.getElementById('highRiskCount').textContent = highRiskData.length;
        document.getElementById('missedFollowUpsCount').textContent = followUpsData.length;
        
        // Count deliveries in the current month
        const thisMonth = new Date().getMonth();
        const thisYear = new Date().getFullYear();
        const deliveriesThisMonth = demographicsData.reduce((sum, group) => sum + group.delivery_count, 0);
        document.getElementById('deliveriesCount').textContent = deliveriesThisMonth;
    } catch (error) {
        console.error('Error:', error);
        document.getElementById('analyticsContainer').innerHTML = `
            <div class="alert alert-danger">
                Failed to load analytics: ${error.message}
            </div>
        `;
    }
}

// Render high-risk pregnancies table
function renderHighRiskTable(data) {
    if (data.length === 0) {
        return '<div class="alert alert-info">No high-risk pregnancies found.</div>';
    }
    
    let html = `
        <div class="table-responsive">
            <table class="table table-striped">
                <thead>
                    <tr>
                        <th>Patient</th>
                        <th>Age</th>
                        <th>Blood Pressure</th>
                        <th>Risk Category</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    data.forEach(patient => {
        html += `
            <tr>
                <td><a href="patient-details.html?id=${patient.patient_id}">${patient.patient_name}</a></td>
                <td>${patient.age}</td>
                <td>${patient.blood_pressure_systolic || 'N/A'}/${patient.blood_pressure_diastolic || 'N/A'}</td>
                <td><span class="badge bg-${getRiskBadgeColor(patient.risk_category)}">${patient.risk_category}</span></td>
            </tr>
        `;
    });
    
    html += `
                </tbody>
            </table>
        </div>
    `;
    
    return html;
}

// Render missed follow-ups table
function renderFollowUpsTable(data) {
    if (data.length === 0) {
        return '<div class="alert alert-info">No missed follow-ups found.</div>';
    }
    
    let html = `
        <div class="table-responsive">
            <table class="table table-striped">
                <thead>
                    <tr>
                        <th>Patient</th>
                        <th>Last Visit</th>
                        <th>Follow-up Due</th>
                        <th>Days Overdue</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    data.forEach(patient => {
        html += `
            <tr>
                <td><a href="patient-details.html?id=${patient.patient_id}">${patient.patient_name}</a></td>
                <td>${formatDate(patient.last_visit_date)}</td>
                <td>${formatDate(patient.scheduled_follow_up)}</td>
                <td><span class="badge bg-${getOverdueBadgeColor(patient.days_overdue)}">${patient.days_overdue}</span></td>
            </tr>
        `;
    });
    
    html += `
                </tbody>
            </table>
        </div>
    `;
    
    return html;
}

// Render demographics table
function renderDemographicsTable(data) {
    if (data.length === 0) {
        return '<div class="alert alert-info">No demographic data found.</div>';
    }
    
    let html = `
        <div class="table-responsive">
            <table class="table table-striped">
                <thead>
                    <tr>
                        <th>Age Group</th>
                        <th>Location</th>
                        <th>Patient Count</th>
                        <th>Unique Conditions</th>
                        <th>Deliveries</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    data.forEach(group => {
        html += `
            <tr>
                <td>${group.age_group}</td>
                <td>${group.city}, ${group.state}</td>
                <td>${group.patient_count}</td>
                <td>${group.unique_conditions}</td>
                <td>${group.delivery_count}</td>
            </tr>
        `;
    });
    
    html += `
                </tbody>
            </table>
        </div>
    `;
    
    return html;
}

// Create demographics chart
function createDemographicsChart(data) {
    // Process data for age distribution chart
    const ageGroups = [...new Set(data.map(item => item.age_group))];
    const ageCounts = ageGroups.map(group => {
        return data
            .filter(item => item.age_group === group)
            .reduce((sum, item) => sum + item.patient_count, 0);
    });
    
    // Update age distribution chart
    const ageCtx = document.getElementById('ageDistributionChart').getContext('2d');
    new Chart(ageCtx, {
        type: 'pie',
        data: {
            labels: ageGroups,
            datasets: [{
                label: 'Patient Age Distribution',
                data: ageCounts,
                backgroundColor: [
                    'rgba(255, 99, 132, 0.7)',
                    'rgba(54, 162, 235, 0.7)',
                    'rgba(255, 206, 86, 0.7)',
                    'rgba(75, 192, 192, 0.7)',
                    'rgba(153, 102, 255, 0.7)'
                ],
                borderColor: [
                    'rgba(255, 99, 132, 1)',
                    'rgba(54, 162, 235, 1)',
                    'rgba(255, 206, 86, 1)',
                    'rgba(75, 192, 192, 1)',
                    'rgba(153, 102, 255, 1)'
                ],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'right',
                },
                title: {
                    display: true,
                    text: 'Patient Age Distribution'
                }
            }
        }
    });
}

// Helper function to format date
function formatDate(dateString) {
    if (!dateString) return 'N/A';
    
    const date = new Date(dateString);
    return date.toLocaleDateString();
}

// Helper function to get risk badge color
function getRiskBadgeColor(riskCategory) {
    switch (riskCategory) {
        case 'Age Risk':
            return 'warning';
        case 'Hypertension Risk':
            return 'danger';
        case 'Previous Complications':
            return 'danger';
        default:
            return 'success';
    }
}

// Helper function to get overdue badge color
function getOverdueBadgeColor(daysOverdue) {
    if (daysOverdue > 30) return 'danger';
    if (daysOverdue > 14) return 'warning';
    return 'info';
}

// Helper function to show alert
function showAlert(type, message) {
    const alertContainer = document.getElementById('alertContainer');
    if (!alertContainer) {
        // Create alert container if it doesn't exist
        const container = document.querySelector('.container');
        const alertDiv = document.createElement('div');
        alertDiv.id = 'alertContainer';
        alertDiv.style.position = 'fixed';
        alertDiv.style.top = '20px';
        alertDiv.style.right = '20px';
        alertDiv.style.zIndex = '1050';
        container.parentNode.insertBefore(alertDiv, container);
    }
    
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show`;
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    document.getElementById('alertContainer').appendChild(alert);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        alert.classList.remove('show');
        setTimeout(() => alert.remove(), 300);
    }, 5000);
} 
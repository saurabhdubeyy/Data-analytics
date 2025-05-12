-- Query 1: High-risk pregnancy identification
-- This query identifies patients who might have high-risk pregnancies based on 
-- vital signs, age, and previous complications
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
    END;

-- Query 2: Follow-up compliance analysis
-- This query identifies patients who missed their follow-up appointments
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
    days_overdue DESC;

-- Query 3: Abnormal vitals trend detection
-- This query identifies patients with consistently abnormal vital signs
SELECT 
    p.patient_id,
    CONCAT(p.first_name, ' ', p.last_name) AS patient_name,
    COUNT(v.vital_id) AS total_measurements,
    AVG(v.temperature) AS avg_temperature,
    AVG(v.heart_rate) AS avg_heart_rate,
    AVG(v.blood_pressure_systolic) AS avg_systolic,
    AVG(v.blood_pressure_diastolic) AS avg_diastolic,
    AVG(v.oxygen_saturation) AS avg_oxygen,
    SUM(CASE WHEN v.temperature > 37.5 THEN 1 ELSE 0 END) AS high_temp_count,
    SUM(CASE WHEN v.heart_rate > 100 THEN 1 ELSE 0 END) AS high_hr_count,
    SUM(CASE WHEN v.blood_pressure_systolic > 140 THEN 1 ELSE 0 END) AS high_bp_systolic_count,
    SUM(CASE WHEN v.blood_pressure_diastolic > 90 THEN 1 ELSE 0 END) AS high_bp_diastolic_count,
    SUM(CASE WHEN v.oxygen_saturation < 95 THEN 1 ELSE 0 END) AS low_oxygen_count
FROM 
    patients p
JOIN 
    vitals v ON p.patient_id = v.patient_id
GROUP BY 
    p.patient_id, patient_name
HAVING 
    (high_temp_count >= 2 OR 
     high_hr_count >= 2 OR 
     high_bp_systolic_count >= 2 OR 
     high_bp_diastolic_count >= 2 OR
     low_oxygen_count >= 2)
ORDER BY 
    (high_temp_count + high_hr_count + high_bp_systolic_count + high_bp_diastolic_count + low_oxygen_count) DESC;

-- Query 4: Delivery method analysis by doctor
-- This query analyzes the rate of different delivery methods by doctor
SELECT 
    d.attending_doctor,
    COUNT(*) AS total_deliveries,
    SUM(CASE WHEN d.delivery_method = 'Vaginal' THEN 1 ELSE 0 END) AS vaginal_deliveries,
    SUM(CASE WHEN d.delivery_method = 'C-section' THEN 1 ELSE 0 END) AS c_section_deliveries,
    ROUND(SUM(CASE WHEN d.delivery_method = 'C-section' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS c_section_rate,
    AVG(d.birth_weight) AS avg_birth_weight
FROM 
    delivery_information d
GROUP BY 
    d.attending_doctor
ORDER BY 
    total_deliveries DESC;

-- Query 5: Patient demographic analysis for targeted health programs
-- This query segments patients by age group and location for targeted health initiatives
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
    p.state, p.city, age_group; 
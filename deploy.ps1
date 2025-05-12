# Hospital Patient Management System AWS Deployment Script
# This script deploys the application to AWS - Free Tier Compatible

Write-Host "Starting deployment process for Hospital Patient Management System (Free Tier)..." -ForegroundColor Green

# Check if AWS CLI is installed
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    Write-Host "AWS CLI is not installed. Please install it first." -ForegroundColor Red
    Write-Host "Visit https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
    exit 1
}

# Check if AWS CLI is configured
try {
    aws sts get-caller-identity | Out-Null
} catch {
    Write-Host "AWS CLI is not configured. Please run 'aws configure' first." -ForegroundColor Red
    exit 1
}

# Set environment variables - Free Tier compatible
$DB_INSTANCE_TYPE = "db.t3.micro" # Free tier eligible
$EC2_INSTANCE_TYPE = "t2.micro"   # Free tier eligible
$PREFIX = "hpms-freetier"
$REGION = "us-east-1"  # Make sure this matches your configured region

# Create S3 bucket for frontend assets
Write-Host "Creating S3 bucket for frontend assets..." -ForegroundColor Green
$BUCKET_NAME = "$PREFIX-frontend-$(Get-Date -UFormat %s)"
aws s3api create-bucket --bucket $BUCKET_NAME --region $REGION

# Create RDS database instance - Free Tier compatible
Write-Host "Creating RDS database instance (Free Tier)..." -ForegroundColor Green
$DB_IDENTIFIER = "$PREFIX-db"
$DB_NAME = "hospital_db"
$DB_USERNAME = "admin"
# Generate a random password
$DB_PASSWORD = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 16 | ForEach-Object {[char]$_})

aws rds create-db-instance `
    --db-instance-identifier "$DB_IDENTIFIER" `
    --db-instance-class "$DB_INSTANCE_TYPE" `
    --engine "mysql" `
    --engine-version "8.0" `
    --allocated-storage 20 `         # Free tier eligible (up to 20GB)
    --db-name "$DB_NAME" `
    --master-username "$DB_USERNAME" `
    --master-user-password "$DB_PASSWORD" `
    --publicly-accessible `
    --backup-retention-period 7 `
    --tags "Key=Environment,Value=freetier"

Write-Host "Waiting for database to be created (this may take several minutes)..." -ForegroundColor Yellow
aws rds wait db-instance-available --db-instance-identifier "$DB_IDENTIFIER"

# Get database endpoint
$DB_ENDPOINT = aws rds describe-db-instances --db-instance-identifier "$DB_IDENTIFIER" --query "DBInstances[0].Endpoint.Address" --output text

# Create EC2 security group
Write-Host "Creating security group for EC2 instance..." -ForegroundColor Green
$SG_NAME = "$PREFIX-sg"
$SG_ID = aws ec2 create-security-group --group-name "$SG_NAME" --description "Security group for Hospital Patient Management System" --output text --query 'GroupId'

# Allow HTTP, HTTPS, and SSH traffic
aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 80 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 443 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 22 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 5000 --cidr 0.0.0.0/0

# Create EC2 instance for backend API - Free Tier compatible
Write-Host "Creating EC2 instance for backend API (Free Tier t2.micro)..." -ForegroundColor Green
$EC2_NAME = "$PREFIX-api"

# Create user data script for EC2 instance
$JWT_SECRET = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object {[char]$_})

$USER_DATA = @"
#!/bin/bash
apt-get update
apt-get install -y python3-pip python3-dev nginx git
pip3 install virtualenv

# Clone the repository
git clone https://github.com/saurabhdubeyy/Data-analytics.git /home/ubuntu/app

# Setup virtual environment
cd /home/ubuntu/app
virtualenv venv
source venv/bin/activate
pip install -r src/api/requirements.txt

# Configure environment variables
cat > /home/ubuntu/app/src/api/.env <<EOL
DB_HOST=$DB_ENDPOINT
DB_USER=$DB_USERNAME
DB_PASSWORD=$DB_PASSWORD
DB_NAME=$DB_NAME
JWT_SECRET_KEY=$JWT_SECRET
DEBUG=False
PORT=5000
HOST=0.0.0.0
EOL

# Setup systemd service
cat > /etc/systemd/system/hpms-api.service <<EOL
[Unit]
Description=Hospital Patient Management System API
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/app/src/api
Environment="PATH=/home/ubuntu/app/venv/bin"
ExecStart=/home/ubuntu/app/venv/bin/gunicorn --workers 2 --bind 0.0.0.0:5000 app:app

[Install]
WantedBy=multi-user.target
EOL

# Setup Nginx
cat > /etc/nginx/sites-available/hpms <<EOL
server {
    listen 80;
    server_name _;

    location /api {
        proxy_pass http://localhost:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }

    location / {
        root /home/ubuntu/app/src/frontend;
        index index.html;
        try_files \$uri /index.html;
    }
}
EOL

ln -s /etc/nginx/sites-available/hpms /etc/nginx/sites-enabled
rm /etc/nginx/sites-enabled/default

# Start services
systemctl daemon-reload
systemctl start hpms-api
systemctl enable hpms-api
systemctl restart nginx

# Initialize the database
cd /home/ubuntu/app/src/database
mysql -h $DB_ENDPOINT -u $DB_USERNAME -p$DB_PASSWORD $DB_NAME < schema.sql
"@

# Launch EC2 instance - Free Tier compatible AMI (Amazon Linux 2)
# ami-0261755bbcb8c4a84 is Ubuntu, using Amazon Linux 2 AMI instead which is free tier eligible
$INSTANCE_ID = aws ec2 run-instances `
    --image-id "ami-0230bd60aa48260c6" `  # Amazon Linux 2 AMI - Free tier eligible
    --instance-type "$EC2_INSTANCE_TYPE" `
    --security-group-ids "$SG_ID" `
    --user-data "$USER_DATA" `
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$EC2_NAME}]" `
    --query 'Instances[0].InstanceId' `
    --output text

Write-Host "Waiting for EC2 instance to start..." -ForegroundColor Yellow
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"

# Get EC2 public IP
$EC2_IP = aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --query 'Reservations[0].Instances[0].PublicIpAddress' --output text

# Deploy frontend to S3
Write-Host "Deploying frontend to S3..." -ForegroundColor Green
# Replace API URL in frontend files (PowerShell version)
$frontendFiles = @("src/frontend/auth.js", "src/frontend/scripts.js")
foreach ($file in $frontendFiles) {
    (Get-Content $file) -replace 'http://localhost:5000/api', "http://$EC2_IP/api" | Set-Content $file
}

# Upload frontend files to S3
aws s3 sync src/frontend/ s3://$BUCKET_NAME/ --acl public-read

# Configure S3 bucket for static website hosting
aws s3 website s3://$BUCKET_NAME/ --index-document index.html --error-document index.html

# Get S3 website URL
$S3_URL = "http://$BUCKET_NAME.s3-website-$REGION.amazonaws.com"

# Summary
Write-Host "`n====== Deployment Summary (Free Tier) ======" -ForegroundColor Green
Write-Host "Environment: FREE TIER" -ForegroundColor Yellow
Write-Host "Database endpoint: $DB_ENDPOINT" -ForegroundColor Yellow
Write-Host "Database name: $DB_NAME" -ForegroundColor Yellow
Write-Host "Database username: $DB_USERNAME" -ForegroundColor Yellow
Write-Host "Database password: $DB_PASSWORD" -ForegroundColor Yellow
Write-Host "Backend API server: http://$EC2_IP" -ForegroundColor Yellow
Write-Host "Frontend URL: $S3_URL" -ForegroundColor Yellow
Write-Host "S3 bucket name: $BUCKET_NAME" -ForegroundColor Yellow
Write-Host "=========================================" -ForegroundColor Green

Write-Host "`nDeployment completed successfully!" -ForegroundColor Green
Write-Host "NOTE: It may take a few minutes for the EC2 instance to complete its startup script." -ForegroundColor Yellow
Write-Host "For SSH access: ssh ec2-user@$EC2_IP" -ForegroundColor Yellow
Write-Host "IMPORTANT: To stay within free tier limits, remember to delete these resources when not in use with:" -ForegroundColor Red
Write-Host "aws rds delete-db-instance --db-instance-identifier $DB_IDENTIFIER --skip-final-snapshot" -ForegroundColor Yellow
Write-Host "aws ec2 terminate-instances --instance-ids $INSTANCE_ID" -ForegroundColor Yellow
Write-Host "aws s3 rb s3://$BUCKET_NAME --force" -ForegroundColor Yellow 
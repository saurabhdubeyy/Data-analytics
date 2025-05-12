#!/bin/bash

# Hospital Patient Management System AWS Deployment Script
# This script deploys the application to AWS

# Colors for console output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting deployment process for Hospital Patient Management System...${NC}"

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}AWS CLI is not installed. Please install it first.${NC}"
    echo "Visit https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
    exit 1
fi

# Check if AWS CLI is configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}AWS CLI is not configured. Please run 'aws configure' first.${NC}"
    exit 1
fi

# Ask for environment (development, production)
echo -e "${YELLOW}Which environment do you want to deploy to? (dev/prod)${NC}"
read ENV

if [ "$ENV" != "dev" ] && [ "$ENV" != "prod" ]; then
    echo -e "${RED}Invalid environment. Please specify 'dev' or 'prod'.${NC}"
    exit 1
fi

# Set environment-specific variables
if [ "$ENV" = "dev" ]; then
    DB_INSTANCE_TYPE="db.t3.micro"
    EC2_INSTANCE_TYPE="t2.micro"
    PREFIX="hpms-dev"
else
    DB_INSTANCE_TYPE="db.t3.small"
    EC2_INSTANCE_TYPE="t2.small"
    PREFIX="hpms-prod"
fi

# Create S3 bucket for frontend assets
echo -e "${GREEN}Creating S3 bucket for frontend assets...${NC}"
BUCKET_NAME="$PREFIX-frontend-$(date +%s)"
aws s3api create-bucket --bucket $BUCKET_NAME --region us-east-1

# Create RDS database instance
echo -e "${GREEN}Creating RDS database instance...${NC}"
DB_IDENTIFIER="$PREFIX-db"
DB_NAME="hospital_db"
DB_USERNAME="admin"
DB_PASSWORD="$(openssl rand -base64 12)"

aws rds create-db-instance \
    --db-instance-identifier $DB_IDENTIFIER \
    --db-instance-class $DB_INSTANCE_TYPE \
    --engine mysql \
    --engine-version 8.0 \
    --allocated-storage 20 \
    --db-name $DB_NAME \
    --master-username $DB_USERNAME \
    --master-user-password $DB_PASSWORD \
    --publicly-accessible \
    --backup-retention-period 7 \
    --tags Key=Environment,Value=$ENV

echo -e "${YELLOW}Waiting for database to be created (this may take several minutes)...${NC}"
aws rds wait db-instance-available --db-instance-identifier $DB_IDENTIFIER

# Get database endpoint
DB_ENDPOINT=$(aws rds describe-db-instances --db-instance-identifier $DB_IDENTIFIER --query "DBInstances[0].Endpoint.Address" --output text)

# Create EC2 security group
echo -e "${GREEN}Creating security group for EC2 instance...${NC}"
SG_NAME="$PREFIX-sg"
SG_ID=$(aws ec2 create-security-group --group-name $SG_NAME --description "Security group for Hospital Patient Management System" --output text --query 'GroupId')

# Allow HTTP, HTTPS, and SSH traffic
aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port 80 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port 443 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port 22 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-id $SG_ID --protocol tcp --port 5000 --cidr 0.0.0.0/0

# Create EC2 instance for backend API
echo -e "${GREEN}Creating EC2 instance for backend API...${NC}"
EC2_NAME="$PREFIX-api"

# Create user data script for EC2 instance
USER_DATA=$(cat <<EOF
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
JWT_SECRET_KEY=$(openssl rand -base64 32)
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
ExecStart=/home/ubuntu/app/venv/bin/gunicorn --workers 3 --bind 0.0.0.0:5000 app:app

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
EOF
)

# Launch EC2 instance
INSTANCE_ID=$(aws ec2 run-instances \
    --image-id ami-0261755bbcb8c4a84 \
    --instance-type $EC2_INSTANCE_TYPE \
    --security-group-ids $SG_ID \
    --user-data "$USER_DATA" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$EC2_NAME}]" \
    --query 'Instances[0].InstanceId' \
    --output text)

echo -e "${YELLOW}Waiting for EC2 instance to start...${NC}"
aws ec2 wait instance-running --instance-ids $INSTANCE_ID

# Get EC2 public IP
EC2_IP=$(aws ec2 describe-instances --instance-ids $INSTANCE_ID --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)

# Deploy frontend to S3
echo -e "${GREEN}Deploying frontend to S3...${NC}"
# Replace API URL in frontend files
sed -i "s|http://localhost:5000/api|http://$EC2_IP/api|g" src/frontend/auth.js
sed -i "s|http://localhost:5000/api|http://$EC2_IP/api|g" src/frontend/scripts.js

# Upload frontend files to S3
aws s3 sync src/frontend/ s3://$BUCKET_NAME/ --acl public-read

# Configure S3 bucket for static website hosting
aws s3 website s3://$BUCKET_NAME/ --index-document index.html --error-document index.html

# Get S3 website URL
S3_URL="http://$BUCKET_NAME.s3-website-us-east-1.amazonaws.com"

# Summary
echo -e "${GREEN}\n====== Deployment Summary ======${NC}"
echo -e "Environment: ${YELLOW}$ENV${NC}"
echo -e "Database endpoint: ${YELLOW}$DB_ENDPOINT${NC}"
echo -e "Database name: ${YELLOW}$DB_NAME${NC}"
echo -e "Database username: ${YELLOW}$DB_USERNAME${NC}"
echo -e "Database password: ${YELLOW}$DB_PASSWORD${NC}"
echo -e "Backend API server: ${YELLOW}http://$EC2_IP${NC}"
echo -e "Frontend URL: ${YELLOW}$S3_URL${NC}"
echo -e "S3 bucket name: ${YELLOW}$BUCKET_NAME${NC}"
echo -e "${GREEN}=================================${NC}"

echo -e "${GREEN}\nDeployment completed successfully!${NC}"
echo -e "${YELLOW}NOTE: It may take a few minutes for the EC2 instance to complete its startup script.${NC}"
echo -e "${YELLOW}You can SSH into the instance with: ssh ubuntu@$EC2_IP${NC}"
echo -e "${YELLOW}For production deployments, consider setting up HTTPS with a domain name and SSL certificate.${NC}" 
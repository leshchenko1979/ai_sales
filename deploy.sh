#!/bin/bash

set -e  # Exit on any error

# Load environment variables
if [ ! -f .env ]; then
    echo "Error: .env file not found!"
    exit 1
fi

source .env

echo "Running code quality checks..."

# Check Python installation
if ! command -v python &> /dev/null && ! command -v python3 &> /dev/null; then
    echo "Python is not installed!"
    exit 1
fi

# Use python3 if available, otherwise use python
if command -v python3 &> /dev/null; then
    PYTHON_CMD=python3
else
    PYTHON_CMD=python
fi

# Check if we're in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Creating virtual environment..."
    # Create new venv
    $PYTHON_CMD -m venv venv || {
        echo "Failed to create virtual environment"
        exit 1
    }
    # Activate venv with proper path based on OS
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
        source venv/Scripts/activate
    else
        source venv/bin/activate
    fi
    # Install requirements
    pip install -r requirements.local.txt
fi

# Run isort to sort imports
echo "Running isort..."
isort jeeves tests

# Run black for code formatting
echo "Running black..."
black jeeves tests

# Run tests
echo "Running tests..."
pytest tests -v

# If any of the above commands failed, exit
if [ $? -ne 0 ]; then
    echo "Tests failed! Aborting deployment."
    exit 1
fi

echo "Starting deployment of Jeeves to ${REMOTE_HOST}..."

# Check Docker and Docker Compose installation on remote
echo "Checking Docker installation..."
ssh ${REMOTE_USER}@${REMOTE_HOST} '
    if ! command -v docker &> /dev/null; then
        echo "Docker is not installed. Installing Docker..."
        curl -fsSL https://get.docker.com -o get-docker.sh
        sudo sh get-docker.sh
        sudo usermod -aG docker $USER
        rm get-docker.sh
    fi

    if ! command -v docker compose &> /dev/null; then
        echo "Docker Compose is not installed. Installing Docker Compose..."
        sudo curl -L "https://github.com/docker/compose/releases/download/v2.23.3/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose
        sudo ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose
    fi
'

# Create deployment directory
echo "Creating remote directory structure..."
ssh ${REMOTE_USER}@${REMOTE_HOST} "mkdir -p /home/jeeves/docker"

# Copy necessary files
echo "Copying Docker files..."
scp Dockerfile docker-compose.yml .dockerignore .env ${REMOTE_USER}@${REMOTE_HOST}:/home/jeeves/docker/

# Create a temporary directory for the build
echo "Preparing project files..."
TEMP_DIR=$(mktemp -d)
cp -r . "$TEMP_DIR/"
cd "$TEMP_DIR"

# Create the tar file
echo "Creating deployment archive..."
tar --exclude-from=.dockerignore -czf deploy.tar.gz .

# Copy and extract files
echo "Copying project files..."
scp deploy.tar.gz ${REMOTE_USER}@${REMOTE_HOST}:/home/jeeves/docker/
ssh ${REMOTE_USER}@${REMOTE_HOST} "cd /home/jeeves/docker && tar xzf deploy.tar.gz && rm deploy.tar.gz"

# Clean up
cd - > /dev/null
rm -rf "$TEMP_DIR"

# Build and deploy on remote using full paths
echo "Building and starting Docker container..."
ssh ${REMOTE_USER}@${REMOTE_HOST} '
    cd /home/jeeves/docker && \
    if command -v docker compose &> /dev/null; then
        docker compose down && docker compose up -d --build
    else
        /usr/local/bin/docker-compose down && /usr/local/bin/docker-compose up -d --build
    fi
'

# Check container status
echo "Checking container status..."
ssh ${REMOTE_USER}@${REMOTE_HOST} "docker ps | grep jeeves || echo 'Container not found!'"

echo "Deployment completed successfully!"

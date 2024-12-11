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

# Set up logs directory structure and permissions
echo "Setting up logs directory structure..."
ssh ${REMOTE_USER}@${REMOTE_HOST} '
    # Create and set up new logs directory
    rm -rf /home/jeeves/*
    mkdir -p /home/jeeves/logs

    # Set proper ownership and permissions
    chown -R jeeves:jeeves /home/jeeves/logs
    chmod 755 /home/jeeves/logs
'

# Remove local tar file if it exists
echo "Creating Python package archive..."

TEMP_DIR=$(mktemp -d)
if [ -f "$TEMP_DIR/jeeves.tar.gz" ]; then
    rm "$TEMP_DIR/jeeves.tar.gz"
fi
tar \
    --exclude='venv' \
    --exclude='*.pyc' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='.pytest_cache' \
    --exclude='node_modules' \
    --exclude='Dockerfile' \
    --exclude='docker-compose.yml' \
    --exclude='.env' \
    --exclude='.dockerignore' \
    -czf "$TEMP_DIR/jeeves.tar.gz" jeeves/

# Copy and extract Python package
echo "Copying and extracting Python package..."
scp "$TEMP_DIR/jeeves.tar.gz" ${REMOTE_USER}@${REMOTE_HOST}:/home/jeeves/
ssh ${REMOTE_USER}@${REMOTE_HOST} "cd /home/jeeves && tar xzf jeeves.tar.gz && rm jeeves.tar.gz && ls -la"

# Copy Docker configuration files
echo "Copying Docker configuration files..."
scp Dockerfile docker-compose.yml .dockerignore .env ${REMOTE_USER}@${REMOTE_HOST}:/home/jeeves/

# Copy requirements and app files to the correct location
scp requirements.txt ${REMOTE_USER}@${REMOTE_HOST}:/home/jeeves/

# Clean up
rm -rf "$TEMP_DIR"

# Build and deploy on remote
echo "Building and starting Docker container..."
ssh ${REMOTE_USER}@${REMOTE_HOST} '
    cd /home/jeeves && \
    if command -v docker compose &> /dev/null; then
        echo "Stopping existing container..."
        docker compose stop --timeout 10 || true
        echo "Removing container..."
        docker compose rm -f || true
        echo "Building and starting new container..."
        docker compose up -d --build
    else
        echo "Stopping existing container..."
        /usr/local/bin/docker-compose stop --timeout 10 || true
        echo "Removing container..."
        /usr/local/bin/docker-compose rm -f || true
        echo "Building and starting new container..."
        /usr/local/bin/docker-compose up -d --build
    fi
'

# Check container status
echo "Checking container status..."
ssh ${REMOTE_USER}@${REMOTE_HOST} "docker ps | grep jeeves || echo 'Container not found!'"

echo "Deployment completed successfully!"

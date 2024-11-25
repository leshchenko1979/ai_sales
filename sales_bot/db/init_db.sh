#!/bin/bash

# Stop on any error
set -e

# Restart PostgreSQL (adjust service name if needed)
echo "Restarting PostgreSQL..."
sudo service postgresql restart

# Run the SQL script as postgres user
echo "Running initialization script..."
chmod +x init_db.sql
sudo -u postgres psql -f "init_db.sql"

echo "Database initialization completed!"

#!/bin/bash

# Stop on any error
set -e

# Restart PostgreSQL (adjust service name if needed)
echo "Restarting PostgreSQL..."
sudo service postgresql restart

# Create temp directory and copy SQL file
echo "Copying initialization script..."
TEMP_DIR=$(mktemp -d)
cp "$(dirname "$0")/init_db.sql" "$TEMP_DIR/init_db.sql"

# Run the SQL script as postgres user
echo "Running initialization script..."
sudo -u postgres psql -f "$TEMP_DIR/init_db.sql"

# Cleanup
echo "Cleaning up..."
rm -rf "$TEMP_DIR"

echo "Database initialization completed!"

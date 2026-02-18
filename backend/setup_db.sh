#!/bin/bash

# Simple Database Setup Script for Policy Chatbot
# Usage: ./setup_database.sh [dimensions]
# Example: ./setup_database.sh 384

set -e  # Exit on any error

# Database configuration
DB_NAME="chatbot_db"
DB_USER="postgres"
DB_HOST="localhost"

# Get dimensions from command line argument or default to 384
DIMENSIONS=${1:-384}

echo "Setting up database '$DB_NAME' with $DIMENSIONS dimensions..."

# Terminate existing connections
echo "Terminating existing connections..."
psql -h $DB_HOST -U $DB_USER -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();" > /dev/null 2>&1 || true

# Drop and create database
echo "Dropping and creating database..."
psql -h $DB_HOST -U $DB_USER -d postgres -c "DROP DATABASE IF EXISTS $DB_NAME;"
psql -h $DB_HOST -U $DB_USER -d postgres -c "CREATE DATABASE $DB_NAME;"

# Add pgvector extension
echo "Adding pgvector extension..."
psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Update local.py with the dimension
echo "Updating EMBEDDING_DIMENSIONS to $DIMENSIONS in local.py..."
sed -i.bak "s/EMBEDDING_DIMENSIONS = [0-9]*/EMBEDDING_DIMENSIONS = $DIMENSIONS/" config/settings/local.py

# Run migrations
echo "Running migrations..."
python3 manage.py makemigrations
python3 manage.py migrate

echo "✓ Database setup complete!"
echo "✓ Database: $DB_NAME"
echo "✓ Dimensions: $DIMENSIONS"
echo "✓ pgvector extension added"

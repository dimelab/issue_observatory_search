#!/bin/bash
# Setup test database for pytest

set -e  # Exit on error

echo "Setting up test database for Issue Observatory Search..."
echo ""

# Check if PostgreSQL container is running
if ! docker ps | grep -q postgres; then
    echo "❌ PostgreSQL container not running. Starting it..."
    docker-compose up -d postgres
    echo "⏳ Waiting for PostgreSQL to be ready..."
    sleep 5
fi

# Get the container name
CONTAINER_NAME=$(docker ps --filter "name=postgres" --format "{{.Names}}" | head -1)

if [ -z "$CONTAINER_NAME" ]; then
    echo "❌ Could not find PostgreSQL container. Make sure docker-compose is running."
    echo "   Try: docker-compose up -d postgres"
    exit 1
fi

echo "✅ Found PostgreSQL container: $CONTAINER_NAME"
echo ""

# Drop existing test database if it exists
echo "🗑️  Dropping existing test database (if exists)..."
docker exec $CONTAINER_NAME psql -U postgres -c "DROP DATABASE IF EXISTS test_issue_observatory;" 2>/dev/null || true

# Drop existing test user if exists
echo "🗑️  Dropping existing test user (if exists)..."
docker exec $CONTAINER_NAME psql -U postgres -c "DROP OWNED BY test CASCADE;" 2>/dev/null || true
docker exec $CONTAINER_NAME psql -U postgres -c "DROP USER IF EXISTS test;" 2>/dev/null || true

# Create test user with proper permissions
echo "👤 Creating test user..."
docker exec $CONTAINER_NAME psql -U postgres -c "CREATE USER test WITH PASSWORD 'test' CREATEDB;"

# Create test database
echo "💾 Creating test database..."
docker exec $CONTAINER_NAME psql -U postgres -c "CREATE DATABASE test_issue_observatory OWNER test;"

# Grant all privileges
echo "🔐 Granting privileges..."
docker exec $CONTAINER_NAME psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE test_issue_observatory TO test;"
docker exec $CONTAINER_NAME psql -U postgres -d test_issue_observatory -c "GRANT ALL ON SCHEMA public TO test;"

# Verify the user can connect
echo ""
echo "🔍 Verifying test user connection..."
if docker exec $CONTAINER_NAME psql -U test -d test_issue_observatory -c "SELECT 1;" > /dev/null 2>&1; then
    echo "✅ Test user can connect successfully!"
else
    echo "❌ Test user connection failed!"
    echo ""
    echo "Trying to diagnose the issue..."
    docker exec $CONTAINER_NAME psql -U postgres -c "\du test"
    docker exec $CONTAINER_NAME psql -U postgres -c "\l test_issue_observatory"
    exit 1
fi

echo ""
echo "✅ Test database setup complete!"
echo ""
echo "Configuration:"
echo "  Database: test_issue_observatory"
echo "  User: test"
echo "  Password: test"
echo "  Host: localhost"
echo "  Port: 5433 (external)"
echo ""
echo "Connection URL:"
echo "  postgresql+psycopg://test:test@localhost:5433/test_issue_observatory"
echo ""
echo "You can now run tests with:"
echo "  pytest -v"
echo "  pytest tests/test_auth.py -v"
echo "  pytest --cov=backend --cov-report=term-missing"
echo ""

#!/bin/bash
# Setup test database for pytest

echo "Setting up test database for Issue Observatory Search..."

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
    exit 1
fi

echo "✅ Found PostgreSQL container: $CONTAINER_NAME"

# Drop existing test database if it exists
echo "🗑️  Dropping existing test database (if exists)..."
docker exec -it $CONTAINER_NAME psql -U postgres -c "DROP DATABASE IF EXISTS test_issue_observatory;" 2>/dev/null

# Drop existing test user if exists
echo "🗑️  Dropping existing test user (if exists)..."
docker exec -it $CONTAINER_NAME psql -U postgres -c "DROP USER IF EXISTS test;" 2>/dev/null

# Create test user
echo "👤 Creating test user..."
docker exec -it $CONTAINER_NAME psql -U postgres -c "CREATE USER test WITH PASSWORD 'test';"

# Create test database
echo "💾 Creating test database..."
docker exec -it $CONTAINER_NAME psql -U postgres -c "CREATE DATABASE test_issue_observatory OWNER test;"

# Grant privileges
echo "🔐 Granting privileges..."
docker exec -it $CONTAINER_NAME psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE test_issue_observatory TO test;"

# Verify setup
echo ""
echo "✅ Test database setup complete!"
echo ""
echo "Database URL: postgresql+psycopg://test:test@localhost:5433/test_issue_observatory"
echo ""
echo "Note: The tests use port 5433 (external) which maps to 5432 (internal)"
echo "This matches the docker-compose.yml configuration"
echo ""
echo "You can now run tests with:"
echo "  pytest -v"
echo "  pytest --cov=backend --cov-report=term-missing"
echo ""

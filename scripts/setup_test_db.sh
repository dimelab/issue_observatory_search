#!/bin/bash
# Setup test database for pytest

set -e  # Exit on error

echo "=========================================="
echo "Test Database Setup for Issue Observatory"
echo "=========================================="
echo ""

# Detect docker compose command (v1 vs v2)
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    echo "❌ Neither 'docker-compose' nor 'docker compose' found"
    echo "   Please install Docker Compose"
    exit 1
fi

echo "ℹ️  Using: $DOCKER_COMPOSE"
echo ""

# Function to check if PostgreSQL is running and ready
check_postgres() {
    # Check if container is running via docker compose
    if $DOCKER_COMPOSE ps postgres 2>/dev/null | grep -qE "Up|running"; then
        # Check if it's actually ready to accept connections
        if $DOCKER_COMPOSE exec -T postgres pg_isready -U postgres >/dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# Function to wait for PostgreSQL to be ready
wait_for_postgres() {
    echo "⏳ Waiting for PostgreSQL to be ready..."
    for i in {1..30}; do
        if $DOCKER_COMPOSE exec -T postgres pg_isready -U postgres >/dev/null 2>&1; then
            echo "✅ PostgreSQL is ready!"
            return 0
        fi
        echo "   Attempt $i/30..."
        sleep 1
    done
    echo "❌ PostgreSQL did not become ready in time"
    return 1
}

# Check if PostgreSQL is running
echo "🔍 Checking PostgreSQL status..."
if check_postgres; then
    echo "✅ PostgreSQL is running and ready"
else
    echo "❌ PostgreSQL not running or not ready"
    echo "🚀 Starting PostgreSQL container..."

    if ! $DOCKER_COMPOSE up -d postgres; then
        echo "❌ Failed to start PostgreSQL"
        echo "   Try: $DOCKER_COMPOSE up -d postgres"
        exit 1
    fi

    # Wait for it to be ready
    if ! wait_for_postgres; then
        echo "❌ PostgreSQL started but not accepting connections"
        echo "   Check logs: $DOCKER_COMPOSE logs postgres"
        exit 1
    fi
fi

echo ""

# Get the container name
CONTAINER_NAME=$($DOCKER_COMPOSE ps postgres --format json 2>/dev/null | grep -o '"Name":"[^"]*"' | cut -d'"' -f4 | head -1)

# Fallback to docker ps if docker-compose ps doesn't work
if [ -z "$CONTAINER_NAME" ]; then
    CONTAINER_NAME=$(docker ps --filter "name=postgres" --format "{{.Names}}" | head -1)
fi

if [ -z "$CONTAINER_NAME" ]; then
    echo "❌ Could not find PostgreSQL container name"
    echo "   Available containers:"
    docker ps --format "   - {{.Names}}"
    exit 1
fi

echo "✅ Found PostgreSQL container: $CONTAINER_NAME"
echo ""

# Drop existing test database if it exists
echo "🗑️  Cleaning up existing test database..."
docker exec $CONTAINER_NAME psql -U postgres -c "DROP DATABASE IF EXISTS test_issue_observatory;" 2>/dev/null || true

# Drop existing test user if exists
echo "🗑️  Cleaning up existing test user..."
docker exec $CONTAINER_NAME psql -U postgres -c "DROP OWNED BY test CASCADE;" 2>/dev/null || true
docker exec $CONTAINER_NAME psql -U postgres -c "DROP USER IF EXISTS test;" 2>/dev/null || true

echo ""

# Create test user with proper permissions
echo "👤 Creating test user..."
if ! docker exec $CONTAINER_NAME psql -U postgres -c "CREATE USER test WITH PASSWORD 'test' CREATEDB;"; then
    echo "❌ Failed to create test user"
    exit 1
fi

# Create test database
echo "💾 Creating test database..."
if ! docker exec $CONTAINER_NAME psql -U postgres -c "CREATE DATABASE test_issue_observatory OWNER test;"; then
    echo "❌ Failed to create test database"
    exit 1
fi

# Grant all privileges
echo "🔐 Granting privileges..."
docker exec $CONTAINER_NAME psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE test_issue_observatory TO test;" || true
docker exec $CONTAINER_NAME psql -U postgres -d test_issue_observatory -c "GRANT ALL ON SCHEMA public TO test;" || true

echo ""

# Verify the user can connect
echo "🔍 Verifying test user connection..."
if docker exec $CONTAINER_NAME psql -U test -d test_issue_observatory -c "SELECT current_database(), current_user;" > /dev/null 2>&1; then
    echo "✅ Test user can connect successfully!"
else
    echo "❌ Test user connection failed!"
    echo ""
    echo "Diagnosis:"
    echo "=========================================="
    echo "User info:"
    docker exec $CONTAINER_NAME psql -U postgres -c "\du test" || true
    echo ""
    echo "Database info:"
    docker exec $CONTAINER_NAME psql -U postgres -c "\l test_issue_observatory" || true
    echo "=========================================="
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ Test database setup complete!"
echo "=========================================="
echo ""
echo "Configuration:"
echo "  Database: test_issue_observatory"
echo "  User:     test"
echo "  Password: test"
echo "  Host:     localhost"
echo "  Port:     5433 (external) → 5432 (container)"
echo ""
echo "Connection URL:"
echo "  postgresql+psycopg://test:test@localhost:5433/test_issue_observatory"
echo ""
echo "Next steps:"
echo "  1. Run tests:          pytest tests/test_auth.py -v"
echo "  2. All tests:          pytest -v"
echo "  3. With coverage:      pytest --cov=backend --cov-report=term-missing"
echo "  4. Parallel execution: pytest -n auto -v"
echo ""
echo "Note: Your production database is safe and unaffected!"
echo ""

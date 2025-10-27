# Test Database Troubleshooting

## Issue: Password authentication failed for user "test"

```
sqlalchemy.exc.OperationalError: (psycopg.OperationalError)
connection failed: FATAL: password authentication failed for user "test"
```

## Quick Fix

Run the updated setup script:

```bash
bash scripts/setup_test_db.sh
```

## Manual Setup (If Script Fails)

### Step 1: Find PostgreSQL Container

```bash
docker ps | grep postgres
```

You should see something like:
```
issue_observatory_search-postgres-1   postgres:15
```

### Step 2: Drop Existing Test User and Database

```bash
# Replace CONTAINER_NAME with your actual container name
CONTAINER_NAME="issue_observatory_search-postgres-1"

# Drop database
docker exec $CONTAINER_NAME psql -U postgres -c "DROP DATABASE IF EXISTS test_issue_observatory;"

# Drop user and owned objects
docker exec $CONTAINER_NAME psql -U postgres -c "DROP OWNED BY test CASCADE;" 2>/dev/null
docker exec $CONTAINER_NAME psql -U postgres -c "DROP USER IF EXISTS test;" 2>/dev/null
```

### Step 3: Create Test User with Password

```bash
# Create user with CREATEDB permission
docker exec $CONTAINER_NAME psql -U postgres -c "CREATE USER test WITH PASSWORD 'test' CREATEDB;"
```

### Step 4: Create Test Database

```bash
# Create database owned by test user
docker exec $CONTAINER_NAME psql -U postgres -c "CREATE DATABASE test_issue_observatory OWNER test;"
```

### Step 5: Grant Privileges

```bash
# Grant database-level privileges
docker exec $CONTAINER_NAME psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE test_issue_observatory TO test;"

# Grant schema-level privileges
docker exec $CONTAINER_NAME psql -U postgres -d test_issue_observatory -c "GRANT ALL ON SCHEMA public TO test;"
```

### Step 6: Verify Connection

```bash
# Test connection as test user
docker exec $CONTAINER_NAME psql -U test -d test_issue_observatory -c "SELECT 1;"
```

Should output:
```
 ?column?
----------
        1
(1 row)
```

## Common Issues

### Issue 1: Container Not Found

**Error**: "Could not find PostgreSQL container"

**Solution**:
```bash
# Start PostgreSQL container
docker-compose up -d postgres

# Wait a few seconds
sleep 5

# Verify it's running
docker ps | grep postgres
```

### Issue 2: Connection Refused

**Error**: "connection refused"

**Possible causes**:
1. PostgreSQL not started
2. Wrong port (should be 5433 externally, 5432 internally)
3. Container networking issue

**Solution**:
```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check logs
docker-compose logs postgres | tail -20

# Restart if needed
docker-compose restart postgres
```

### Issue 3: Role "test" already exists

**Error**: `ERROR: role "test" already exists`

**Solution**:
```bash
# First drop all objects owned by the user
docker exec $CONTAINER_NAME psql -U postgres -c "DROP OWNED BY test CASCADE;"

# Then drop the user
docker exec $CONTAINER_NAME psql -U postgres -c "DROP USER test;"

# Now recreate
docker exec $CONTAINER_NAME psql -U postgres -c "CREATE USER test WITH PASSWORD 'test' CREATEDB;"
```

### Issue 4: Database "test_issue_observatory" already exists

**Error**: `ERROR: database "test_issue_observatory" already exists`

**Solution**:
```bash
# Drop the database
docker exec $CONTAINER_NAME psql -U postgres -c "DROP DATABASE test_issue_observatory;"

# Recreate it
docker exec $CONTAINER_NAME psql -U postgres -c "CREATE DATABASE test_issue_observatory OWNER test;"
```

### Issue 5: Permission denied for schema public

**Error**: `permission denied for schema public`

**Solution**:
```bash
# Grant schema permissions
docker exec $CONTAINER_NAME psql -U postgres -d test_issue_observatory -c "GRANT ALL ON SCHEMA public TO test;"
docker exec $CONTAINER_NAME psql -U postgres -d test_issue_observatory -c "GRANT ALL ON ALL TABLES IN SCHEMA public TO test;"
docker exec $CONTAINER_NAME psql -U postgres -d test_issue_observatory -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO test;"
```

## Verification Commands

### Check User Exists
```bash
docker exec $CONTAINER_NAME psql -U postgres -c "\du test"
```

Should show:
```
          List of roles
 Role name | Attributes
-----------+------------
 test      | Create DB
```

### Check Database Exists
```bash
docker exec $CONTAINER_NAME psql -U postgres -c "\l test_issue_observatory"
```

Should show:
```
          Name           | Owner | Encoding |  ...
-------------------------+-------+----------+-----
 test_issue_observatory | test  | UTF8     | ...
```

### Check Connection String
```bash
# From inside container
docker exec $CONTAINER_NAME psql -U test -d test_issue_observatory -c "SELECT current_database(), current_user;"
```

Should show:
```
 current_database      | current_user
-----------------------+--------------
 test_issue_observatory| test
```

### Test from Python
```bash
python3 << 'EOF'
import psycopg
conn = psycopg.connect("postgresql://test:test@localhost:5433/test_issue_observatory")
print("✅ Connection successful!")
conn.close()
EOF
```

## PostgreSQL Authentication Methods

If password authentication keeps failing, check PostgreSQL's `pg_hba.conf`:

```bash
# View authentication config
docker exec $CONTAINER_NAME cat /var/lib/postgresql/data/pg_hba.conf | grep -v "^#"
```

Should include:
```
host    all             all             all                     md5
```

If it shows `trust` or `peer`, passwords won't be checked.

## Reset Everything

If all else fails, completely reset the test database:

```bash
# Stop PostgreSQL
docker-compose stop postgres

# Remove PostgreSQL volume (WARNING: deletes all data!)
docker-compose rm -f postgres
docker volume rm issue_observatory_search_postgres_data 2>/dev/null

# Start fresh
docker-compose up -d postgres

# Wait for PostgreSQL to initialize
sleep 10

# Run setup script
bash scripts/setup_test_db.sh
```

## Alternative: Use Local PostgreSQL

If Docker PostgreSQL continues to have issues:

1. Install PostgreSQL locally (e.g., `brew install postgresql` on macOS)
2. Start it: `brew services start postgresql`
3. Create test database:
   ```bash
   createuser -s test
   createdb -O test test_issue_observatory
   psql -U postgres -c "ALTER USER test WITH PASSWORD 'test';"
   ```
4. Update `tests/conftest.py`:
   ```python
   TEST_DATABASE_URL = "postgresql+psycopg://test:test@localhost:5432/test_issue_observatory"
   ```

## Test Database Port

The test database should use **port 5433** (external) which maps to **port 5432** (internal container port).

**Correct URL**:
```
postgresql+psycopg://test:test@localhost:5433/test_issue_observatory
```

**Incorrect URL**:
```
postgresql+psycopg://test:test@localhost:5432/test_issue_observatory  # Wrong port!
```

## After Setup

Once the database is set up correctly, run tests:

```bash
# Run auth tests
pytest tests/test_auth.py -v

# Run all tests
pytest -v

# Run with coverage
pytest --cov=backend --cov-report=term-missing
```

## Getting Help

If you still have issues:

1. Check PostgreSQL logs: `docker-compose logs postgres`
2. Verify container is healthy: `docker inspect CONTAINER_NAME`
3. Check if port 5433 is accessible: `nc -zv localhost 5433`
4. Try connecting with psql: `psql -h localhost -p 5433 -U test -d test_issue_observatory`

## Quick Reference

```bash
# Setup script (recommended)
bash scripts/setup_test_db.sh

# Manual verification
CONTAINER=$(docker ps --filter "name=postgres" --format "{{.Names}}" | head -1)
docker exec $CONTAINER psql -U test -d test_issue_observatory -c "SELECT 1;"

# Run tests
pytest tests/test_auth.py -v
```

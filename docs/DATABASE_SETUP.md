# Database Setup Guide

Complete guide for setting up PostgreSQL for Issue Observatory Search.

---

## TL;DR - Quick Setup with Docker (Recommended)

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Start PostgreSQL with Docker (no manual setup needed!)
docker-compose up -d postgres

# 3. Run migrations (make sure venv is activated!)
python -m alembic upgrade head

# Done! Database is ready.
```

**You do NOT need to manually create users or databases with Docker!** 🎉

---

## Option 1: Docker PostgreSQL (Recommended)

### How It Works

Docker **automatically creates everything** when you run `docker-compose up`:

1. **Creates database user**: `postgres` (or whatever you set in `.env`)
2. **Creates password**: `postgres` (or whatever you set in `.env`)
3. **Creates database**: `issue_observatory` (or whatever you set in `.env`)
4. **Ready to use**: No manual SQL commands needed!

### Step-by-Step

#### 1. Copy environment file
```bash
cp .env.example .env
```

#### 2. (Optional) Customize database credentials

Edit `.env` if you want different credentials:
```bash
# Docker will create these automatically
DB_USER=postgres            # Database user (default: postgres)
DB_PASSWORD=postgres        # Database password (default: postgres)
DB_NAME=issue_observatory   # Database name (default: issue_observatory)

# Application DATABASE_URL must match
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/issue_observatory
```

**Default values work fine!** You can skip this step.

#### 3. Start PostgreSQL
```bash
docker-compose up -d postgres
```

**What happens**:
- Downloads PostgreSQL 16 image (~100MB)
- Creates container named `issue_observatory_db`
- **Automatically creates**:
  - User: `postgres`
  - Password: `postgres`
  - Database: `issue_observatory`
- Starts on port 5432
- Persists data in Docker volume `postgres_data`

#### 4. Verify it's running
```bash
# Check container status
docker ps | grep postgres

# Should show:
# issue_observatory_db   Up X minutes   5432/tcp

# Check logs
docker-compose logs postgres

# Should show:
# database system is ready to accept connections
```

#### 5. Run migrations
```bash
python -m alembic upgrade head
```

This creates all tables in the database.

#### 6. Verify connection
```bash
# Python check
python -c "from sqlalchemy import create_engine; \
engine = create_engine('postgresql+psycopg://postgres:postgres@localhost:5432/issue_observatory'); \
conn = engine.connect(); \
print('✅ Database connected!'); \
conn.close()"

# Or use psql
docker exec -it issue_observatory_db psql -U postgres -d issue_observatory -c "SELECT version();"
```

### Understanding the Defaults

**docker-compose.yml** has these defaults:
```yaml
environment:
  POSTGRES_USER: ${DB_USER:-postgres}       # Default: postgres
  POSTGRES_PASSWORD: ${DB_PASSWORD:-postgres}  # Default: postgres
  POSTGRES_DB: ${DB_NAME:-issue_observatory}   # Default: issue_observatory
```

The `:-` syntax means "use environment variable OR default value":
- `${DB_USER:-postgres}` → Use `DB_USER` from .env, or default to `postgres`

### DATABASE_URL Format

```
postgresql+psycopg://user:password@host:port/database
                     ↑    ↑         ↑    ↑    ↑
                     |    |         |    |    database name
                     |    |         |    port number
                     |    |         host (localhost for Docker)
                     |    password
                     username
```

**For Docker defaults**:
```
postgresql+psycopg://postgres:postgres@localhost:5432/issue_observatory
```

### Changing Credentials

If you want different credentials:

**1. Edit `.env`:**
```bash
DB_USER=myuser
DB_PASSWORD=mypassword
DB_NAME=mydb
```

**2. Update `DATABASE_URL` to match:**
```bash
DATABASE_URL=postgresql+psycopg://myuser:mypassword@localhost:5432/mydb
```

**3. Recreate container** (only needed if already running):
```bash
docker-compose down -v  # ⚠️ Deletes data!
docker-compose up -d postgres
```

---

## Option 2: Manual PostgreSQL Installation

If you install PostgreSQL manually (not using Docker):

### Install PostgreSQL

**Ubuntu/Debian**:
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**macOS (Homebrew)**:
```bash
brew install postgresql@15
brew services start postgresql@15
```

**Windows**:
Download from: https://www.postgresql.org/download/windows/

### Create Database and User

```bash
# Switch to postgres user
sudo -u postgres psql

# Inside psql:
CREATE USER issue_observatory_user WITH PASSWORD 'your_secure_password';
CREATE DATABASE issue_observatory OWNER issue_observatory_user;
GRANT ALL PRIVILEGES ON DATABASE issue_observatory TO issue_observatory_user;
\q
```

### Update .env

```bash
DATABASE_URL=postgresql+psycopg://issue_observatory_user:your_secure_password@localhost:5432/issue_observatory
```

### Run Migrations

```bash
python -m alembic upgrade head
```

---

## DATABASE_URL Explained

### Format Breakdown

```
postgresql+psycopg://user:password@host:port/database
```

**Components**:
- `postgresql` - Database type
- `psycopg` - Database driver (psycopg3, modern async driver)
- `user` - Database username
- `password` - Database password
- `host` - Database server hostname
  - `localhost` - Local machine
  - `postgres` - Docker service name (when app runs in Docker)
  - `10.0.1.5` - Remote server IP
- `port` - Database port (default: 5432)
- `database` - Database name

### Common Configurations

**Local Docker (development)**:
```bash
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/issue_observatory
```

**App in Docker, DB in Docker**:
```bash
DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres:5432/issue_observatory
#                                                    ↑
#                                          Service name, not localhost
```

**Remote PostgreSQL**:
```bash
DATABASE_URL=postgresql+psycopg://user:pass@db.example.com:5432/dbname
```

**With special characters in password**:
```bash
# Password: my@pass#word
# URL-encode special characters: @ = %40, # = %23
DATABASE_URL=postgresql+psycopg://user:my%40pass%23word@localhost:5432/dbname
```

---

## Troubleshooting

### Issue: "Connection refused"

**Symptoms**:
```
sqlalchemy.exc.OperationalError: connection to server at "localhost" (127.0.0.1), port 5432 failed: Connection refused
```

**Solutions**:

1. **PostgreSQL not running**:
```bash
# Docker
docker-compose ps postgres  # Check if running
docker-compose up -d postgres  # Start it

# Manual install
sudo systemctl status postgresql  # Linux
brew services list  # macOS
```

2. **Wrong port**:
```bash
# Check what port PostgreSQL is on
docker-compose ps postgres  # Should show 5432->5432

# Or
lsof -i :5432  # See what's using port 5432
```

3. **Wrong host**:
```bash
# If app is in Docker, use service name
DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres:5432/issue_observatory
#                                                    ↑ Not localhost!
```

---

### Issue: "Database does not exist"

**Symptoms**:
```
sqlalchemy.exc.OperationalError: database "issue_observatory" does not exist
```

**Solutions**:

1. **Docker - database not created**:
```bash
# Check environment variables
docker-compose config | grep POSTGRES

# Recreate with correct env vars
docker-compose down -v
docker-compose up -d postgres
```

2. **Manual - create database**:
```bash
sudo -u postgres createdb issue_observatory
```

---

### Issue: "Authentication failed"

**Symptoms**:
```
sqlalchemy.exc.OperationalError: password authentication failed for user "postgres"
```

**Solutions**:

1. **Wrong password in DATABASE_URL**:
```bash
# Check what password Docker is using
docker-compose exec postgres env | grep POSTGRES_PASSWORD

# Update .env to match
DATABASE_URL=postgresql+psycopg://postgres:CORRECT_PASSWORD@localhost:5432/issue_observatory
```

2. **User doesn't exist**:
```bash
# Docker - recreate container
docker-compose down -v
docker-compose up -d postgres

# Manual - create user
sudo -u postgres psql -c "CREATE USER postgres WITH PASSWORD 'postgres';"
```

---

### Issue: "Role does not exist"

**Symptoms**:
```
psycopg.errors.UndefinedObject: role "user" does not exist
```

**Solution**:
Wrong username in DATABASE_URL. Check and fix:
```bash
# Docker default is 'postgres'
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/issue_observatory
```

---

### Issue: Port already in use

**Symptoms**:
```
Error starting userland proxy: listen tcp4 0.0.0.0:5432: bind: address already in use
```

**Solution**:

1. **Another PostgreSQL running**:
```bash
# Find what's using port 5432
lsof -i :5432

# Stop existing PostgreSQL
sudo systemctl stop postgresql  # Linux
brew services stop postgresql   # macOS

# Or use different port in docker-compose.yml
ports:
  - "5433:5432"  # External:Internal

# Update DATABASE_URL
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/issue_observatory
```

---

## Testing Database Connection

### From Python

```python
from sqlalchemy import create_engine, text

# Test connection
engine = create_engine(
    "postgresql+psycopg://postgres:postgres@localhost:5432/issue_observatory"
)

with engine.connect() as conn:
    result = conn.execute(text("SELECT version();"))
    print(result.fetchone())
    print("✅ Database connected!")
```

### From Command Line

```bash
# Using Docker
docker exec -it issue_observatory_db psql -U postgres -d issue_observatory

# Inside psql:
\dt           # List tables
\du           # List users
\l            # List databases
SELECT version();
\q            # Quit
```

### Using pgAdmin (GUI)

1. Start pgAdmin container (included in docker-compose.yml):
```bash
docker-compose --profile tools up -d pgadmin
```

2. Open: http://localhost:5050

3. Login:
   - Email: `admin@example.com` (or from .env)
   - Password: `admin` (or from .env)

4. Add server:
   - Host: `postgres` (Docker service name)
   - Port: `5432`
   - Username: `postgres`
   - Password: `postgres`

---

## Data Persistence

### Docker Volumes

Data is stored in Docker volumes:
```bash
# View volumes
docker volume ls | grep postgres

# Inspect volume
docker volume inspect issue_observatory_postgres_data

# Backup
docker run --rm -v issue_observatory_postgres_data:/data \
  -v $(pwd):/backup ubuntu tar czf /backup/postgres_backup.tar.gz /data

# Restore
docker run --rm -v issue_observatory_postgres_data:/data \
  -v $(pwd):/backup ubuntu tar xzf /backup/postgres_backup.tar.gz -C /
```

### Removing All Data

```bash
# ⚠️ WARNING: This deletes ALL database data!
docker-compose down -v

# The -v flag removes volumes
```

---

## Quick Reference

| Task | Docker Command | Manual Command |
|------|---------------|----------------|
| Start DB | `docker-compose up -d postgres` | `sudo systemctl start postgresql` |
| Stop DB | `docker-compose stop postgres` | `sudo systemctl stop postgresql` |
| View logs | `docker-compose logs postgres` | `sudo journalctl -u postgresql` |
| Access psql | `docker exec -it issue_observatory_db psql -U postgres` | `sudo -u postgres psql` |
| Create DB | Automatic | `createdb issue_observatory` |
| Create user | Automatic | `createuser username` |
| Check status | `docker ps \| grep postgres` | `systemctl status postgresql` |

---

## Summary

**✅ With Docker (Recommended)**:
1. `cp .env.example .env` (defaults work!)
2. `docker-compose up -d postgres`
3. `alembic upgrade head`
4. Done! No manual user/database creation needed.

**✅ Without Docker (Manual)**:
1. Install PostgreSQL
2. Create user and database manually
3. Update `.env` with credentials
4. `alembic upgrade head`

**DATABASE_URL defaults for Docker**:
```bash
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/issue_observatory
```

No manual setup required with Docker! 🎉

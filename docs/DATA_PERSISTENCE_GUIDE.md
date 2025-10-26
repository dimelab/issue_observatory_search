# Data Persistence Guide

**Version**: 3.0.0 | **Last Updated**: October 24, 2025

---

## Overview

This guide explains how data persistence is configured in the Issue Observatory Search project, ensuring your research data is safe even when Docker containers are removed or recreated.

---

## Data Persistence Architecture

The project uses **Docker named volumes** for all critical data, ensuring persistence across container lifecycles.

### What is Persisted

| Data Type | Storage Location | Volume Type | Survives Container Removal? |
|-----------|------------------|-------------|----------------------------|
| PostgreSQL Database | `postgres_data` volume | Named Volume | ✅ Yes |
| Redis Cache/Queue | `redis_data` volume | Named Volume | ✅ Yes |
| Network GEXF Files | `app_data` volume | Named Volume | ✅ Yes |
| Application Files | `app_data` volume | Named Volume | ✅ Yes |
| pgAdmin Config | `pgadmin_data` volume | Named Volume | ✅ Yes |
| Source Code | `.:/app` bind mount | Host Directory | ✅ Yes (on host) |

---

## Docker Volumes Configuration

### Named Volumes (Persistent)

```yaml
volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local
  app_data:
    driver: local
  pgadmin_data:
    driver: local
```

**Key Characteristics:**
- ✅ Managed by Docker
- ✅ Persist when containers are removed
- ✅ Can be backed up and restored
- ✅ Portable across Docker hosts
- ✅ Not deleted with `docker-compose down`
- ❌ Only deleted with `docker-compose down -v` or `docker volume rm`

### Bind Mounts (Host Directory)

```yaml
volumes:
  - .:/app  # Source code - persists on host
```

**Key Characteristics:**
- ✅ Direct mapping to host filesystem
- ✅ Changes reflect immediately
- ✅ Useful for development
- ✅ Easy to backup (standard filesystem)
- ⚠️ Requires host directory to exist

---

## Critical Data Locations

### 1. PostgreSQL Database

**What's Stored:**
- User accounts and authentication
- Search sessions and queries
- Search results and websites
- Scraped content
- Extracted nouns and entities
- Network metadata
- Query expansion candidates
- Templates and bulk uploads

**Volume:** `postgres_data`

**Container Path:** `/var/lib/postgresql/data`

**Persistence:** ✅ **Fully Persistent**

### 2. Redis Data

**What's Stored:**
- Celery task queue
- Celery task results
- Analysis results cache (1-hour TTL)
- Session data
- Rate limiting counters

**Volume:** `redis_data`

**Container Path:** `/data`

**Persistence:** ✅ **Fully Persistent** (with AOF/RDB enabled)

**Note:** Redis cache is **transient by design** (1-hour TTL), but task queue data persists.

### 3. Application Data

**What's Stored:**
- Network GEXF files (`/app/data/networks/*.gexf`)
- Future: Uploaded CSV files
- Future: Export archives
- Future: Temporary processing files

**Volume:** `app_data`

**Container Path:** `/app/data`

**Persistence:** ✅ **Fully Persistent**

### 4. pgAdmin Configuration

**What's Stored:**
- pgAdmin user preferences
- Saved database connections
- Query history

**Volume:** `pgadmin_data`

**Container Path:** `/var/lib/pgadmin`

**Persistence:** ✅ **Fully Persistent**

---

## Data Lifecycle

### Normal Operations

```bash
# Start services
docker-compose up -d
# Data is loaded from volumes

# Stop services
docker-compose stop
# Data remains in volumes

# Restart services
docker-compose start
# Data is still there!
```

✅ **Data persists through stop/start**

### Container Recreation

```bash
# Remove containers (NOT volumes)
docker-compose down

# Recreate containers
docker-compose up -d
# Data is restored from volumes
```

✅ **Data persists through container recreation**

### Volume Removal (DANGER!)

```bash
# Remove containers AND volumes
docker-compose down -v
# ⚠️ ALL DATA IS DELETED!
```

❌ **Data is LOST when volumes are removed**

---

## Backup Strategies

### 1. PostgreSQL Database Backup

#### Method 1: Docker Volume Backup

```bash
# Backup volume to tar archive
docker run --rm \
  -v issue_observatory_search_postgres_data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/postgres-backup-$(date +%Y%m%d-%H%M%S).tar.gz /data

# Restore from backup
docker run --rm \
  -v issue_observatory_search_postgres_data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar xzf /backup/postgres-backup-TIMESTAMP.tar.gz -C /
```

#### Method 2: pg_dump (Recommended)

```bash
# Backup database
docker exec issue_observatory_db pg_dump \
  -U postgres \
  -d issue_observatory \
  -F c \
  -f /tmp/backup.dump

# Copy backup to host
docker cp issue_observatory_db:/tmp/backup.dump \
  ./backups/db-backup-$(date +%Y%m%d-%H%M%S).dump

# Restore database
docker cp ./backups/db-backup-TIMESTAMP.dump \
  issue_observatory_db:/tmp/restore.dump

docker exec issue_observatory_db pg_restore \
  -U postgres \
  -d issue_observatory \
  -c \
  /tmp/restore.dump
```

#### Method 3: Automated Backup Script

Create `scripts/backup-db.sh`:

```bash
#!/bin/bash
set -e

BACKUP_DIR="./backups/database"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="$BACKUP_DIR/db-backup-$TIMESTAMP.dump"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup database
docker exec issue_observatory_db pg_dump \
  -U postgres \
  -d issue_observatory \
  -F c \
  > "$BACKUP_FILE"

echo "✅ Database backed up to: $BACKUP_FILE"

# Keep only last 7 backups
ls -t "$BACKUP_DIR"/db-backup-*.dump | tail -n +8 | xargs -r rm

echo "✅ Old backups cleaned up (keeping last 7)"
```

Run with:
```bash
chmod +x scripts/backup-db.sh
./scripts/backup-db.sh
```

### 2. Application Data Backup

```bash
# Backup network files
BACKUP_DIR="./backups/app-data"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

mkdir -p "$BACKUP_DIR"

docker run --rm \
  -v issue_observatory_search_app_data:/data \
  -v $(pwd)/$BACKUP_DIR:/backup \
  alpine tar czf /backup/app-data-$TIMESTAMP.tar.gz /data

echo "✅ Application data backed up"
```

### 3. Complete System Backup

Create `scripts/backup-all.sh`:

```bash
#!/bin/bash
set -e

BACKUP_ROOT="./backups"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="$BACKUP_ROOT/full-backup-$TIMESTAMP"

mkdir -p "$BACKUP_DIR"

echo "🔄 Starting full system backup..."

# 1. Backup PostgreSQL
echo "📦 Backing up PostgreSQL..."
docker exec issue_observatory_db pg_dump \
  -U postgres \
  -d issue_observatory \
  -F c \
  > "$BACKUP_DIR/database.dump"

# 2. Backup Redis (if needed)
echo "📦 Backing up Redis..."
docker exec issue_observatory_redis redis-cli SAVE
docker cp issue_observatory_redis:/data/dump.rdb \
  "$BACKUP_DIR/redis-dump.rdb"

# 3. Backup application data
echo "📦 Backing up application data..."
docker run --rm \
  -v issue_observatory_search_app_data:/data \
  -v $(pwd)/$BACKUP_DIR:/backup \
  alpine tar czf /backup/app-data.tar.gz /data

# 4. Copy .env file (contains configuration)
echo "📦 Backing up configuration..."
cp .env "$BACKUP_DIR/.env.backup" 2>/dev/null || echo "No .env file found"

# 5. Create backup manifest
echo "📦 Creating manifest..."
cat > "$BACKUP_DIR/MANIFEST.txt" <<EOF
Issue Observatory Search - Full Backup
Created: $(date)
Version: 3.0.0

Contents:
- database.dump (PostgreSQL database)
- redis-dump.rdb (Redis data)
- app-data.tar.gz (Network files and application data)
- .env.backup (Environment configuration)

Restore Instructions:
1. docker-compose down
2. Restore database: docker exec -i issue_observatory_db pg_restore -U postgres -d issue_observatory -c < database.dump
3. Restore Redis: docker cp redis-dump.rdb issue_observatory_redis:/data/dump.rdb && docker exec issue_observatory_redis redis-cli SHUTDOWN SAVE
4. Restore app data: docker run --rm -v issue_observatory_search_app_data:/data -v $(pwd):/backup alpine tar xzf /backup/app-data.tar.gz -C /
5. Restore .env: cp .env.backup ../.env
6. docker-compose up -d
EOF

echo "✅ Full backup completed: $BACKUP_DIR"
echo "📊 Backup size: $(du -sh $BACKUP_DIR | cut -f1)"
```

Run with:
```bash
chmod +x scripts/backup-all.sh
./scripts/backup-all.sh
```

---

## Restore Procedures

### Full System Restore

```bash
#!/bin/bash
set -e

BACKUP_DIR="./backups/full-backup-TIMESTAMP"

echo "🔄 Starting full system restore..."

# 1. Stop all services
echo "⏸️  Stopping services..."
docker-compose down

# 2. Restore database
echo "📦 Restoring PostgreSQL..."
docker-compose up -d postgres
sleep 10  # Wait for PostgreSQL to start

docker exec -i issue_observatory_db pg_restore \
  -U postgres \
  -d issue_observatory \
  -c \
  < "$BACKUP_DIR/database.dump"

# 3. Restore Redis
echo "📦 Restoring Redis..."
docker-compose up -d redis
sleep 5

docker cp "$BACKUP_DIR/redis-dump.rdb" \
  issue_observatory_redis:/data/dump.rdb

docker exec issue_observatory_redis redis-cli SHUTDOWN SAVE
docker-compose restart redis

# 4. Restore application data
echo "📦 Restoring application data..."
docker run --rm \
  -v issue_observatory_search_app_data:/data \
  -v $(pwd)/$BACKUP_DIR:/backup \
  alpine tar xzf /backup/app-data.tar.gz -C /

# 5. Restore .env
echo "📦 Restoring configuration..."
if [ -f "$BACKUP_DIR/.env.backup" ]; then
    cp "$BACKUP_DIR/.env.backup" .env
    echo "⚠️  Review .env file and update any changed secrets"
fi

# 6. Start all services
echo "🚀 Starting all services..."
docker-compose up -d

echo "✅ Full restore completed!"
echo "🔍 Verify data integrity and test application"
```

---

## Disaster Recovery

### Scenario 1: Accidental `docker-compose down -v`

**Impact:** All volumes deleted, all data lost

**Recovery:**
1. Restore from backup (see above)
2. If no backup exists:
   - Database: **UNRECOVERABLE**
   - Application files: **UNRECOVERABLE**
   - Recommendation: Implement automated daily backups

### Scenario 2: Container Corruption

**Impact:** Containers broken but volumes intact

**Recovery:**
```bash
# Remove corrupted containers
docker-compose down

# Rebuild containers
docker-compose up -d --build

# Data automatically restores from volumes
```

✅ **No data loss**

### Scenario 3: Disk Failure

**Impact:** Complete data loss

**Recovery:**
1. Restore volumes from offsite backup
2. Recommendation: Use cloud-based volume backup solutions

---

## Best Practices

### Development Environment

1. **Regular Local Backups:**
   ```bash
   # Add to crontab
   0 2 * * * cd /path/to/project && ./scripts/backup-all.sh
   ```

2. **Test Restores:**
   ```bash
   # Monthly: test backup restore in separate environment
   docker-compose -f docker-compose.test.yml up -d
   # Restore backup
   # Verify functionality
   docker-compose -f docker-compose.test.yml down -v
   ```

3. **Version Control `.env.example`:**
   - Keep `.env.example` in git
   - Add `.env` to `.gitignore`
   - Document all required variables

### Production Environment

1. **Automated Backups:**
   - Daily full backups
   - Hourly incremental backups (PostgreSQL WAL archiving)
   - Offsite storage (S3, Google Cloud Storage)

2. **Monitoring:**
   - Volume usage monitoring
   - Backup success/failure alerts
   - Data integrity checks

3. **Backup Retention:**
   - Daily backups: Keep 7 days
   - Weekly backups: Keep 4 weeks
   - Monthly backups: Keep 12 months

4. **Disaster Recovery Plan:**
   - Document restore procedures
   - Test restores quarterly
   - Maintain offsite backups
   - Define RTO (Recovery Time Objective): < 1 hour
   - Define RPO (Recovery Point Objective): < 1 hour

---

## Volume Management Commands

### List Volumes

```bash
# List all volumes
docker volume ls

# List project volumes
docker volume ls | grep issue_observatory
```

### Inspect Volume

```bash
# Get volume details
docker volume inspect issue_observatory_search_postgres_data

# Check volume size
docker system df -v
```

### Remove Volumes (DANGER!)

```bash
# Remove all unused volumes
docker volume prune

# Remove specific volume (DESTRUCTIVE!)
docker volume rm issue_observatory_search_postgres_data

# Remove all project volumes (VERY DESTRUCTIVE!)
docker-compose down -v
```

⚠️ **WARNING:** Volume removal is **irreversible**. Always backup first!

### Export/Import Volumes

```bash
# Export volume
docker run --rm \
  -v issue_observatory_search_postgres_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/postgres-volume.tar.gz /data

# Import volume (to new volume)
docker volume create issue_observatory_search_postgres_data_restored

docker run --rm \
  -v issue_observatory_search_postgres_data_restored:/data \
  -v $(pwd):/backup \
  alpine tar xzf /backup/postgres-volume.tar.gz -C /
```

---

## Migration Between Environments

### Export from Development

```bash
# 1. Create full backup
./scripts/backup-all.sh

# 2. Archive backup
tar czf migration-backup.tar.gz backups/full-backup-TIMESTAMP/

# 3. Transfer to production
scp migration-backup.tar.gz user@prod-server:/path/to/project/
```

### Import to Production

```bash
# 1. Extract backup
tar xzf migration-backup.tar.gz

# 2. Run restore script
./scripts/restore-all.sh backups/full-backup-TIMESTAMP/

# 3. Update .env with production values
nano .env

# 4. Start services
docker-compose up -d
```

---

## Troubleshooting

### Volume Permission Issues

```bash
# Fix volume permissions
docker run --rm \
  -v issue_observatory_search_app_data:/data \
  alpine chown -R 1000:1000 /data
```

### Database Connection Issues After Restore

```bash
# Reset database connections
docker-compose restart postgres

# Verify database
docker exec issue_observatory_db psql -U postgres -d issue_observatory -c "\dt"
```

### Volume Full

```bash
# Check volume size
docker system df -v

# Clean up old data
docker exec issue_observatory_db psql -U postgres -d issue_observatory -c "
  DELETE FROM network_exports WHERE created_at < NOW() - INTERVAL '30 days';
"

# Vacuum database
docker exec issue_observatory_db psql -U postgres -d issue_observatory -c "VACUUM FULL;"
```

---

## Security Considerations

### Backup Encryption

```bash
# Encrypt backup
tar czf - backups/full-backup-TIMESTAMP/ | \
  openssl enc -aes-256-cbc -salt -out backup-encrypted.tar.gz.enc

# Decrypt backup
openssl enc -aes-256-cbc -d -in backup-encrypted.tar.gz.enc | \
  tar xzf -
```

### Access Control

- Limit backup directory permissions: `chmod 700 backups/`
- Encrypt backups for offsite storage
- Use strong encryption keys
- Rotate encryption keys periodically

---

## Summary

✅ **All critical data is persistent** using Docker named volumes:
- PostgreSQL database: `postgres_data`
- Redis cache/queue: `redis_data`
- Network files: `app_data`
- pgAdmin config: `pgadmin_data`

✅ **Data survives:**
- Container removal (`docker-compose down`)
- Container recreation
- System reboots
- Docker upgrades

❌ **Data is lost with:**
- `docker-compose down -v` (removes volumes)
- `docker volume rm` (manual volume deletion)
- Disk failure (without backups)

🔐 **Recommended actions:**
1. Set up automated daily backups
2. Test restore procedures monthly
3. Maintain offsite backups
4. Document recovery procedures
5. Monitor volume usage

---

**Last Updated:** October 24, 2025
**Version:** 3.0.0
**Maintained By:** Issue Observatory Team

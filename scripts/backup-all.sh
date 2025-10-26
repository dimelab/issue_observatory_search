#!/bin/bash
# Complete System Backup Script for Issue Observatory Search
# Backs up database, Redis, application data, and configuration

set -e

BACKUP_ROOT="./backups"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="$BACKUP_ROOT/full-backup-$TIMESTAMP"

# Container names
DB_CONTAINER="issue_observatory_db"
REDIS_CONTAINER="issue_observatory_redis"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Issue Observatory Search             ║${NC}"
echo -e "${BLUE}║  Full System Backup                    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# Create backup directory
mkdir -p "$BACKUP_DIR"

# 1. Backup PostgreSQL
echo -e "${YELLOW}📦 [1/5] Backing up PostgreSQL database...${NC}"
if docker ps | grep -q "$DB_CONTAINER"; then
    docker exec "$DB_CONTAINER" pg_dump \
      -U postgres \
      -d issue_observatory \
      -F c \
      > "$BACKUP_DIR/database.dump"

    DB_SIZE=$(du -h "$BACKUP_DIR/database.dump" | cut -f1)
    echo -e "${GREEN}   ✅ Database backup complete ($DB_SIZE)${NC}"
else
    echo -e "${RED}   ❌ Database container not running, skipping...${NC}"
fi

# 2. Backup Redis
echo -e "${YELLOW}📦 [2/5] Backing up Redis data...${NC}"
if docker ps | grep -q "$REDIS_CONTAINER"; then
    # Trigger Redis save
    docker exec "$REDIS_CONTAINER" redis-cli SAVE > /dev/null 2>&1

    # Copy dump file
    docker cp "$REDIS_CONTAINER:/data/dump.rdb" \
      "$BACKUP_DIR/redis-dump.rdb" 2>/dev/null || \
      echo -e "${YELLOW}   ⚠️  No Redis dump file found (cache may be empty)${NC}"

    if [ -f "$BACKUP_DIR/redis-dump.rdb" ]; then
        REDIS_SIZE=$(du -h "$BACKUP_DIR/redis-dump.rdb" | cut -f1)
        echo -e "${GREEN}   ✅ Redis backup complete ($REDIS_SIZE)${NC}"
    fi
else
    echo -e "${RED}   ❌ Redis container not running, skipping...${NC}"
fi

# 3. Backup application data
echo -e "${YELLOW}📦 [3/5] Backing up application data (networks, files)...${NC}"
docker run --rm \
  -v issue_observatory_search_app_data:/data \
  -v "$(pwd)/$BACKUP_DIR:/backup" \
  alpine tar czf /backup/app-data.tar.gz /data 2>/dev/null

if [ -f "$BACKUP_DIR/app-data.tar.gz" ]; then
    APP_SIZE=$(du -h "$BACKUP_DIR/app-data.tar.gz" | cut -f1)
    echo -e "${GREEN}   ✅ Application data backup complete ($APP_SIZE)${NC}"
else
    echo -e "${YELLOW}   ⚠️  Application data backup may be empty${NC}"
fi

# 4. Backup .env configuration
echo -e "${YELLOW}📦 [4/5] Backing up configuration...${NC}"
if [ -f ".env" ]; then
    cp .env "$BACKUP_DIR/.env.backup"
    echo -e "${GREEN}   ✅ Configuration backup complete${NC}"
else
    echo -e "${YELLOW}   ⚠️  No .env file found${NC}"
fi

# 5. Create backup manifest
echo -e "${YELLOW}📦 [5/5] Creating backup manifest...${NC}"
cat > "$BACKUP_DIR/MANIFEST.txt" <<EOF
╔════════════════════════════════════════════════════════════╗
║  Issue Observatory Search - Full System Backup            ║
╚════════════════════════════════════════════════════════════╝

Created: $(date)
Version: 3.0.0
Backup ID: $TIMESTAMP

CONTENTS:
─────────────────────────────────────────────────────────────
✓ database.dump          PostgreSQL database (pg_dump format)
✓ redis-dump.rdb         Redis data (RDB snapshot)
✓ app-data.tar.gz        Network files and application data
✓ .env.backup            Environment configuration
✓ MANIFEST.txt           This file

RESTORE INSTRUCTIONS:
─────────────────────────────────────────────────────────────
1. Stop all services:
   docker-compose down

2. Restore PostgreSQL database:
   docker-compose up -d postgres
   sleep 10
   docker exec -i issue_observatory_db pg_restore \\
     -U postgres -d issue_observatory -c < database.dump

3. Restore Redis data:
   docker-compose up -d redis
   docker cp redis-dump.rdb issue_observatory_redis:/data/dump.rdb
   docker exec issue_observatory_redis redis-cli SHUTDOWN SAVE
   docker-compose restart redis

4. Restore application data:
   docker run --rm \\
     -v issue_observatory_search_app_data:/data \\
     -v \$(pwd):/backup \\
     alpine tar xzf /backup/app-data.tar.gz -C /

5. Restore configuration:
   cp .env.backup ../.env
   # Review and update any changed secrets

6. Start all services:
   docker-compose up -d

7. Verify:
   - Check dashboard loads
   - Test search functionality
   - Verify networks are accessible

NOTES:
─────────────────────────────────────────────────────────────
• Keep this backup in a secure location
• Test restore procedure periodically
• Update .env secrets after restore
• This backup contains sensitive data - encrypt for storage

For automated restore, use:
  ./scripts/restore-all.sh $BACKUP_DIR

EOF

echo -e "${GREEN}   ✅ Manifest created${NC}"

# Calculate total backup size
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)

echo ""
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Backup Completed Successfully        ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo -e "📁 Location: $BACKUP_DIR"
echo -e "📊 Total size: $TOTAL_SIZE"
echo -e "📋 Manifest: $BACKUP_DIR/MANIFEST.txt"
echo ""
echo -e "${YELLOW}💡 Recommendation: Store backup in a secure, offsite location${NC}"
echo ""

# Optional: Clean up old backups (keep last 3 full backups)
BACKUP_COUNT=$(ls -d "$BACKUP_ROOT"/full-backup-* 2>/dev/null | wc -l)
if [ "$BACKUP_COUNT" -gt 3 ]; then
    echo -e "${YELLOW}🧹 Cleaning up old backups (keeping last 3)...${NC}"
    ls -dt "$BACKUP_ROOT"/full-backup-* | tail -n +4 | xargs rm -rf
    echo -e "${GREEN}✅ Cleanup complete${NC}"
fi

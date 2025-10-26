#!/bin/bash
# Database Backup Script for Issue Observatory Search
# Creates timestamped PostgreSQL backups and maintains last 7 backups

set -e

BACKUP_DIR="./backups/database"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="$BACKUP_DIR/db-backup-$TIMESTAMP.dump"
CONTAINER_NAME="issue_observatory_db"
DB_USER="postgres"
DB_NAME="issue_observatory"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🔄 Starting database backup...${NC}"

# Check if container is running
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo -e "${RED}❌ Error: Container '$CONTAINER_NAME' is not running${NC}"
    echo "Start it with: docker-compose up -d postgres"
    exit 1
fi

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup database
echo -e "📦 Backing up database to: $BACKUP_FILE"
docker exec "$CONTAINER_NAME" pg_dump \
  -U "$DB_USER" \
  -d "$DB_NAME" \
  -F c \
  > "$BACKUP_FILE"

# Check if backup was successful
if [ $? -eq 0 ] && [ -f "$BACKUP_FILE" ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo -e "${GREEN}✅ Database backed up successfully${NC}"
    echo -e "📊 Backup size: $BACKUP_SIZE"
    echo -e "📁 Location: $BACKUP_FILE"
else
    echo -e "${RED}❌ Backup failed${NC}"
    exit 1
fi

# Keep only last 7 backups
echo -e "🧹 Cleaning up old backups (keeping last 7)..."
BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/db-backup-*.dump 2>/dev/null | wc -l)

if [ "$BACKUP_COUNT" -gt 7 ]; then
    DELETED=$(ls -t "$BACKUP_DIR"/db-backup-*.dump | tail -n +8 | xargs -r rm -v | wc -l)
    echo -e "${GREEN}✅ Deleted $DELETED old backup(s)${NC}"
else
    echo -e "ℹ️  No old backups to delete (total: $BACKUP_COUNT)"
fi

echo -e "${GREEN}✅ Backup completed successfully${NC}"

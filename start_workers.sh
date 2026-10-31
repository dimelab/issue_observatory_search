#!/bin/bash
# Script to start all required Celery workers

echo "Starting Celery workers for Issue Observatory Search"
echo "======================================================"
echo ""

# Check if Redis is running (try multiple connection methods)
REDIS_RUNNING=false

# Try default port
if redis-cli ping > /dev/null 2>&1; then
    REDIS_RUNNING=true
# Try with host specified (for docker)
elif redis-cli -h localhost -p 6379 ping > /dev/null 2>&1; then
    REDIS_RUNNING=true
# Try docker container directly
elif docker exec issue_observatory_redis redis-cli ping > /dev/null 2>&1; then
    REDIS_RUNNING=true
fi

if [ "$REDIS_RUNNING" = false ]; then
    echo "⚠ WARNING: Redis is not running or not accessible!"
    echo "Start Redis with: docker compose up -d redis"
    echo ""
    echo "Continuing anyway (Redis might be running but not detectable)..."
    echo ""
else
    echo "✓ Redis is running"
    echo ""
fi

# Function to start a worker in the background
start_worker() {
    local queue=$1
    local name=$2

    echo "Starting worker for queue: $queue"
    celery -A backend.celery_app worker \
        -Q $queue \
        -n ${name}@%h \
        --loglevel=info \
        --logfile=logs/celery_${queue}.log \
        --pidfile=logs/celery_${queue}.pid \
        --detach

    if [ $? -eq 0 ]; then
        echo "  ✓ Worker started for $queue queue"
    else
        echo "  ✗ Failed to start worker for $queue queue"
    fi
}

# Create logs directory if it doesn't exist
mkdir -p logs

# Start workers for each queue
echo "Starting workers..."
echo ""

start_worker "scraping" "scraping_worker"
start_worker "analysis" "analysis_worker"
start_worker "networks" "networks_worker"

# Searches: their own worker, several searches at a time (see SEARCH_WORKER_CONCURRENCY)
echo "Starting worker for queue: search"
celery -A backend.celery_app worker \
    -Q search \
    -n search_worker@%h \
    -c ${SEARCH_WORKER_CONCURRENCY:-4} \
    --prefetch-multiplier=1 \
    -O fair \
    --loglevel=info \
    --logfile=logs/celery_search.log \
    --pidfile=logs/celery_search.pid \
    --detach
if [ $? -eq 0 ]; then
    echo "  ✓ Worker started for search queue"
else
    echo "  ✗ Failed to start worker for search queue"
fi

# Beat: restarts a search whose worker was killed (recover_stalled_searches, every minute)
echo "Starting Celery beat"
celery -A backend.celery_app beat \
    --loglevel=info \
    --logfile=logs/celery_beat.log \
    --pidfile=logs/celery_beat.pid \
    -s logs/celerybeat-schedule \
    --detach
if [ $? -eq 0 ]; then
    echo "  ✓ Beat started"
else
    echo "  ✗ Failed to start beat"
fi

echo ""
echo "======================================================"
echo "All workers started!"
echo ""
echo "To monitor workers:"
echo "  celery -A backend.celery_app inspect active"
echo ""
echo "To view logs:"
echo "  tail -f logs/celery_scraping.log"
echo "  tail -f logs/celery_analysis.log"
echo "  tail -f logs/celery_networks.log"
echo "  tail -f logs/celery_search.log"
echo ""
echo "To stop all workers:"
echo "  ./stop_workers.sh"
echo "======================================================"

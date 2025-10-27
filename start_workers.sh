#!/bin/bash
# Script to start all required Celery workers

echo "Starting Celery workers for Issue Observatory Search"
echo "======================================================"
echo ""

# Check if Redis is running
if ! redis-cli ping > /dev/null 2>&1; then
    echo "⚠ WARNING: Redis is not running!"
    echo "Start Redis first: redis-server"
    echo ""
    exit 1
fi

echo "✓ Redis is running"
echo ""

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
echo ""
echo "To stop all workers:"
echo "  ./stop_workers.sh"
echo "======================================================"

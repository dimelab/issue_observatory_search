#!/bin/bash
# Script to stop all Celery workers

echo "Stopping Celery workers..."
echo "======================================================"
echo ""

# Function to stop a worker
stop_worker() {
    local queue=$1
    local pidfile="logs/celery_${queue}.pid"

    if [ -f "$pidfile" ]; then
        local pid=$(cat "$pidfile")
        echo "Stopping $queue worker (PID: $pid)"
        kill $pid 2>/dev/null
        rm -f "$pidfile"
        echo "  ✓ Stopped $queue worker"
    else
        echo "  ⚠ No PID file found for $queue worker"
    fi
}

# Stop all workers
stop_worker "scraping"
stop_worker "analysis"
stop_worker "networks"

# Also try to stop any workers by name
echo ""
echo "Cleaning up any remaining workers..."
pkill -f "celery.*worker" 2>/dev/null

echo ""
echo "======================================================"
echo "All workers stopped!"
echo "======================================================"

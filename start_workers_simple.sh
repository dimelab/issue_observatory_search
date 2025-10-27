#!/bin/bash
# Simple script to start all Celery workers

echo "Starting Celery workers..."
echo ""

# Create logs directory
mkdir -p logs

# Start networks worker (the missing one!)
echo "Starting networks worker..."
celery -A backend.celery_app worker \
    -Q networks \
    -n networks_worker@%h \
    --loglevel=info \
    --logfile=logs/celery_networks.log \
    --pidfile=logs/celery_networks.pid \
    --detach

echo "✓ Networks worker started"
echo ""

# Start analysis worker
echo "Starting analysis worker..."
celery -A backend.celery_app worker \
    -Q analysis \
    -n analysis_worker@%h \
    --loglevel=info \
    --logfile=logs/celery_analysis.log \
    --pidfile=logs/celery_analysis.pid \
    --detach

echo "✓ Analysis worker started"
echo ""

# Start Xvfb on display :99
echo "Starting Xvfb..."
Xvfb :99 -screen 0 1920x1080x24 > /dev/null 2>&1 &
XVFB_PID=$!
sleep 1

# Start scraping worker with DISPLAY set
echo "Starting scraping worker..."
DISPLAY=:99 celery -A backend.celery_app worker \
    -Q scraping \
    -n scraping_worker@%h \
    --loglevel=info \
    --logfile=logs/celery_scraping.log \
    --pidfile=logs/celery_scraping.pid \
    --detach

echo "✓ Scraping worker started (Xvfb PID: $XVFB_PID)"
echo ""

echo "======================================================"
echo "All workers started!"
echo ""
echo "Check status with:"
echo "  python check_celery_tasks.py"
echo ""
echo "View logs with:"
echo "  tail -f logs/celery_networks.log"
echo "  tail -f logs/celery_analysis.log"
echo "  tail -f logs/celery_scraping.log"
echo "======================================================"

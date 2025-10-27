# Celery Workers Guide

## Quick Start

### Start all workers (recommended):
```bash
# Make scripts executable first
chmod +x start_workers.sh stop_workers.sh

# Start all workers
./start_workers.sh

# Check status
python check_celery_tasks.py

# Stop all workers
./stop_workers.sh
```

## Manual Worker Management

### Required Workers

The application needs **3 separate workers** for different queues:

#### 1. Scraping Worker
```bash
celery -A backend.celery_app worker -Q scraping -n scraping_worker@%h --loglevel=info
```

#### 2. Analysis Worker
```bash
celery -A backend.celery_app worker -Q analysis -n analysis_worker@%h --loglevel=info
```

#### 3. Networks Worker (REQUIRED FOR NETWORK GENERATION)
```bash
celery -A backend.celery_app worker -Q networks -n networks_worker@%h --loglevel=info
```

### Run Multiple Workers in Background

```bash
# Start in background with logs
celery -A backend.celery_app worker -Q scraping -n scraping_worker@%h --loglevel=info --logfile=logs/scraping.log --detach
celery -A backend.celery_app worker -Q analysis -n analysis_worker@%h --loglevel=info --logfile=logs/analysis.log --detach
celery -A backend.celery_app worker -Q networks -n networks_worker@%h --loglevel=info --logfile=logs/networks.log --detach
```

### Monitor Workers

```bash
# Check active tasks
celery -A backend.celery_app inspect active

# Check registered tasks
celery -A backend.celery_app inspect registered

# Check worker stats
celery -A backend.celery_app inspect stats

# Or use the diagnostic script
python check_celery_tasks.py
```

### View Logs

```bash
# Follow log in real-time
tail -f logs/scraping.log
tail -f logs/analysis.log
tail -f logs/networks.log
```

### Stop Workers

```bash
# Stop specific worker by name
celery -A backend.celery_app control shutdown -d scraping_worker@hostname

# Or kill all workers
pkill -f "celery.*worker"

# Or use the script
./stop_workers.sh
```

## Troubleshooting

### Worker not picking up tasks?

1. **Check Redis is running:**
   ```bash
   redis-cli ping
   # Should return: PONG
   ```

2. **Verify worker is on correct queue:**
   ```bash
   python check_celery_tasks.py
   # Check "REGISTERED TASKS" section
   ```

3. **Check for duplicate node names:**
   - Each worker must have a unique name using `-n` flag
   - Don't run multiple workers with same name

### Current Issue (Your Case)

You have a worker running but it's **not listening to the `networks` queue**.

**Solution:**
```bash
# Stop the existing worker
./stop_workers.sh

# Or manually:
pkill -f "celery.*worker"

# Start all three workers
./start_workers.sh

# Verify networks worker is registered
python check_celery_tasks.py
# Should see "tasks.generate_network" in REGISTERED TASKS
```

## Task Queue Routing

The application routes tasks to specific queues:

- **`scraping` queue**: `scrape_session`, `scrape_content`, `cancel_scraping_job`
- **`analysis` queue**: `analyze_content_task`, `analyze_batch_task`, `analyze_job_task`
- **`networks` queue**: `generate_network_task`, `cleanup_old_networks_task`

Each queue needs its own worker to process its tasks.

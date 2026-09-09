# Issue Observatory — Deployment Guide

Production runs the whole stack from `docker-compose.yml`. All four application
services share one image (`Dockerfile`, target `development`), so the Celery worker
has the same spaCy models and Playwright browser as the API — a mismatch there is
what silently produced empty keyword networks in the past.

## Services

| Service    | Container                         | Published port      | Purpose                                |
| ---------- | --------------------------------- | ------------------- | -------------------------------------- |
| PostgreSQL | `issue_observatory_db`            | `127.0.0.1:5433`    | Database, pgvector + pg_trgm enabled    |
| Redis      | `issue_observatory_redis`         | `127.0.0.1:6379`    | Celery broker, result backend, cache    |
| Backend    | `issue_observatory_backend`       | `8080`              | FastAPI app and API                     |
| Worker     | `issue_observatory_celery_worker` | —                   | Scraping, NLP, network generation       |
| Beat       | `issue_observatory_celery_beat`   | —                   | Scheduler for recurring tasks           |
| Flower     | `issue_observatory_flower`        | `5555`              | Celery monitoring UI                    |
| Nginx      | `issue_observatory_nginx`         | `80`, `443`         | Reverse proxy — `--profile proxy` only  |

Postgres and Redis bind to loopback so they are not reachable from outside the
host. Nginx is behind a profile because `nginx/nginx.conf` still carries
Let's Encrypt paths for `your-domain` and will not start until real certificates
exist and the `server_name` is set.

## First run

```bash
cp .env.example .env      # then fill in SECRET_KEY, DB_PASSWORD, and a search API key
docker compose build
docker compose up -d
docker compose exec backend python scripts/create_admin.py
```

The backend applies `alembic upgrade head` on every start, so migrations need no
separate step.

## Everyday commands

```bash
# Update and restart
git pull origin main && docker compose up --build -d

# Logs
docker compose logs -f backend
docker compose logs -f celery_worker

# Database shell
docker exec -it issue_observatory_db psql -U postgres -d issue_observatory

# Add users in bulk (one "username;password" per line)
docker compose exec backend python scripts/add_users.py users.txt

# Queue state — a task whose queue has no consumer waits in Redis indefinitely
docker compose exec celery_worker celery -A backend.celery_app inspect active_queues
```

## Adopting an existing database volume

Volume names come from `.env` and are project-independent. Docker reuses a volume
that already exists under the configured name and creates one only when missing,
so pointing at a previous deployment's volume adopts its data:

```bash
docker volume ls | grep postgres     # find the existing volume
# then set POSTGRES_VOLUME_NAME in .env to that name and bring the stack up
```

Verify what a volume holds before committing to it:

```bash
docker run --rm -v <volume>:/v alpine ls /v
```

## Migrations

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend alembic revision --autogenerate -m "description"
```

`alembic.ini` points at `migrations/`, not `alembic/`. If a migration fails, the
maintenance scripts apply the equivalent DDL directly:

```bash
docker compose exec backend python scripts/add_excluded_domains_column.py
docker compose exec backend python scripts/fix_analysis_columns.py
```

## Troubleshooting

**Networks generate with 0 edges.** The worker could not run NLP. Check that both
spaCy models are present, then clear the cached (empty) analyses before retrying —
`analyze_content` returns a cached result before touching the database, so a
poisoned cache entry survives fixing the underlying cause for `NLP_CACHE_TTL`:

```bash
docker compose exec celery_worker python -m spacy validate
docker compose exec celery_worker python -c "
import asyncio
from backend.core.nlp.cache import get_analysis_cache
async def main():
    print(await (await get_analysis_cache()).invalidate_batch(list(range(<first>, <last>))))
asyncio.run(main())
"
```

**Tasks never start.** The worker consumes `celery,scraping,analysis,networks,search`.
If `task_routes` in `backend/celery_app.py` gains a new queue, add it to the
worker's `-Q` list in `docker-compose.yml` or those tasks will never be picked up.

**`Event loop is closed` in the worker.** The async engine in `backend/database.py`
is module-level while each Celery task runs on a fresh event loop, so pooled
connections can outlive the loop that created them. Restarting the worker clears
it; the durable fix is a per-task engine or `NullPool` in worker processes.

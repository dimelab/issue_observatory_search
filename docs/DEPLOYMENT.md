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

**How searches run, and results from `google.com/goto`.** A search is queued by the web request and
done by the `celery_search_worker` service (queue `search`), so it keeps running if the user closes the
page or the backend restarts; the session page shows its progress (`GET /api/search/session/{id}/progress`,
polled every 3 seconds). A session is `pending` (queued), `processing`, then `completed` or `failed`. If the
search worker is down, searches wait in the queue until it is back; if Redis is down the page says the
queue is not available.

Why it is a worker: since 30 Oct 2026 Google returns result links beyond the top three as redirects
(`google.com/goto?url=...`). `SerperSearch` sends each page of results to Serper's free `/resolve` endpoint
for the real URLs. That waits for Google, so one keyword takes about 30 seconds instead of one or two.
Keywords are searched in parallel, within what the Serper account allows (50 requests per second). The
limits in `.env`, shared by all workers through Redis (`backend/core/concurrency.py`):

| Setting | Default | Meaning |
|---|---|---|
| `SEARCH_WORKER_CONCURRENCY` | 4 | Searches (sessions) running at once, all users (`-c` of the search worker) |
| `SEARCH_MAX_ACTIVE_PER_USER` | 1 | Sessions one user searches at once; their others show as queued |
| `SEARCH_CONCURRENCY` | 20 | Keywords at once within one session |
| `SEARCH_GLOBAL_CONCURRENCY` | 30 | Keywords at once across all sessions and workers |
| `SERPER_RESOLVE_CONCURRENCY` | 60 | `/resolve` requests in flight across all workers |
| `SERPER_RATE_LIMIT_PER_SECOND` | 35 | Requests per second to Serper across all workers, paced evenly (a burst of 3 is allowed): against the fake Serper the busiest second was 38. Serper's limit is 50 |
| `SEARCH_STALE_SECONDS` | 180 | A session saying `processing` with no report for this long lost its worker and is restarted |

A hundred keywords take roughly 3 minutes for one user, about 50 minutes one after another; several users
share the same budget. If the worker log shows `rate limit hit, waiting ...` often, Serper is throttling:
lower the limits (a 429 is waited out and retried up to 3 times, then the keyword fails; search again to
retry it). If Redis is unreachable while a search runs, the shared limits are skipped (logged once a minute).

**If the search worker is killed** (a container stopped hard, out of memory, a crash), Redis keeps the
task it was running as "unacknowledged" for the broker's visibility timeout (6 hours), so it is *not*
redelivered in time to matter (tested on a real Redis). Instead, a running search reports to its session
every `SEARCH_STALE_SECONDS / 6` seconds, and the `recover_stalled_searches` task, run every minute by
Celery beat, queues again any session that says `processing` but has not reported for
`SEARCH_STALE_SECONDS` (default 180). It carries on with the keywords that were not stored (nothing is
stored twice); the old task, if it is ever delivered, finds itself superseded. So expect a killed search to
resume within about 4 minutes. After 3 automatic restarts the session is marked failed. **This needs
`celery_beat`** (a compose service; `./start_workers.sh` starts it for local use). Before it picks the
session up the page shows "This search seems to have stopped" with a **Search again** button, which does
the same by hand. Sessions left `processing` by the old in-request searches (before this change) look
the same: search again, or delete.

A link that stays unresolved is dropped (logged as `dropped N result(s)`), and a failing `/resolve` fails
the keyword with a message saying so. Searches stored between 30 Oct and the update hold redirect links
that cannot be resolved any more. List them and search those keywords again:

```bash
docker compose exec backend python scripts/find_redirect_results.py
```

Scraping skips stored redirect links (`skipping N stored Google redirect link(s)` in the worker log).

**Tasks never start.** The worker consumes `celery,scraping,analysis,networks,search`.
If `task_routes` in `backend/celery_app.py` gains a new queue, add it to the
worker's `-Q` list in `docker-compose.yml` or those tasks will never be picked up.

**`Event loop is closed` in the worker.** The async engine in `backend/database.py`
is module-level while each Celery task runs on a fresh event loop, so pooled
connections can outlive the loop that created them. Restarting the worker clears
it; the durable fix is a per-task engine or `NullPool` in worker processes.

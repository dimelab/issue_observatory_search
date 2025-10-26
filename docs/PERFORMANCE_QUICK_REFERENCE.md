# Performance Optimization - Quick Reference

## Phase 9: Essential Performance Patterns

---

## 1. Caching

### Cache Function Results
```python
from backend.core.cache import cached

@cached("resource:type:{id}", ttl=3600)
async def get_expensive_data(id: int):
    return await db.execute(...)
```

### Invalidate Cache
```python
from backend.core.cache import cache_invalidate

@cache_invalidate("resource:*:{id}")
async def update_data(id: int, data: dict):
    await db.execute(update(...)...)
```

### Manual Cache Operations
```python
from backend.core.cache import get_redis_cache

cache = await get_redis_cache()
await cache.set("key", value, ttl=3600)
value = await cache.get("key")
await cache.delete("key")
await cache.delete_pattern("prefix:*")
```

---

## 2. Database Queries

### Eager Loading (Prevent N+1)
```python
from sqlalchemy.orm import selectinload, joinedload

# One-to-many
stmt = select(Session).options(
    selectinload(Session.queries)
)

# Many-to-one
stmt = select(Result).options(
    joinedload(Result.website)
)

# Nested
stmt = select(Session).options(
    selectinload(Session.queries).options(
        selectinload(Query.results)
    )
)
```

### Pagination
```python
from backend.utils.pagination import paginate

page = await paginate(
    select(Model),
    db,
    page=1,
    per_page=50
)

items = page.items
total = page.total
has_more = page.has_next
```

### Aggregation
```python
from sqlalchemy import func

# Count
count = await db.scalar(
    select(func.count(Model.id))
)

# Sum/Average
total = await db.scalar(
    select(func.sum(Model.value))
)
```

---

## 3. Bulk Operations

### Bulk Insert
```python
from backend.utils.bulk_operations import bulk_insert

data = [{"field": "value"}, ...]
ids = await bulk_insert(
    db,
    Model,
    data,
    return_ids=True
)
```

### Bulk Update
```python
from backend.utils.bulk_operations import bulk_update

updates = [(id, {"field": "new_value"}), ...]
await bulk_update(db, Model, updates)
```

### Bulk Upsert
```python
from backend.utils.bulk_operations import bulk_upsert

await bulk_upsert(
    db,
    Model,
    data,
    conflict_columns=["url"],
    update_columns=["text_content"]
)
```

---

## 4. Rate Limiting

### Protect Endpoints
```python
from backend.middleware import limiter

@router.post("/expensive-operation")
@limiter.limit("5/hour")
async def expensive_operation(request: Request):
    pass

@router.get("/data")
@limiter.limit("100/minute")
async def get_data(request: Request):
    pass
```

---

## 5. Performance Checklist

Before writing new code:

### Database Queries
- [ ] Use pagination for lists
- [ ] Add eager loading for relationships
- [ ] Use indexes on filtered columns
- [ ] Aggregate in database, not Python
- [ ] Limit result set size

### Caching
- [ ] Cache expensive operations
- [ ] Set appropriate TTL
- [ ] Invalidate on updates
- [ ] Monitor cache hit rate

### API Endpoints
- [ ] Add rate limiting
- [ ] Use pagination
- [ ] Return only needed fields
- [ ] Handle errors gracefully

### Background Tasks
- [ ] Make tasks idempotent
- [ ] Use bulk operations
- [ ] Set time limits
- [ ] Handle retries

---

## 6. Common Patterns

### Load User Sessions with Queries
```python
# ❌ Bad: N+1 queries
sessions = await db.execute(select(Session))
for session in sessions:
    queries = await db.execute(
        select(Query).where(Query.session_id == session.id)
    )

# ✅ Good: Eager loading
sessions = await db.execute(
    select(Session).options(
        selectinload(Session.queries)
    )
)
```

### Count Related Records
```python
# ❌ Bad: Load all, count in Python
nouns = await db.execute(select(Noun))
count = len(nouns.all())

# ✅ Good: Count in database
count = await db.scalar(
    select(func.count(Noun.id))
)
```

### Insert Multiple Records
```python
# ❌ Bad: Individual inserts
for item in items:
    db.add(Model(**item))
await db.commit()

# ✅ Good: Bulk insert
from backend.utils.bulk_operations import bulk_insert
await bulk_insert(db, Model, items)
```

### Cache Expensive Calculation
```python
# ❌ Bad: No caching
async def get_stats():
    return await complex_calculation()

# ✅ Good: Cache results
from backend.core.cache import cached

@cached("stats:global", ttl=900)
async def get_stats():
    return await complex_calculation()
```

---

## 7. Performance Targets

| Operation | Target | How to Achieve |
|-----------|--------|----------------|
| API Response | < 200ms | Cache + indexes + pagination |
| Concurrent Users | 100+ | Connection pooling + rate limiting |
| Bulk Insert | 1000+/sec | bulk_insert() with chunks |
| Cache Hit Rate | > 80% | Appropriate TTLs |
| Query Time | < 100ms | Indexes + eager loading |

---

## 8. Monitoring

### Check Slow Queries
```bash
tail -f logs/app.log | grep "SLOW QUERY"
```

### Cache Statistics
```python
cache = await get_redis_cache()
info = await cache.redis.info("stats")
hit_rate = info['keyspace_hits'] / (info['keyspace_hits'] + info['keyspace_misses'])
```

### Connection Pool
```python
from backend.database import engine
pool = engine.pool
print(f"Size: {pool.size()}, Checked out: {pool.checkedout()}")
```

---

## 9. Configuration

### Key Settings (.env)
```bash
# Database
DATABASE_POOL_SIZE=20
DATABASE_POOL_RECYCLE=3600

# Redis
REDIS_MAX_CONNECTIONS=50

# Caching
CACHE_ENABLED=true
CACHE_DEFAULT_TTL=3600

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=100

# Performance
QUERY_SLOW_THRESHOLD=0.1
BULK_INSERT_CHUNK_SIZE=1000
```

---

## 10. Benchmarking

### Run Benchmarks
```bash
# All tests
python scripts/benchmark.py --all

# Specific tests
python scripts/benchmark.py --api
python scripts/benchmark.py --concurrent --users 200
python scripts/benchmark.py --database
```

---

## Quick Wins

### If response time is high:
1. Add caching with `@cached`
2. Add indexes to filtered columns
3. Use pagination
4. Enable eager loading

### If database is slow:
1. Check slow query logs
2. Add missing indexes
3. Use `EXPLAIN ANALYZE`
4. Optimize query joins

### If cache hit rate is low:
1. Increase TTL
2. Pre-warm cache
3. Check invalidation logic
4. Monitor eviction rate

### If concurrent users fail:
1. Increase pool size
2. Add rate limiting
3. Enable compression
4. Use CDN for static files

---

## Common Mistakes to Avoid

1. ❌ Loading all records without pagination
2. ❌ N+1 queries (loading relationships in loop)
3. ❌ Aggregating in Python instead of database
4. ❌ Individual inserts instead of bulk operations
5. ❌ No caching for expensive operations
6. ❌ Missing indexes on filtered columns
7. ❌ No rate limiting on resource-intensive endpoints
8. ❌ Not monitoring slow queries

---

## Need Help?

- Full documentation: `PERFORMANCE.md`
- Implementation details: `PHASE9_SUMMARY.md`
- Code examples: `backend/repositories/search_repository_optimized.py`
- Benchmarks: `scripts/benchmark.py`

---

**Remember**: Optimize for readability first, performance second. Only optimize when benchmarks show a problem.

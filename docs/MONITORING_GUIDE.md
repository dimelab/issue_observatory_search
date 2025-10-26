# Monitoring Guide

## Overview

This guide covers the monitoring and observability features of the Issue Observatory Search application.

## Monitoring Stack

### Prometheus
- **Metrics Collection:** Scrapes `/metrics` endpoint every 15 seconds
- **Port:** 9090
- **Access:** http://your-domain:9090
- **Data Retention:** 30 days

### Grafana (Optional)
- **Visualization:** Pre-built dashboards for key metrics
- **Port:** 3000
- **Access:** http://your-domain:3000
- **Default Credentials:** admin / (set in .env.prod)

## Key Metrics

### HTTP Metrics
- `http_request_duration_seconds` - Request duration by endpoint
- `http_requests_total` - Total requests by status code
- `http_requests_active` - Active concurrent requests
- `http_request_size_bytes` - Request payload sizes
- `http_response_size_bytes` - Response payload sizes

### Application Metrics
- `search_operations_total` - Search operations by engine
- `scraping_operations_total` - Scraping operations by status
- `analysis_operations_total` - Analysis operations by type
- `network_generation_total` - Network generation operations
- `cache_hit_rate` - Cache effectiveness
- `db_connections_active` - Database connection usage

### Business Metrics
- `users_active` - Active user count
- `sessions_total` - Total sessions created
- `searches_per_user` - Search frequency distribution

## Health Check Endpoints

### `/health`
Basic health check - returns `{"status": "healthy"}`

### `/health/live`
Kubernetes liveness probe - indicates if application is running

### `/health/ready`
Kubernetes readiness probe - checks critical dependencies (DB, Redis)

### `/health/detail`
Comprehensive health check with status of all components:
- Database (response time, connection pool)
- Redis (response time, memory usage)
- Celery workers
- Disk space

## Alerting

### Recommended Prometheus Alert Rules

```yaml
groups:
  - name: issue_observatory_alerts
    rules:
      # High error rate
      - alert: HighErrorRate
        expr: rate(http_requests_total{status_code=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"

      # Slow responses
      - alert: SlowAPIResponses
        expr: histogram_quantile(0.95, http_request_duration_seconds) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "95th percentile response time >1s"

      # Database connection pool exhaustion
      - alert: DatabasePoolExhausted
        expr: db_connections_active / db_connections_pool_size > 0.8
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Database connection pool nearly exhausted"

      # Low cache hit rate
      - alert: LowCacheHitRate
        expr: cache_hit_rate < 0.5
        for: 10m
        labels:
          severity: info
        annotations:
          summary: "Cache hit rate below 50%"

      # No Celery workers
      - alert: NoCeleryWorkers
        expr: celery_tasks_active == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "No active Celery workers"
```

## Log Management

### Log Locations
- Application logs: `/var/log/app/`
- Nginx access logs: `/var/log/nginx/access.log`
- Nginx error logs: `/var/log/nginx/error.log`

### Log Rotation
Configured in `/etc/logrotate.d/issue-observatory`
- Daily rotation
- 30 days retention
- Compressed after 1 day

### Structured Logging
All logs include:
- Timestamp
- Log level
- Request ID (for tracing)
- User ID (if authenticated)
- Context information

## Performance Monitoring

### Key Performance Indicators

1. **API Response Time:** Target <200ms (95th percentile)
2. **Search Operations:** Target <5 seconds
3. **Cache Hit Rate:** Target >70%
4. **Error Rate:** Target <1%
5. **Database Query Time:** Target <100ms

### Monitoring Commands

```bash
# Check application health
curl https://your-domain/health/detail

# View metrics
curl https://your-domain/metrics

# Check service status
docker-compose ps

# View application logs
docker-compose logs -f app

# View metrics in Prometheus
# Visit http://your-domain:9090

# Check specific metric
curl -s https://your-domain/metrics | grep http_requests_total
```

## Troubleshooting

### High Memory Usage
1. Check Redis memory: `docker-compose exec redis redis-cli INFO memory`
2. Check database connections: `curl /health/detail`
3. Review application memory: `docker stats`

### Slow Queries
1. Check slow query logs in application logs
2. Review database performance in health check
3. Check cache hit rate

### High Error Rate
1. Check error logs: `docker-compose logs app | grep ERROR`
2. Review error metrics in Prometheus
3. Check database and Redis connectivity

## Best Practices

1. **Set up alerts** for critical metrics
2. **Review metrics** daily for unusual patterns
3. **Monitor trends** over time, not just current values
4. **Document incidents** and their resolutions
5. **Test monitoring** during deployment

---

**Last Updated:** 2025-10-26

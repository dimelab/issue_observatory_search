# Production Deployment Guide

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Server Setup](#server-setup)
3. [SSL Certificate Setup](#ssl-certificate-setup)
4. [Environment Configuration](#environment-configuration)
5. [Deployment](#deployment)
6. [Post-Deployment](#post-deployment)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements
- **OS:** Ubuntu 22.04 LTS or similar
- **CPU:** 4+ cores recommended
- **RAM:** 8GB minimum, 16GB recommended
- **Disk:** 50GB+ SSD
- **Network:** Static IP address, DNS configured

### Software Requirements
- Docker 24.0+
- Docker Compose 2.0+
- Git
- certbot (for SSL)

### Domain Setup
- Domain name pointing to server IP
- DNS A record configured
- Ports 80, 443 open in firewall

---

## Server Setup

### 1. Initial Server Configuration

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y apt-transport-https ca-certificates curl software-properties-common git

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Add user to docker group
sudo usermod -aG docker $USER
```

### 2. Firewall Configuration

```bash
# Install UFW
sudo apt install ufw

# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow Prometheus (optional, restrict by IP)
sudo ufw allow from YOUR_MONITORING_IP to any port 9090

# Enable firewall
sudo ufw enable
```

### 3. Create Application Directory

```bash
sudo mkdir -p /opt/issue-observatory
sudo chown $USER:$USER /opt/issue-observatory
cd /opt/issue-observatory
```

---

## SSL Certificate Setup

### Using Let's Encrypt (Recommended)

```bash
# Install certbot
sudo apt install certbot

# Obtain certificate (replace YOUR_DOMAIN)
sudo certbot certonly --standalone -d YOUR_DOMAIN.com

# Certificates will be in /etc/letsencrypt/live/YOUR_DOMAIN.com/
```

### Update Nginx Configuration

Edit `nginx/nginx.conf`:
```nginx
server_name YOUR_DOMAIN.com;
ssl_certificate /etc/letsencrypt/live/YOUR_DOMAIN.com/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/YOUR_DOMAIN.com/privkey.pem;
ssl_trusted_certificate /etc/letsencrypt/live/YOUR_DOMAIN.com/chain.pem;
```

---

## Environment Configuration

### 1. Create Production Environment File

```bash
cd /opt/issue-observatory
cp .env.example .env.prod
```

### 2. Configure `.env.prod`

```bash
# Application
APP_NAME=Issue Observatory Search
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=YOUR_SUPER_SECRET_KEY_HERE_CHANGE_THIS

# Database
POSTGRES_USER=issue_observatory
POSTGRES_PASSWORD=STRONG_PASSWORD_HERE
POSTGRES_DB=issue_observatory_prod
DATABASE_URL=postgresql://issue_observatory:STRONG_PASSWORD_HERE@db:5432/issue_observatory_prod

# Redis
REDIS_URL=redis://redis:6379/0

# API Keys (obtain from providers)
GOOGLE_CUSTOM_SEARCH_API_KEY=your_key_here
GOOGLE_CUSTOM_SEARCH_ENGINE_ID=your_engine_id_here
SERPER_API_KEY=your_serper_key_here
OPENAI_API_KEY=your_openai_key_here

# Security
CORS_ORIGINS=["https://YOUR_DOMAIN.com"]

# Monitoring
GRAFANA_USER=admin
GRAFANA_PASSWORD=STRONG_GRAFANA_PASSWORD
```

### 3. Generate Secret Key

```python
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## Deployment

### 1. Clone Repository

```bash
cd /opt/issue-observatory
git clone https://github.com/YOUR_USERNAME/issue-observatory-search.git .
```

### 2. Build and Start Services

```bash
# Build images
docker-compose -f docker-compose.prod.yml build

# Start services
docker-compose -f docker-compose.prod.yml up -d

# Check logs
docker-compose -f docker-compose.prod.yml logs -f
```

### 3. Initialize Database

```bash
# Run migrations
docker-compose -f docker-compose.prod.yml exec app alembic upgrade head

# Create admin user (interactive)
docker-compose -f docker-compose.prod.yml exec app python scripts/create_admin.py
```

### 4. Verify Deployment

```bash
# Check services
docker-compose -f docker-compose.prod.yml ps

# Check health
curl https://YOUR_DOMAIN.com/health/detail

# Check metrics
curl https://YOUR_DOMAIN.com/metrics
```

---

## Post-Deployment

### 1. Set Up Automatic Backups

Create backup script:
```bash
sudo nano /opt/issue-observatory/backup.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/opt/issue-observatory/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Backup database
docker-compose -f /opt/issue-observatory/docker-compose.prod.yml exec -T db pg_dump -U issue_observatory issue_observatory_prod | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Backup uploaded files
tar -czf $BACKUP_DIR/files_$DATE.tar.gz /opt/issue-observatory/data

# Keep only last 30 days
find $BACKUP_DIR -name "*.gz" -mtime +30 -delete
```

```bash
chmod +x /opt/issue-observatory/backup.sh

# Add to crontab (daily at 2 AM)
crontab -e
0 2 * * * /opt/issue-observatory/backup.sh
```

### 2. Set Up Log Rotation

```bash
sudo nano /etc/logrotate.d/issue-observatory
```

```
/opt/issue-observatory/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0640 www-data www-data
}
```

### 3. Configure Monitoring Alerts

Set up Prometheus alerting rules in `monitoring/alerts.yml`.

### 4. SSL Auto-Renewal

```bash
# Test renewal
sudo certbot renew --dry-run

# Automatic renewal via cron (already set up by certbot)
```

---

## Maintenance

### Update Application

```bash
cd /opt/issue-observatory

# Pull latest code
git pull origin main

# Rebuild and restart
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d

# Run migrations
docker-compose -f docker-compose.prod.yml exec app alembic upgrade head
```

### View Logs

```bash
# All services
docker-compose -f docker-compose.prod.yml logs -f

# Specific service
docker-compose -f docker-compose.prod.yml logs -f app
```

### Scale Services

```bash
# Scale workers
docker-compose -f docker-compose.prod.yml up -d --scale celery_worker=4
```

---

## Troubleshooting

### Services Won't Start

```bash
# Check logs
docker-compose -f docker-compose.prod.yml logs

# Check system resources
docker stats

# Restart services
docker-compose -f docker-compose.prod.yml restart
```

### Database Connection Issues

```bash
# Check database status
docker-compose -f docker-compose.prod.yml exec db psql -U issue_observatory -d issue_observatory_prod -c "SELECT 1"

# Reset database (CAUTION: destroys data)
docker-compose -f docker-compose.prod.yml down -v
docker-compose -f docker-compose.prod.yml up -d
```

### SSL Certificate Issues

```bash
# Check certificate
sudo certbot certificates

# Renew manually
sudo certbot renew --force-renewal
```

### Performance Issues

```bash
# Check resource usage
docker stats

# Check slow queries
docker-compose -f docker-compose.prod.yml logs app | grep "slow query"

# Scale workers
docker-compose -f docker-compose.prod.yml up -d --scale celery_worker=6
```

---

## Security Checklist

- [ ] Changed all default passwords
- [ ] Generated strong secret key
- [ ] Configured firewall (UFW)
- [ ] SSL certificate installed and auto-renewal configured
- [ ] Environment variables secured
- [ ] Database backups configured
- [ ] Log rotation configured
- [ ] Monitoring alerts configured
- [ ] Admin user created with strong password
- [ ] API rate limiting verified
- [ ] Health checks passing

---

## Additional Resources

- [Monitoring Guide](MONITORING_GUIDE.md)
- [Security Best Practices](SECURITY.md)
- [API Documentation](API_SPECIFICATION.md)
- [Database Schema](DATABASE_SCHEMA.md)

---

**Last Updated:** 2025-10-26
**Version:** 1.0.0

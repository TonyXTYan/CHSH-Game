# Production Deployment

This guide covers deploying the CHSH Game to production environments including cloud platforms and self-hosted servers.

## Cloud Platform Deployment

### Fly.io (Recommended)

The project includes optimized Fly.io configuration for easy deployment.

#### Prerequisites
```bash
# Install Fly CLI
curl -L https://fly.io/install.sh | sh

# Login to Fly.io
fly auth login
```

#### Deployment Steps
```bash
# Navigate to project directory
cd CHSH-Game

# Create app (modify app name in fly.toml if needed)
fly create chsh-game-your-name

# Deploy application
fly deploy

# Set environment variables
fly secrets set SECRET_KEY="your-production-secret-key"
fly secrets set DATABASE_URL="your-postgresql-url"

# Open application
fly open
```

#### Fly.io Configuration (`fly.toml`)
```toml
app = 'chsh-game'
primary_region = 'syd'  # Choose region closer to users

[build]
  # Uses Dockerfile automatically

[env]
  PORT = "8080"
  FLY_SCALE_TO_ZERO = "1h"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = "suspend"
  auto_start_machines = true
  min_machines_running = 0

  [http_service.concurrency]
    type = "connections"
    hard_limit = 400
    soft_limit = 200

[[vm]]
  memory = '256mb'
  size = "shared-cpu-1x"
```

#### Production Scaling
```bash
# Scale for higher traffic
fly scale memory 512    # Increase memory
fly scale count 2       # Multiple instances

# Monitor performance
fly logs
fly status
fly dashboard
```

### Render

#### Setup
1. **Connect GitHub repository** to Render
2. **Create Web Service** with these settings:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn wsgi:app --worker-class eventlet --bind 0.0.0.0:$PORT`

#### Environment Variables
```bash
SECRET_KEY=your-production-secret-key
DATABASE_URL=postgresql://user:pass@host/db
PORT=10000  # Render assigns this automatically
```

#### Render Configuration
```yaml
# render.yaml (optional)
services:
  - type: web
    name: chsh-game
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn wsgi:app --worker-class eventlet --bind 0.0.0.0:$PORT
    envVars:
      - key: SECRET_KEY
        generateValue: true
      - key: DATABASE_URL
        fromDatabase:
          name: chsh-game-db
          property: connectionString
```

### Heroku

#### Setup
```bash
# Install Heroku CLI
# Create Heroku app
heroku create chsh-game-your-name

# Add PostgreSQL addon
heroku addons:create heroku-postgresql:hobby-dev

# Set environment variables
heroku config:set SECRET_KEY="your-production-secret-key"

# Deploy
git push heroku main

# Scale dynos
heroku ps:scale web=1
```

#### Procfile
```
web: gunicorn wsgi:app --worker-class eventlet
```

### AWS (EC2 + RDS)

#### Infrastructure Setup
```bash
# Launch EC2 instance (Ubuntu 20.04 LTS)
# Configure security groups:
# - HTTP (80)
# - HTTPS (443) 
# - SSH (22)
# - Custom TCP (8080) for application

# Create RDS PostgreSQL instance
# Note connection details
```

#### Server Setup
```bash
# Connect to EC2 instance
ssh -i your-key.pem ubuntu@your-ec2-ip

# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and dependencies
sudo apt install python3.11 python3.11-venv python3-pip nginx supervisor -y

# Clone repository
git clone https://github.com/TonyXTYan/CHSH-Game.git
cd CHSH-Game

# Setup application
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
```

#### Systemd Service
Create `/etc/systemd/system/chsh-game.service`:
```ini
[Unit]
Description=CHSH Game
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/CHSH-Game
Environment=PATH=/home/ubuntu/CHSH-Game/venv/bin
Environment=DATABASE_URL=postgresql://user:pass@rds-endpoint/db
Environment=SECRET_KEY=your-production-secret-key
ExecStart=/home/ubuntu/CHSH-Game/venv/bin/gunicorn wsgi:app --worker-class eventlet --workers 2 --bind 127.0.0.1:8080
Restart=always

[Install]
WantedBy=multi-user.target
```

#### Nginx Configuration
Create `/etc/nginx/sites-available/chsh-game`:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
```

Enable and start services:
```bash
# Enable nginx site
sudo ln -s /etc/nginx/sites-available/chsh-game /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Enable and start application
sudo systemctl enable chsh-game
sudo systemctl start chsh-game
sudo systemctl status chsh-game
```

## Database Configuration

### PostgreSQL (Recommended for Production)

#### Cloud PostgreSQL Services
- **Fly.io Postgres**: `fly postgres create`
- **Render PostgreSQL**: Available as addon
- **Heroku Postgres**: `heroku addons:create heroku-postgresql`
- **AWS RDS**: Managed PostgreSQL service
- **DigitalOcean Managed Database**

#### Self-Hosted PostgreSQL
```bash
# Install PostgreSQL
sudo apt install postgresql postgresql-contrib

# Create database and user
sudo -u postgres psql
postgres=# CREATE USER chsh_user WITH PASSWORD 'secure_password';
postgres=# CREATE DATABASE chsh_game OWNER chsh_user;
postgres=# GRANT ALL PRIVILEGES ON DATABASE chsh_game TO chsh_user;
postgres=# \q

# Configure connection
DATABASE_URL=postgresql://chsh_user:secure_password@localhost/chsh_game
```

#### Database Optimization
```sql
-- Create indexes for performance
CREATE INDEX CONCURRENTLY idx_teams_active_created ON teams(is_active, created_at);
CREATE INDEX CONCURRENTLY idx_answers_team_timestamp ON answers(team_id, timestamp);
CREATE INDEX CONCURRENTLY idx_answers_team_item ON answers(team_id, assigned_item);

-- Configure PostgreSQL settings
-- In postgresql.conf:
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
```

## Environment Configuration

### Production Environment Variables
```bash
# Application
SECRET_KEY=very-secure-random-string-32-chars-minimum
DEBUG=False
PORT=8080

# Database
DATABASE_URL=postgresql://user:password@host:port/database

# Security
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
FORCE_HTTPS=true

# Performance
MAX_CONNECTIONS=1000
WORKER_CONNECTIONS=1000

# Monitoring
LOG_LEVEL=INFO
SENTRY_DSN=https://your-sentry-dsn  # Optional
```

### Secret Management
```bash
# Fly.io
fly secrets set SECRET_KEY="$(openssl rand -base64 32)"

# Heroku
heroku config:set SECRET_KEY="$(openssl rand -base64 32)"

# AWS Systems Manager Parameter Store
aws ssm put-parameter --name "/chsh-game/secret-key" --value "$(openssl rand -base64 32)" --type "SecureString"
```

## SSL/TLS Configuration

### Automatic SSL (Cloud Platforms)
- **Fly.io**: Automatic SSL certificates
- **Render**: Automatic SSL certificates
- **Heroku**: Automatic SSL certificates

### Manual SSL (Self-Hosted)
```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Obtain SSL certificate
sudo certbot --nginx -d yourdomain.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

## Performance Optimization

### Application Configuration
```python
# gunicorn.conf.py
bind = "0.0.0.0:8080"
workers = 2  # CPU cores * 2
worker_class = "eventlet"
worker_connections = 1000
keepalive = 5
max_requests = 10000
max_requests_jitter = 1000
timeout = 30
graceful_timeout = 30
```

### Nginx Optimization
```nginx
server {
    # ... existing configuration ...
    
    # Compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;
    
    # Caching
    location /static/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req zone=api burst=20 nodelay;
}
```

### Database Connection Pooling
```python
# In production configuration
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=30,
    pool_timeout=30,
    pool_recycle=3600
)
```

## Monitoring and Logging

### Application Monitoring
```python
# Add to your application
import logging
import sys

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Health check endpoint
@app.route('/health')
def health_check():
    try:
        # Check database connection
        db.session.execute('SELECT 1')
        return {'status': 'healthy', 'timestamp': datetime.utcnow()}, 200
    except Exception as e:
        return {'status': 'unhealthy', 'error': str(e)}, 500
```

### External Monitoring Services
- **Sentry**: Error tracking and performance monitoring
- **New Relic**: Application performance monitoring
- **DataDog**: Infrastructure and application monitoring
- **Prometheus + Grafana**: Self-hosted monitoring

### Log Management
```bash
# Centralized logging with rsyslog
# /etc/rsyslog.d/chsh-game.conf
$ModLoad imfile
$InputFileName /var/log/chsh-game/app.log
$InputFileTag chsh-game:
$InputFileStateFile chsh-game-log
$InputFileSeverity info
$InputRunFileMonitor
```

## Security Hardening

### Application Security
```python
# Security headers
@app.after_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

# CORS configuration
from flask_cors import CORS
CORS(app, origins=['https://yourdomain.com'])
```

### Server Security
```bash
# Firewall configuration
sudo ufw enable
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Fail2ban for SSH protection
sudo apt install fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# Regular security updates
sudo apt update && sudo apt upgrade -y
```

## Backup and Recovery

### Database Backups
```bash
# Automated PostgreSQL backups
#!/bin/bash
# backup.sh
DATE=$(date +%Y%m%d_%H%M%S)
pg_dump $DATABASE_URL > /backups/chsh_game_$DATE.sql
gzip /backups/chsh_game_$DATE.sql

# Keep only last 30 days
find /backups -name "chsh_game_*.sql.gz" -mtime +30 -delete

# Schedule with cron
# 0 2 * * * /home/ubuntu/backup.sh
```

### Application Backups
```bash
# Backup application code and configuration
tar -czf /backups/chsh-game-$(date +%Y%m%d).tar.gz \
  /home/ubuntu/CHSH-Game \
  /etc/systemd/system/chsh-game.service \
  /etc/nginx/sites-available/chsh-game
```

## Scaling Strategies

### Horizontal Scaling
```bash
# Load balancer configuration (nginx)
upstream chsh_game {
    server 127.0.0.1:8080;
    server 127.0.0.1:8081;
    server 127.0.0.1:8082;
}

server {
    location / {
        proxy_pass http://chsh_game;
        # ... other proxy settings
    }
}
```

### Session Storage (for Multiple Instances)
```python
# Use Redis for shared session storage
import redis
from flask_session import Session

app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_REDIS'] = redis.from_url('redis://localhost:6379')
Session(app)
```

### Database Scaling
- **Read replicas** for dashboard queries
- **Connection pooling** across instances
- **Query optimization** and caching
- **Partitioning** for large datasets

## Troubleshooting

### Common Production Issues

#### High Memory Usage
```bash
# Monitor memory
free -h
ps aux --sort=-%mem | head

# Check application memory
sudo systemctl status chsh-game
journalctl -u chsh-game -f
```

#### Database Connection Issues
```bash
# Check PostgreSQL connections
sudo -u postgres psql -c "SELECT count(*) FROM pg_stat_activity;"

# Monitor connection pool
tail -f /var/log/postgresql/postgresql-13-main.log
```

#### WebSocket Connection Problems
```bash
# Check nginx configuration
sudo nginx -t
sudo tail -f /var/log/nginx/error.log

# Verify proxy settings
curl -I -H "Connection: Upgrade" -H "Upgrade: websocket" http://localhost:8080/socket.io/
```

### Performance Issues
```bash
# Check system resources
htop
iotop
nethogs

# Application performance
sudo systemctl status chsh-game
journalctl -u chsh-game --since "1 hour ago"
```

## Deployment Checklist

### Pre-Deployment
- [ ] All tests pass in staging environment
- [ ] Database migrations tested
- [ ] Environment variables configured
- [ ] SSL certificates ready
- [ ] Monitoring configured
- [ ] Backup procedures tested

### Deployment
- [ ] Deploy to production
- [ ] Verify application starts successfully
- [ ] Test basic functionality
- [ ] Check WebSocket connections
- [ ] Verify database connectivity
- [ ] Test with multiple users

### Post-Deployment
- [ ] Monitor error rates
- [ ] Check performance metrics
- [ ] Verify backup automation
- [ ] Test recovery procedures
- [ ] Update monitoring alerts
- [ ] Document any issues

---

Your production deployment should now be secure, scalable, and monitored. For load testing and performance validation, see [Load Testing](./load-testing.md).
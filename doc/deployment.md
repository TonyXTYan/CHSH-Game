# Deployment Guide

This guide covers deploying the CHSH Game to various cloud platforms and production environments.

## Overview

The CHSH Game is a Flask application with Socket.IO that can be deployed to various platforms. The application requires:
- Python 3.11+ runtime
- WebSocket support
- Database storage (SQLite/PostgreSQL)
- Persistent file storage (for SQLite)

## Platform-Specific Deployments

### Fly.io (Recommended)

Fly.io provides excellent support for WebSocket applications and global edge deployment.

#### Prerequisites
- Fly.io account
- Flyctl CLI installed

#### Deployment Steps
1. **Install Flyctl**:
   ```bash
   # macOS/Linux
   curl -L https://fly.io/install.sh | sh
   
   # Windows
   iwr https://fly.io/install.ps1 -useb | iex
   ```

2. **Login to Fly.io**:
   ```bash
   flyctl auth login
   ```

3. **Initialize Fly App**:
   ```bash
   flyctl launch
   # Follow the prompts to configure your app
   ```

4. **Configure fly.toml**:
   ```toml
   app = "your-app-name"
   
   [env]
     PORT = "8080"
   
   [http_service]
     internal_port = 8080
     force_https = true
     auto_stop_machines = true
     auto_start_machines = true
     min_machines_running = 0
   
   [[vm]]
     cpu_kind = "shared"
     cpus = 1
     memory_mb = 512
   ```

5. **Set Environment Variables**:
   ```bash
   flyctl secrets set SECRET_KEY="your-secure-secret-key"
   flyctl secrets set DATABASE_URL="your-database-url"  # Optional for PostgreSQL
   ```

6. **Deploy**:
   ```bash
   flyctl deploy
   ```

7. **View Application**:
   ```bash
   flyctl open
   flyctl logs  # View logs
   ```

#### Fly.io with PostgreSQL
```bash
# Create PostgreSQL database
flyctl postgres create --name your-app-db

# Connect to your app
flyctl postgres attach --app your-app-name your-app-db
```

### Render.com

Render provides easy deployment with automatic builds from GitHub.

#### Prerequisites
- Render.com account
- GitHub repository

#### Deployment Steps
1. **Connect GitHub Repository**:
   - Go to Render dashboard
   - Click "New Web Service"
   - Connect your GitHub repository

2. **Configure Service**:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn wsgi:app --worker-class eventlet`
   - **Environment**: `Python 3`

3. **Set Environment Variables**:
   ```
   SECRET_KEY=your-secure-secret-key
   DATABASE_URL=postgresql://... (if using PostgreSQL)
   FLASK_ENV=production
   ```

4. **Deploy**:
   - Service builds and deploys automatically on git push
   - View logs in Render dashboard

#### Render with PostgreSQL
1. **Create PostgreSQL Database**:
   - In Render dashboard, create new PostgreSQL service
   - Note the connection details

2. **Update Environment Variables**:
   ```
   DATABASE_URL=postgresql://user:pass@host:port/database
   ```

### Heroku

Heroku provides a simple platform-as-a-service deployment.

#### Prerequisites
- Heroku account
- Heroku CLI installed

#### Deployment Steps
1. **Install Heroku CLI**:
   ```bash
   # Follow instructions at https://devcenter.heroku.com/articles/heroku-cli
   ```

2. **Login to Heroku**:
   ```bash
   heroku login
   ```

3. **Create Heroku App**:
   ```bash
   heroku create your-app-name
   ```

4. **Configure Buildpack**:
   ```bash
   heroku buildpacks:set heroku/python
   ```

5. **Set Environment Variables**:
   ```bash
   heroku config:set SECRET_KEY="your-secure-secret-key"
   heroku config:set FLASK_ENV="production"
   ```

6. **Deploy**:
   ```bash
   git push heroku main
   ```

7. **Scale Web Dyno**:
   ```bash
   heroku ps:scale web=1
   ```

#### Heroku with PostgreSQL
```bash
# Add PostgreSQL addon
heroku addons:create heroku-postgresql:hobby-dev

# DATABASE_URL is automatically set
```

### Railway

Railway offers modern deployment with excellent developer experience.

#### Prerequisites
- Railway account
- GitHub repository

#### Deployment Steps
1. **Connect Repository**:
   - Go to Railway dashboard
   - Click "New Project"
   - Connect GitHub repository

2. **Configure Environment**:
   - Railway auto-detects Python
   - Set environment variables in dashboard

3. **Environment Variables**:
   ```
   SECRET_KEY=your-secure-secret-key
   DATABASE_URL=postgresql://... (if using PostgreSQL)
   PORT=8080
   ```

4. **Deploy**:
   - Automatic deployment on git push
   - View logs in Railway dashboard

### DigitalOcean App Platform

DigitalOcean App Platform provides managed deployment with scaling.

#### Prerequisites
- DigitalOcean account
- GitHub repository

#### Deployment Steps
1. **Create App**:
   - Go to DigitalOcean Apps
   - Connect GitHub repository

2. **Configure App Spec**:
   ```yaml
   name: chsh-game
   services:
   - name: web
     source_dir: /
     github:
       repo: your-username/CHSH-Game
       branch: main
     run_command: gunicorn wsgi:app --worker-class eventlet
     environment_slug: python
     instance_count: 1
     instance_size_slug: basic-xxs
     http_port: 8080
     envs:
     - key: SECRET_KEY
       value: your-secure-secret-key
       type: SECRET
   ```

3. **Deploy**:
   - App builds and deploys automatically

## Docker Deployment

### Building Docker Image

#### Using Provided Dockerfile
```bash
# Build image
docker build -t chsh-game .

# Run container
docker run -p 8080:8080 chsh-game
```

#### Custom Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8080

# Run application
CMD ["gunicorn", "wsgi:app", "--worker-class", "eventlet", "--bind", "0.0.0.0:8080"]
```

### Docker Compose

#### Basic Compose
```yaml
version: '3.8'
services:
  web:
    build: .
    ports:
      - "8080:8080"
    environment:
      - SECRET_KEY=your-secret-key
    volumes:
      - ./data:/app/data  # For SQLite persistence
```

#### With PostgreSQL
```yaml
version: '3.8'
services:
  web:
    build: .
    ports:
      - "8080:8080"
    environment:
      - SECRET_KEY=your-secret-key
      - DATABASE_URL=postgresql://postgres:password@db:5432/chsh_game
    depends_on:
      - db
  
  db:
    image: postgres:13
    environment:
      - POSTGRES_DB=chsh_game
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

## VPS/Self-Hosted Deployment

### Prerequisites
- Linux VPS (Ubuntu/Debian recommended)
- SSH access
- Domain name (optional)

### Setup Steps

#### 1. Server Preparation
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install python3.11 python3.11-venv python3.11-dev nginx git -y

# Create application user
sudo useradd -m -s /bin/bash chsh-game
sudo usermod -aG sudo chsh-game
```

#### 2. Application Setup
```bash
# Switch to app user
sudo su - chsh-game

# Clone repository
git clone https://github.com/TonyXTYan/CHSH-Game.git
cd CHSH-Game

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install gunicorn
```

#### 3. Systemd Service
```bash
# Create service file
sudo tee /etc/systemd/system/chsh-game.service > /dev/null <<EOF
[Unit]
Description=CHSH Game
After=network.target

[Service]
Type=exec
User=chsh-game
Group=chsh-game
WorkingDirectory=/home/chsh-game/CHSH-Game
Environment=PATH=/home/chsh-game/CHSH-Game/venv/bin
ExecStart=/home/chsh-game/CHSH-Game/venv/bin/gunicorn wsgi:app --worker-class eventlet --bind 127.0.0.1:8080
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl enable chsh-game
sudo systemctl start chsh-game
sudo systemctl status chsh-game
```

#### 4. Nginx Configuration
```bash
# Create Nginx config
sudo tee /etc/nginx/sites-available/chsh-game > /dev/null <<EOF
server {
    listen 80;
    server_name your-domain.com;  # Replace with your domain
    
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
        proxy_read_timeout 86400;
    }
}
EOF

# Enable site
sudo ln -s /etc/nginx/sites-available/chsh-game /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

#### 5. SSL with Let's Encrypt
```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx -y

# Get SSL certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

## Production Configuration

### Environment Variables
```bash
# Required
export SECRET_KEY="your-very-secure-secret-key-here"

# Database (optional, defaults to SQLite)
export DATABASE_URL="postgresql://user:password@host:port/database"

# Flask environment
export FLASK_ENV="production"

# Port (for platforms that set it dynamically)
export PORT="8080"
```

### Database Configuration

#### SQLite (Default)
- **Pros**: Simple, no additional setup
- **Cons**: Not suitable for multiple workers, limited scalability
- **Use for**: Single-instance deployments, development

#### PostgreSQL (Recommended for Production)
- **Pros**: Scalable, ACID compliance, multiple connections
- **Cons**: Requires separate database service
- **Use for**: Production deployments, multiple workers

### Security Considerations

#### HTTPS
- Always use HTTPS in production
- Platforms like Fly.io and Render provide automatic HTTPS
- For self-hosted, use Let's Encrypt

#### Secret Key
```bash
# Generate secure secret key
python -c "import secrets; print(secrets.token_hex(32))"
```

#### Environment Variables
- Never commit secrets to version control
- Use platform-specific secret management
- Rotate secrets regularly

### Performance Optimization

#### Gunicorn Configuration
```bash
# Single worker (recommended for Socket.IO)
gunicorn wsgi:app --worker-class eventlet --workers 1

# Multiple workers (experimental, requires session affinity)
gunicorn wsgi:app --worker-class eventlet --workers 4
```

#### Resource Limits
- **Memory**: 512MB minimum, 1GB recommended
- **CPU**: 1 vCPU sufficient for moderate load
- **Storage**: 1GB minimum for logs and database

#### Monitoring
```bash
# Check resource usage
htop
df -h
systemctl status chsh-game

# View logs
journalctl -u chsh-game -f
tail -f /var/log/nginx/access.log
```

## Deployment Checklist

### Pre-Deployment
- [ ] Tests pass locally
- [ ] Environment variables configured
- [ ] Database connection tested
- [ ] Secret key generated and set
- [ ] Domain name configured (if applicable)

### Deployment
- [ ] Application deployed successfully
- [ ] Database initialized
- [ ] Static files served correctly
- [ ] WebSocket connections working
- [ ] HTTPS enabled

### Post-Deployment
- [ ] Health check endpoints respond
- [ ] Game functionality tested
- [ ] Dashboard accessible
- [ ] Performance monitoring enabled
- [ ] Backup strategy implemented
- [ ] Log aggregation configured

### Testing Production Deployment
```bash
# Test HTTP endpoint
curl https://your-domain.com/

# Test WebSocket (using wscat)
npm install -g wscat
wscat -c wss://your-domain.com/socket.io/?EIO=4&transport=websocket

# Load testing
python chsh_load_test.py --url https://your-domain.com --teams 10
```

## Monitoring and Maintenance

### Health Monitoring
- Monitor application uptime
- Check WebSocket connection health
- Monitor database performance
- Track error rates

### Log Management
- Aggregate application logs
- Monitor error patterns
- Set up alerting for critical errors
- Rotate logs to prevent disk usage issues

### Backup Strategy
- Regular database backups
- Store backups securely off-site
- Test backup restoration procedures
- Document recovery processes

### Updates and Maintenance
- Monitor for security updates
- Test updates in staging environment
- Plan maintenance windows
- Keep dependencies up to date

## Troubleshooting Common Issues

### WebSocket Connection Issues
- Verify WebSocket support on platform
- Check proxy configuration
- Ensure proper CORS settings
- Test with different clients

### Database Connection Problems
- Verify connection string format
- Check network connectivity
- Validate credentials
- Monitor connection pool

### Performance Issues
- Monitor resource usage
- Check for memory leaks
- Optimize database queries
- Scale resources as needed

For platform-specific issues, consult the respective platform documentation and support channels.
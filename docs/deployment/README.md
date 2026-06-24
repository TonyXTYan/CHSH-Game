# Deployment Guide

This section provides comprehensive guidance for deploying the CHSH Game in different environments.

## Deployment Options

### Quick Links
- **[Local Deployment](./local-deployment.md)** - Development and testing setup
- **[Production Deployment](./production-deployment.md)** - Cloud and server deployment
- **[Load Testing](./load-testing.md)** - Performance testing and optimization

## Overview

The CHSH Game supports multiple deployment strategies:

### Development
- **Local Flask server** with SQLite database
- **Docker containers** for consistent environments
- **Development tools** with hot reload and debugging

### Production
- **Cloud platforms**: Fly.io, Render, Heroku, AWS, GCP
- **Self-hosted servers** with nginx and gunicorn
- **Database options**: PostgreSQL, MySQL
- **Monitoring and logging** integration

### Performance Considerations

| Environment | Database | Players | Memory | CPU |
|-------------|----------|---------|---------|-----|
| Development | SQLite | 1-10 | 256MB | 1 core |
| Testing | SQLite/PostgreSQL | 10-100 | 512MB | 1-2 cores |
| Production | PostgreSQL | 100-1000+ | 1-4GB | 2-8 cores |

## Technology Stack

### Backend
- **Python 3.11+** with Flask framework
- **Flask-SocketIO** for real-time WebSocket communication
- **SQLAlchemy** ORM with database support
- **Eventlet** for asynchronous networking

### Frontend
- **Static HTML/CSS/JavaScript** served by Flask
- **Socket.IO client** for real-time communication
- **Responsive design** for mobile and desktop

### Infrastructure
- **Web server**: Gunicorn with eventlet workers
- **Reverse proxy**: nginx (production)
- **Database**: SQLite (dev), PostgreSQL (prod)
- **Monitoring**: Health checks and logging

## Environment Variables

### Required Configuration
```bash
# Database configuration
DATABASE_URL=sqlite:///quiz_app.db                    # Development
DATABASE_URL=postgresql://user:pass@host/db           # Production

# Application settings
SECRET_KEY=your-secret-key-here                       # Flask session secret
DEBUG=True                                            # Enable debug mode (dev only)
PORT=8080                                             # Application port
```

### Optional Configuration
```bash
# Logging
LOG_LEVEL=INFO                                        # Logging verbosity

# Performance
MAX_CONNECTIONS=1000                                  # Maximum concurrent connections
WORKER_CONNECTIONS=1000                               # Eventlet worker connections

# Security
ALLOWED_ORIGINS=*                                     # CORS allowed origins
FORCE_HTTPS=true                                      # Force HTTPS in production

# Monitoring
HEALTH_CHECK_PATH=/health                             # Health check endpoint
METRICS_PATH=/metrics                                 # Metrics endpoint
```

## Security Considerations

### Network Security
- **HTTPS enforcement** in production
- **CORS configuration** for allowed origins
- **WebSocket origin validation**
- **Firewall rules** for database access

### Application Security
- **Input validation** for all user inputs
- **SQL injection prevention** via SQLAlchemy ORM
- **Session management** with secure session keys
- **Error handling** without information disclosure

### Infrastructure Security
- **Database encryption** at rest and in transit
- **Secret management** via environment variables
- **Access controls** for administrative functions
- **Security headers** via reverse proxy

## Monitoring and Logging

### Health Checks
```python
@app.route('/health')
def health_check():
    return {'status': 'healthy', 'timestamp': datetime.utcnow()}
```

### Logging Configuration
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
```

### Metrics
- **Connection count**: Active WebSocket connections
- **Team statistics**: Active teams and players
- **Response times**: API and WebSocket response latency
- **Error rates**: Application and database errors

## Scaling Considerations

### Horizontal Scaling
- **Load balancer** distribution across multiple instances
- **Session affinity** for WebSocket connections
- **Shared state storage** via Redis or database
- **Database connection pooling**

### Vertical Scaling
- **Memory requirements**: 256MB base + 50MB per 100 concurrent users
- **CPU utilization**: Single core sufficient for <100 users
- **Network bandwidth**: ~1KB/s per active player

### Database Scaling
- **Connection pooling** for multiple application instances
- **Read replicas** for dashboard analytics queries
- **Indexing optimization** for frequently accessed data
- **Query performance monitoring**

## Backup and Recovery

### Database Backups
```bash
# PostgreSQL backup
pg_dump -h host -U user -d database > backup.sql

# SQLite backup
cp quiz_app.db quiz_app_backup.db
```

### Application State
- **Configuration backup**: Environment variables and settings
- **Code deployment**: Git-based deployment with rollback capability
- **Data migration**: Database schema migration scripts

### Disaster Recovery
- **Recovery time objective (RTO)**: < 30 minutes
- **Recovery point objective (RPO)**: < 1 hour data loss
- **Backup retention**: 30 days of daily backups
- **Testing**: Monthly recovery procedure testing

## Performance Optimization

### Application Performance
- **Database query optimization** with proper indexing
- **Caching strategies** for frequently accessed data
- **Connection pooling** for database and WebSocket connections
- **Static asset optimization** with CDN delivery

### Frontend Performance
- **Minification** of JavaScript and CSS assets
- **Compression** via gzip encoding
- **Browser caching** with appropriate cache headers
- **CDN integration** for global asset delivery

### Database Performance
- **Index optimization** for query performance
- **Query analysis** and optimization
- **Connection pooling** configuration
- **Performance monitoring** and alerting

## Deployment Best Practices

### Development
1. **Use virtual environments** for dependency isolation
2. **Enable debug mode** for detailed error information
3. **Use SQLite** for simple development setup
4. **Implement hot reload** for rapid development

### Staging
1. **Mirror production environment** as closely as possible
2. **Use production database type** (PostgreSQL)
3. **Test with realistic data volumes**
4. **Validate monitoring and alerting**

### Production
1. **Disable debug mode** for security and performance
2. **Use production-grade database** (PostgreSQL)
3. **Implement comprehensive monitoring**
4. **Configure automated backups**
5. **Set up alerting** for critical issues
6. **Plan for scaling** based on usage patterns

---

Choose your deployment path:
- **[Local Development](./local-deployment.md)** - Quick start for development
- **[Production Deployment](./production-deployment.md)** - Cloud and server setup
- **[Load Testing](./load-testing.md)** - Performance validation
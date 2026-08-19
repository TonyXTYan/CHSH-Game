# Troubleshooting Guide

This guide covers common issues and solutions for the CHSH Game application.

## Common Issues

### Installation and Setup Issues

#### Python Version Compatibility
**Problem**: `ImportError` or syntax errors during startup
**Symptoms**: 
- ModuleNotFoundError for required packages
- Syntax errors in Python code
- Package installation failures

**Solutions**:
```bash
# Check Python version
python --version
# Should be 3.11 or higher

# Update Python (Ubuntu/Debian)
sudo apt update
sudo apt install python3.11 python3.11-venv

# Recreate virtual environment
rm -rf venv
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### Package Installation Issues
**Problem**: `pip install` fails with dependency conflicts
**Symptoms**:
- Package conflict errors
- Permission denied errors
- Network timeout errors

**Solutions**:
```bash
# Update pip
pip install --upgrade pip

# Clear pip cache
pip cache purge

# Install with no cache
pip install --no-cache-dir -r requirements.txt

# Permission issues (Linux/macOS)
pip install --user -r requirements.txt

# Network issues - use different index
pip install -i https://pypi.org/simple/ -r requirements.txt
```

#### Virtual Environment Issues
**Problem**: Commands not found or wrong Python version
**Symptoms**:
- `command not found: gunicorn`
- Wrong Python version in venv
- Import errors for installed packages

**Solutions**:
```bash
# Ensure virtual environment is activated
source venv/bin/activate
# Windows: venv\Scripts\activate

# Verify activation
which python
which pip

# Recreate if corrupted
deactivate
rm -rf venv
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Database Issues

#### SQLite Database Corruption
**Problem**: Database errors or corruption
**Symptoms**:
- `database is locked` errors
- `database disk image is malformed`
- Unexpected query failures

**Solutions**:
```bash
# Check database integrity
sqlite3 quiz_app.db "PRAGMA integrity_check;"

# Backup and recreate (data will be lost)
mv quiz_app.db quiz_app.db.backup
# Database will be recreated on next startup

# If data recovery needed
sqlite3 quiz_app.db.backup ".backup quiz_app_recovered.db"
```

#### PostgreSQL Connection Issues
**Problem**: Cannot connect to PostgreSQL database
**Symptoms**:
- Connection timeout errors
- Authentication failures
- `database does not exist` errors

**Solutions**:
```bash
# Verify connection string format
export DATABASE_URL="postgresql://username:password@host:port/database"

# Test connection manually
psql $DATABASE_URL

# Common fixes
# 1. Check if PostgreSQL is running
sudo systemctl status postgresql

# 2. Verify database exists
psql -U username -l

# 3. Create database if missing
createdb -U username database_name

# 4. Check firewall/network connectivity
telnet host port
```

### Server Startup Issues

#### Port Already in Use
**Problem**: Server fails to start with port conflict
**Symptoms**:
- `Address already in use` error
- `Permission denied` on port binding

**Solutions**:
```bash
# Find process using port
lsof -i :8080
# Or: netstat -tulpn | grep :8080

# Kill process using port
kill -9 <PID>

# Use different port
gunicorn wsgi:app --worker-class eventlet --bind 0.0.0.0:8081

# Check permissions (ports < 1024 need sudo)
sudo gunicorn wsgi:app --worker-class eventlet --bind 0.0.0.0:80
```

#### Import Errors
**Problem**: ModuleNotFoundError during server startup
**Symptoms**:
- Cannot import application modules
- Missing dependency errors

**Solutions**:
```bash
# Verify Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Check for missing dependencies
pip install -r requirements.txt

# Verify all files present
ls -la src/
ls -la src/models/
ls -la src/sockets/

# Check for circular imports
python -c "from src.config import app"
```

#### Secret Key Issues
**Problem**: Application fails to start with secret key errors
**Symptoms**:
- `RuntimeError: The session is unavailable because no secret key was set`
- Session-related errors

**Solutions**:
```bash
# Set secret key
export SECRET_KEY="your-secure-secret-key"

# Generate new secret key
python -c "import secrets; print(secrets.token_hex(32))"

# Temporary fix for development
export SECRET_KEY="dev-secret-key-not-for-production"
```

### Runtime Issues

#### WebSocket Connection Problems
**Problem**: Players cannot connect or stay connected
**Symptoms**:
- "Disconnected from server" messages
- Frequent reconnection attempts
- WebSocket handshake failures

**Solutions**:
1. **Check browser console** for detailed error messages
2. **Verify WebSocket support**:
   ```javascript
   // Test in browser console
   new WebSocket('ws://localhost:8080/socket.io/?EIO=4&transport=websocket')
   ```
3. **Check proxy/firewall settings**
4. **Verify server configuration**:
   ```bash
   # Ensure eventlet worker class
   gunicorn wsgi:app --worker-class eventlet
   
   # Check CORS settings in config.py
   socketio = SocketIO(app, cors_allowed_origins="*")
   ```

#### Game State Synchronization Issues
**Problem**: Players see different game states
**Symptoms**:
- Teams not showing correctly
- Game status inconsistencies
- Missing player updates

**Solutions**:
```bash
# Check server logs
tail -f application.log

# Verify state management
# Add debug endpoint (development only)
@app.route('/debug/state')
def debug_state():
    return jsonify({
        'active_teams': len(state.active_teams),
        'connected_players': len(state.connected_players),
        'game_started': state.game_started
    })

# Clear application state
# Restart server to reset in-memory state
```

#### Performance Issues
**Problem**: Slow response times or high resource usage
**Symptoms**:
- Delayed answer submissions
- High CPU or memory usage
- Timeout errors

**Solutions**:
1. **Monitor resource usage**:
   ```bash
   # Check CPU and memory
   htop
   
   # Monitor specific process
   ps aux | grep gunicorn
   
   # Check disk space
   df -h
   ```

2. **Optimize configuration**:
   ```bash
   # Increase worker timeout
   gunicorn wsgi:app --worker-class eventlet --timeout 60
   
   # Monitor worker processes
   gunicorn wsgi:app --worker-class eventlet --max-requests 1000
   ```

3. **Database optimization**:
   ```sql
   -- Check for long-running queries
   SELECT * FROM pg_stat_activity WHERE state = 'active';
   
   -- Vacuum database (PostgreSQL)
   VACUUM ANALYZE;
   ```

### Frontend Issues

#### JavaScript Errors
**Problem**: Frontend functionality not working
**Symptoms**:
- Buttons not responding
- Forms not submitting
- Socket.IO events not firing

**Solutions**:
1. **Check browser console** (F12 → Console tab)
2. **Verify JavaScript loading**:
   ```javascript
   // Check if Socket.IO loaded
   console.log(typeof io);  // Should be 'function'
   
   // Check if theme manager loaded
   console.log(typeof window.themeManager);  // Should be 'object'
   ```

3. **Clear browser cache**: Ctrl+Shift+R (hard refresh)
4. **Test in different browsers**
5. **Check for ad blockers** blocking WebSocket connections

#### UI Display Issues
**Problem**: Layout broken or elements missing
**Symptoms**:
- CSS not loading
- Mobile layout issues
- Theme not applying

**Solutions**:
1. **Check CSS loading**:
   ```html
   <!-- Verify CSS link in HTML -->
   <link rel="stylesheet" href="/static/styles.css">
   ```

2. **Clear browser cache**
3. **Check responsive design**:
   ```css
   /* Test mobile viewport */
   @media (max-width: 768px) { /* mobile styles */ }
   ```

4. **Verify theme system**:
   ```javascript
   // Test theme switching
   window.themeManager.setTheme('food');
   window.themeManager.setMode('simplified');
   ```

### Deployment Issues

#### Docker Build Failures
**Problem**: Docker image build fails
**Symptoms**:
- Package installation errors in container
- Python version mismatches
- File permission issues

**Solutions**:
```dockerfile
# Use specific Python version
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first (for cache efficiency)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Set permissions
RUN chmod +x wsgi.py

# Expose port
EXPOSE 8080

# Run application
CMD ["gunicorn", "wsgi:app", "--worker-class", "eventlet", "--bind", "0.0.0.0:8080"]
```

#### Platform-Specific Issues

##### Fly.io Issues
**Problem**: App not starting on Fly.io
**Solutions**:
```bash
# Check logs
flyctl logs

# Verify fly.toml configuration
[env]
  PORT = "8080"

[http_service]
  internal_port = 8080
  force_https = true

# Check disk usage
flyctl status
```

##### Render.com Issues
**Problem**: Build or runtime failures on Render
**Solutions**:
```bash
# Check build logs in Render dashboard
# Verify start command
gunicorn wsgi:app --worker-class eventlet

# Set environment variables
PYTHON_VERSION=3.11.0
SECRET_KEY=your-secret-key
```

##### Heroku Issues
**Problem**: Application errors on Heroku
**Solutions**:
```bash
# Check logs
heroku logs --tail

# Verify Procfile
web: gunicorn wsgi:app --worker-class eventlet

# Check dyno status
heroku ps

# Restart dyno
heroku restart
```

### Testing Issues

#### Test Failures
**Problem**: Tests failing unexpectedly
**Symptoms**:
- Import errors in tests
- Database connection failures
- Timing-dependent test failures

**Solutions**:
```bash
# Run tests with verbose output
pytest -v

# Run specific test
pytest tests/unit/test_models.py::test_team_creation

# Check test environment
export FLASK_ENV=testing
export DATABASE_URL=sqlite:///:memory:

# Clear test database
rm test_*.db

# Run with coverage
pytest --cov=src --cov-report=html
```

#### Load Test Issues
**Problem**: Load tests failing or giving inconsistent results
**Solutions**:
```bash
# Start with smaller load
python chsh_load_test.py --teams 5 --max-duration 30

# Check server capacity
htop  # During load test

# Increase timeout
python chsh_load_test.py --teams 10 --timeout 60

# Use gradual connection strategy
python chsh_load_test.py --teams 50 --connection-strategy gradual
```

## Diagnostic Tools

### Server Diagnostics

#### Health Check Endpoint
```python
# Add to routes for debugging
@app.route('/health')
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'active_teams': len(state.active_teams),
        'connected_players': len(state.connected_players),
        'game_started': state.game_started
    })
```

#### Log Analysis
```bash
# Monitor real-time logs
tail -f application.log | grep ERROR

# Search for specific errors
grep "WebSocket" application.log
grep "Database" application.log

# Analyze error patterns
awk '/ERROR/ {print $1, $2, $NF}' application.log | sort | uniq -c
```

### Database Diagnostics

#### SQLite
```bash
# Check database size
ls -lh quiz_app.db

# Analyze database
sqlite3 quiz_app.db ".schema"
sqlite3 quiz_app.db "SELECT COUNT(*) FROM teams;"
sqlite3 quiz_app.db "SELECT COUNT(*) FROM answers;"
```

#### PostgreSQL
```sql
-- Check database size
SELECT pg_size_pretty(pg_database_size('chsh_game'));

-- Check table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) 
FROM pg_tables 
WHERE schemaname = 'public';

-- Check active connections
SELECT count(*) FROM pg_stat_activity;
```

### Network Diagnostics

#### WebSocket Testing
```bash
# Install wscat for WebSocket testing
npm install -g wscat

# Test WebSocket connection
wscat -c ws://localhost:8080/socket.io/?EIO=4&transport=websocket

# Test with authentication
wscat -c "wss://your-domain.com/socket.io/?EIO=4&transport=websocket"
```

#### HTTP Testing
```bash
# Test HTTP endpoints
curl -I http://localhost:8080/
curl http://localhost:8080/health

# Test with specific headers
curl -H "Accept: application/json" http://localhost:8080/api/status
```

## Performance Monitoring

### Resource Monitoring
```bash
# Monitor CPU and memory
watch 'ps aux | grep gunicorn'

# Monitor disk I/O
iotop

# Monitor network connections
netstat -tulpn | grep :8080
ss -tulpn | grep :8080
```

### Application Monitoring
```python
# Add performance logging
import time
import logging

def log_performance(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        logging.info(f"{func.__name__} took {end_time - start_time:.2f} seconds")
        return result
    return wrapper
```

## Error Recovery

### Automatic Recovery
```bash
# Create systemd service with restart
[Unit]
Description=CHSH Game
After=network.target

[Service]
Type=exec
User=chsh-game
WorkingDirectory=/app
ExecStart=/app/venv/bin/gunicorn wsgi:app --worker-class eventlet
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Manual Recovery
```bash
# Restart application
sudo systemctl restart chsh-game

# Reset database (data loss)
rm quiz_app.db
sudo systemctl restart chsh-game

# Clear application cache
rm -rf __pycache__/
rm -rf src/__pycache__/
sudo systemctl restart chsh-game
```

## Getting Help

### Information to Collect
When reporting issues, please include:

1. **Environment Information**:
   ```bash
   python --version
   pip list | grep -E "(Flask|socketio|eventlet)"
   uname -a  # Linux/macOS
   ```

2. **Error Messages**:
   - Complete error traceback
   - Browser console errors
   - Server log excerpts

3. **Reproduction Steps**:
   - What you were trying to do
   - Steps to reproduce the issue
   - Expected vs actual behavior

4. **Configuration**:
   - Environment variables (redact sensitive data)
   - Deployment platform
   - Database type and version

### Support Channels
- **GitHub Issues**: For bugs and feature requests
- **Documentation**: Check [doc/index.md](index.md) for guides
- **Load Testing**: See [load_test/LOAD_TEST_README.md](../load_test/LOAD_TEST_README.md)

### Before Seeking Help
1. **Check this troubleshooting guide**
2. **Search existing GitHub issues**
3. **Try the basic solutions** (restart, clear cache, etc.)
4. **Test with minimal configuration**
5. **Verify the issue exists** in a clean environment

Remember to redact sensitive information (passwords, API keys, etc.) when sharing configuration or logs.
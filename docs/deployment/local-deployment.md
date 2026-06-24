# Local Deployment

This guide covers setting up the CHSH Game for local development and testing.

## Quick Start

### Prerequisites
- Python 3.11+ installed
- Git for version control
- A modern web browser

### Basic Setup

1. **Clone and setup**:
```bash
git clone https://github.com/TonyXTYan/CHSH-Game.git
cd CHSH-Game

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

2. **Run the application**:
```bash
python src/main.py
```

3. **Access the application**:
- **Player interface**: http://localhost:8080/
- **Dashboard**: http://localhost:8080/dashboard

## Development Environment

### Using Python Virtual Environment

#### Setup
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# For development tools
pip install -r requirements-dev.txt
```

#### Running with Debug Mode
```bash
# Set environment variables
export FLASK_ENV=development
export DEBUG=True

# Run with auto-reload
python src/main.py
```

The server will automatically reload when you make code changes.

### Using Docker

#### Basic Docker Setup
```bash
# Build the image
docker build -t chsh-game .

# Run the container
docker run -p 8080:8080 chsh-game
```

#### Docker with Development Volumes
```bash
# Run with code volume for live editing
docker run -p 8080:8080 \
  -v $(pwd)/src:/app/src \
  -v $(pwd)/static:/app/static \
  -e DEBUG=True \
  chsh-game
```

#### Docker Compose (Optional)
Create `docker-compose.dev.yml`:
```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8080:8080"
    volumes:
      - ./src:/app/src
      - ./static:/app/static
    environment:
      - DEBUG=True
      - DATABASE_URL=sqlite:///quiz_app.db
    command: python src/main.py
```

Run with:
```bash
docker-compose -f docker-compose.dev.yml up --build
```

## Database Configuration

### SQLite (Default)
No additional setup required. The application creates `quiz_app.db` automatically.

```python
# Default configuration in src/config.py
DATABASE_URL = 'sqlite:///quiz_app.db'
```

**Location**: `quiz_app.db` in the project root

**Pros**:
- No setup required
- Good for development
- Easy to reset (just delete the file)

**Cons**:
- Single connection limitations
- Not suitable for production

### PostgreSQL (Optional for Local Development)

#### Using Docker PostgreSQL
```bash
# Run PostgreSQL container
docker run -d \
  --name chsh-postgres \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_USER=chsh_user \
  -e POSTGRES_DB=chsh_game \
  -p 5432:5432 \
  postgres:13

# Set environment variable
export DATABASE_URL=postgresql://chsh_user:password@localhost:5432/chsh_game

# Run the application
python src/main.py
```

#### Using Local PostgreSQL Installation
```bash
# Install PostgreSQL (varies by OS)
# Ubuntu/Debian:
sudo apt-get install postgresql postgresql-contrib

# Create database and user
sudo -u postgres psql
postgres=# CREATE USER chsh_user WITH PASSWORD 'password';
postgres=# CREATE DATABASE chsh_game OWNER chsh_user;
postgres=# \q

# Set environment variable
export DATABASE_URL=postgresql://chsh_user:password@localhost:5432/chsh_game
```

## Environment Configuration

### Environment Variables
Create a `.env` file in the project root:
```bash
# Database
DATABASE_URL=sqlite:///quiz_app.db

# Application
SECRET_KEY=dev-secret-key-change-in-production
DEBUG=True
PORT=8080

# Logging
LOG_LEVEL=DEBUG
```

Load with python-dotenv:
```bash
pip install python-dotenv
```

### Configuration Files
The application supports multiple configuration methods:

#### 1. Environment Variables (Recommended)
```bash
export DATABASE_URL=sqlite:///quiz_app.db
export SECRET_KEY=your-secret-key
export DEBUG=True
```

#### 2. .env File
```bash
# .env
DATABASE_URL=sqlite:///quiz_app.db
SECRET_KEY=your-secret-key
DEBUG=True
```

#### 3. Direct Configuration
Edit `src/config.py` for development-specific settings.

## Development Tools

### Code Quality Tools
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Code formatting
black src/
isort src/

# Linting
flake8 src/
pylint src/

# Type checking
mypy src/
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/

# Run specific test files
pytest tests/unit/
pytest tests/integration/
```

### Database Management
```bash
# Reset database (SQLite)
rm quiz_app.db
python src/main.py  # Will recreate tables

# View database contents
sqlite3 quiz_app.db
.tables
.schema teams
SELECT * FROM teams;
```

## Development Workflow

### Code Changes
1. **Make changes** to Python or frontend files
2. **Server auto-reloads** (if debug mode enabled)
3. **Refresh browser** to see frontend changes
4. **Check console** for any errors

### Database Changes
1. **Modify models** in `src/models/quiz_models.py`
2. **Delete database** file to reset: `rm quiz_app.db`
3. **Restart server** to recreate tables
4. **Test with fresh data**

### Frontend Changes
1. **Edit HTML/CSS/JS** files in `src/static/`
2. **Refresh browser** to see changes
3. **Check browser console** for JavaScript errors
4. **Test on different browsers** if needed

## Debugging

### Python Debugging
```python
# Add breakpoints in code
import pdb; pdb.set_trace()

# Or use debugger in IDE
```

### Flask Debug Mode
```bash
export DEBUG=True
python src/main.py
```

Provides:
- Detailed error pages
- Auto-reload on code changes
- Debug toolbar (if installed)

### Browser Developer Tools
- **Console**: Check for JavaScript errors
- **Network**: Monitor WebSocket connections
- **Application**: Inspect local storage and cookies
- **Performance**: Profile frontend performance

### Logging
```python
import logging
logger = logging.getLogger(__name__)

# Add debug logs
logger.debug("Debug information")
logger.info("General information")
logger.warning("Warning message")
logger.error("Error occurred")
```

## Testing Your Setup

### Basic Functionality Test
1. **Start the server**: `python src/main.py`
2. **Open player interface**: http://localhost:8080/
3. **Create a team** with any name
4. **Open second browser tab/window**
5. **Join the same team**
6. **Open dashboard**: http://localhost:8080/dashboard
7. **Start the game** from dashboard
8. **Answer questions** in both player windows
9. **Verify statistics** update on dashboard

### Multiple Teams Test
1. **Create multiple teams** (3-5 teams)
2. **Add 2 players to each team**
3. **Start the game**
4. **Have all players answer questions**
5. **Monitor dashboard statistics**
6. **Download CSV data** to verify exports

### Error Handling Test
1. **Disconnect players** during game
2. **Try to join full teams**
3. **Submit invalid answers**
4. **Check error messages** are user-friendly

## Performance Testing

### Local Load Testing
```bash
# Test with simulated players
python chsh_load_test.py --url http://localhost:8080 --teams 10

# Monitor system resources
top  # or htop on Linux/Mac
# Task Manager on Windows
```

### Memory Usage Monitoring
```python
# Add to your code for memory monitoring
import psutil
import os

process = psutil.Process(os.getpid())
print(f"Memory usage: {process.memory_info().rss / 1024 / 1024:.2f} MB")
```

## Common Issues

### Port Already in Use
```bash
# Find process using port 8080
lsof -ti:8080  # Mac/Linux
netstat -ano | findstr :8080  # Windows

# Kill the process
kill -9 <PID>  # Mac/Linux
taskkill /PID <PID> /F  # Windows
```

### Database Connection Issues
```bash
# SQLite permission issues
chmod 666 quiz_app.db

# PostgreSQL connection issues
# Check if PostgreSQL is running
pg_isready -h localhost -p 5432
```

### WebSocket Connection Issues
- **Check firewall settings**
- **Verify port is not blocked**
- **Test with different browsers**
- **Check browser console for errors**

### Python Module Import Issues
```bash
# Verify virtual environment is active
which python  # Should point to venv

# Reinstall dependencies
pip install -r requirements.txt

# Check Python path
python -c "import sys; print('\n'.join(sys.path))"
```

## IDE Setup

### Visual Studio Code
1. **Install Python extension**
2. **Select interpreter**: `Ctrl+Shift+P` → "Python: Select Interpreter"
3. **Choose virtual environment** interpreter
4. **Configure launch.json**:
```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "CHSH Game",
            "type": "python",
            "request": "launch",
            "program": "${workspaceFolder}/src/main.py",
            "env": {
                "DEBUG": "True"
            },
            "console": "integratedTerminal"
        }
    ]
}
```

### PyCharm
1. **Create new project** from existing sources
2. **Configure interpreter**: Settings → Project → Python Interpreter
3. **Add run configuration**: Run → Edit Configurations
4. **Set script path**: `src/main.py`
5. **Set working directory**: project root

## Next Steps

### For Development
- Review the [Architecture Guide](../developer-guide/architecture.md)
- Check the [API Reference](../developer-guide/api-reference.md)
- Follow [Contributing Guidelines](../developer-guide/contributing.md)

### For Production
- See [Production Deployment](./production-deployment.md)
- Configure [Load Testing](./load-testing.md)
- Set up monitoring and logging

---

Your local development environment should now be ready! Start coding and testing your changes.
# Installation Guide

This guide covers setting up the CHSH Game locally for development or deployment.

## Prerequisites

### System Requirements
- **Python**: 3.11 or higher
- **Operating System**: Linux, macOS, or Windows
- **Memory**: Minimum 512MB RAM (2GB+ recommended for development)
- **Disk Space**: 100MB for dependencies and application

### Required Tools
- Git (for cloning the repository)
- Python 3.11+ with pip
- Virtual environment tool (venv, virtualenv, or conda)

## Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/TonyXTYan/CHSH-Game.git
cd CHSH-Game
```

### 2. Set Up Python Virtual Environment
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the Application
```bash
gunicorn wsgi:app --worker-class eventlet --bind 0.0.0.0:8080
```

### 5. Access the Game
- **Player Interface**: http://localhost:8080/
- **Host Dashboard**: http://localhost:8080/dashboard

## Detailed Installation

### Development Setup

#### 1. Environment Configuration
Create a `.env` file (optional) to configure environment variables:
```bash
# .env file
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///quiz_app.db
```

#### 2. Database Initialization
The database is automatically created when you first run the application. By default, it uses SQLite and creates a file called `quiz_app.db` in the project root.

#### 3. Install Development Dependencies
```bash
pip install -r requirements-dev.txt
```

This includes additional tools for development:
- pytest (testing framework)
- pytest-cov (coverage reporting)
- Additional testing utilities

### Production Setup

#### Database Configuration
For production, use PostgreSQL:

1. **Install PostgreSQL** on your system
2. **Create a database**:
   ```sql
   CREATE DATABASE chsh_game;
   CREATE USER chsh_user WITH PASSWORD 'your_password';
   GRANT ALL PRIVILEGES ON DATABASE chsh_game TO chsh_user;
   ```
3. **Set DATABASE_URL**:
   ```bash
   export DATABASE_URL="postgresql://chsh_user:your_password@localhost/chsh_game"
   ```

#### Environment Variables
Set the following environment variables for production:
```bash
export SECRET_KEY="your-secure-secret-key"
export DATABASE_URL="postgresql://user:password@host:port/database"
export FLASK_ENV="production"
```

## Platform-Specific Instructions

### Docker Installation

#### 1. Build Docker Image
```bash
docker build -t chsh-game .
```

#### 2. Run Container
```bash
docker run -p 8080:8080 chsh-game
```

#### 3. With Environment Variables
```bash
docker run -p 8080:8080 \
  -e SECRET_KEY=your-secret-key \
  -e DATABASE_URL=your-database-url \
  chsh-game
```

### Windows Installation

#### Using Windows Subsystem for Linux (WSL)
1. Install WSL2 from Microsoft Store
2. Install Ubuntu or similar Linux distribution
3. Follow the Linux installation steps

#### Native Windows Installation
1. Install Python 3.11+ from python.org
2. Install Git for Windows
3. Use Command Prompt or PowerShell:
   ```cmd
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   python -m gunicorn wsgi:app --worker-class eventlet --bind 0.0.0.0:8080
   ```

### macOS Installation

#### Using Homebrew
```bash
# Install Python 3.11
brew install python@3.11

# Set Python 3.11 as default
export PATH="/opt/homebrew/bin/python3.11:$PATH"

# Follow standard installation steps
git clone https://github.com/TonyXTYan/CHSH-Game.git
cd CHSH-Game
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
gunicorn wsgi:app --worker-class eventlet --bind 0.0.0.0:8080
```

### Linux Installation

#### Ubuntu/Debian
```bash
# Update package list
sudo apt update

# Install Python 3.11 and dependencies
sudo apt install python3.11 python3.11-venv python3.11-dev git

# Follow standard installation steps
git clone https://github.com/TonyXTYan/CHSH-Game.git
cd CHSH-Game
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
gunicorn wsgi:app --worker-class eventlet --bind 0.0.0.0:8080
```

#### CentOS/RHEL/Fedora
```bash
# Install Python 3.11
sudo dnf install python3.11 python3.11-pip git

# Follow standard installation steps
git clone https://github.com/TonyXTYan/CHSH-Game.git
cd CHSH-Game
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
gunicorn wsgi:app --worker-class eventlet --bind 0.0.0.0:8080
```

## Development Configuration

### IDE Setup

#### Visual Studio Code
1. Install Python extension
2. Open the project folder
3. Select the virtual environment as Python interpreter
4. Recommended extensions:
   - Python
   - Flask Snippets
   - SQLite Viewer

#### PyCharm
1. Open project in PyCharm
2. Configure Python interpreter to use the virtual environment
3. Set up run configuration for Flask application

### Development Server

For development with auto-reload:
```bash
# Using Flask development server (not recommended for production)
export FLASK_APP=wsgi.py
export FLASK_ENV=development
flask run --host=0.0.0.0 --port=8080

# Or using gunicorn with reload
gunicorn wsgi:app --worker-class eventlet --bind 0.0.0.0:8080 --reload
```

### Testing Setup

#### Running Tests
```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_game_logic.py
```

#### Load Testing
```bash
# Install load test dependencies
pip install -r load_test_requirements.txt

# Run load test
python chsh_load_test.py --teams 10 --max-duration 60
```

## Configuration Options

### Environment Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `SECRET_KEY` | Flask secret key for sessions | Random | `your-secret-key` |
| `DATABASE_URL` | Database connection string | SQLite file | `postgresql://user:pass@host/db` |
| `FLASK_ENV` | Flask environment | `production` | `development` |
| `PORT` | Port to bind to | `8080` | `5000` |

### Runtime Configuration

#### Server Options
```bash
# Different worker classes
gunicorn wsgi:app --worker-class eventlet    # Recommended
gunicorn wsgi:app --worker-class gevent      # Alternative
gunicorn wsgi:app --worker-class sync        # Not recommended

# Multiple workers (experimental)
gunicorn wsgi:app --worker-class eventlet --workers 4

# Binding options
gunicorn wsgi:app --worker-class eventlet --bind 0.0.0.0:8080    # All interfaces
gunicorn wsgi:app --worker-class eventlet --bind 127.0.0.1:8080  # Localhost only
```

## Troubleshooting Installation

### Common Issues

#### Python Version Issues
```bash
# Check Python version
python --version
python3 --version

# Use specific Python version
python3.11 -m venv venv
```

#### Permission Issues (Linux/macOS)
```bash
# If pip install fails with permissions
pip install --user -r requirements.txt

# Or use sudo (not recommended)
sudo pip install -r requirements.txt
```

#### Port Already in Use
```bash
# Check what's using port 8080
sudo lsof -i :8080

# Use a different port
gunicorn wsgi:app --worker-class eventlet --bind 0.0.0.0:5000
```

#### Virtual Environment Issues
```bash
# Recreate virtual environment
rm -rf venv
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

#### Database Issues
```bash
# Remove SQLite database to reset
rm quiz_app.db

# The database will be recreated on next run
```

### Getting Help

If you encounter issues:
1. Check the [Troubleshooting Guide](troubleshooting.md)
2. Review application logs for error messages
3. Ensure all prerequisites are met
4. Check the GitHub repository for known issues
5. Create an issue on GitHub with:
   - Operating system and version
   - Python version
   - Error messages
   - Steps to reproduce

## Next Steps

After successful installation:
1. Read the [Game Rules](game-rules.md) to understand how to play
2. Check the [Development Guide](development.md) for code contribution
3. See [Deployment Guide](deployment.md) for production deployment
4. Review [API Documentation](api.md) for integration
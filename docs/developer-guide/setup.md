# Development Setup

This guide will help you set up a complete development environment for the CHSH Game.

## Prerequisites

### Required Software
- **Python 3.11+** (recommended: 3.11 or 3.12)
- **Git** for version control
- **A modern web browser** (Chrome, Firefox, Safari, or Edge)

### Optional but Recommended
- **Virtual environment tool** (venv, conda, or virtualenv)
- **Code editor** with Python support (VS Code, PyCharm, etc.)
- **Docker** for containerized development (optional)

## Step 1: Clone the Repository

```bash
git clone https://github.com/TonyXTYan/CHSH-Game.git
cd CHSH-Game
```

## Step 2: Set Up Python Environment

### Option A: Using venv (Recommended)
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Verify Python version
python --version  # Should be 3.11+
```

### Option B: Using conda
```bash
# Create conda environment
conda create -n chsh-game python=3.11
conda activate chsh-game
```

## Step 3: Install Dependencies

### Production Dependencies
```bash
pip install -r requirements.txt
```

### Development Dependencies (for testing and development tools)
```bash
pip install -r requirements-dev.txt
```

### Verify Installation
```bash
python -c "import flask, flask_socketio; print('Dependencies installed successfully')"
```

## Step 4: Environment Configuration

### Environment Variables (Optional)
Create a `.env` file in the project root (optional - defaults are provided):

```bash
# .env file
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///quiz_app.db
DEBUG=True
```

### Available Configuration Options
- `SECRET_KEY`: Flask session secret (auto-generated if not provided)
- `DATABASE_URL`: Database connection string
  - SQLite (default): `sqlite:///quiz_app.db`
  - PostgreSQL: `postgresql://user:password@host:port/database`
- `DEBUG`: Enable debug mode (default: True in development)

## Step 5: Database Setup

The application automatically creates the necessary database tables on first run.

### Initialize Database
```bash
python src/main.py
# This will create the SQLite database and tables automatically
```

### Database Location
- **SQLite** (default): `quiz_app.db` in the project root
- **PostgreSQL**: Configure via `DATABASE_URL` environment variable

## Step 6: Run the Application

### Start the Development Server
```bash
python src/main.py
```

### Access the Application
- **Player Interface**: http://localhost:8080/
- **Dashboard**: http://localhost:8080/dashboard
- **Server Info**: http://localhost:8080/api/server/id

### Verify Everything Works
1. Open the player interface in one browser tab
2. Create a team and note the team name
3. Open the dashboard in another tab
4. Verify you see the team in the dashboard
5. Add a second player to form a complete team
6. Start the game from the dashboard
7. Answer a few questions to test the flow

## Development Tools Setup

### Code Editor Configuration

#### Visual Studio Code
Recommended extensions:
```json
{
    "recommendations": [
        "ms-python.python",
        "ms-python.flake8",
        "ms-python.black-formatter",
        "bradlc.vscode-tailwindcss",
        "esbenp.prettier-vscode"
    ]
}
```

#### Settings for Python Development
```json
{
    "python.defaultInterpreterPath": "./venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.formatting.provider": "black"
}
```

### Git Hooks (Optional)
Set up pre-commit hooks for code quality:

```bash
# Install pre-commit
pip install pre-commit

# Install git hooks
pre-commit install
```

## Testing Setup

### Run Unit Tests
```bash
pytest tests/unit/
```

### Run Integration Tests
```bash
pytest tests/integration/
```

### Run All Tests with Coverage
```bash
pytest --cov=src/ tests/
```

### Load Testing
```bash
python chsh_load_test.py
```

## Docker Development (Optional)

### Build Docker Image
```bash
docker build -t chsh-game .
```

### Run with Docker
```bash
docker run -p 8080:8080 chsh-game
```

### Docker Compose (if available)
```bash
docker-compose up --build
```

## Debugging Setup

### Flask Debug Mode
Debug mode is enabled by default in development. Features include:
- Automatic server reload on code changes
- Detailed error pages
- Interactive debugger in browser

### Logging Configuration
The application uses Python's logging module. Check logs for:
- Server startup messages
- Database connection status
- Socket.IO events
- Error traceback

### Browser Developer Tools
- **Console**: Check for JavaScript errors
- **Network**: Monitor WebSocket connections
- **Application**: Inspect local storage and cookies

## Common Development Issues

### Port Already in Use
```bash
# Kill process using port 8080
lsof -ti:8080 | xargs kill -9

# Or use a different port
python src/main.py --port 8081
```

### Database Issues
```bash
# Reset database (removes all data)
rm quiz_app.db
python src/main.py  # Will recreate tables
```

### Package Conflicts
```bash
# Create fresh virtual environment
rm -rf venv
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### Socket.IO Connection Issues
- Check firewall settings
- Verify WebSocket support in browser
- Test with different browsers
- Check network proxy settings

## IDE-Specific Setup

### PyCharm
1. Open project in PyCharm
2. Configure Python interpreter: Settings → Project → Python Interpreter
3. Select the virtual environment interpreter
4. Mark `src/` as Sources Root
5. Configure run configuration for `src/main.py`

### VS Code
1. Open project folder in VS Code
2. Select Python interpreter: Ctrl+Shift+P → "Python: Select Interpreter"
3. Choose the virtual environment interpreter
4. Install recommended extensions
5. Configure launch.json for debugging

## Performance Considerations

### Development vs Production
- Development uses SQLite (single file database)
- Production should use PostgreSQL for better performance
- Debug mode should be disabled in production
- Consider using gunicorn for production deployment

### Memory Usage
- Monitor memory usage during development
- Use browser dev tools to check for memory leaks
- Test with multiple simultaneous connections

## Next Steps

### Explore the Codebase
1. **[Architecture Overview](./architecture.md)** - Understand the system design
2. **[API Reference](./api-reference.md)** - Learn about Socket.IO events and endpoints
3. **[Contributing Guidelines](./contributing.md)** - Code standards and workflow

### Start Contributing
1. Pick an issue from the GitHub issue tracker
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

### Advanced Setup
- Configure load testing environment
- Set up continuous integration
- Deploy to staging environment
- Configure monitoring and logging

---

Need help? Check the [Troubleshooting Guide](../user-guide/troubleshooting.md) or create an issue on GitHub.
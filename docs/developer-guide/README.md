# Developer Guide

Welcome to the CHSH Game developer documentation! This section contains everything you need to contribute to and extend the project.

## Quick Start for Developers

### Prerequisites
- Python 3.11+ 
- Git
- A modern web browser for testing

### Get the Code
```bash
git clone https://github.com/TonyXTYan/CHSH-Game.git
cd CHSH-Game
```

### Essential Resources
- **[Development Setup](./setup.md)** - Complete environment setup guide
- **[Architecture Overview](./architecture.md)** - System design and component overview
- **[API Reference](./api-reference.md)** - Complete API documentation
- **[Contributing Guidelines](./contributing.md)** - How to contribute code

## Project Overview

The CHSH Game is a real-time multiplayer web application built with:

- **Backend**: Python 3, Flask, Flask-SocketIO, SQLAlchemy
- **Frontend**: HTML5, CSS3, JavaScript, Socket.IO client  
- **Database**: SQLite (development), PostgreSQL (production)
- **Real-time Communication**: WebSocket via Socket.IO
- **Deployment**: Docker, Fly.io, Render

## Key Components

### Backend Structure
```
src/
├── config.py           # Flask app, SocketIO, DB configuration
├── game_logic.py       # Core game round and question logic
├── main.py             # Application entry point
├── state.py            # In-memory application state
├── models/
│   ├── quiz_models.py  # Game models (Teams, Answers, Rounds)
│   └── user.py         # User model (separate from core game)
├── routes/
│   ├── static.py       # Static file serving
│   └── user.py         # User CRUD operations
└── sockets/
    ├── dashboard.py    # Dashboard event handlers
    ├── game.py         # Game event handlers
    └── team_management.py # Team management handlers
```

### Frontend Structure  
```
src/static/
├── index.html          # Player client interface
├── dashboard.html      # Host/instructor dashboard
├── app.js              # Player client JavaScript
├── dashboard.js        # Dashboard JavaScript
├── socket-handlers.js  # Shared Socket.IO handling
├── styles.css          # Player client styles
└── dashboard.css       # Dashboard styles
```

## Core Technologies

### Flask & Flask-SocketIO
- **Flask**: Lightweight web framework for HTTP routes and static serving
- **Flask-SocketIO**: WebSocket support for real-time bidirectional communication
- **Eventlet**: Asynchronous networking for Socket.IO

### Database Layer
- **SQLAlchemy**: ORM for database operations
- **Models**: Teams, Answers, PairQuestionRounds
- **Support**: SQLite (dev), PostgreSQL (prod)

### Real-time Features
- **Team management**: Join/leave/create teams
- **Game flow**: Question distribution and answer collection
- **Live dashboard**: Real-time statistics and monitoring
- **Statistics**: CHSH calculations with uncertainty analysis

## Development Workflow

### 1. Setup Your Environment
Follow the [Setup Guide](./setup.md) to configure your development environment.

### 2. Understanding the Architecture
Review the [Architecture Overview](./architecture.md) to understand system design.

### 3. API Documentation
Check the [API Reference](./api-reference.md) for Socket.IO events and HTTP endpoints.

### 4. Making Changes
Follow our [Contributing Guidelines](./contributing.md) for code standards and workflow.

## Testing

### Running Tests
```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=src/

# Run specific test categories
pytest tests/unit/
pytest tests/integration/
```

### Test Structure
- **Unit tests**: Individual component testing
- **Integration tests**: Socket.IO and database integration
- **Load tests**: Performance and stress testing

## Key Concepts

### Game Flow
1. **Team Formation**: Players create/join teams of 2
2. **Game Start**: Host initiates game from dashboard
3. **Question Rounds**: Players receive A/B/X/Y questions
4. **Answer Collection**: True/False responses recorded
5. **Statistics**: Real-time CHSH and correlation calculations

### Statistics Engine
- **Correlation Matrix**: 4x4 matrix of player response correlations
- **CHSH Calculation**: Quantum mechanics inequality measurement
- **Uncertainty Analysis**: Statistical significance using uncertainties library

### Real-time Communication
- **WebSocket Events**: Bidirectional communication between client and server
- **State Management**: In-memory state with database persistence
- **Error Handling**: Graceful degradation and reconnection

## Common Development Tasks

### Adding New Features
1. Plan the feature and discuss with maintainers
2. Update database models if needed
3. Implement backend logic
4. Add Socket.IO events if needed
5. Update frontend interfaces
6. Add tests
7. Update documentation

### Debugging Issues
1. Check browser console for JavaScript errors
2. Monitor Flask application logs
3. Use Socket.IO debugging features
4. Test with multiple browsers/devices
5. Check database state and queries

### Performance Optimization
1. Profile database queries
2. Monitor WebSocket connection counts
3. Optimize frontend JavaScript
4. Use caching where appropriate
5. Review memory usage patterns

## Getting Help

### Resources
- **Code Review**: See our [comprehensive code review](../code-review/) for detailed analysis
- **Issue Tracker**: GitHub Issues for bugs and feature requests
- **Discussions**: GitHub Discussions for questions and ideas

### Community
- Follow coding standards in [Contributing Guidelines](./contributing.md)
- Join discussions about new features and improvements
- Help review pull requests from other contributors

---

Ready to contribute? Start with the [Development Setup](./setup.md) guide!
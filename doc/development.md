# Development Guide

This guide covers the development workflow, code structure, and contribution guidelines for the CHSH Game project.

## Development Environment Setup

### Prerequisites
- Python 3.11 or higher
- Git
- A code editor (VS Code, PyCharm, etc.)
- Basic knowledge of Flask, Socket.IO, and JavaScript

### Initial Setup
1. **Fork and Clone**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/CHSH-Game.git
   cd CHSH-Game
   ```

2. **Set up Virtual Environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

3. **Verify Installation**:
   ```bash
   pytest tests/unit/
   python -m flask --version
   ```

## Project Structure

### Backend Architecture
```
src/
├── config.py              # Flask and database configuration
├── main.py                # Application entry point and server setup
├── state.py               # In-memory application state management
├── game_logic.py          # Core game logic and round management
├── models/                # Database models
│   ├── __init__.py
│   ├── quiz_models.py     # Teams, Answers, PairQuestionRounds
│   └── user.py           # User model (optional feature)
├── routes/               # HTTP route handlers
│   ├── __init__.py
│   ├── static.py         # Static file serving
│   └── user.py          # User management API
├── sockets/             # Socket.IO event handlers
│   ├── __init__.py
│   ├── game.py          # Game events (submit_answer)
│   ├── team_management.py # Team operations
│   └── dashboard.py     # Dashboard and statistics
└── static/              # Frontend assets
    ├── index.html       # Player interface
    ├── dashboard.html   # Host dashboard
    ├── app.js          # Player client JavaScript
    ├── dashboard.js    # Dashboard JavaScript
    ├── socket-handlers.js # Shared Socket.IO utilities
    ├── themes.js       # Theme system
    ├── styles.css      # Player interface styles
    └── dashboard.css   # Dashboard styles
```

### Key Components

#### 1. Application State (`src/state.py`)
Manages in-memory game state:
```python
class AppState:
    active_teams = {}          # Team information and players
    player_to_team = {}        # Session ID to team mapping
    connected_players = set()   # All connected player sessions
    dashboard_clients = set()   # Dashboard client sessions
    game_started = False       # Global game state
    game_paused = False        # Game pause state
    game_mode = 'simplified'   # Current game mode
    game_theme = 'food'        # Current theme
```

#### 2. Game Logic (`src/game_logic.py`)
Core game mechanics:
```python
def start_new_round_for_pair(team_name):
    # 1. Validate team eligibility
    # 2. Select optimal question items
    # 3. Create database round record
    # 4. Send questions to players
    # 5. Update team state
```

#### 3. Socket Event Handlers (`src/sockets/`)
Real-time communication:
- **game.py**: Answer submission and validation
- **team_management.py**: Team creation, joining, leaving
- **dashboard.py**: Statistics calculation and streaming

#### 4. Database Models (`src/models/quiz_models.py`)
SQLAlchemy models:
- **Teams**: Team information and player sessions
- **PairQuestionRounds**: Individual game rounds
- **Answers**: Player responses with timestamps

## Development Workflow

### 1. Running the Development Server
```bash
# Basic development server
gunicorn wsgi:app --worker-class eventlet --bind 0.0.0.0:8080 --reload

# With environment variables
export FLASK_ENV=development
export SECRET_KEY=dev-secret-key
gunicorn wsgi:app --worker-class eventlet --bind 0.0.0.0:8080 --reload
```

### 2. Code Style and Linting
The project follows Python PEP 8 standards:

```bash
# Install linting tools
pip install flake8 black isort

# Format code
black src/ tests/
isort src/ tests/

# Check style
flake8 src/ tests/
```

### 3. Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test categories
pytest tests/unit/
pytest tests/integration/
pytest tests/browser_refresh/

# Run load tests
python chsh_load_test.py --teams 5 --max-duration 30
```

### 4. Database Management
```bash
# Reset database (development)
rm quiz_app.db  # SQLite database will be recreated

# View database content
sqlite3 quiz_app.db
.tables
.schema teams
SELECT * FROM teams;
```

## Making Changes

### Backend Development

#### Adding New Socket Events
1. **Choose appropriate handler file**:
   - Game mechanics → `src/sockets/game.py`
   - Team operations → `src/sockets/team_management.py`  
   - Dashboard features → `src/sockets/dashboard.py`

2. **Create event handler**:
   ```python
   @socketio.on('your_event_name')
   def handle_your_event(data):
       try:
           # Validate input
           # Process request
           # Update state
           # Emit response
           emit('response_event', {'status': 'success'})
       except Exception as e:
           emit('error', {'message': str(e)})
   ```

3. **Add corresponding frontend handling**:
   ```javascript
   socket.on('response_event', (data) => {
       // Handle server response
   });
   
   socket.emit('your_event_name', { /* data */ });
   ```

#### Modifying Game Logic
1. **Update `src/game_logic.py`** for core mechanics
2. **Update `src/state.py`** for state management
3. **Update statistics calculation** in `src/sockets/dashboard.py`
4. **Add corresponding tests** in `tests/unit/`

#### Database Schema Changes
1. **Modify models** in `src/models/quiz_models.py`
2. **Add migration logic** if needed
3. **Update test fixtures** in `tests/conftest.py`
4. **Test with fresh database**:
   ```bash
   rm quiz_app.db
   python -c "from src.config import app, db; app.app_context().push(); db.create_all()"
   ```

### Frontend Development

#### Theme System
1. **Modify `src/static/themes.js`** for new themes
2. **Update theme definitions**:
   ```javascript
   const NEW_THEME = {
       name: 'Theme Name',
       description: 'Theme description',
       items: { A: 'Label A', B: 'Label B', X: 'Label X', Y: 'Label Y' },
       // ... other theme properties
   };
   ```

3. **Add theme to dropdown** in dashboard.html
4. **Test all game modes** with new theme

#### UI Components
1. **Player interface**: Modify `src/static/index.html` and `src/static/app.js`
2. **Dashboard interface**: Modify `src/static/dashboard.html` and `src/static/dashboard.js`
3. **Styling**: Update `src/static/styles.css` or `src/static/dashboard.css`

#### Socket.IO Integration
1. **Use existing patterns** from `src/static/socket-handlers.js`
2. **Handle connection states** properly
3. **Add error handling** for all events
4. **Test reconnection scenarios**

## Testing Guidelines

### Unit Tests
Create tests for individual functions:
```python
# tests/unit/test_game_logic.py
import pytest
from src.game_logic import start_new_round_for_pair
from src.state import state

def test_start_round_for_valid_team():
    # Setup test data
    # Call function
    # Assert expected behavior
    pass
```

### Integration Tests
Test component interactions:
```python
# tests/integration/test_game_flow.py
def test_complete_game_flow(app, client):
    # Test full game scenario
    # Multiple players, teams, rounds
    pass
```

### Frontend Testing
Test UI interactions:
```javascript
// Manual testing checklist
// - Team creation/joining
// - Answer submission
// - Dashboard updates
// - Error handling
// - Reconnection
```

### Load Testing
```bash
# Test with multiple concurrent users
python chsh_load_test.py --teams 50 --max-duration 120

# Monitor performance
# Check for memory leaks
# Verify statistics accuracy
```

## Code Quality Guidelines

### Python Code Standards
1. **Follow PEP 8** styling guidelines
2. **Use type hints** where appropriate:
   ```python
   def calculate_chsh(correlations: Dict[str, float]) -> float:
       return abs(correlations['AX'] + correlations['AY'] + 
                 correlations['BX'] - correlations['BY'])
   ```

3. **Add docstrings** for public functions:
   ```python
   def start_new_round_for_pair(team_name: str) -> None:
       """Start a new game round for a paired team.
       
       Args:
           team_name: Name of the team to start round for
           
       Raises:
           ValueError: If team is not valid or not paired
       """
   ```

4. **Handle errors gracefully**:
   ```python
   try:
       # Risky operation
       pass
   except SpecificException as e:
       logger.error(f"Specific error occurred: {e}")
       # Handle appropriately
   except Exception as e:
       logger.error(f"Unexpected error: {e}")
       # Fail safely
   ```

### JavaScript Code Standards
1. **Use modern ES6+ syntax**
2. **Handle async operations properly**:
   ```javascript
   socket.on('event', (data) => {
       try {
           // Handle event
       } catch (error) {
           console.error('Error handling event:', error);
       }
   });
   ```

3. **Validate data before use**:
   ```javascript
   if (data && data.team_name && typeof data.team_name === 'string') {
       // Safe to use data.team_name
   }
   ```

4. **Use meaningful variable names**
5. **Add comments for complex logic**

### Database Guidelines
1. **Use appropriate indexes** for performance
2. **Validate foreign key constraints**
3. **Handle database errors gracefully**
4. **Use transactions** for multi-step operations

## Performance Considerations

### Backend Optimization
1. **Cache expensive calculations** using LRU cache
2. **Throttle dashboard updates** to prevent spam
3. **Use efficient database queries**
4. **Monitor memory usage** for long-running games

### Frontend Optimization
1. **Minimize DOM manipulation**
2. **Debounce rapid events**
3. **Use efficient event listeners**
4. **Optimize for mobile devices**

### Socket.IO Optimization
1. **Emit only to relevant clients**
2. **Batch multiple updates** when possible
3. **Use rooms for targeted broadcasts**
4. **Handle disconnections gracefully**

## Debugging Tips

### Backend Debugging
1. **Use logging extensively**:
   ```python
   import logging
   logger = logging.getLogger(__name__)
   logger.info(f"Processing team: {team_name}")
   ```

2. **Monitor application state**:
   ```python
   # Add debug endpoints for development
   @app.route('/debug/state')
   def debug_state():
       return jsonify({
           'active_teams': len(state.active_teams),
           'connected_players': len(state.connected_players)
       })
   ```

3. **Use debugger**:
   ```python
   import pdb; pdb.set_trace()  # Add breakpoint
   ```

### Frontend Debugging
1. **Use browser developer tools**
2. **Monitor Socket.IO events**:
   ```javascript
   socket.onAny((event, ...args) => {
       console.log('Socket event:', event, args);
   });
   ```

3. **Add console logging**:
   ```javascript
   console.log('Current game state:', {
       team: currentTeam,
       round: currentRound,
       mode: currentGameMode
   });
   ```

### Network Debugging
1. **Monitor WebSocket connections** in browser dev tools
2. **Check for connection drops**
3. **Test with poor network conditions**
4. **Verify event timing**

## Contributing Guidelines

### Before Making Changes
1. **Check existing issues** on GitHub
2. **Discuss major changes** in issues before implementing
3. **Read the codebase** to understand patterns
4. **Set up development environment** properly

### Making a Pull Request
1. **Create feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make focused commits**:
   ```bash
   git add src/specific_file.py
   git commit -m "Add specific feature functionality"
   ```

3. **Write tests** for new functionality
4. **Update documentation** if needed
5. **Run full test suite**:
   ```bash
   pytest
   python chsh_load_test.py --teams 5 --max-duration 30
   ```

6. **Create pull request** with:
   - Clear description of changes
   - Reference to related issues
   - Screenshots for UI changes
   - Test results

### Code Review Process
1. **Automated tests** must pass
2. **Code quality** checks must pass
3. **Manual testing** by maintainers
4. **Documentation** updates reviewed
5. **Performance impact** considered

## Release Process

### Version Management
1. **Update version** in relevant files
2. **Tag release**:
   ```bash
   git tag -a v1.2.0 -m "Release version 1.2.0"
   git push origin v1.2.0
   ```

3. **Create release notes** with:
   - New features
   - Bug fixes
   - Breaking changes
   - Migration instructions

### Deployment
1. **Test on staging environment**
2. **Run full test suite**
3. **Deploy to production**
4. **Monitor for issues**

## Common Development Tasks

### Adding a New Game Mode
1. **Update `src/state.py`** with new mode
2. **Modify `src/game_logic.py`** for mode-specific logic
3. **Update statistics calculation** in `src/sockets/dashboard.py`
4. **Add frontend support** in `src/static/themes.js`
5. **Update dashboard controls**
6. **Add comprehensive tests**

### Adding a New Theme
1. **Define theme** in `src/static/themes.js`
2. **Add theme selection** in dashboard
3. **Update styling** as needed
4. **Test all game modes** with new theme
5. **Add theme documentation**

### Optimizing Performance
1. **Profile application** under load
2. **Identify bottlenecks** in statistics calculation
3. **Optimize database queries**
4. **Implement additional caching**
5. **Test improvements** with load testing

For questions about development, please check existing GitHub issues or create a new one.
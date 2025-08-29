# CHSH Game Architecture

This document provides a comprehensive overview of the CHSH Game system architecture, including component interactions, data flow, and technical design decisions.

## System Overview

The CHSH Game is a real-time multiplayer web application built with a modern Python backend and vanilla JavaScript frontend. The architecture follows a client-server model with real-time communication via WebSockets.

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Player Client  │    │  Host Dashboard │    │     Backend     │
│   (Frontend)    │◄──►│   (Frontend)    │◄──►│   (Flask App)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
                                               ┌───────▼────────┐
                                               │   Database     │
                                               │ (SQLite/PgSQL) │
                                               └────────────────┘
```

## Architecture Components

### 1. Backend (Python Flask)

#### Core Framework
- **Flask**: Main web framework
- **Flask-SocketIO**: Real-time WebSocket communication
- **Flask-SQLAlchemy**: Database ORM
- **Eventlet**: Asynchronous networking library

#### Directory Structure
```
src/
├── config.py              # Flask app and database configuration
├── main.py                # Application entry point
├── state.py               # In-memory state management
├── game_logic.py          # Core game logic and round management
├── models/                # Database models
│   ├── quiz_models.py     # Game entities (Teams, Answers, Rounds)
│   └── user.py           # User model (optional feature)
├── routes/               # HTTP routes
│   ├── static.py         # Static file serving
│   └── user.py          # User API endpoints
├── sockets/             # Socket.IO event handlers
│   ├── game.py          # Game events (submit_answer)
│   ├── team_management.py # Team creation/joining
│   └── dashboard.py     # Dashboard statistics
└── static/              # Frontend assets
    ├── index.html       # Player interface
    ├── dashboard.html   # Host dashboard
    ├── app.js          # Player client logic
    ├── dashboard.js    # Dashboard logic
    └── styles.css      # Styling
```

### 2. Database Schema

The application uses three main entities:

#### Teams Table
```sql
CREATE TABLE teams (
    team_id INTEGER PRIMARY KEY,
    team_name VARCHAR(100) NOT NULL,
    player1_session_id VARCHAR(100),
    player2_session_id VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team_name, is_active)  -- One active team per name
);
```

#### PairQuestionRounds Table
```sql
CREATE TABLE pair_question_rounds (
    round_id INTEGER PRIMARY KEY,
    team_id INTEGER REFERENCES teams(team_id),
    round_number_for_team INTEGER,
    player1_item ENUM('A','B','X','Y'),
    player2_item ENUM('A','B','X','Y'),
    p1_answered_at DATETIME,
    p2_answered_at DATETIME,
    timestamp_initiated DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team_id, round_number_for_team)
);
```

#### Answers Table
```sql
CREATE TABLE answers (
    answer_id INTEGER PRIMARY KEY,
    team_id INTEGER REFERENCES teams(team_id),
    player_session_id VARCHAR(100),
    question_round_id INTEGER REFERENCES pair_question_rounds(round_id),
    assigned_item ENUM('A','B','X','Y'),
    response_value BOOLEAN,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 3. State Management

#### In-Memory State (`src/state.py`)
The application maintains critical game state in memory for performance:

```python
class AppState:
    active_teams = {}          # Team info and players
    player_to_team = {}        # Session ID to team mapping
    connected_players = set()   # All connected player sessions
    dashboard_clients = set()   # Dashboard client sessions
    game_started = False       # Global game state
    game_paused = False        # Game pause state
    game_mode = 'simplified'   # Game mode: classic/simplified/aqmjoe
    game_theme = 'food'        # Theme: classic/food/aqmjoe
```

#### Team State Structure
```python
team_info = {
    'players': [sid1, sid2],           # Session IDs
    'team_id': db_team_id,             # Database team ID
    'current_round_number': 0,         # Round counter
    'combo_tracker': {},               # Question combination tracking
    'current_db_round_id': None,       # Current round in database
    'answered_current_round': {},      # Round completion tracking
    'player_slots': {sid: slot},       # SID to DB slot mapping
    'status': 'active'                 # Team status
}
```

### 4. Real-Time Communication

#### Socket.IO Events

**Player Events:**
- `connect` - Player joins game
- `create_team` - Create new team
- `join_team` - Join existing team
- `submit_answer` - Submit answer for current round
- `disconnect` - Player leaves game

**Dashboard Events:**
- `join_dashboard` - Dashboard client connects
- `start_game` - Start/resume game
- `pause_game` - Pause game
- `reset_game_stats` - Reset all statistics
- `set_game_mode` - Change game mode
- `toggle_teams_streaming` - Toggle real-time team updates

**Server Events:**
- `teams_update` - Team list updates
- `game_state_update` - Game state changes
- `question` - New question for player
- `answer_received` - Answer confirmation
- `dashboard_update` - Statistics updates

### 5. Game Logic

#### Game Modes
1. **Classic Mode**: Both players answer A/B/X/Y questions
2. **Simplified Mode**: Player 1 answers A/B, Player 2 answers X/Y
3. **AQM Joe Mode**: Theme-based questions (food/color)

#### Round Management
```python
def start_new_round_for_pair(team_name):
    # 1. Check team eligibility
    # 2. Select optimal question items based on combo tracking
    # 3. Create database round record
    # 4. Send questions to players
    # 5. Update team state
```

#### Question Selection Algorithm
- Tracks item combinations (A,A), (A,B), etc.
- Targets balanced distribution across all combinations
- Considers game mode constraints
- Uses randomization with weighted selection

### 6. Statistics Calculation

#### CHSH Value Calculation
The system calculates quantum correlation statistics:

```python
# Correlation matrix elements
E_AX = correlation(A_responses, X_responses)
E_AY = correlation(A_responses, Y_responses)  
E_BX = correlation(B_responses, X_responses)
E_BY = correlation(B_responses, Y_responses)

# CHSH inequality value
CHSH = |E_AX + E_AY + E_BX - E_BY|
```

#### Other Metrics
- **Trace**: Diagonal correlation average
- **Balance**: Response distribution evenness
- **Balanced |⟨Tr⟩|**: Combined consistency metric

### 7. Frontend Architecture

#### Player Interface (`index.html`, `app.js`)
- Team creation and joining
- Question display and answer submission
- Real-time status updates
- Mobile-responsive design

#### Dashboard Interface (`dashboard.html`, `dashboard.js`)
- Game control (start/pause/reset)
- Live team statistics
- Real-time answer streaming
- Data export functionality
- Performance metrics

#### Socket.IO Integration
```javascript
// Shared socket handlers
socket.on('teams_update', updateTeamsList);
socket.on('game_state_update', updateGameState);
socket.on('question', displayQuestion);
```

## Performance Considerations

### 1. Caching Strategy
- LRU cache for expensive statistical calculations
- Throttled dashboard updates (0.5s for team updates, 1.0s for full updates)
- Cached team statistics with staleness tracking

### 2. Database Optimization
- Strategic indexing on frequently queried columns
- Optimized queries with proper joins
- Connection pooling via SQLAlchemy

### 3. Real-Time Optimization
- Selective event emission to relevant clients
- Batched dashboard updates
- Connection state management with heartbeats

## Security Features

### 1. Session Management
- Unique session IDs for each connection
- Team membership validation
- Session cleanup on disconnect

### 2. Input Validation
- Data type validation for all inputs
- Game state validation before actions
- SQL injection prevention via ORM

### 3. Rate Limiting
- Answer submission throttling
- Dashboard update rate limiting
- Connection state validation

## Deployment Architecture

### 1. WSGI Configuration
```python
# wsgi.py
from src.main import app, socketio
if __name__ == "__main__":
    socketio.run(app)
```

### 2. Gunicorn with Eventlet
```bash
gunicorn wsgi:app --worker-class eventlet --bind 0.0.0.0:8080
```

### 3. Environment Configuration
- Database URL configuration
- Secret key management
- Platform-specific optimizations (Fly.io, Render.com)

## Scalability Limitations

### Current Constraints
- Single-process architecture (no horizontal scaling)
- In-memory state (no persistence across restarts)
- Single database connection

### Future Improvements
- Redis for shared state management
- Multi-worker support with sticky sessions
- Database connection pooling
- CDN for static assets

## Testing Architecture

The application includes comprehensive testing:
- **Unit Tests**: Individual component testing
- **Integration Tests**: Multi-component interactions
- **Load Testing**: Performance and scalability testing
- **Browser Tests**: Frontend functionality testing

See [Testing Guide](testing.md) for detailed information.
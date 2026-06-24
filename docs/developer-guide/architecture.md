# Architecture Overview

This document provides a comprehensive overview of the CHSH Game's system architecture, component relationships, and design decisions.

## System Architecture

### High-Level Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Player        │    │   Dashboard     │    │   Load Testing  │
│   Clients       │    │   (Host)        │    │   Tools         │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              WebSocket (Socket.IO)           │
         └─────────────────┬─────────────────────────────┘
                           │
         ┌─────────────────────────────────────────────────────┐
         │                Flask Application                      │
         │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
         │  │   Routes    │  │   Sockets   │  │   Game      │ │
         │  │   Layer     │  │   Layer     │  │   Logic     │ │
         │  └─────────────┘  └─────────────┘  └─────────────┘ │
         └─────────────────────────────────────────────────────┘
                           │
         ┌─────────────────────────────────────────────────────┐
         │              Data Layer                             │
         │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
         │  │ SQLAlchemy  │  │ In-Memory   │  │  Database   │ │
         │  │    ORM      │  │   State     │  │  (SQLite/   │ │
         │  │             │  │             │  │ PostgreSQL) │ │
         │  └─────────────┘  └─────────────┘  └─────────────┘ │
         └─────────────────────────────────────────────────────┘
```

## Core Components

### 1. Flask Application (`src/config.py`)

**Purpose**: Central application configuration and initialization

**Key Features**:
- Flask web framework setup
- Database configuration (SQLite/PostgreSQL)
- Socket.IO integration with eventlet
- CORS configuration for cross-origin requests
- Environment-based configuration

**Configuration**:
```python
# Database auto-detection
DATABASE_URL = sqlite:///quiz_app.db (default)
             postgresql://... (production)

# Socket.IO settings
cors_allowed_origins = "*"
async_mode = 'eventlet'
ping_timeout = 30 seconds
ping_interval = 5 seconds
```

### 2. Data Models (`src/models/`)

#### Teams Model
```python
class Teams(db.Model):
    team_id: Primary key
    team_name: Unique team identifier
    player1_session_id: WebSocket session ID
    player2_session_id: WebSocket session ID  
    is_active: Boolean flag for team status
    created_at: Timestamp
```

#### Answers Model
```python
class Answers(db.Model):
    answer_id: Primary key
    team_id: Foreign key to Teams
    player_session_id: WebSocket session ID
    question_round_id: Foreign key to PairQuestionRounds
    assigned_item: Enum (A, B, X, Y)
    response_value: Boolean (True/False)
    timestamp: Answer submission time
```

#### PairQuestionRounds Model
```python
class PairQuestionRounds(db.Model):
    round_id: Primary key
    team_id: Foreign key to Teams
    round_number_for_team: Sequential round counter
    player1_item: Enum (A, B, X, Y)
    player2_item: Enum (A, B, X, Y)
    created_at: Round creation time
```

### 3. State Management (`src/state.py`)

**Purpose**: In-memory state for real-time game operations

**State Components**:
```python
class AppState:
    active_teams: Dict[team_id, team_info]
    player_to_team: Dict[session_id, team_id]
    connected_players: Set[session_id]
    game_running: Boolean
```

**Key Functions**:
- Real-time team membership tracking
- Player connection state
- Game status management
- Session cleanup on disconnect

### 4. Game Logic (`src/game_logic.py`)

**Purpose**: Core game mechanics and question generation

**Key Features**:
- **Question Distribution**: Ensures balanced coverage of all 16 possible item combinations (AA, AB, AX, AY, BA, BB, BX, BY, XA, XB, XX, XY, YA, YB, YX, YY)
- **Round Management**: Tracks progress for each team independently
- **Strategy**: Targets `TARGET_COMBO_REPEATS` for each combination with randomization

**Algorithm**:
1. Calculate current combination counts for team
2. Identify under-represented combinations
3. Select combination with lowest count (with random tie-breaking)
4. Assign items to players and create round record

### 5. Socket.IO Event Handlers (`src/sockets/`)

#### Team Management (`team_management.py`)
```python
Events:
- connect: Player connection handling
- disconnect: Cleanup and team updates
- create_team: New team creation
- join_team: Join existing team
- leave_team: Player departure
```

#### Game Events (`game.py`)
```python
Events:
- submit_answer: Process player responses
- round_complete: Handle completion of team rounds
```

#### Dashboard Events (`dashboard.py`)
```python
Events:
- start_game: Initialize game for all teams
- pause_game: Pause/resume game state
- reset_game_stats: Clear current game data
- get_dashboard_data: Fetch real-time statistics

HTTP Endpoints:
- /api/dashboard/data: JSON dashboard data
- /download: CSV export of game data
```

### 6. Frontend Architecture

#### Player Client (`index.html` + `app.js`)
**Features**:
- Team creation/joining interface
- Real-time question display
- Answer submission with visual feedback
- Connection status monitoring
- Session management

**Key JavaScript Components**:
```javascript
// Socket.IO connection management
socket = io();

// Event handlers
socket.on('new_question', handleQuestion);
socket.on('round_complete', handleRoundComplete);
socket.on('game_started', handleGameStart);

// UI state management
updateTeamsList();
updateConnectionStatus();
```

#### Dashboard (`dashboard.html` + `dashboard.js`)
**Features**:
- Game control interface (start/pause/reset)
- Real-time team monitoring
- Live statistics display
- Answer stream logging
- CSV data export

**Statistics Engine**:
- Correlation matrix calculation
- CHSH value computation
- Uncertainty analysis
- Performance metrics

## Data Flow

### 1. Team Formation Flow
```
Player → create_team/join_team → State Update → Database → 
Dashboard Update → All Clients Notified
```

### 2. Game Round Flow
```
Dashboard → start_game → All Teams → game_logic.py → 
new_question → Players → submit_answer → Database → 
Statistics Update → Dashboard → Next Round
```

### 3. Statistics Calculation Flow
```
Answers Database → Correlation Matrix → CHSH Calculation → 
Uncertainty Analysis → Dashboard Display → Live Updates
```

## Real-Time Communication

### WebSocket Events

#### Client → Server
- `create_team(team_name)`
- `join_team(team_id)`
- `leave_team()`
- `submit_answer(round_id, answer)`

#### Server → Client
- `team_created(team_data)`
- `team_joined(team_data)`
- `new_question(round_id, item)`
- `round_complete()`
- `game_started()`
- `game_paused()`

#### Server → Dashboard
- `teams_update(teams_data)`
- `stats_update(statistics)`
- `new_answer(answer_data)`

## Database Design

### Indexing Strategy
```sql
-- Performance indexes
idx_teams_active_created (is_active, created_at)
idx_answers_team_timestamp (team_id, timestamp)
idx_answers_round_team (question_round_id, team_id)
idx_answers_team_item (team_id, assigned_item)
```

### Constraints
```sql
-- Business logic constraints
_team_name_active_uc: UNIQUE(team_name, is_active)
-- Prevents duplicate active team names
```

## Performance Considerations

### Memory Management
- **LRU Caches**: Team statistics caching with size limits
- **State Cleanup**: Automatic cleanup of disconnected players
- **Connection Limits**: Configurable maximum player capacity

### Database Optimization
- **Prepared Statements**: SQLAlchemy ORM with query optimization
- **Batch Operations**: Efficient bulk operations for statistics
- **Connection Pooling**: Database connection management

### Real-Time Performance
- **Event Batching**: Grouped updates for dashboard efficiency
- **Selective Updates**: Only relevant clients receive updates
- **Connection Management**: Heartbeat and reconnection handling

## Security Architecture

### Input Validation
- **Team Names**: Length and character restrictions
- **SQL Injection**: SQLAlchemy ORM protection
- **XSS Prevention**: Input sanitization

### Session Management
- **WebSocket Sessions**: Secure session ID generation
- **State Validation**: Server-side state verification
- **CSRF Protection**: Flask built-in CSRF handling

### Network Security
- **CORS Configuration**: Controlled cross-origin access
- **WebSocket Security**: Origin validation
- **HTTPS Support**: TLS encryption in production

## Deployment Architecture

### Development
```
SQLite Database + Flask Dev Server + Local File Serving
```

### Production
```
PostgreSQL + Gunicorn + Nginx/CDN + Load Balancer
```

### Scaling Considerations
- **Horizontal Scaling**: Multiple application instances
- **Database Scaling**: PostgreSQL with read replicas
- **Session Store**: Redis for shared session state
- **CDN**: Static asset delivery optimization

## Extension Points

### Adding New Game Modes
1. Extend `ItemEnum` for new question types
2. Update `game_logic.py` distribution algorithm
3. Modify frontend question display
4. Update statistics calculations

### Custom Statistics
1. Add new calculation functions in `dashboard.py`
2. Update database models if persistent storage needed
3. Extend dashboard UI for new metrics
4. Add CSV export support

### Authentication System
1. Extend `User` model for authentication
2. Add session management middleware
3. Update Socket.IO connection handling
4. Implement role-based access control

---

This architecture provides a solid foundation for the CHSH Game while maintaining flexibility for future enhancements and scaling requirements.
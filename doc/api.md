# API Documentation

This document describes the Socket.IO events and HTTP endpoints for the CHSH Game application.

## Overview

The CHSH Game uses Socket.IO for real-time communication between clients and the server. The API is organized into three main categories:
- **Player Events**: For game participants
- **Dashboard Events**: For host/presenter control
- **System Events**: For connection management

## Connection Setup

### Socket.IO Configuration
```javascript
const socket = io(window.location.origin, {
    pingTimeout: 30000,  // 30 seconds
    pingInterval: 5000   // 5 seconds
});
```

### Client Types
- **Player Client**: Individual game participants
- **Dashboard Client**: Host/presenter interface

## Player Events

### Client to Server Events

#### `connect`
**Description**: Automatically fired when a player connects to the server
**Parameters**: None
**Response**: `teams_update` event with current team list

#### `create_team`
**Description**: Creates a new team
**Parameters**:
```javascript
{
    "team_name": "string" // Team name (required)
}
```
**Responses**:
- Success: `team_created` event
- Error: `error` event with message

**Example**:
```javascript
socket.emit('create_team', { team_name: 'Team Alpha' });
```

#### `join_team`
**Description**: Joins an existing active team
**Parameters**:
```javascript
{
    "team_name": "string" // Team name to join (required)
}
```
**Responses**:
- Success: `team_joined` event
- Error: `error` event with message

#### `reactivate_team`
**Description**: Reactivates an inactive team
**Parameters**:
```javascript
{
    "team_name": "string" // Inactive team name (required)
}
```
**Responses**:
- Success: `team_reactivated` event
- Error: `error` event with message

#### `get_reconnectable_teams`
**Description**: Gets list of teams available for reconnection
**Parameters**: None
**Response**: `reconnectable_teams` event with team list

#### `leave_team`
**Description**: Leaves current team
**Parameters**: None
**Responses**:
- Success: `team_left` event
- Dashboard update: `dashboard_update` event

#### `submit_answer`
**Description**: Submits answer for current round
**Parameters**:
```javascript
{
    "round_id": "integer",    // Current round ID (required)
    "item": "string",         // Question item (A/B/X/Y) (required)
    "answer": "boolean"       // True/False response (required)
}
```
**Responses**:
- Success: `answer_received` event
- Error: `error` event with message

**Example**:
```javascript
socket.emit('submit_answer', {
    round_id: 123,
    item: 'A',
    answer: true
});
```

#### `disconnect`
**Description**: Automatically fired when player disconnects
**Parameters**: None
**Side Effects**: Updates team status, triggers dashboard updates

### Server to Client Events

#### `teams_update`
**Description**: Updates the list of available teams
**Data Structure**:
```javascript
{
    "active_teams": [
        {
            "team_name": "string",
            "player_count": "integer",
            "status": "string" // "waiting" or "active"
        }
    ],
    "inactive_teams": [
        {
            "team_name": "string",
            "created_at": "string" // ISO datetime
        }
    ]
}
```

#### `team_created`
**Description**: Confirmation of successful team creation
**Data Structure**:
```javascript
{
    "team_name": "string",
    "session_id": "string",
    "team_id": "integer",
    "is_creator": "boolean"
}
```

#### `team_joined`
**Description**: Confirmation of successful team join
**Data Structure**:
```javascript
{
    "team_name": "string",
    "session_id": "string",
    "team_id": "integer",
    "player_position": "integer" // 1 or 2
}
```

#### `team_left`
**Description**: Confirmation of leaving team
**Data Structure**:
```javascript
{
    "message": "string"
}
```

#### `question`
**Description**: New question for the player
**Data Structure**:
```javascript
{
    "round_id": "integer",
    "item": "string",        // A, B, X, or Y
    "round_number": "integer"
}
```

#### `answer_received`
**Description**: Confirmation of answer submission
**Data Structure**:
```javascript
{
    "message": "string",
    "waiting_for_partner": "boolean"
}
```

#### `game_state_update`
**Description**: Updates about game state changes
**Data Structure**:
```javascript
{
    "game_started": "boolean",
    "game_paused": "boolean",
    "game_mode": "string",    // "classic", "simplified", "aqmjoe"
    "game_theme": "string"    // "classic", "food", "aqmjoe"
}
```

#### `error`
**Description**: Error messages
**Data Structure**:
```javascript
{
    "message": "string"
}
```

## Dashboard Events

### Client to Server Events

#### `dashboard_join`
**Description**: Registers client as dashboard
**Parameters**: None
**Response**: `dashboard_update` with full game state

#### `start_game`
**Description**: Starts or resumes the game
**Parameters**: None
**Side Effects**: 
- Sets `game_started = true`
- Emits `game_state_update` to all clients
- Starts new rounds for all active teams

#### `pause_game`
**Description**: Pauses the game
**Parameters**: None
**Side Effects**:
- Sets `game_paused = true`
- Emits `game_state_update` to all clients

#### `restart_game`
**Description**: Resets all game statistics and data
**Parameters**: None
**Side Effects**:
- Clears all database records
- Resets team states
- Emits full dashboard update

#### `toggle_game_mode`
**Description**: Cycles through game modes
**Parameters**: None
**Side Effects**: Changes mode between classic/simplified/aqmjoe

#### `change_game_theme`
**Description**: Changes game theme
**Parameters**:
```javascript
{
    "theme": "string" // "classic", "food", "aqmjoe"
}
```

#### `set_theme_and_mode`
**Description**: Sets both theme and mode atomically
**Parameters**:
```javascript
{
    "theme": "string",  // "classic", "food", "aqmjoe"
    "mode": "string"    // "classic", "simplified", "aqmjoe"
}
```

#### `set_teams_streaming`
**Description**: Enables/disables real-time team updates
**Parameters**:
```javascript
{
    "enabled": "boolean"
}
```

#### `request_teams_update`
**Description**: Requests immediate teams data update
**Parameters**: None
**Response**: `teams_data_update` event

#### `keep_alive`
**Description**: Maintains dashboard connection
**Parameters**: None
**Purpose**: Prevents timeout disconnection

### Server to Client Events

#### `dashboard_update`
**Description**: Complete dashboard state update
**Data Structure**:
```javascript
{
    "active_teams_count": "integer",
    "connected_players_count": "integer", 
    "ready_players_count": "integer",
    "total_responses_count": "integer",
    "game_started": "boolean",
    "game_paused": "boolean",
    "game_mode": "string",
    "game_theme": "string"
}
```

#### `teams_data_update`
**Description**: Detailed team statistics
**Data Structure**:
```javascript
{
    "teams": [
        {
            "team_name": "string",
            "team_id": "integer",
            "status": "string",
            "round_number": "integer",
            "min_stats_sig": "boolean",
            "statistics": {
                "trace_avg": "number",
                "balance": "number", 
                "balanced_trace": "number",
                "chsh_value": "number",
                "success_rate": "number",
                "response_balance": "number",
                "balanced_success": "number",
                "normalized_score": "number"
            }
        }
    ]
}
```

#### `answer_log_update`
**Description**: Real-time answer stream
**Data Structure**:
```javascript
{
    "timestamp": "string",    // ISO datetime
    "team_name": "string",
    "player_sid": "string",
    "round_number": "integer",
    "item": "string",         // A, B, X, Y
    "response": "boolean"
}
```

## HTTP Endpoints

### Static File Routes

#### `GET /`
**Description**: Serves player interface
**Response**: HTML page (index.html)

#### `GET /dashboard`
**Description**: Serves dashboard interface  
**Response**: HTML page (dashboard.html)

#### `GET /static/<path:filename>`
**Description**: Serves static assets
**Parameters**: 
- `filename`: Path to static file
**Response**: Static file (CSS, JS, images)

### Data Export Routes

#### `GET /export/answers`
**Description**: Downloads all game data as CSV
**Response**: CSV file with answer data
**Headers**: 
- `Content-Type: text/csv`
- `Content-Disposition: attachment; filename=chsh_game_answers.csv`

**CSV Format**:
```
timestamp,team_name,player_session_id,round_number,item,response
2024-01-01T12:00:00,Team Alpha,abc123,1,A,true
```

### User Management Routes (Optional)

#### `GET /api/users`
**Description**: Lists all users (if user management enabled)
**Response**: JSON array of user objects

#### `POST /api/users`
**Description**: Creates new user
**Request Body**: User data (JSON)
**Response**: Created user object

## Error Handling

### Error Event Structure
```javascript
{
    "message": "string",      // Human-readable error message
    "code": "string",         // Optional error code
    "details": "object"       // Optional additional details
}
```

### Common Error Scenarios

#### Connection Errors
- **Timeout**: Client didn't respond within ping timeout
- **Disconnect**: Network connection lost
- **Reconnection**: Automatic reconnection attempts

#### Validation Errors
- **Invalid team name**: Empty or duplicate team names
- **Invalid answer**: Missing or malformed answer data
- **Game state**: Actions not allowed in current game state

#### Business Logic Errors
- **Team full**: Attempting to join team with 2 players
- **Team not found**: Referencing non-existent team
- **Round mismatch**: Submitting answer for wrong round

## Rate Limiting

### Dashboard Updates
- **Team updates**: Maximum once per 0.5 seconds
- **Full updates**: Maximum once per 1.0 seconds
- **Answer streaming**: Real-time (no throttling)

### Player Actions
- **Answer submission**: Once per round per player
- **Team operations**: No specific limits (validated by game state)

## Data Validation

### Input Validation
All incoming data is validated for:
- **Type checking**: Ensures correct data types
- **Range checking**: Validates numeric ranges
- **String validation**: Checks string lengths and characters
- **Game state validation**: Ensures actions are valid in current state

### Output Sanitization
All outgoing data is sanitized to prevent:
- **XSS attacks**: HTML/JavaScript injection
- **Data leakage**: Sensitive information exposure
- **Format errors**: Malformed JSON/data structures

## Authentication & Security

### Session Management
- **Session IDs**: Unique identifier per connection
- **Team membership**: Validated on each action
- **Connection state**: Tracked for reconnection support

### Input Sanitization
- **SQL injection prevention**: Via SQLAlchemy ORM
- **XSS prevention**: Input sanitization and output encoding
- **CSRF protection**: Socket.IO provides built-in protection

## Performance Considerations

### Caching
- **LRU cache**: Expensive calculations cached with 1024 item limit
- **Throttling**: Rate-limited updates to prevent spam
- **Batch operations**: Multiple updates combined where possible

### Database Optimization
- **Indexing**: Strategic indexes on frequently queried columns
- **Connection pooling**: SQLAlchemy manages database connections
- **Query optimization**: Efficient queries with proper joins

## Testing the API

### Socket.IO Testing
```javascript
// Connect to server
const socket = io('http://localhost:8080');

// Test team creation
socket.emit('create_team', { team_name: 'Test Team' });

// Listen for response
socket.on('team_created', (data) => {
    console.log('Team created:', data);
});

// Test error handling
socket.on('error', (error) => {
    console.error('Error:', error.message);
});
```

### Dashboard Testing
```javascript
// Connect as dashboard
socket.emit('dashboard_join');

// Start game
socket.emit('start_game');

// Listen for updates
socket.on('dashboard_update', (data) => {
    console.log('Dashboard update:', data);
});
```

For more examples, see the test files in the `tests/` directory.
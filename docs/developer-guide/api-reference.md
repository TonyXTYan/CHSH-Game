# API Reference

This document provides comprehensive documentation for all Socket.IO events and HTTP endpoints in the CHSH Game application.

## Socket.IO Events

### Player Events

#### `connect`
**Direction**: Client → Server  
**Purpose**: Establish WebSocket connection

**Payload**: None (automatic on connection)

**Response Events**:
- `connected_as_player` - Confirms player connection
- `teams_list` - Current available teams
- `error` - Connection errors

**Example**:
```javascript
// Automatic on socket connection
const socket = io();
```

---

#### `disconnect`
**Direction**: Client → Server  
**Purpose**: Handle player disconnection and cleanup

**Payload**: None (automatic on disconnection)

**Server Actions**:
- Remove player from active teams
- Update team status
- Notify dashboard of changes
- Clean up player state

---

#### `create_team`
**Direction**: Client → Server  
**Purpose**: Create a new team

**Payload**:
```javascript
{
    "team_name": "string"  // Team name (max 100 characters)
}
```

**Response Events**:
- `team_created` - Success with team data
- `error` - Team creation failed

**Success Response**:
```javascript
{
    "message": "Team created successfully",
    "team": {
        "team_id": 123,
        "team_name": "My Team",
        "players": ["session_id_1"],
        "status": "waiting_for_pair"
    }
}
```

**Error Responses**:
- Team name already exists
- Invalid team name
- Maximum teams reached

---

#### `join_team`
**Direction**: Client → Server  
**Purpose**: Join an existing team

**Payload**:
```javascript
{
    "team_id": 123  // Team ID to join
}
```

**Response Events**:
- `team_joined` - Success with team data
- `error` - Join failed

**Success Response**:
```javascript
{
    "message": "Joined team successfully",
    "team": {
        "team_id": 123,
        "team_name": "My Team",
        "players": ["session_id_1", "session_id_2"],
        "status": "active"
    }
}
```

---

#### `leave_team`
**Direction**: Client → Server  
**Purpose**: Leave current team

**Payload**: None

**Response Events**:
- `team_left` - Confirmation of leaving
- `error` - Leave operation failed

---

#### `reactivate_team`
**Direction**: Client → Server  
**Purpose**: Reactivate an inactive team

**Payload**:
```javascript
{
    "team_id": 123  // Inactive team ID
}
```

**Response Events**:
- `team_reactivated` - Success
- `error` - Reactivation failed

---

#### `get_reconnectable_teams`
**Direction**: Client → Server  
**Purpose**: Get list of teams available for reconnection

**Payload**: None

**Response Events**:
- `reconnectable_teams` - List of available teams

**Response**:
```javascript
{
    "teams": [
        {
            "team_id": 123,
            "team_name": "My Team",
            "can_reconnect": true
        }
    ]
}
```

---

#### `submit_answer`
**Direction**: Client → Server  
**Purpose**: Submit answer for current question

**Payload**:
```javascript
{
    "round_id": 456,      // Current round ID
    "answer": true        // Boolean answer (true/false)
}
```

**Response Events**:
- `answer_submitted` - Confirmation
- `round_complete` - Both players answered
- `new_question` - Next question (if applicable)
- `error` - Submission failed

**Success Response**:
```javascript
{
    "message": "Answer submitted successfully",
    "round_id": 456,
    "waiting_for_partner": false
}
```

### Dashboard Events

#### `dashboard_join`
**Direction**: Dashboard → Server  
**Purpose**: Register as dashboard client

**Payload**: None

**Response Events**:
- `dashboard_connected` - Connection confirmed
- `teams_update` - Current teams data
- `stats_update` - Current statistics

---

#### `start_game`
**Direction**: Dashboard → Server  
**Purpose**: Start the game for all paired teams

**Payload**: None

**Response Events**:
- `game_started` - Confirmation to all clients
- `new_question` - First questions to players

**Broadcast Events**:
- All players receive `game_started`
- Paired teams receive first `new_question`

---

#### `pause_game`
**Direction**: Dashboard → Server  
**Purpose**: Pause or resume the game

**Payload**: None

**Response Events**:
- `game_paused` or `game_resumed` - Status change
- Broadcast to all clients

---

#### `restart_game`
**Direction**: Dashboard → Server  
**Purpose**: Reset game statistics and restart

**Payload**: None

**Server Actions**:
- Clear answer database
- Reset team round counters
- Clear statistics cache
- Restart game flow

---

#### `request_teams_update`
**Direction**: Dashboard → Server  
**Purpose**: Request current teams status

**Payload**: None

**Response Events**:
- `teams_update` - Current teams data

---

#### `set_teams_streaming`
**Direction**: Dashboard → Server  
**Purpose**: Enable/disable real-time team updates

**Payload**:
```javascript
{
    "streaming": true  // Boolean flag
}
```

---

#### `toggle_game_mode`
**Direction**: Dashboard → Server  
**Purpose**: Switch between different game modes

**Payload**:
```javascript
{
    "mode": "chsh"  // Game mode ("chsh", "balanced", etc.)
}
```

---

#### `change_game_theme`
**Direction**: Dashboard → Server  
**Purpose**: Change dashboard visual theme

**Payload**:
```javascript
{
    "theme": "dark"  // Theme name
}
```

---

#### `keep_alive`
**Direction**: Dashboard → Server  
**Purpose**: Maintain dashboard connection

**Payload**: None

## Server → Client Events

### Player Events

#### `connected_as_player`
**Purpose**: Confirm player connection

**Payload**:
```javascript
{
    "session_id": "abc123",
    "message": "Connected as player"
}
```

---

#### `teams_list`
**Purpose**: Provide available teams

**Payload**:
```javascript
{
    "teams": [
        {
            "team_id": 123,
            "team_name": "Team Alpha",
            "player_count": 1,
            "status": "waiting_for_pair"
        }
    ]
}
```

---

#### `new_question`
**Purpose**: Send question to player

**Payload**:
```javascript
{
    "round_id": 456,
    "item": "A",           // Question type (A, B, X, Y)
    "round_number": 5
}
```

---

#### `round_complete`
**Purpose**: Notify that round is finished

**Payload**:
```javascript
{
    "round_id": 456,
    "team_id": 123
}
```

---

#### `game_started`
**Purpose**: Notify game has started

**Payload**:
```javascript
{
    "message": "Game started"
}
```

---

#### `game_paused` / `game_resumed`
**Purpose**: Notify game state change

**Payload**:
```javascript
{
    "message": "Game paused",
    "paused": true
}
```

### Dashboard Events

#### `teams_update`
**Purpose**: Update dashboard with team information

**Payload**:
```javascript
{
    "teams": [
        {
            "team_id": 123,
            "team_name": "Team Alpha",
            "players": ["sid1", "sid2"],
            "status": "active",
            "round_number": 5,
            "created_at": "2023-01-01T12:00:00"
        }
    ],
    "stats": {
        "active_teams": 5,
        "total_players": 10,
        "paired_players": 8
    }
}
```

---

#### `stats_update`
**Purpose**: Update dashboard statistics

**Payload**:
```javascript
{
    "team_stats": {
        "123": {
            "team_name": "Team Alpha",
            "chsh_value": "2.456 ± 0.123",
            "trace_avg": "0.789 ± 0.045",
            "balance": "0.856 ± 0.067",
            "balanced_trace": "0.823 ± 0.041"
        }
    },
    "global_stats": {
        "total_answers": 1250,
        "avg_chsh": "2.234 ± 0.089"
    }
}
```

---

#### `new_answer`
**Purpose**: Stream live answers to dashboard

**Payload**:
```javascript
{
    "answer_id": 789,
    "team_id": 123,
    "team_name": "Team Alpha",
    "player_session_id": "abc123",
    "question_round_id": 456,
    "assigned_item": "A",
    "response_value": true,
    "timestamp": "2023-01-01T12:00:00"
}
```

## HTTP Endpoints

### GET `/api/dashboard/data`
**Purpose**: Retrieve dashboard data as JSON

**Response**:
```json
{
    "answers": [
        {
            "answer_id": 789,
            "team_id": 123,
            "team_name": "Team Alpha",
            "player_session_id": "abc123",
            "question_round_id": 456,
            "assigned_item": "A",
            "response_value": true,
            "timestamp": "2023-01-01T12:00:00.000Z"
        }
    ]
}
```

**Error Response**:
```json
{
    "error": "An error occurred while retrieving dashboard data"
}
```

---

### GET `/download`
**Purpose**: Download game data as CSV

**Response**: CSV file with headers:
```csv
Timestamp,Team Name,Team ID,Player ID,Round ID,Question Item (A/B/X/Y),Answer (True/False)
01/01/2023, 12:00:00 PM,Team Alpha,123,abc123,456,A,True
```

**Content Headers**:
- `Content-Type: text/csv`
- `Content-Disposition: attachment; filename=chsh-game-data.csv`

---

### GET `/api/server/id`
**Purpose**: Get unique server instance ID

**Response**:
```json
{
    "instance_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

### GET `/` (Static Routes)
**Purpose**: Serve static frontend files

**Routes**:
- `/` → `index.html` (player interface)
- `/dashboard` → `dashboard.html` (dashboard interface)
- `/about` → `about.html` (about page)
- Static assets served from `/static/`

## Error Handling

### Socket.IO Errors

All Socket.IO events can emit error responses:

```javascript
{
    "error": "Error message description"
}
```

**Common Error Types**:
- `"Team name already exists"`
- `"Team is full"`
- `"You are not in a team"`
- `"Game is currently paused"`
- `"Invalid team ID"`
- `"Session expired"`

### HTTP Errors

**500 Internal Server Error**:
```json
{
    "error": "An error occurred while processing request"
}
```

**404 Not Found**: File/route not found

**403 Forbidden**: Path traversal attempt blocked

## Rate Limiting

Currently no rate limiting is implemented. Consider implementing rate limiting for:
- Team creation: Max 5 teams per IP per minute
- Answer submission: Max 100 answers per session per minute
- Dashboard requests: Max 60 requests per minute

## Authentication

Currently no authentication is required. All endpoints and events are publicly accessible.

Future authentication considerations:
- JWT tokens for dashboard access
- Session-based authentication for players
- Role-based access control (player vs instructor)

## WebSocket Connection

**Connection URL**: `ws://localhost:8080/socket.io/`

**Configuration**:
```javascript
const socket = io({
    timeout: 30000,
    forceNew: false,
    reconnection: true,
    reconnectionDelay: 1000,
    reconnectionAttempts: 5
});
```

**Connection Events**:
- `connect` - Successfully connected
- `disconnect` - Connection lost
- `connect_error` - Connection failed
- `reconnect` - Reconnected after disconnect

---

This API documentation covers all current endpoints and events. For implementation details, see the [Architecture Overview](./architecture.md).
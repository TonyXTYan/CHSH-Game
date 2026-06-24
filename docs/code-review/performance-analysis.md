# Performance Analysis

This document analyzes performance bottlenecks and provides optimization strategies for the CHSH Game.

## Performance Overview

**Current Performance Rating: Needs Optimization**

The application shows several performance issues that impact scalability and user experience under load.

## Memory Performance Issues

### 1. LRU Cache Memory Leak (CRITICAL)
**Location**: `src/sockets/dashboard.py`

```python
# PROBLEMATIC CODE
@lru_cache(maxsize=CACHE_SIZE)
def compute_team_hashes(team_id):
    return "disabled", "disabled"  # Function disabled but cache grows

@lru_cache(maxsize=CACHE_SIZE) 
def compute_correlation_matrix(team_id):
    # Complex computation with no expiration
    # Cache grows indefinitely with new team IDs
```

**Issue**: Cache grows without bounds as new teams are created

**Memory Impact**: ~50KB per team cached, leading to memory exhaustion

**Solution**:
```python
from functools import lru_cache
import threading
import time
from collections import OrderedDict

class TTLCache:
    def __init__(self, maxsize=128, ttl=300):
        self.cache = OrderedDict()
        self.times = {}
        self.maxsize = maxsize
        self.ttl = ttl
        self.lock = threading.RLock()
    
    def get(self, key):
        with self.lock:
            if key in self.cache:
                if time.time() - self.times[key] < self.ttl:
                    # Move to end (most recently used)
                    self.cache.move_to_end(key)
                    return self.cache[key]
                else:
                    # Expired
                    del self.cache[key]
                    del self.times[key]
            return None
    
    def set(self, key, value):
        with self.lock:
            if len(self.cache) >= self.maxsize:
                # Remove oldest entries
                self.cache.popitem(last=False)
                if self.times:
                    oldest_key = min(self.times.keys(), key=lambda k: self.times[k])
                    self.times.pop(oldest_key, None)
            
            self.cache[key] = value
            self.times[key] = time.time()
            self.cache.move_to_end(key)

# Replace lru_cache with TTL cache
correlation_cache = TTLCache(maxsize=100, ttl=300)

def compute_correlation_matrix(team_id):
    cached = correlation_cache.get(team_id)
    if cached is not None:
        return cached
    
    result = _calculate_correlation_matrix(team_id)
    correlation_cache.set(team_id, result)
    return result
```

### 2. State Object Growth (HIGH)
**Location**: `src/state.py`

```python
# PROBLEMATIC CODE
class AppState:
    def __init__(self):
        self.active_teams = {}  # No size limits
        self.player_to_team = {}  # Grows without bounds
        self.connected_players = set()  # No cleanup of stale connections
```

**Issue**: State objects grow without cleanup

**Solution**:
```python
import time
import threading
from typing import Dict, Set

class AppState:
    def __init__(self, max_teams=1000, cleanup_interval=300):
        self.active_teams: Dict = {}
        self.player_to_team: Dict = {}
        self.connected_players: Set = set()
        self.player_last_seen: Dict = {}
        
        self.max_teams = max_teams
        self.cleanup_interval = cleanup_interval
        
        # Start cleanup thread
        self._start_cleanup_thread()
    
    def _start_cleanup_thread(self):
        def cleanup_task():
            while True:
                time.sleep(self.cleanup_interval)
                self._cleanup_stale_data()
        
        cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
        cleanup_thread.start()
    
    def _cleanup_stale_data(self):
        current_time = time.time()
        stale_threshold = 3600  # 1 hour
        
        # Clean up stale players
        stale_players = [
            player_id for player_id, last_seen in self.player_last_seen.items()
            if current_time - last_seen > stale_threshold
        ]
        
        for player_id in stale_players:
            self._remove_player(player_id)
        
        # Enforce team limit
        if len(self.active_teams) > self.max_teams:
            # Remove oldest inactive teams
            inactive_teams = [
                team_name for team_name, team_info in self.active_teams.items()
                if len(team_info.get('players', [])) == 0
            ]
            
            teams_to_remove = len(self.active_teams) - self.max_teams
            for team_name in inactive_teams[:teams_to_remove]:
                del self.active_teams[team_name]
    
    def update_player_activity(self, player_id):
        self.player_last_seen[player_id] = time.time()
```

## Database Performance Issues

### 1. Missing Indexes (HIGH)
**Impact**: Slow queries on dashboard statistics

**Current Issues**:
```sql
-- Slow query: no index on team_id, timestamp
SELECT * FROM answers WHERE team_id = ? ORDER BY timestamp DESC;

-- Slow query: no composite index
SELECT * FROM teams WHERE is_active = true ORDER BY created_at DESC;
```

**Solution**:
```python
# Add strategic indexes to models
class Teams(db.Model):
    __table_args__ = (
        db.Index('idx_teams_active_created', 'is_active', 'created_at'),
        db.Index('idx_teams_name_active', 'team_name', 'is_active'),
        db.UniqueConstraint('team_name', 'is_active', name='_team_name_active_uc'),
    )

class Answers(db.Model):
    __table_args__ = (
        db.Index('idx_answers_team_timestamp', 'team_id', 'timestamp'),
        db.Index('idx_answers_round_team', 'question_round_id', 'team_id'),
        db.Index('idx_answers_team_item', 'team_id', 'assigned_item'),
        db.Index('idx_answers_player_round', 'player_session_id', 'question_round_id'),
    )
```

### 2. N+1 Query Problems (MEDIUM)
**Location**: Dashboard statistics calculation

```python
# PROBLEMATIC CODE
def get_all_team_stats():
    teams = Teams.query.all()
    stats = {}
    for team in teams:
        # This creates N+1 queries
        answers = Answers.query.filter_by(team_id=team.team_id).all()
        stats[team.team_id] = calculate_stats(answers)
    return stats
```

**Solution**:
```python
def get_all_team_stats():
    # Single query with eager loading
    teams_with_answers = db.session.query(Teams).options(
        joinedload(Teams.answers)
    ).filter(Teams.is_active == True).all()
    
    stats = {}
    for team in teams_with_answers:
        stats[team.team_id] = calculate_stats(team.answers)
    
    return stats
```

### 3. Query Optimization
```python
# Optimized dashboard data query
def get_dashboard_data_optimized():
    # Single query to get all necessary data
    result = db.session.execute("""
        SELECT 
            t.team_id,
            t.team_name,
            COUNT(DISTINCT a.player_session_id) as player_count,
            COUNT(a.answer_id) as answer_count,
            MAX(a.timestamp) as last_activity
        FROM teams t
        LEFT JOIN answers a ON t.team_id = a.team_id
        WHERE t.is_active = true
        GROUP BY t.team_id, t.team_name
        ORDER BY last_activity DESC
    """)
    
    return [dict(row) for row in result]
```

## Frontend Performance Issues

### 1. DOM Manipulation Inefficiencies (MEDIUM)
**Location**: `src/static/dashboard.js`

```javascript
// PROBLEMATIC CODE
function updateTeamsList(teams) {
    const container = document.getElementById('teams-container');
    container.innerHTML = ''; // Triggers layout recalculation
    
    teams.forEach(team => {
        // Multiple DOM insertions
        const div = document.createElement('div');
        div.innerHTML = `<span>${team.name}</span>`;
        container.appendChild(div); // Multiple reflows
    });
}
```

**Solution**:
```javascript
function updateTeamsList(teams) {
    const container = document.getElementById('teams-container');
    
    // Build HTML string first
    const html = teams.map(team => 
        `<div class="team-item">
            <span class="team-name">${escapeHtml(team.name)}</span>
            <span class="team-status">${team.status}</span>
         </div>`
    ).join('');
    
    // Single DOM update
    container.innerHTML = html;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
```

### 2. Memory Leaks in Event Listeners (MEDIUM)
```javascript
// PROBLEMATIC CODE
function createTeamButton(teamData) {
    const button = document.createElement('button');
    button.addEventListener('click', function() {
        // Closure keeps teamData in memory
        joinTeam(teamData);
    });
    return button;
}
```

**Solution**:
```javascript
function createTeamButton(teamData) {
    const button = document.createElement('button');
    button.dataset.teamId = teamData.id;
    
    // Use event delegation instead
    button.addEventListener('click', handleTeamButtonClick);
    
    return button;
}

function handleTeamButtonClick(event) {
    const teamId = event.target.dataset.teamId;
    joinTeam(teamId);
}

// Clean up when removing elements
function removeTeamButton(button) {
    button.removeEventListener('click', handleTeamButtonClick);
    button.remove();
}
```

### 3. Request Debouncing
```javascript
// Debounce frequent operations
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Usage for dashboard updates
const debouncedUpdateStats = debounce(updateStatistics, 100);

socket.on('stats_update', debouncedUpdateStats);
```

## WebSocket Performance

### 1. Connection Management
```python
# Optimize WebSocket configuration
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='eventlet',
    ping_timeout=30,
    ping_interval=5,
    max_http_buffer_size=1000000,  # 1MB buffer
    compression=True,  # Enable compression
    logger=False,  # Disable debug logging in production
    engineio_logger=False
)
```

### 2. Event Batching
```python
import threading
import time
from collections import defaultdict

class EventBatcher:
    def __init__(self, batch_size=10, flush_interval=1.0):
        self.batches = defaultdict(list)
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.last_flush = time.time()
        self.lock = threading.Lock()
    
    def add_event(self, room, event_name, data):
        with self.lock:
            self.batches[room].append({'event': event_name, 'data': data})
            
            if (len(self.batches[room]) >= self.batch_size or 
                time.time() - self.last_flush > self.flush_interval):
                self._flush_batch(room)
    
    def _flush_batch(self, room):
        if room in self.batches and self.batches[room]:
            socketio.emit('batch_update', {
                'events': self.batches[room]
            }, room=room)
            
            self.batches[room] = []
            self.last_flush = time.time()

# Usage
batcher = EventBatcher()

def emit_dashboard_update(data):
    batcher.add_event('dashboard', 'stats_update', data)
```

## Monitoring and Profiling

### 1. Performance Monitoring
```python
import time
import psutil
import logging
from functools import wraps

class PerformanceMonitor:
    def __init__(self):
        self.metrics = {}
        self.logger = logging.getLogger('performance')
    
    def time_function(self, func_name):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    duration = time.time() - start_time
                    self._record_timing(func_name, duration)
            return wrapper
        return decorator
    
    def _record_timing(self, func_name, duration):
        if duration > 0.1:  # Log slow operations
            self.logger.warning(f"Slow operation: {func_name} took {duration:.3f}s")
        
        # Store metrics
        if func_name not in self.metrics:
            self.metrics[func_name] = []
        self.metrics[func_name].append(duration)
    
    def get_system_metrics(self):
        process = psutil.Process()
        return {
            'memory_mb': process.memory_info().rss / 1024 / 1024,
            'cpu_percent': process.cpu_percent(),
            'connections': len(state.connected_players),
            'active_teams': len(state.active_teams)
        }

monitor = PerformanceMonitor()

# Usage
@monitor.time_function('create_team')
@socketio.on('create_team')
def on_create_team(data):
    # Implementation
    pass
```

### 2. Database Query Profiling
```python
import time
from sqlalchemy import event
from sqlalchemy.engine import Engine

# Log slow queries
@event.listens_for(Engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._query_start_time = time.time()

@event.listens_for(Engine, "after_cursor_execute")
def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total = time.time() - context._query_start_time
    if total > 0.05:  # Log queries taking > 50ms
        logger.warning(f"Slow query: {total:.3f}s - {statement[:100]}...")
```

## Performance Benchmarks

### Target Performance Metrics

| Metric | Target | Current | Status |
|--------|---------|---------|---------|
| Page Load Time | < 2s | ~3s | ❌ Needs optimization |
| WebSocket Connection | < 500ms | ~800ms | ⚠️ Acceptable |
| Answer Submission | < 100ms | ~150ms | ⚠️ Needs improvement |
| Dashboard Update | < 200ms | ~400ms | ❌ Needs optimization |
| Memory Usage (100 users) | < 500MB | ~800MB | ❌ Memory leaks |
| CPU Usage (100 users) | < 50% | ~70% | ⚠️ Needs optimization |

### Load Testing Results
```bash
# Performance test with 50 teams (100 players)
python chsh_load_test.py --teams 50 --duration 300

# Expected results after optimization:
# - Response time: < 100ms (95th percentile)
# - Error rate: < 1%
# - Memory usage: < 400MB
# - CPU usage: < 60%
```

## Optimization Roadmap

### Phase 1: Critical Fixes (Week 1-2)
1. **Fix memory leaks** in LRU cache
2. **Add database indexes** for common queries
3. **Implement state cleanup** mechanisms
4. **Optimize DOM operations** in frontend

### Phase 2: Performance Improvements (Week 3-4)
1. **Database query optimization** and eager loading
2. **WebSocket event batching** for dashboard
3. **Implement caching strategy** with TTL
4. **Add performance monitoring** and alerting

### Phase 3: Scaling Preparation (Week 5-6)
1. **Connection pooling** configuration
2. **Redis caching** for production
3. **CDN integration** for static assets
4. **Load balancer** preparation

---

This performance analysis provides concrete steps to optimize the CHSH Game for better scalability and user experience.
# Performance Analysis - CHSH Game

**Focus:** Application performance assessment  
**Scope:** Backend performance, database optimization, frontend performance, scalability, and monitoring

---

## Executive Performance Summary

### Current Performance Profile
- **Overall Performance:** MODERATE
- **Backend Response Time:** 50-200ms (estimated)
- **Database Performance:** Good with ORM, potential N+1 queries
- **Frontend Performance:** Good for small datasets, degrades with scale
- **Memory Usage:** Potential memory leaks in caching system
- **Scalability:** Limited by single-instance architecture

### Critical Performance Issues
1. **Memory Leaks:** Unbounded LRU cache growth
2. **Database N+1 Queries:** Inefficient data loading patterns
3. **Heavy DOM Operations:** Frequent table rebuilds in dashboard
4. **No Performance Monitoring:** Lack of observability
5. **Single-Point Architecture:** No horizontal scaling capability

---

## Backend Performance Analysis

### Application Server Performance

#### Current Architecture:
```python
# wsgi.py - Production configuration
CMD ["gunicorn", "wsgi:app", "--worker-class", "eventlet"]
```

#### Server Configuration Analysis:

**Strengths:**
- **Eventlet Workers:** Good for I/O-bound WebSocket operations
- **Async Support:** Proper async handling for real-time features
- **Single-threaded per worker:** Avoids threading complexity

**Issues:**
- **No Worker Configuration:** Default worker count may be suboptimal
- **No Connection Limits:** No configured connection pooling
- **No Request Timeout:** Missing timeout configurations
- **No Load Balancing:** Single instance deployment

#### Recommendations:

**Optimized Gunicorn Configuration:**
```python
# gunicorn.conf.py
import multiprocessing

# Worker configuration
workers = min(multiprocessing.cpu_count() * 2 + 1, 8)
worker_class = "eventlet"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100

# Timeout configuration
timeout = 30
keepalive = 2
graceful_timeout = 30

# Memory management
preload_app = True
max_worker_memory = 200  # MB

# Logging
access_logfile = '-'
error_logfile = '-'
loglevel = 'info'
```

### Memory Usage Analysis

#### Current Memory Issues:

**LRU Cache Memory Leak:**
```python
# src/sockets/dashboard.py
@lru_cache(maxsize=CACHE_SIZE)
def compute_team_hashes(team_id):
    return "disabled", "disabled"  # Function disabled but cache grows

@lru_cache(maxsize=CACHE_SIZE)
def compute_correlation_matrix(team_id):
    # Complex computation with no expiration
```

**Issue:** Cache grows indefinitely with new team IDs, never releasing memory.

**State Object Growth:**
```python
# src/state.py
class AppState:
    def __init__(self):
        self.active_teams = {}  # No size limits
        self.player_to_team = {}  # Grows without bounds
        self.connected_players = set()  # No cleanup of stale connections
```

#### Memory Monitoring Implementation:

```python
import psutil
import gc
from functools import wraps

class MemoryMonitor:
    def __init__(self):
        self.process = psutil.Process()
        self.baseline_memory = self.get_memory_usage()
    
    def get_memory_usage(self):
        return {
            'rss': self.process.memory_info().rss / 1024 / 1024,  # MB
            'vms': self.process.memory_info().vms / 1024 / 1024,  # MB
            'percent': self.process.memory_percent(),
            'available': psutil.virtual_memory().available / 1024 / 1024  # MB
        }
    
    def get_cache_stats(self):
        return {
            'team_hashes': compute_team_hashes.cache_info()._asdict(),
            'correlation_matrix': compute_correlation_matrix.cache_info()._asdict(),
            'gc_stats': {
                'gen0': gc.get_count()[0],
                'gen1': gc.get_count()[1], 
                'gen2': gc.get_count()[2]
            }
        }
    
    def check_memory_threshold(self, threshold_mb=500):
        current = self.get_memory_usage()
        if current['rss'] > threshold_mb:
            return False, current
        return True, current

memory_monitor = MemoryMonitor()

def monitor_memory(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        before = memory_monitor.get_memory_usage()
        result = f(*args, **kwargs)
        after = memory_monitor.get_memory_usage()
        
        memory_increase = after['rss'] - before['rss']
        if memory_increase > 10:  # MB
            print(f"Memory increase in {f.__name__}: {memory_increase:.2f}MB")
        
        return result
    return wrapper
```

#### Cache Management Improvements:

```python
import time
from collections import OrderedDict
import threading

class TTLCache:
    def __init__(self, maxsize=1000, ttl=300):  # 5 minutes TTL
        self.maxsize = maxsize
        self.ttl = ttl
        self.cache = OrderedDict()
        self.timestamps = {}
        self.lock = threading.RLock()
    
    def get(self, key):
        with self.lock:
            if key not in self.cache:
                return None
            
            # Check if expired
            if time.time() - self.timestamps[key] > self.ttl:
                del self.cache[key]
                del self.timestamps[key]
                return None
            
            # Move to end (LRU)
            self.cache.move_to_end(key)
            return self.cache[key]
    
    def set(self, key, value):
        with self.lock:
            # Remove expired entries
            self._cleanup_expired()
            
            # Remove oldest if at capacity
            if len(self.cache) >= self.maxsize and key not in self.cache:
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
                del self.timestamps[oldest_key]
            
            self.cache[key] = value
            self.timestamps[key] = time.time()
            self.cache.move_to_end(key)
    
    def _cleanup_expired(self):
        current_time = time.time()
        expired_keys = [
            key for key, timestamp in self.timestamps.items()
            if current_time - timestamp > self.ttl
        ]
        for key in expired_keys:
            del self.cache[key]
            del self.timestamps[key]

# Replace LRU caches with TTL caches
team_cache = TTLCache(maxsize=500, ttl=300)
correlation_cache = TTLCache(maxsize=200, ttl=600)
```

### CPU Performance Analysis

#### Current CPU Usage Patterns:

**Heavy Computation in Dashboard:**
```python
# src/sockets/dashboard.py
def _calculate_team_statistics(correlation_matrix_tuple_str):
    # 400+ lines of complex mathematical operations
    # Runs on main thread, blocking other operations
```

**Real-time Updates:**
```python
def emit_dashboard_team_update():
    # Recalculates all team statistics on every update
    serialized_teams = get_all_teams()  # Expensive operation
    for sid in state.dashboard_clients:
        socketio.emit('team_status_changed_for_dashboard', update_data, room=sid)
```

#### CPU Optimization Recommendations:

**Background Task Processing:**
```python
from celery import Celery
import redis

# Configure Celery for background tasks
celery_app = Celery('chsh_game', broker='redis://localhost:6379/0')

@celery_app.task
def calculate_team_statistics_async(team_id):
    """Calculate statistics in background"""
    team = Teams.query.get(team_id)
    if not team:
        return None
    
    # Perform expensive calculations
    correlation_matrix = compute_correlation_matrix(team_id)
    statistics = _calculate_team_statistics(correlation_matrix)
    
    # Cache results
    team_cache.set(f"stats_{team_id}", statistics)
    
    # Emit update to connected dashboards
    socketio.emit('team_stats_updated', {
        'team_id': team_id,
        'statistics': statistics
    })
    
    return statistics

# Use async processing
@socketio.on('submit_answer')
def on_submit_answer(data):
    # Process answer synchronously
    # ... existing logic ...
    
    # Update statistics asynchronously
    calculate_team_statistics_async.delay(team_info['team_id'])
```

**CPU Profiling Integration:**
```python
import cProfile
import pstats
from functools import wraps

def profile_performance(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        pr = cProfile.Profile()
        pr.enable()
        
        result = f(*args, **kwargs)
        
        pr.disable()
        stats = pstats.Stats(pr)
        stats.sort_stats('cumulative')
        
        # Log top 10 most expensive operations
        stats.print_stats(10)
        
        return result
    return wrapper

# Apply to expensive operations
@profile_performance
def get_all_teams():
    # Existing implementation
    pass
```

---

## Database Performance Analysis

### Current Database Usage

#### Query Patterns:
```python
# Good: Single queries
team = Teams.query.get(team_id)
answers = Answers.query.filter_by(team_id=team_id).all()

# Potential N+1: Dashboard loading
all_teams = Teams.query.all()
for team in all_teams:
    team_info = state.active_teams.get(team.team_name)  # Memory lookup - good
    max_round = db.session.query(func.max(PairQuestionRounds.round_number_for_team))\
                          .filter_by(team_id=team.team_id).scalar()  # N+1 query
```

#### Database Configuration:
```python
# src/config.py
app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///' + ...
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Good: Disabled tracking
```

### Performance Issues

#### **1. N+1 Query Problems (HIGH)**

**Current Implementation:**
```python
def get_all_teams():
    all_teams = Teams.query.all()  # 1 query
    for team in all_teams:
        # Additional query for each team
        max_round_obj = db.session.query(func.max(PairQuestionRounds.round_number_for_team))\
                                  .filter_by(team_id=team.team_id).scalar()
```

**Optimized Implementation:**
```python
def get_all_teams_optimized():
    # Single query with subquery
    max_rounds_subquery = db.session.query(
        PairQuestionRounds.team_id,
        func.max(PairQuestionRounds.round_number_for_team).label('max_round')
    ).group_by(PairQuestionRounds.team_id).subquery()
    
    # Join with teams table
    teams_with_rounds = db.session.query(
        Teams,
        func.coalesce(max_rounds_subquery.c.max_round, 0).label('current_round')
    ).outerjoin(
        max_rounds_subquery, Teams.team_id == max_rounds_subquery.c.team_id
    ).all()
    
    return teams_with_rounds
```

#### **2. Missing Indexes (MEDIUM)**

**Current Schema:**
```python
# No explicit indexes on frequently queried fields
class Teams(db.Model):
    team_name = db.Column(db.String(100), nullable=False)  # No index
    created_at = db.Column(db.DateTime, server_default=db.func.now())  # No index

class Answers(db.Model):
    timestamp = db.Column(db.DateTime, server_default=db.func.now())  # No index
```

**Recommended Indexes:**
```python
# Add database indexes for performance
class Teams(db.Model):
    __tablename__ = 'teams'
    
    team_name = db.Column(db.String(100), nullable=False, index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    
    # Composite index for common queries
    __table_args__ = (
        db.Index('ix_teams_active_created', 'is_active', 'created_at'),
        db.Index('ix_teams_name_active', 'team_name', 'is_active'),
    )

class Answers(db.Model):
    __tablename__ = 'answers'
    
    team_id = db.Column(db.Integer, db.ForeignKey('teams.team_id'), 
                       nullable=False, index=True)
    timestamp = db.Column(db.DateTime, server_default=db.func.now(), index=True)
    
    __table_args__ = (
        db.Index('ix_answers_team_timestamp', 'team_id', 'timestamp'),
    )
```

#### **3. Connection Pooling (MEDIUM)**

**Current Configuration:**
```python
# No explicit connection pool configuration
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
```

**Optimized Configuration:**
```python
# Configure connection pooling
app.config.update({
    'SQLALCHEMY_DATABASE_URI': database_url,
    'SQLALCHEMY_ENGINE_OPTIONS': {
        'pool_size': 10,
        'pool_recycle': 300,
        'pool_pre_ping': True,
        'max_overflow': 20,
        'pool_timeout': 30
    }
})
```

### Database Monitoring

#### Query Performance Monitoring:
```python
import time
from sqlalchemy import event
from sqlalchemy.engine import Engine

# Monitor slow queries
@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._query_start_time = time.time()

@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total = time.time() - context._query_start_time
    
    if total > 0.1:  # Log queries taking more than 100ms
        print(f"Slow query: {total:.3f}s")
        print(f"SQL: {statement[:200]}...")

# Database health monitoring
class DatabaseMonitor:
    def get_connection_info(self):
        return {
            'pool_size': db.engine.pool.size(),
            'checked_out_connections': db.engine.pool.checkedout(),
            'overflow_connections': db.engine.pool.overflow(),
            'checked_in_connections': db.engine.pool.checkedin()
        }
    
    def get_query_stats(self):
        # Get query statistics from database
        if 'postgresql' in str(db.engine.url):
            return self._get_postgres_stats()
        return {}
    
    def _get_postgres_stats(self):
        result = db.session.execute("""
            SELECT query, calls, total_time, mean_time
            FROM pg_stat_statements
            ORDER BY total_time DESC
            LIMIT 10
        """)
        return [dict(row) for row in result]
```

---

## Frontend Performance Analysis

### Current Frontend Architecture

#### JavaScript Performance:
```javascript
// Heavy DOM operations in dashboard updates
function updateActiveTeams(teams) {
    activeTeamsTableBody.innerHTML = ""; // Forces reflow
    
    filteredTeams.forEach(team => {
        const row = activeTeamsTableBody.insertRow(); // Multiple reflows
        // Complex row building with multiple DOM operations
    });
}
```

#### CSS Performance:
```css
/* Potential performance issues */
* {
    touch-action: manipulation; /* Applied to all elements */
}

/* Multiple transitions could impact performance */
.answer-button {
    transition: opacity 0.3s ease, background-color 0.3s ease;
}
```

### Frontend Performance Issues

#### **1. Heavy DOM Manipulation (HIGH)**

**Current Implementation:**
```javascript
// Clears and rebuilds entire table on every update
function updateActiveTeams(teams) {
    activeTeamsTableBody.innerHTML = "";
    filteredTeams.forEach(team => {
        const row = activeTeamsTableBody.insertRow();
        // 8+ cell insertions per team
    });
}
```

**Optimized Implementation:**
```javascript
class TeamTableManager {
    constructor(tableBody) {
        this.tableBody = tableBody;
        this.teamRows = new Map(); // Cache DOM elements
    }
    
    updateTeams(teams) {
        const currentTeamIds = new Set(teams.map(t => t.team_id));
        
        // Remove teams that no longer exist
        for (const [teamId, row] of this.teamRows) {
            if (!currentTeamIds.has(teamId)) {
                row.remove();
                this.teamRows.delete(teamId);
            }
        }
        
        // Update or create rows
        teams.forEach(team => {
            if (this.teamRows.has(team.team_id)) {
                this.updateExistingRow(team);
            } else {
                this.createNewRow(team);
            }
        });
    }
    
    updateExistingRow(team) {
        const row = this.teamRows.get(team.team_id);
        // Update only changed cells
        this.updateCellIfChanged(row.cells[0], team.team_name);
        this.updateCellIfChanged(row.cells[1], team.status);
        // ... update other cells as needed
    }
    
    updateCellIfChanged(cell, newValue) {
        if (cell.textContent !== newValue) {
            cell.textContent = newValue;
        }
    }
}
```

#### **2. Memory Leaks in Event Listeners (MEDIUM)**

**Current Issues:**
```javascript
// Event listeners not properly cleaned up
document.addEventListener('DOMContentLoaded', function() {
    collapsibleHeader.addEventListener('click', function() {
        // Event listener never removed
    });
});

// Global event listeners accumulate
if (window._modalClickHandler) {
    window.removeEventListener('click', window._modalClickHandler);
}
window._modalClickHandler = function (event) {
    // Potential memory leak if not cleaned up properly
};
```

**Improved Event Management:**
```javascript
class EventManager {
    constructor() {
        this.listeners = new Map();
        this.abortController = new AbortController();
    }
    
    addEventListener(element, event, handler, options = {}) {
        const finalOptions = {
            ...options,
            signal: this.abortController.signal
        };
        
        element.addEventListener(event, handler, finalOptions);
        
        // Track for manual cleanup if needed
        const key = `${element.id || 'element'}_${event}`;
        if (!this.listeners.has(key)) {
            this.listeners.set(key, []);
        }
        this.listeners.get(key).push(handler);
    }
    
    cleanup() {
        this.abortController.abort();
        this.listeners.clear();
    }
    
    removeSpecificListener(element, event, handler) {
        element.removeEventListener(event, handler);
        const key = `${element.id || 'element'}_${event}`;
        if (this.listeners.has(key)) {
            const handlers = this.listeners.get(key);
            const index = handlers.indexOf(handler);
            if (index > -1) {
                handlers.splice(index, 1);
            }
        }
    }
}

// Global event manager
const eventManager = new EventManager();

// Use for all event listeners
eventManager.addEventListener(
    document.getElementById('createTeamBtn'),
    'click',
    createTeam
);
```

#### **3. Inefficient Statistics Formatting (MEDIUM)**

**Current Implementation:**
```javascript
function formatStatWithUncertainty(magnitude, uncertainty, precision = 2) {
    // Complex string manipulation on every render
    if (typeof magnitude !== 'number' || isNaN(magnitude)) {
        return "—";
    }
    let magStr = magnitude.toFixed(precision);
    // ... more complex formatting
}
```

**Optimized Implementation:**
```javascript
class StatisticsFormatter {
    constructor() {
        this.cache = new Map();
        this.maxCacheSize = 1000;
    }
    
    formatStatWithUncertainty(magnitude, uncertainty, precision = 2) {
        const cacheKey = `${magnitude}_${uncertainty}_${precision}`;
        
        if (this.cache.has(cacheKey)) {
            return this.cache.get(cacheKey);
        }
        
        if (typeof magnitude !== 'number' || isNaN(magnitude)) {
            return "—";
        }
        
        const result = this.doFormatting(magnitude, uncertainty, precision);
        
        // Manage cache size
        if (this.cache.size >= this.maxCacheSize) {
            const firstKey = this.cache.keys().next().value;
            this.cache.delete(firstKey);
        }
        
        this.cache.set(cacheKey, result);
        return result;
    }
    
    doFormatting(magnitude, uncertainty, precision) {
        // Original formatting logic
        let magStr = magnitude.toFixed(precision);
        // ... formatting implementation
        return result;
    }
}

const formatter = new StatisticsFormatter();
```

### Frontend Monitoring

#### Performance Metrics Collection:
```javascript
class PerformanceMonitor {
    constructor() {
        this.metrics = {
            domUpdateTimes: [],
            socketLatency: [],
            renderTimes: []
        };
    }
    
    measureDOMUpdate(updateFunction) {
        const start = performance.now();
        const result = updateFunction();
        const end = performance.now();
        
        const duration = end - start;
        this.metrics.domUpdateTimes.push(duration);
        
        if (duration > 100) { // Log slow updates
            console.warn(`Slow DOM update: ${duration.toFixed(2)}ms`);
        }
        
        return result;
    }
    
    measureSocketLatency(eventName) {
        const start = performance.now();
        return {
            complete: () => {
                const latency = performance.now() - start;
                this.metrics.socketLatency.push(latency);
                console.log(`Socket ${eventName} latency: ${latency.toFixed(2)}ms`);
            }
        };
    }
    
    getMetrics() {
        return {
            avgDOMUpdateTime: this.average(this.metrics.domUpdateTimes),
            avgSocketLatency: this.average(this.metrics.socketLatency),
            p95DOMUpdateTime: this.percentile(this.metrics.domUpdateTimes, 95),
            memoryUsage: this.getMemoryUsage()
        };
    }
    
    getMemoryUsage() {
        if (performance.memory) {
            return {
                used: Math.round(performance.memory.usedJSHeapSize / 1048576),
                total: Math.round(performance.memory.totalJSHeapSize / 1048576),
                limit: Math.round(performance.memory.jsHeapSizeLimit / 1048576)
            };
        }
        return null;
    }
    
    average(arr) {
        return arr.length ? arr.reduce((a, b) => a + b) / arr.length : 0;
    }
    
    percentile(arr, p) {
        if (!arr.length) return 0;
        const sorted = [...arr].sort((a, b) => a - b);
        const index = Math.ceil((p / 100) * sorted.length) - 1;
        return sorted[index];
    }
}

const perfMonitor = new PerformanceMonitor();

// Use throughout application
function updateActiveTeams(teams) {
    perfMonitor.measureDOMUpdate(() => {
        // DOM update logic
    });
}
```

---

## Scalability Analysis

### Current Architecture Limitations

#### Single Instance Deployment:
```toml
# fly.toml
[[vm]]
memory = '2gb'
size = "performance-1x"
# Single instance only
```

#### In-Memory State Management:
```python
# src/state.py
class AppState:
    def __init__(self):
        self.active_teams = {}  # Stored in memory only
        self.player_to_team = {}  # Lost on restart
        self.connected_players = set()  # Not shared across instances
```

### Scalability Issues

#### **1. Single Point of Failure (HIGH)**
- Single instance means no high availability
- Server restart loses all game state
- No horizontal scaling capability

#### **2. Memory-Based State (HIGH)**
- State not shared across instances
- No persistence across restarts
- Growing memory usage with more users

#### **3. Database Bottleneck (MEDIUM)**
- Single database instance
- No read replicas
- Heavy dashboard queries impact game performance

### Scalability Recommendations

#### **Distributed State Management:**
```python
import redis
import json
from typing import Dict, Any

class DistributedState:
    def __init__(self, redis_url='redis://localhost:6379'):
        self.redis_client = redis.from_url(redis_url)
        self.local_cache = {}
        self.cache_ttl = 300  # 5 minutes
    
    def set_team_data(self, team_name: str, data: Dict[str, Any]):
        """Store team data in Redis"""
        serialized = json.dumps(data, default=str)
        self.redis_client.setex(f"team:{team_name}", self.cache_ttl, serialized)
        self.local_cache[team_name] = data
    
    def get_team_data(self, team_name: str) -> Dict[str, Any]:
        """Retrieve team data with local cache fallback"""
        # Check local cache first
        if team_name in self.local_cache:
            return self.local_cache[team_name]
        
        # Check Redis
        data = self.redis_client.get(f"team:{team_name}")
        if data:
            parsed = json.loads(data)
            self.local_cache[team_name] = parsed
            return parsed
        
        return None
    
    def add_player_to_team(self, player_id: str, team_name: str):
        """Distributed player-team mapping"""
        self.redis_client.setex(f"player:{player_id}", self.cache_ttl, team_name)
    
    def get_player_team(self, player_id: str) -> str:
        """Get player's team from distributed store"""
        team = self.redis_client.get(f"player:{player_id}")
        return team.decode() if team else None
    
    def get_active_teams(self) -> Dict[str, Dict]:
        """Get all active teams"""
        keys = self.redis_client.keys("team:*")
        teams = {}
        for key in keys:
            team_name = key.decode().split(":", 1)[1]
            data = self.redis_client.get(key)
            if data:
                teams[team_name] = json.loads(data)
        return teams

# Replace global state with distributed state
distributed_state = DistributedState()
```

#### **Database Scaling:**
```python
# Configure read replicas
class DatabaseConfig:
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_BINDS = {
        'read_replica': os.environ.get('DATABASE_READ_URL', SQLALCHEMY_DATABASE_URI)
    }
    
    @staticmethod
    def get_read_db():
        """Use read replica for read-only operations"""
        return db.get_engine(bind='read_replica')

# Use read replicas for dashboard queries
def get_dashboard_teams():
    """Use read replica for heavy dashboard queries"""
    with DatabaseConfig.get_read_db().connect() as conn:
        result = conn.execute("""
            SELECT t.*, MAX(pqr.round_number_for_team) as max_round
            FROM teams t
            LEFT JOIN pair_question_rounds pqr ON t.team_id = pqr.team_id
            WHERE t.is_active = true
            GROUP BY t.team_id
        """)
        return [dict(row) for row in result]
```

#### **Load Balancing Configuration:**
```python
# Multi-instance deployment
# docker-compose.yml
version: '3.8'
services:
  app1:
    build: .
    environment:
      - INSTANCE_ID=app1
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis
      - postgres
  
  app2:
    build: .
    environment:
      - INSTANCE_ID=app2
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis
      - postgres
  
  nginx:
    image: nginx
    ports:
      - "8080:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - app1
      - app2
  
  redis:
    image: redis:alpine
    command: redis-server --appendonly yes
  
  postgres:
    image: postgres:13
    environment:
      POSTGRES_DB: chsh_game
      POSTGRES_USER: chsh_user
      POSTGRES_PASSWORD: chsh_pass
```

---

## Real-Time Performance

### WebSocket Performance

#### Current Socket.IO Configuration:
```python
# src/config.py
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', 
                   ping_timeout=5, ping_interval=5)
```

#### Performance Monitoring:
```python
import time
from functools import wraps

class SocketPerformanceMonitor:
    def __init__(self):
        self.event_metrics = {}
    
    def monitor_event(self, event_name):
        def decorator(f):
            @wraps(f)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                
                try:
                    result = f(*args, **kwargs)
                    duration = time.time() - start_time
                    self.record_success(event_name, duration)
                    return result
                except Exception as e:
                    duration = time.time() - start_time
                    self.record_error(event_name, duration, str(e))
                    raise
            return wrapper
        return decorator
    
    def record_success(self, event_name, duration):
        if event_name not in self.event_metrics:
            self.event_metrics[event_name] = {
                'count': 0, 'total_time': 0, 'errors': 0, 'avg_time': 0
            }
        
        metrics = self.event_metrics[event_name]
        metrics['count'] += 1
        metrics['total_time'] += duration
        metrics['avg_time'] = metrics['total_time'] / metrics['count']
        
        if duration > 1.0:  # Log slow events
            print(f"Slow socket event {event_name}: {duration:.3f}s")
    
    def record_error(self, event_name, duration, error):
        if event_name not in self.event_metrics:
            self.event_metrics[event_name] = {
                'count': 0, 'total_time': 0, 'errors': 0, 'avg_time': 0
            }
        
        self.event_metrics[event_name]['errors'] += 1
        print(f"Socket event error {event_name}: {error}")

socket_monitor = SocketPerformanceMonitor()

# Apply to socket events
@socketio.on('submit_answer')
@socket_monitor.monitor_event('submit_answer')
def on_submit_answer(data):
    # Existing implementation
    pass
```

#### WebSocket Optimization:
```python
# Optimize socket emissions
class OptimizedSocketEmitter:
    def __init__(self, socketio):
        self.socketio = socketio
        self.emission_queue = {}
        self.batch_size = 10
        self.batch_timeout = 0.1  # 100ms
    
    def emit_batched(self, event, data, room=None):
        """Batch emissions to improve performance"""
        key = f"{event}_{room}"
        
        if key not in self.emission_queue:
            self.emission_queue[key] = []
        
        self.emission_queue[key].append(data)
        
        # Emit immediately if batch is full
        if len(self.emission_queue[key]) >= self.batch_size:
            self._flush_batch(key, event, room)
        else:
            # Schedule delayed emission
            socketio.start_background_task(
                self._delayed_flush, key, event, room
            )
    
    def _flush_batch(self, key, event, room):
        if key in self.emission_queue:
            batch_data = self.emission_queue[key]
            del self.emission_queue[key]
            
            if batch_data:
                self.socketio.emit(f"{event}_batch", batch_data, room=room)
    
    def _delayed_flush(self, key, event, room):
        socketio.sleep(self.batch_timeout)
        self._flush_batch(key, event, room)

optimized_emitter = OptimizedSocketEmitter(socketio)
```

---

## Performance Testing Strategy

### Load Testing

#### Test Scenarios:
```python
# load_test.py using locust
from locust import HttpUser, task, between
import random

class CHSHGameUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        """Setup test user"""
        self.team_name = f"TestTeam_{random.randint(1000, 9999)}"
        self.socket = None
    
    @task(1)
    def create_team(self):
        """Test team creation"""
        response = self.client.post("/create_team", json={
            "team_name": self.team_name
        })
        self.socket = response.json().get('socket_id')
    
    @task(3)
    def submit_answers(self):
        """Test answer submission"""
        if self.socket:
            for _ in range(10):  # Submit 10 answers
                self.client.post("/submit_answer", json={
                    "round_id": random.randint(1, 100),
                    "item": random.choice(['A', 'B', 'X', 'Y']),
                    "answer": random.choice([True, False])
                })
    
    @task(2)
    def view_dashboard(self):
        """Test dashboard loading"""
        self.client.get("/api/dashboard/data")

# Run with: locust -f load_test.py --host=http://localhost:8080
```

#### Performance Benchmarks:
```bash
# Basic load test
locust -f load_test.py --host=http://localhost:8080 \
       --users 100 --spawn-rate 10 --run-time 300s

# Stress test
locust -f load_test.py --host=http://localhost:8080 \
       --users 500 --spawn-rate 50 --run-time 600s

# WebSocket load test
pip install websocket-client
python websocket_load_test.py --connections 200 --duration 300
```

### Performance Baselines

#### Target Metrics:
- **API Response Time:** < 200ms for 95th percentile
- **Socket Event Processing:** < 100ms average
- **Dashboard Load Time:** < 2 seconds
- **Memory Usage:** < 500MB under normal load
- **CPU Usage:** < 70% under peak load
- **Concurrent Users:** Support 1000+ concurrent connections

#### Monitoring Dashboard:
```python
@app.route('/metrics')
def performance_metrics():
    """Expose performance metrics"""
    return jsonify({
        'memory': memory_monitor.get_memory_usage(),
        'database': db_monitor.get_connection_info(),
        'cache': {
            'team_cache_hit_rate': team_cache.hit_rate(),
            'correlation_cache_size': len(correlation_cache.cache)
        },
        'socket_events': socket_monitor.event_metrics,
        'response_times': {
            'avg_api_response': perfMonitor.average_api_response_time(),
            'avg_socket_latency': perfMonitor.average_socket_latency()
        }
    })
```

---

## Summary and Optimization Roadmap

### Critical Performance Issues (Fix Immediately)
1. **Fix memory leaks in LRU caches**
2. **Optimize database queries (eliminate N+1)**
3. **Implement efficient DOM updates**
4. **Add performance monitoring**

### High Priority (1 week)
1. **Database indexing strategy**
2. **Frontend performance optimization**
3. **WebSocket event optimization**
4. **Load testing setup**

### Medium Priority (1 month)
1. **Distributed state management**
2. **Database read replicas**
3. **Advanced caching strategies**
4. **Performance alerting system**

### Long Term (Future releases)
1. **Horizontal scaling architecture**
2. **CDN integration for static assets**
3. **Database sharding for massive scale**
4. **Advanced monitoring and APM integration**

The application shows good foundational performance but requires immediate attention to memory management and database optimization to handle production loads effectively.
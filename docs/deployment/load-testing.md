# Load Testing

This guide covers performance testing and optimization for the CHSH Game using the built-in load testing tools.

## Overview

The CHSH Game includes a comprehensive load testing suite that simulates realistic user behavior and provides detailed performance metrics.

### What We Test
- **Concurrent player connections** (WebSocket performance)
- **Team creation and management** under load
- **Game flow simulation** with multiple rounds
- **Dashboard performance** with real-time updates
- **Database performance** under concurrent writes
- **Memory and CPU utilization** during peak load

### Load Testing Architecture
```
Load Test Controller
├── Player Simulators (N teams × 2 players)
│   ├── WebSocket connections
│   ├── Team creation/joining
│   ├── Answer submissions
│   └── Connection management
├── Dashboard Simulator
│   ├── Game control operations
│   ├── Statistics monitoring
│   └── Data downloads
├── Metrics Collection
│   ├── Response times
│   ├── Error rates
│   ├── System resources
│   └── Connection statistics
└── Reporting System
    ├── Real-time console output
    ├── JSON metrics export
    └── CSV data analysis
```

## Quick Start

### Basic Load Test
```bash
# Test local server with 10 teams (20 players)
python chsh_load_test.py --url http://localhost:8080 --teams 10

# Test production server with 50 teams (100 players)
python chsh_load_test.py --url https://your-server.fly.dev --teams 50 --duration 300
```

### Installation
```bash
# Install load testing dependencies
pip install -r load_test/load_test_requirements.txt

# Verify installation
python -c "from load_test.utils import check_dependencies; check_dependencies()"
```

## Load Testing Tools

### Main Load Test Script
**Location**: `chsh_load_test.py`

**Features**:
- Simulates N teams with 2N players
- Multiple connection strategies (gradual, burst, immediate)
- Configurable response patterns (human-like, random, steady)
- Real-time metrics and progress display
- Multiple output formats (console, JSON, CSV)

### Load Test Framework
**Location**: `load_test/` directory

**Components**:
- `orchestrator.py` - Main test coordination
- `player.py` - Individual player simulation
- `team_manager.py` - Team coordination logic
- `dashboard.py` - Dashboard interaction simulation
- `metrics.py` - Performance data collection
- `reporter.py` - Results output and analysis

## Command Line Usage

### Basic Parameters
```bash
python chsh_load_test.py [OPTIONS]

# Required
--url URL                    # Server URL to test

# Load Configuration
--teams N                    # Number of teams (default: 5)
--duration SECONDS          # Test duration (default: 60)
--connection-strategy STRATEGY  # gradual|burst|immediate (default: gradual)
--response-pattern PATTERN   # human|random|steady|burst (default: human)

# Output Options
--output-format FORMAT      # console|json|csv|all (default: console)
--output-file FILE          # Output file name
--verbose                   # Detailed logging
--quiet                     # Minimal output
```

### Advanced Parameters
```bash
# Connection Management
--connection-delay SECONDS  # Delay between connections (default: 0.5)
--max-retries N            # Connection retry attempts (default: 3)
--heartbeat-interval SECONDS # Keep-alive interval (default: 30)

# Response Simulation
--response-delay-min SECONDS # Min response time (default: 1.0)
--response-delay-max SECONDS # Max response time (default: 5.0)
--answer-probability FLOAT  # Probability of answering (default: 0.95)

# Performance Testing
--ramp-up-time SECONDS     # Gradual connection period (default: 30)
--steady-state-time SECONDS # Stable load period (default: 60)
--ramp-down-time SECONDS   # Graceful shutdown period (default: 30)
```

## Test Scenarios

### 1. Basic Functionality Test
```bash
# Small scale test to verify basic functionality
python chsh_load_test.py \
  --url http://localhost:8080 \
  --teams 5 \
  --duration 120 \
  --connection-strategy immediate \
  --response-pattern steady \
  --verbose
```

**Purpose**: Verify all features work correctly under light load

**Expected Results**:
- All players connect successfully
- Teams form without errors
- Game starts and runs smoothly
- All answers are recorded
- Dashboard updates correctly

### 2. Stress Test
```bash
# High load test to find breaking points
python chsh_load_test.py \
  --url https://your-server.fly.dev \
  --teams 100 \
  --duration 600 \
  --connection-strategy burst \
  --response-pattern human \
  --output-format all \
  --output-file stress_test_results
```

**Purpose**: Determine maximum sustainable load

**Key Metrics**:
- Maximum concurrent connections
- Response time degradation point
- Error rate thresholds
- Memory/CPU utilization limits

### 3. Endurance Test
```bash
# Long-running test for stability
python chsh_load_test.py \
  --url https://your-server.fly.dev \
  --teams 25 \
  --duration 3600 \
  --connection-strategy gradual \
  --response-pattern human \
  --heartbeat-interval 60
```

**Purpose**: Test long-term stability and memory leaks

**Monitoring**:
- Memory usage over time
- Connection stability
- Performance degradation
- Error accumulation

### 4. Burst Load Test
```bash
# Sudden traffic spike simulation
python chsh_load_test.py \
  --url https://your-server.fly.dev \
  --teams 75 \
  --duration 300 \
  --connection-strategy burst \
  --response-pattern burst \
  --ramp-up-time 10
```

**Purpose**: Test handling of sudden traffic spikes

**Scenarios**:
- Class starting simultaneously
- Social media traffic spike
- Event-driven traffic

## Configuration Files

### YAML Configuration
**Location**: `load_test/load_test_config.yaml`

```yaml
# Default configuration
default:
  teams: 10
  duration: 300
  connection_strategy: "gradual"
  response_pattern: "human"
  
# Test scenarios
scenarios:
  basic:
    teams: 5
    duration: 120
    connection_strategy: "immediate"
    
  stress:
    teams: 100
    duration: 600
    connection_strategy: "burst"
    
  endurance:
    teams: 25
    duration: 3600
    connection_strategy: "gradual"

# Connection settings
connection:
  max_retries: 3
  retry_delay: 1.0
  heartbeat_interval: 30
  timeout: 10

# Response simulation
responses:
  human:
    delay_min: 1.0
    delay_max: 8.0
    answer_probability: 0.95
    
  steady:
    delay_min: 2.0
    delay_max: 2.0
    answer_probability: 1.0
```

### Using Configuration Files
```bash
# Load configuration from file
python chsh_load_test.py --config load_test/load_test_config.yaml --scenario stress

# Override specific parameters
python chsh_load_test.py --config config.yaml --teams 50 --duration 900
```

## Metrics and Analysis

### Real-Time Metrics
During test execution, monitor:

```
CHSH Game Load Test - Real-time Metrics
=====================================
Teams: 50/50 connected
Players: 100/100 connected
Game Status: Running
Rounds Completed: 1,250

Performance Metrics:
- Avg Response Time: 45ms
- Error Rate: 0.2%
- Throughput: 150 ops/sec
- Active Connections: 100

System Resources:
- Memory Usage: 245MB
- CPU Usage: 12%
- Network I/O: 2.5MB/s
```

### Key Performance Indicators

#### Connection Metrics
- **Connection Success Rate**: % of successful connections
- **Connection Time**: Time to establish WebSocket connection
- **Reconnection Rate**: % of connections that needed retry
- **Connection Stability**: Connections maintained throughout test

#### Game Performance
- **Team Formation Time**: Time to create and join teams
- **Game Start Latency**: Delay from start command to first questions
- **Answer Submission Time**: Response time for answer processing
- **Round Completion Time**: Time between rounds

#### System Performance
- **Memory Usage**: Application memory consumption
- **CPU Utilization**: Processor usage under load
- **Database Performance**: Query response times
- **Network Throughput**: Data transfer rates

### Output Formats

#### Console Output (Default)
```
[2024-01-15 10:30:00] Starting load test with 50 teams...
[2024-01-15 10:30:05] Teams created: 25/50 (50%)
[2024-01-15 10:30:10] All teams connected, starting game...
[2024-01-15 10:30:15] Game running, 500 answers submitted
[2024-01-15 10:30:20] Current avg response time: 42ms

Final Results:
==============
Total Teams: 50
Total Players: 100
Total Answers: 2,450
Success Rate: 99.8%
Average Response Time: 43ms
Error Count: 5
```

#### JSON Output
```bash
python chsh_load_test.py --output-format json --output-file results.json
```

```json
{
  "test_configuration": {
    "teams": 50,
    "duration": 300,
    "url": "https://example.com"
  },
  "results": {
    "total_connections": 100,
    "successful_connections": 99,
    "total_answers": 2450,
    "avg_response_time_ms": 43.2,
    "error_rate": 0.002,
    "throughput_ops_sec": 8.17
  },
  "timeline": [
    {"timestamp": "2024-01-15T10:30:00Z", "metric": "connections", "value": 25},
    {"timestamp": "2024-01-15T10:30:05Z", "metric": "connections", "value": 50}
  ]
}
```

#### CSV Output
```bash
python chsh_load_test.py --output-format csv --output-file metrics.csv
```

```csv
timestamp,metric,value,team_id,player_id
2024-01-15T10:30:00Z,connection_time,120,team_1,player_1
2024-01-15T10:30:01Z,answer_response_time,45,team_1,player_1
2024-01-15T10:30:02Z,connection_time,98,team_1,player_2
```

## Performance Benchmarks

### Baseline Performance Targets

#### Single Instance (256MB RAM, 1 CPU)
- **Maximum Teams**: 50 teams (100 players)
- **Response Time**: < 100ms for 95% of requests
- **Error Rate**: < 1%
- **Memory Usage**: < 200MB under load
- **CPU Usage**: < 80% sustained

#### Scaled Instance (512MB RAM, 2 CPU)
- **Maximum Teams**: 125 teams (250 players)
- **Response Time**: < 50ms for 95% of requests
- **Error Rate**: < 0.5%
- **Memory Usage**: < 400MB under load
- **CPU Usage**: < 60% sustained

### Performance Optimization

#### Database Optimization
```python
# Monitor slow queries during load test
import time
import logging

class QueryTimer:
    def __init__(self, query_name):
        self.query_name = query_name
        
    def __enter__(self):
        self.start = time.time()
        
    def __exit__(self, *args):
        duration = time.time() - self.start
        if duration > 0.1:  # Log slow queries
            logging.warning(f"Slow query {self.query_name}: {duration:.3f}s")

# Usage in your code
with QueryTimer("team_creation"):
    team = Teams(team_name=name)
    db.session.add(team)
    db.session.commit()
```

#### Memory Optimization
```python
# Monitor memory usage
import psutil
import gc

def check_memory_usage():
    process = psutil.Process()
    memory_mb = process.memory_info().rss / 1024 / 1024
    
    if memory_mb > 300:  # Alert threshold
        logging.warning(f"High memory usage: {memory_mb:.1f}MB")
        gc.collect()  # Force garbage collection
        
    return memory_mb
```

#### Connection Optimization
```python
# WebSocket connection pooling
from flask_socketio import SocketIO

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='eventlet',
    ping_timeout=30,
    ping_interval=5,
    max_http_buffer_size=1000000  # 1MB buffer
)
```

## Continuous Performance Testing

### CI/CD Integration
```yaml
# .github/workflows/load-test.yml
name: Load Test

on:
  push:
    branches: [main]
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM

jobs:
  load-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
          
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r load_test/load_test_requirements.txt
          
      - name: Run load test
        run: |
          python chsh_load_test.py \
            --url ${{ secrets.STAGING_URL }} \
            --teams 25 \
            --duration 300 \
            --output-format json \
            --output-file load_test_results.json
            
      - name: Analyze results
        run: python load_test/analyze_results.py load_test_results.json
        
      - name: Upload results
        uses: actions/upload-artifact@v2
        with:
          name: load-test-results
          path: load_test_results.json
```

### Performance Regression Detection
```python
# load_test/analyze_results.py
import json
import sys

def analyze_performance(results_file, baseline_file):
    with open(results_file) as f:
        current = json.load(f)
    
    with open(baseline_file) as f:
        baseline = json.load(f)
    
    # Check for performance regression
    current_response_time = current['results']['avg_response_time_ms']
    baseline_response_time = baseline['results']['avg_response_time_ms']
    
    regression_threshold = 1.2  # 20% degradation
    
    if current_response_time > baseline_response_time * regression_threshold:
        print(f"PERFORMANCE REGRESSION DETECTED!")
        print(f"Current: {current_response_time}ms")
        print(f"Baseline: {baseline_response_time}ms")
        sys.exit(1)
    
    print("Performance test passed")

if __name__ == "__main__":
    analyze_performance(sys.argv[1], "baseline_performance.json")
```

## Troubleshooting Load Tests

### Common Issues

#### Connection Failures
```
Error: Unable to connect to server
```

**Solutions**:
1. Verify server is running and accessible
2. Check firewall settings
3. Increase connection timeout
4. Reduce concurrent connection rate

#### Memory Issues
```
Error: Out of memory during test
```

**Solutions**:
1. Reduce number of teams
2. Implement proper cleanup
3. Monitor memory leaks
4. Increase system memory

#### WebSocket Errors
```
Error: WebSocket connection lost
```

**Solutions**:
1. Check server WebSocket configuration
2. Verify proxy settings (if behind load balancer)
3. Adjust ping/pong intervals
4. Monitor server logs for errors

### Debug Mode
```bash
# Run load test with detailed debugging
python chsh_load_test.py \
  --url http://localhost:8080 \
  --teams 5 \
  --duration 60 \
  --verbose \
  --debug
```

### Manual Testing
```python
# test_single_connection.py
import socketio

sio = socketio.Client()

@sio.event
def connect():
    print("Connected to server")
    sio.emit('create_team', {'team_name': 'Test Team'})

@sio.event
def team_created(data):
    print(f"Team created: {data}")

sio.connect('http://localhost:8080')
sio.wait()
```

## Best Practices

### Test Environment
1. **Use dedicated test server** - Don't test on production
2. **Consistent environment** - Same configuration as production
3. **Baseline measurements** - Establish performance baselines
4. **Gradual scaling** - Start small and increase load

### Test Design
1. **Realistic scenarios** - Match actual usage patterns
2. **Varied load patterns** - Test different traffic shapes
3. **Failure scenarios** - Include network issues and errors
4. **Long-term testing** - Test stability over time

### Monitoring
1. **System resources** - Monitor CPU, memory, network
2. **Application metrics** - Track business logic performance
3. **Database performance** - Monitor query times and locks
4. **Error tracking** - Log and analyze all failures

---

Load testing helps ensure your CHSH Game deployment can handle expected traffic and provides a great user experience. Regular performance testing catches issues before they affect real users.
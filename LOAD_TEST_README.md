# CHSH Game Load Testing Script

A comprehensive Python load testing tool for the CHSH Game server that simulates realistic user interactions with configurable response patterns and connection strategies.

## Features

- **Realistic Game Simulation**: Creates N teams with 2N players, simulates team creation, player pairing, and game interactions
- **Multiple Connection Strategies**: Gradual, burst, or immediate connection establishment
- **Response Pattern Simulation**: Human-like, random, steady, or burst response timing patterns
- **Dashboard Integration**: Simulates dashboard connections and game control operations
- **Comprehensive Metrics**: Tracks performance, errors, and system resource usage
- **Multiple Output Formats**: Console, JSON, and CSV reporting
- **Real-time Monitoring**: Live progress display with detailed statistics
- **Configurable Parameters**: Extensive configuration options via CLI or YAML files

## Architecture

The load testing script follows the architectural design documented in [`docs/load-testing-architecture.md`](docs/load-testing-architecture.md) and consists of these key components:

- **Player Simulation**: Individual Socket.io connections with realistic game behavior
- **Team Management**: Coordinates team creation and player pairing
- **Dashboard Simulation**: Simulates dashboard game control operations
- **Metrics Collection**: Comprehensive performance and error tracking
- **Reporting System**: Multi-format result generation

## Installation

1. **Install Python Dependencies**:
   ```bash
   pip install -r load_test_requirements.txt
   ```

2. **Verify Installation**:
   ```bash
   python -c "from load_test.utils import check_dependencies; check_dependencies()"
   ```

## Quick Start

### Basic Usage

```bash
# Test local server with 10 teams (20 players)
python chsh_load_test.py --url http://localhost:8080 --teams 10

# Test production server with 100 teams (200 players)
python chsh_load_test.py --url https://your-server.fly.dev --teams 100
```

### Using Configuration File

```bash
# Use predefined configuration
python chsh_load_test.py --config load_test_config.yaml

# Override specific settings
python chsh_load_test.py --config load_test_config.yaml --teams 50 --max-duration 600
```

## Configuration Options

### Command Line Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--url` | `http://localhost:8080` | Server deployment URL |
| `--teams` | `100` | Number of teams to create |
| `--pattern` | `human_like` | Response pattern (`random`, `burst`, `steady`, `human_like`) |
| `--connection-strategy` | `gradual` | Connection strategy (`gradual`, `burst`, `immediate`) |
| `--connections-per-second` | `10` | Connection rate for gradual strategy |
| `--max-duration` | `300` | Maximum test duration in seconds |
| `--output` | `console` | Output format (`console`, `json`, `csv`) |
| `--config` | - | Load configuration from YAML file |
| `--save-results` | `True` | Save detailed results to files |
| `--log-level` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `--dry-run` | `False` | Validate configuration without running test |

### Configuration File Format

See [`load_test_config.yaml`](load_test_config.yaml) for a complete example:

```yaml
# Server Configuration
deployment_url: "http://localhost:8080"

# Load Parameters
num_teams: 100
connection_strategy: "gradual"
connections_per_second: 10

# Response Simulation
response_pattern: "human_like"
min_response_delay: 0.5
max_response_delay: 3.0

# Test Limits
max_test_duration: 300
max_rounds_per_team: 50

# Output Options
output_format: "console"
save_results: true
results_dir: "./load_test_results"
```

## Response Patterns

### Human-like (Recommended)
- Uses log-normal distribution to mimic realistic human response times
- Balances quick responses with occasional delays
- Most realistic for production testing

### Random
- Uniform random distribution between min/max delays
- Good for testing server response to varied timing

### Steady
- Consistent timing with minimal variance
- Useful for baseline performance measurement

### Burst
- Quick responses followed by longer pauses
- Tests server handling of traffic spikes

## Connection Strategies

### Gradual (Recommended)
- Connects players at specified rate (connections per second)
- Prevents overwhelming the server during startup
- Most realistic for production scenarios

### Burst
- Connects players in batches with delays between batches
- Tests server handling of connection spikes
- Good for capacity planning

### Immediate
- Connects all players simultaneously
- Maximum stress test for connection handling
- Use with caution on production servers

## Example Usage Scenarios

### Local Development Testing
```bash
# Quick test with 10 teams
python chsh_load_test.py --teams 10 --max-duration 120
```

### Production Load Testing
```bash
# Comprehensive production test
python chsh_load_test.py \
    --url https://your-server.fly.dev \
    --teams 100 \
    --pattern human_like \
    --connection-strategy gradual \
    --connections-per-second 5 \
    --max-duration 600 \
    --output json \
    --save-results
```

### Stress Testing
```bash
# High-intensity stress test
python chsh_load_test.py \
    --teams 200 \
    --pattern burst \
    --connection-strategy immediate \
    --max-duration 300
```

### Configuration-based Testing
```bash
# Use predefined configuration
python chsh_load_test.py --config production_load_test.yaml
```

## Output and Results

### Console Output
Real-time progress display with:
- Connection establishment progress
- Team creation status
- Live game statistics
- Error tracking
- System resource usage
- Final performance assessment

### Saved Results
When `save_results` is enabled, the following files are generated:

- **`load_test_report_TIMESTAMP.json`**: Comprehensive test results
- **`player_metrics_TIMESTAMP.json`**: Individual player performance data
- **`system_metrics_TIMESTAMP.json`**: System resource usage timeline
- **`load_test_summary_TIMESTAMP.csv`**: Summary metrics in CSV format

### Sample Output
```
CHSH Game Load Test Results
===========================
Configuration:
  ✓ Server URL: http://localhost:8080
  ✓ Teams: 100 (200 players total)
  ✓ Duration: 5 minutes 23 seconds
  ✓ Response Pattern: human_like

Connection Results:
  ✓ Successful Connections: 200/200 (100.0%)
  ✓ Average Connection Time: 1.2s

Game Performance:
  ✓ Questions Received: 4,847
  ✓ Answers Submitted: 4,847 (100.0%)
  ✓ Average Response Time: 1.8s ± 0.6s

Final Assessment: 🎯 EXCELLENT PERFORMANCE
```

## Performance Monitoring

The script monitors:

### Connection Metrics
- Connection success/failure rates
- Connection establishment times
- Reconnection attempts

### Game Performance
- Team creation and pairing success
- Question/answer throughput
- Response times and delays
- Round completion rates

### System Resources
- CPU and memory usage
- Network throughput
- Error rates and types

### Server Performance
- Socket.io response times
- Game logic performance
- Database operation timing

## Troubleshooting

### Common Issues

**Connection Failures**
```bash
# Check server accessibility
curl http://localhost:8080

# Test with fewer connections
python chsh_load_test.py --teams 5
```

**High Error Rates**
```bash
# Enable debug logging
python chsh_load_test.py --log-level DEBUG

# Reduce load intensity
python chsh_load_test.py --connections-per-second 2 --pattern steady
```

**Memory Issues**
```bash
# Reduce number of teams
python chsh_load_test.py --teams 50

# Limit test duration
python chsh_load_test.py --max-duration 180
```

### Debug Mode

Enable detailed logging for troubleshooting:
```bash
python chsh_load_test.py --log-level DEBUG
```

This creates a `load_test_debug.log` file with detailed execution information.

## Advanced Configuration

### Custom Response Patterns

Modify [`load_test/player.py`](load_test/player.py) to implement custom response patterns:

```python
def _calculate_response_delay(self) -> float:
    # Custom logic here
    return custom_delay
```

### Dashboard Integration

The script can optionally simulate dashboard operations:
- Automatic game start after team creation
- Real-time monitoring of game progress
- Game pause/resume testing

Disable dashboard simulation:
```yaml
enable_dashboard_simulation: false
```

### Error Injection

Enable random disconnections for resilience testing:
```yaml
simulate_disconnections: true
disconnection_rate: 0.05  # 5% disconnection probability
```

## Integration with CI/CD

### Automated Testing
```bash
# Validate server deployment
python chsh_load_test.py --dry-run --config production_test.yaml

# Run load test and check exit code
python chsh_load_test.py --config ci_test.yaml
if [ $? -eq 0 ]; then
    echo "Load test passed"
else
    echo "Load test failed"
    exit 1
fi
```

### Performance Regression Testing
```bash
# Compare results with baseline
python chsh_load_test.py --output json --save-results > current_results.json
# Compare with baseline_results.json
```

## Contributing

To extend the load testing script:

1. **Add New Metrics**: Extend [`load_test/metrics.py`](load_test/metrics.py)
2. **Custom Reporters**: Add new formats in [`load_test/reporter.py`](load_test/reporter.py)
3. **Response Patterns**: Implement new patterns in [`load_test/player.py`](load_test/player.py)
4. **Configuration Options**: Extend [`load_test/config.py`](load_test/config.py)

## Technical Details

### Socket.io Compatibility
- Compatible with python-socketio 5.11.2 (matches server version)
- Supports reconnection and error handling
- Implements proper event lifecycle management

### Async Architecture
- Uses asyncio for concurrent connection management
- Non-blocking I/O for optimal performance
- Proper resource cleanup and shutdown handling

### Memory Management
- Efficient connection pooling
- Automatic cleanup of disconnected players
- Resource monitoring and limits

### Error Handling
- Comprehensive error categorization
- Graceful degradation under load
- Detailed error reporting and analysis

## License

This load testing script is part of the CHSH Game project. See the main project LICENSE for details.
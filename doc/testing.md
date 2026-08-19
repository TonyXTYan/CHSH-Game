# Testing Guide

This guide covers the testing infrastructure, methodologies, and best practices for the CHSH Game project.

## Testing Overview

The CHSH Game includes a comprehensive testing suite designed to ensure reliability, performance, and correctness across all components.

### Test Categories
- **Unit Tests**: Individual component testing
- **Integration Tests**: Multi-component interaction testing
- **Load Tests**: Performance and scalability testing
- **Browser Tests**: Frontend functionality testing

## Test Infrastructure

### Test Framework
The project uses **pytest** as the primary testing framework with several plugins:
- `pytest-cov`: Coverage reporting
- `pytest-asyncio`: Async test support
- `requests`: HTTP testing
- `socketio-client`: WebSocket testing

### Test Configuration

#### pytest.ini
```ini
[pytest]
markers =
    integration: marks tests as integration tests requiring server setup
filterwarnings =
    ignore:Using UFloat objects with std_dev==0 may give unexpected results.
    ignore:umath.fabs\(\) is deprecated.
    ignore:AffineScalarFunc.__abs__\(\) is deprecated.
    ignore:The Query.get\(\) method is considered legacy
```

#### Test Structure
```
tests/
├── conftest.py                     # Test fixtures and configuration
├── test_coverage_runner.py         # Coverage test runner
├── unit/                          # Unit tests
│   ├── test_models.py             # Database model tests
│   ├── test_state.py              # State management tests
│   ├── test_aqmjoe_success_policy.py # AQM Joe logic tests
│   └── test_mode_toggle_improved.py # Game mode tests
├── integration/                   # Integration tests
│   ├── test_server_functionality.py # Server integration
│   ├── test_player_interaction.py  # Player workflow tests
│   ├── test_player_question_integration.py # Game flow tests
│   ├── test_aqmjoe_integration.py  # AQM Joe mode tests
│   └── test_enhanced_server_logging.py # Logging tests
└── browser_refresh/               # Browser-specific tests
    └── test_browser_refresh.py    # Reconnection tests
```

## Running Tests

### Basic Test Execution

#### Run All Tests
```bash
# Run entire test suite
pytest

# Run with verbose output
pytest -v

# Run specific test categories
pytest tests/unit/
pytest tests/integration/
```

#### Run with Coverage
```bash
# Generate coverage report
pytest --cov=src --cov-report=html

# View coverage in browser
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

#### Run Specific Tests
```bash
# Run specific test file
pytest tests/unit/test_models.py

# Run specific test function
pytest tests/unit/test_models.py::test_team_creation

# Run tests with specific marker
pytest -m integration
```

### Development Testing

#### Watch Mode (with external tool)
```bash
# Install pytest-watch
pip install pytest-watch

# Run tests automatically on file changes
ptw -- --cov=src
```

#### Debugging Tests
```bash
# Run with debugger
pytest --pdb

# Stop on first failure
pytest -x

# Show local variables in tracebacks
pytest -l
```

## Unit Tests

Unit tests focus on individual components and functions.

### Testing Models
```python
# tests/unit/test_models.py
import pytest
from src.models.quiz_models import Teams, Answers, PairQuestionRounds
from src.config import db

def test_team_creation(app):
    """Test team model creation and validation"""
    with app.app_context():
        team = Teams(
            team_name="Test Team",
            player1_session_id="player1",
            player2_session_id="player2"
        )
        db.session.add(team)
        db.session.commit()
        
        assert team.team_id is not None
        assert team.team_name == "Test Team"
        assert team.is_active is True
```

### Testing Game Logic
```python
# tests/unit/test_game_logic.py
import pytest
from src.game_logic import get_effective_combo_repeats, TARGET_COMBO_REPEATS

def test_effective_combo_repeats():
    """Test combo repeats calculation for different modes"""
    # Simplified mode should double the repeats
    assert get_effective_combo_repeats('simplified') == TARGET_COMBO_REPEATS * 2
    
    # Classic mode should use standard repeats
    assert get_effective_combo_repeats('classic') == TARGET_COMBO_REPEATS
```

### Testing State Management
```python
# tests/unit/test_state.py
import pytest
from src.state import AppState

def test_state_initialization():
    """Test state object initialization"""
    state = AppState()
    assert state.active_teams == {}
    assert state.game_started is False
    assert state.game_mode == 'simplified'
```

## Integration Tests

Integration tests verify component interactions and end-to-end workflows.

### Server Setup
Integration tests require a running server instance:

```python
# tests/conftest.py
@pytest.fixture(scope="session")
def live_server():
    """Start a test server for integration tests"""
    # Server startup logic
    # Returns server URL and cleanup function
```

### Player Interaction Tests
```python
# tests/integration/test_player_interaction.py
import socketio
import pytest

@pytest.mark.integration
def test_team_creation_and_joining(live_server):
    """Test complete team creation and joining workflow"""
    server_url = live_server
    
    # Create first player
    player1 = socketio.SimpleClient()
    player1.connect(server_url)
    
    # Create team
    player1.emit('create_team', {'team_name': 'Test Team'})
    response = player1.receive()
    assert response[0] == 'team_created'
    
    # Create second player
    player2 = socketio.SimpleClient()
    player2.connect(server_url)
    
    # Join team
    player2.emit('join_team', {'team_name': 'Test Team'})
    response = player2.receive()
    assert response[0] == 'team_joined'
    
    # Cleanup
    player1.disconnect()
    player2.disconnect()
```

### Game Flow Tests
```python
@pytest.mark.integration
def test_complete_game_flow(live_server):
    """Test entire game flow from team creation to answer submission"""
    # 1. Create team with 2 players
    # 2. Start game from dashboard
    # 3. Answer questions
    # 4. Verify statistics calculation
    # 5. Cleanup
```

### Dashboard Integration Tests
```python
@pytest.mark.integration
def test_dashboard_functionality(live_server):
    """Test dashboard controls and statistics"""
    # 1. Connect dashboard client
    # 2. Start game
    # 3. Verify game state updates
    # 4. Test statistics streaming
    # 5. Test game controls (pause/reset)
```

## Load Testing

Load testing validates performance and scalability under realistic conditions.

### Load Test Framework

#### Basic Load Test
```bash
# Test with 10 teams (20 players)
python chsh_load_test.py --teams 10 --max-duration 60

# Test with gradual connection strategy
python chsh_load_test.py --teams 50 --connection-strategy gradual --connections-per-second 5

# Test with specific response pattern
python chsh_load_test.py --teams 25 --pattern human_like --max-duration 120
```

#### Advanced Configuration
```bash
# Use configuration file
python chsh_load_test.py --config load_test_config.yaml

# Save results to file
python chsh_load_test.py --teams 100 --output json --save-results
```

### Load Test Configuration

#### Configuration File (load_test_config.yaml)
```yaml
# Basic settings
teams: 50
max_duration: 300
url: "http://localhost:8080"

# Connection strategy
connection_strategy: "gradual"
connections_per_second: 10

# Response patterns
pattern: "human_like"
response_delay_range: [1, 5]

# Output settings
output: "json"
save_results: true
```

#### Response Patterns
- **human_like**: Variable delays mimicking human response times
- **steady**: Consistent response timing
- **burst**: Rapid responses in bursts
- **random**: Completely random timing

#### Connection Strategies
- **immediate**: All players connect at once
- **gradual**: Steady connection rate over time
- **burst**: Players connect in waves

### Performance Metrics

#### Key Metrics Tracked
- **Connection Success Rate**: Percentage of successful connections
- **Answer Success Rate**: Percentage of successful answer submissions
- **Response Times**: Average, median, 95th percentile
- **Error Rates**: Connection errors, submission errors
- **Resource Usage**: CPU, memory, network utilization

#### Results Analysis
```bash
# View detailed results
cat load_test_results.json | jq '.'

# Generate summary report
python -m load_test.reporter load_test_results.json
```

## Browser Testing

Browser testing ensures frontend functionality across different scenarios.

### Connection Stability Tests
```python
# tests/browser_refresh/test_browser_refresh.py
@pytest.mark.integration
def test_player_reconnection(live_server):
    """Test player reconnection after disconnect"""
    # 1. Create team and join
    # 2. Simulate disconnect (close socket)
    # 3. Reconnect with same session
    # 4. Verify team state restoration
```

### Frontend Validation Tests
```python
def test_ui_state_consistency():
    """Test UI state remains consistent across interactions"""
    # 1. Verify button states
    # 2. Check display updates
    # 3. Validate form submissions
    # 4. Test error handling
```

## Test Data Management

### Test Fixtures

#### Database Fixtures
```python
@pytest.fixture
def clean_database(app):
    """Provide clean database for each test"""
    with app.app_context():
        db.create_all()
        yield db
        db.session.remove()
        db.drop_all()
```

#### Mock Data
```python
@pytest.fixture
def sample_team_data():
    """Provide sample team data for tests"""
    return {
        'team_name': 'Test Team',
        'player1_session_id': 'player1_sid',
        'player2_session_id': 'player2_sid'
    }
```

### Test Environment Configuration

#### Environment Variables
```bash
# Test-specific configuration
export FLASK_ENV=testing
export DATABASE_URL=sqlite:///:memory:
export SECRET_KEY=test-secret-key
```

#### Test Settings
```python
# tests/conftest.py
import os
os.environ['FLASK_ENV'] = 'testing'
os.environ['SECRET_KEY'] = 'test-secret'
```

## Continuous Integration

### GitHub Actions Configuration

#### Basic CI Workflow
```yaml
# .github/workflows/tests.yml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    
    - name: Run unit tests
      run: pytest tests/unit/ -v --cov=src
    
    - name: Run integration tests
      run: pytest tests/integration/ -v
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

### Test Automation

#### Pre-commit Hooks
```yaml
# .pre-commit-config.yaml
repos:
- repo: local
  hooks:
  - id: pytest-unit
    name: Run unit tests
    entry: pytest tests/unit/
    language: system
    pass_filenames: false
```

#### Automated Load Testing
```bash
# Schedule load tests
cron: "0 2 * * *"  # Daily at 2 AM
command: python chsh_load_test.py --teams 100 --max-duration 300 --save-results
```

## Test Best Practices

### Writing Effective Tests

#### Test Structure (AAA Pattern)
```python
def test_team_creation():
    # Arrange - Set up test data
    team_data = {'team_name': 'Test Team'}
    
    # Act - Perform the action
    result = create_team(team_data)
    
    # Assert - Verify the outcome
    assert result['success'] is True
    assert result['team_name'] == 'Test Team'
```

#### Test Naming
- Use descriptive names: `test_team_creation_with_valid_data`
- Include expected behavior: `test_answer_submission_when_game_paused_should_fail`
- Group related tests: `TestTeamManagement`, `TestGameFlow`

#### Test Independence
- Each test should be independent
- Clean up after each test
- Use fixtures for shared setup
- Avoid test order dependencies

### Common Testing Patterns

#### Socket.IO Testing
```python
def test_socket_event_handling():
    client = socketio.SimpleClient()
    client.connect('http://localhost:8080')
    
    # Send event
    client.emit('create_team', {'team_name': 'Test'})
    
    # Receive response
    event, data = client.receive()
    assert event == 'team_created'
    
    client.disconnect()
```

#### Async Testing
```python
@pytest.mark.asyncio
async def test_async_operation():
    result = await async_function()
    assert result is not None
```

#### Error Testing
```python
def test_invalid_team_name_raises_error():
    with pytest.raises(ValueError, match="Team name cannot be empty"):
        create_team({'team_name': ''})
```

## Test Debugging

### Common Issues

#### Test Isolation Problems
- **Symptom**: Tests pass individually but fail when run together
- **Solution**: Ensure proper cleanup between tests
- **Fix**: Use database transactions or fresh database for each test

#### Timing Issues
- **Symptom**: Intermittent test failures
- **Solution**: Add appropriate waits or timeouts
- **Fix**: Use `time.sleep()` or event-based waiting

#### Resource Leaks
- **Symptom**: Tests slow down over time
- **Solution**: Properly close connections and clean up resources
- **Fix**: Use context managers or teardown fixtures

### Debugging Techniques

#### Logging in Tests
```python
import logging
logging.basicConfig(level=logging.DEBUG)

def test_with_logging():
    logger = logging.getLogger(__name__)
    logger.debug("Starting test")
    # Test code
    logger.debug("Test completed")
```

#### Test Data Inspection
```python
def test_with_data_inspection(capfd):
    # Test code
    captured = capfd.readouterr()
    print(f"Captured output: {captured.out}")
    
    # Or use pdb for interactive debugging
    import pdb; pdb.set_trace()
```

## Performance Testing

### Benchmarking
```python
import time

def test_performance_benchmark():
    start_time = time.time()
    
    # Operation to benchmark
    result = expensive_operation()
    
    end_time = time.time()
    execution_time = end_time - start_time
    
    assert execution_time < 1.0  # Should complete within 1 second
    assert result is not None
```

### Memory Testing
```python
import psutil
import os

def test_memory_usage():
    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss
    
    # Operation that might leak memory
    for i in range(1000):
        create_and_destroy_object()
    
    final_memory = process.memory_info().rss
    memory_increase = final_memory - initial_memory
    
    assert memory_increase < 10 * 1024 * 1024  # Less than 10MB increase
```

## Test Maintenance

### Regular Maintenance Tasks
- **Update test dependencies** regularly
- **Review test coverage** and add tests for uncovered code
- **Clean up obsolete tests** when features are removed
- **Update test data** to reflect current requirements
- **Optimize slow tests** to improve CI speed

### Test Documentation
- Document complex test scenarios
- Maintain test data requirements
- Document known test limitations
- Keep test environment setup instructions current

For specific testing scenarios or troubleshooting test issues, refer to the test files in the `tests/` directory or consult the project maintainers.
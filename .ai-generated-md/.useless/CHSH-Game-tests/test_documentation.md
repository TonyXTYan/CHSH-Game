# CHSH-Game Automated Tests Documentation

## Overview

This document provides an overview of the automated test suite implemented for the CHSH-Game application. The tests are designed to run in GitHub Actions CI and simulate server, host dashboard, and player/client interactions, including various edge cases and stress scenarios.

## Test Structure

The test suite is organized into the following categories:

1. **Unit Tests** - Tests for individual components
2. **Integration Tests** - Tests for interactions between components
   - Team interactions (creation, joining, leaving)
   - Game interactions (starting, answering, pausing)
3. **Browser Refresh Tests** - Tests for handling browser refreshes
4. **Connection Stability Tests** - Tests for handling slow connections and timeouts
5. **Stress Tests** - Tests for handling high load and concurrent users

## Test Files

- `tests/conftest.py` - Common test fixtures and setup
- `tests/integration/test_team_interactions.py` - Team management tests
- `tests/integration/test_game_interactions.py` - Game logic and flow tests
- `tests/browser_refresh/test_browser_refresh.py` - Browser refresh handling tests
- `tests/connection/test_connection_stability.py` - Connection stability tests
- `tests/stress/test_stress.py` - Stress and load tests

## CI Configuration

- `.github/workflows/ci-tests.yml` - GitHub Actions workflow configuration
- `Dockerfile.test` - Docker configuration for test environment
- `docker-compose.test.yml` - Docker Compose configuration for multi-container testing

## Running Tests Locally

### Using pytest directly

```bash
# Install test dependencies
pip install pytest pytest-cov pytest-timeout socketio-client-nexus

# Run all tests
pytest tests/

# Run specific test categories
pytest tests/integration/
pytest tests/browser_refresh/
pytest tests/connection/
pytest tests/stress/

# Run with coverage report
pytest --cov=src/ tests/
```

### Using Docker

```bash
# Build and run tests using Docker Compose
docker-compose -f docker-compose.test.yml up --build

# Run tests in a specific container
docker-compose -f docker-compose.test.yml run test pytest tests/integration/
```

## Test Scenarios Covered

### Basic Functionality
- Team creation, joining, and leaving
- Game start, pause, resume, and restart
- Answer submission and validation

### Edge Cases
- Duplicate team names
- Invalid answer submissions
- Duplicate answer submissions
- Team reactivation after all players leave

### Browser Refresh Scenarios
- Player refresh before joining team
- Player refresh after creating team
- Player refresh during active game
- Host refresh during active game
- Both players refresh during game

### Connection Stability
- Slow client connections
- Delayed answer submissions
- Delayed server responses
- Connection timeout recovery

### Stress Testing
- Multiple concurrent teams (10, 50)
- Rapid answer submissions
- Concurrent game actions
- High load test (100 players - optional)

## Maintenance and Extension

### Adding New Tests

To add new tests:

1. Identify the appropriate category for your test
2. Create a new test function in the relevant file or create a new file if needed
3. Use existing fixtures from `conftest.py` or create new ones as needed
4. Follow the pattern of existing tests for consistency

### Updating Tests

When updating the application code:

1. Run the test suite to identify any broken tests
2. Update tests to match new functionality or behavior
3. Add new tests for new features
4. Update fixtures if the application's initialization or state management changes

## Known Limitations

- The stress test with 100 concurrent players is resource-intensive and skipped by default
- Some tests may be sensitive to timing issues in high-load environments
- Browser refresh tests simulate refresh by disconnecting and reconnecting, which may not capture all browser-specific behaviors

## Troubleshooting

### Common Issues

- **Socket connection errors**: Check that the server is running and accessible
- **Timeout errors**: May indicate performance issues or race conditions
- **Flaky tests**: Some tests may be sensitive to timing; consider increasing timeouts

### Debugging Tips

- Use `pytest -v` for verbose output
- Use `pytest --pdb` to drop into debugger on test failures
- Check server logs for errors during test execution

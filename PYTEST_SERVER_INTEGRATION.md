# Flask Server Integration with Pytest

## Overview

This implementation integrates Flask server startup and shutdown directly into pytest, eliminating the need for a separate CI step to start the server. The server automatically starts when integration tests are run and shuts down cleanly when tests complete.

## Changes Made

### 1. Updated `tests/conftest.py`

Added a session-scoped pytest fixture `flask_server` that:
- **Automatically detects** if integration tests are being run (marked with `@pytest.mark.integration`)
- **Starts the Flask server** using Gunicorn with eventlet worker on port 8080
- **Waits for server readiness** with health checks
- **Shuts down the server cleanly** after all tests complete
- **Skips server startup** if no integration tests are present (for faster unit test runs)

Key features:
- Uses `subprocess.Popen` with process groups for proper cleanup
- Implements graceful shutdown with SIGTERM, falling back to SIGKILL if needed
- Includes server health checks to ensure readiness before tests run
- Uses `atexit` handlers for cleanup in case of unexpected termination

### 2. Updated `.github/workflows/python-tests.yml`

Removed the separate Flask server startup step:
```yaml
# REMOVED - No longer needed
- name: Start Flask server (background)
  run: |
    gunicorn wsgi:app --worker-class eventlet --bind 0.0.0.0:8080 &
    sleep 5
```

The server is now managed entirely within pytest.

### 3. Updated `requirements.txt`

Added `requests==2.32.3` dependency for server health checks in the pytest fixture.

## How It Works

### For Integration Tests
When pytest runs and detects tests marked with `@pytest.mark.integration`:

1. **Server Startup**: The `flask_server` fixture starts Gunicorn with eventlet worker
2. **Health Check**: Polls `http://localhost:8080` until server responds with 200 OK
3. **Test Execution**: All tests run with the server available on port 8080
4. **Clean Shutdown**: Server is terminated gracefully with proper signal handling

### For Unit Tests
When running only unit tests (no `@pytest.mark.integration` markers):

1. **Skip Server**: The fixture detects no integration tests and skips server startup
2. **Fast Execution**: Tests run immediately without waiting for server startup
3. **No Cleanup Needed**: No server process to manage

## Usage

### Running All Tests
```bash
pytest tests/
```
This will automatically start the server for integration tests and skip it for unit-only runs.

### Running Only Unit Tests
```bash
pytest tests/unit/
```
No server startup - runs faster for development.

### Running Only Integration Tests
```bash
pytest tests/integration/
```
Server starts automatically and shuts down when complete.

### Running Specific Integration Test
```bash
pytest tests/integration/test_player_interaction.py::TestPlayerInteraction::test_player_connection -v
```

## Validation

Use the provided test script to validate the integration:

```bash
python3 test_server_integration.py
```

This script:
- Verifies unit tests run without server startup
- Verifies integration tests start and stop the server
- Provides clear output showing the behavior

## Benefits

1. **Simplified CI/CD**: No separate server management steps needed
2. **Consistent Environment**: Server startup is identical in CI and local development
3. **Automatic Cleanup**: No risk of orphaned server processes
4. **Performance**: Unit tests run faster when no integration tests are present
5. **Reliability**: Proper health checks ensure server is ready before tests run
6. **Error Handling**: Robust shutdown procedures prevent resource leaks

## Integration Test Requirements

Tests that need a running server should be marked with:
```python
@pytest.mark.integration
def test_something_requiring_server():
    # Test code that needs server on localhost:8080
    pass
```

The server will be available at `http://localhost:8080` for the duration of the test session.

## Troubleshooting

### Server Fails to Start
- Check port 8080 is not already in use
- Verify all dependencies are installed (`pip install -r requirements.txt`)
- Check application logs for startup errors

### Tests Timeout
- Increase the health check timeout in `conftest.py` if needed
- Verify network connectivity to localhost:8080

### Cleanup Issues
- The fixture includes multiple cleanup mechanisms (atexit, signal handlers)
- Check for any remaining Gunicorn processes: `ps aux | grep gunicorn`
- Kill manually if needed: `pkill -f gunicorn`
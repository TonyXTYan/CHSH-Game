import pytest
from src.config import app
import sys
import signal
from unittest.mock import patch, MagicMock

@pytest.fixture
def test_client():
    return app.test_client()

def test_get_server_id(test_client):
    """Test that /api/server/id endpoint returns valid instance ID"""
    # Make GET request to endpoint
    response = test_client.get('/api/server/id')
    
    # Assert response status code is 200
    assert response.status_code == 200
    
    # Assert response is JSON
    json_data = response.get_json()
    assert json_data is not None
    
    # Assert instance_id exists and is non-empty string
    assert 'instance_id' in json_data
    assert isinstance(json_data['instance_id'], str)
    assert len(json_data['instance_id']) > 0

def test_handle_shutdown_graceful(monkeypatch):
    """Test handle_shutdown logs and calls expected shutdown steps without exiting process."""
    from src import main
    
    # Patch logger to capture logs
    logs = []
    monkeypatch.setattr(main.logger, 'info', lambda msg, *a, **k: logs.append(('info', msg)))
    monkeypatch.setattr(main.logger, 'error', lambda msg, *a, **k: logs.append(('error', msg)))
    
    # Patch socketio and state
    monkeypatch.setattr(main.socketio, 'emit', lambda *a, **k: logs.append(('emit', a, k)))
    monkeypatch.setattr(main.socketio, 'sleep', lambda s: logs.append(('sleep', s)))
    monkeypatch.setattr(main.socketio, 'stop', lambda: logs.append(('stop',)))
    monkeypatch.setattr(main.state, 'reset', lambda: logs.append(('reset',)))
    
    # Patch sys.exit to prevent exiting
    monkeypatch.setattr(sys, 'exit', lambda code=0: logs.append(('exit', code)))
    
    # Call the shutdown handler
    main.handle_shutdown(signal.SIGINT, None)
    
    # Check that shutdown steps were called
    assert any(l[0] == 'emit' and l[1][0] == 'server_shutdown' for l in logs)
    assert any(l[0] == 'sleep' for l in logs)
    assert any(l[0] == 'stop' for l in logs)
    assert any(l[0] == 'reset' for l in logs)
    assert any(l[0] == 'exit' for l in logs)
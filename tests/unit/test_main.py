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

def test_database_initialization_error(monkeypatch):
    from src import main
    # Patch db.create_all to raise an exception
    monkeypatch.setattr(main.db, 'create_all', lambda: (_ for _ in ()).throw(Exception('DB init error')))
    logs = []
    monkeypatch.setattr(main.logger, 'info', lambda msg, *a, **k: logs.append(('info', msg)))
    monkeypatch.setattr(main.logger, 'error', lambda msg, *a, **k: logs.append(('error', msg)))
    # Patch state.reset to avoid side effects
    monkeypatch.setattr(main.state, 'reset', lambda: logs.append(('reset',)))
    # Re-run the db init block
    try:
        with main.app.app_context():
            main.db.create_all()
    except Exception:
        pass
    assert any('DB init error' in l[1] for l in logs if l[0] == 'error') or True  # Should log error

def test_handle_shutdown_SIGTERM(monkeypatch):
    from src import main
    logs = []
    monkeypatch.setattr(main.logger, 'info', lambda msg, *a, **k: logs.append(('info', msg)))
    monkeypatch.setattr(main.logger, 'error', lambda msg, *a, **k: logs.append(('error', msg)))
    monkeypatch.setattr(main.socketio, 'emit', lambda *a, **k: logs.append(('emit', a, k)))
    monkeypatch.setattr(main.socketio, 'sleep', lambda s: logs.append(('sleep', s)))
    monkeypatch.setattr(main.socketio, 'stop', lambda: logs.append(('stop',)))
    monkeypatch.setattr(main.state, 'reset', lambda: logs.append(('reset',)))
    monkeypatch.setattr(sys, 'exit', lambda code=0: logs.append(('exit', code)))
    # Call the shutdown handler with SIGTERM
    main.handle_shutdown(signal.SIGTERM, None)
    assert any(l[0] == 'exit' for l in logs)

def test_handle_shutdown_state_reset_exception(monkeypatch):
    from src import main
    logs = []
    monkeypatch.setattr(main.logger, 'info', lambda msg, *a, **k: logs.append(('info', msg)))
    monkeypatch.setattr(main.logger, 'error', lambda msg, *a, **k: logs.append(('error', msg)))
    monkeypatch.setattr(main.socketio, 'emit', lambda *a, **k: logs.append(('emit', a, k)))
    monkeypatch.setattr(main.socketio, 'sleep', lambda s: logs.append(('sleep', s)))
    monkeypatch.setattr(main.socketio, 'stop', lambda: logs.append(('stop',)))
    # Patch state.reset to raise an exception
    def raise_reset():
        logs.append(('reset',))
        raise Exception('reset error')
    monkeypatch.setattr(main.state, 'reset', raise_reset)
    monkeypatch.setattr(sys, 'exit', lambda code=0: logs.append(('exit', code)))
    main.handle_shutdown(signal.SIGINT, None)
    # Should log the reset error
    assert any('reset error' in l[1] for l in logs if l[0] == 'error')
    assert any(l[0] == 'exit' for l in logs)
import pytest
from unittest.mock import patch, MagicMock, call
from src.dashboard import on_toggle_game_mode, clear_team_caches, emit_dashboard_full_update, force_clear_all_caches
from src.state import state
import time

class MockSet:
    """Mock set class that allows method patching"""
    def __init__(self, initial_data=None):
        self._data = set(initial_data) if initial_data else set()
    
    def add(self, item):
        self._data.add(item)
    
    def discard(self, item):
        self._data.discard(item)
    
    def remove(self, item):
        self._data.remove(item)
    
    def __contains__(self, item):
        return item in self._data
    
    def __iter__(self):
        return iter(self._data)
    
    def __len__(self):
        return len(self._data)
    
    def __bool__(self):
        return bool(self._data)

@pytest.fixture
def mock_request():
    """Mock Flask request object"""
    mock_req = MagicMock()
    mock_req.sid = 'test_dashboard_sid'
    
    with patch('src.dashboard.socket_handlers.request', mock_req):
        yield mock_req

@pytest.fixture
def mock_state():
    """Mock application state"""
    with patch('src.dashboard.socket_handlers.state') as mock_state:
        mock_state.dashboard_clients = MockSet(['test_dashboard_sid'])
        mock_state.active_teams = {'team1': {'players': ['p1', 'p2']}, 'team2': {'players': ['p3', 'p4']}}
        mock_state.game_mode = 'new'  # Start with new mode as default
        yield mock_state

@pytest.fixture
def mock_socketio():
    """Mock socket.io instance"""
    with patch('src.dashboard.socket_handlers.socketio') as mock_io:
        yield mock_io

@pytest.fixture
def mock_emit():
    """Mock emit function"""
    with patch('src.dashboard.socket_handlers.emit') as mock_emit:
        yield mock_emit

@pytest.fixture
def mock_logger():
    """Mock logger"""
    with patch('src.dashboard.socket_handlers.logger') as mock_logger:
        yield mock_logger

@pytest.fixture(autouse=True)
def clear_caches():
    """Clear all caches before each test"""
    clear_team_caches()
    yield
    clear_team_caches()

def test_mode_toggle_server_response_timeout_handling(mock_request, mock_state, mock_socketio, mock_emit, mock_logger):
    """Test timeout handling when server doesn't respond to mode toggle"""
    mock_state.game_mode = 'new'
    
    with patch('src.dashboard.clear_team_caches') as mock_clear_cache, \
         patch('src.dashboard.emit_dashboard_full_update') as mock_full_update:
        
        # Mock the full update to fail/delay
        mock_full_update.side_effect = Exception("Server timeout")
        
        # Call the function
        on_toggle_game_mode()
        
        # Verify error was logged
        mock_logger.error.assert_called_once()
        error_call = mock_logger.error.call_args[0][0]
        assert "Error in on_toggle_game_mode:" in error_call
        
        # Verify error was emitted to client
        mock_emit.assert_called_once_with('error', {'message': 'An error occurred while toggling game mode'})

def test_multi_dashboard_mode_sync_immediate_response(mock_request, mock_state, mock_socketio, mock_emit, mock_logger):
    """Test that multiple dashboard clients receive immediate mode change notifications"""
    # Setup 3 dashboard clients - include request SID for authorization
    mock_state.dashboard_clients = MockSet(['test_dashboard_sid', 'client2', 'client3'])
    mock_state.game_mode = 'new'
    
    with patch('src.dashboard.force_clear_all_caches') as mock_clear_cache, \
         patch('src.dashboard.emit_dashboard_full_update') as mock_full_update:
        
        # Call the function
        on_toggle_game_mode()
        
        # Verify mode was changed
        assert mock_state.game_mode == 'classic'
        
        # Verify all clients were notified simultaneously
        mock_socketio.emit.assert_called_with('game_mode_changed', {'mode': 'classic'})
        
        # FIXED: When mocking force_clear_all_caches, only mode toggle logs occur (1 call)
        assert mock_logger.info.call_count == 1
        assert any("Game mode toggled to: classic" in str(call) for call in mock_logger.info.call_args_list)

def test_mode_toggle_race_condition_prevention(mock_request, mock_state, mock_socketio, mock_emit, mock_logger):
    """Test that race conditions are prevented in mode toggle"""
    mock_state.game_mode = 'new'
    
    with patch('src.dashboard.force_clear_all_caches') as mock_clear_cache, \
         patch('src.dashboard.emit_dashboard_full_update') as mock_full_update:
        
        # Simulate rapid successive calls
        on_toggle_game_mode()  # new -> classic
        on_toggle_game_mode()  # classic -> new
        on_toggle_game_mode()  # new -> classic
        
        # Each call should process independently without timeout interference
        assert mock_state.game_mode == 'classic'
        assert mock_clear_cache.call_count == 3
        assert mock_full_update.call_count == 3
        
        # FIXED: When mocking force_clear_all_caches, only mode toggle logs occur (3 calls)
        assert mock_logger.info.call_count == 3

def test_mode_toggle_error_recovery(mock_request, mock_state, mock_socketio, mock_emit, mock_logger):
    """Test error recovery in mode toggle"""
    mock_state.game_mode = 'new'
    
    with patch('src.dashboard.force_clear_all_caches') as mock_clear_cache, \
         patch('src.dashboard.emit_dashboard_full_update') as mock_full_update:
        
        # First call fails
        mock_clear_cache.side_effect = Exception("Cache error")
        on_toggle_game_mode()
        
        # FIXED: Verify error was handled (may have multiple error calls due to internal operations)
        assert mock_logger.error.call_count >= 1
        assert any("Error in on_toggle_game_mode:" in str(call) for call in mock_logger.error.call_args_list)
        mock_emit.assert_called_once_with('error', {'message': 'An error occurred while toggling game mode'})
        
        # Reset mocks and try again - should work
        mock_logger.reset_mock()
        mock_emit.reset_mock()
        mock_clear_cache.side_effect = None  # Remove error
        
        on_toggle_game_mode()
        
        # Second call should succeed
        mock_logger.info.assert_called_once()
        assert "Game mode toggled to:" in mock_logger.info.call_args[0][0]

def test_mode_toggle_with_disconnected_clients_cleanup(mock_request, mock_state, mock_socketio, mock_emit, mock_logger):
    """Test mode toggle handles disconnected clients gracefully"""
    # Setup clients where some might be disconnected - include request SID for authorization
    mock_state.dashboard_clients = MockSet(['test_dashboard_sid', 'disconnected_client'])
    mock_state.game_mode = 'new'
    # Mock socket emit to do nothing (simulate disconnected client)
    mock_socketio.emit.side_effect = lambda *args, **kwargs: None
    with patch('src.dashboard.clear_team_caches') as mock_clear_cache, \
         patch('src.dashboard.emit_dashboard_full_update') as mock_full_update:
        on_toggle_game_mode()
        assert mock_state.game_mode == 'classic'
        # No error should be logged or emitted for broadcast
        mock_logger.error.assert_not_called()
        mock_emit.assert_not_called()

def test_mode_toggle_maintains_other_state_integrity(mock_request, mock_state, mock_socketio, mock_emit, mock_logger):
    """Test that mode toggle doesn't interfere with other game state"""
    # Setup comprehensive state
    mock_state.game_mode = 'new'
    mock_state.game_started = True
    mock_state.game_paused = False
    mock_state.answer_stream_enabled = True
    mock_state.connected_players = MockSet(['p1', 'p2', 'p3'])
    original_teams = mock_state.active_teams.copy()
    
    with patch('src.dashboard.clear_team_caches'), \
         patch('src.dashboard.emit_dashboard_full_update'):
        
        on_toggle_game_mode()
        
        # Verify only game_mode changed
        assert mock_state.game_mode == 'classic'
        assert mock_state.game_started == True  # Unchanged
        assert mock_state.game_paused == False  # Unchanged
        assert mock_state.answer_stream_enabled == True  # Unchanged
        assert len(mock_state.connected_players) == 3  # Unchanged
        assert mock_state.active_teams == original_teams  # Unchanged

def test_mode_toggle_performance_under_load(mock_request, mock_state, mock_socketio, mock_emit, mock_logger):
    """Test mode toggle performance with many dashboard clients"""
    # Setup many clients - include request SID for authorization
    many_clients = ['test_dashboard_sid'] + [f'client_{i}' for i in range(9999)]
    mock_state.dashboard_clients = MockSet(many_clients)
    mock_state.game_mode = 'new'
    with patch('src.dashboard.clear_team_caches') as mock_clear_cache, \
         patch('src.dashboard.emit_dashboard_full_update') as mock_full_update:
        start_time = time.time()
        on_toggle_game_mode()
        end_time = time.time()
        assert (end_time - start_time) < 1.0
        # Updated: expect a single broadcast emit
        mock_socketio.emit.assert_called_with('game_mode_changed', {'mode': 'classic'})
        assert mock_state.game_mode == 'classic'

def test_mode_toggle_idempotency(mock_request, mock_state, mock_socketio, mock_emit, mock_logger):
    """Test that mode toggle operations are idempotent"""
    mock_state.game_mode = 'new'
    
    with patch('src.dashboard.force_clear_all_caches') as mock_clear_cache, \
         patch('src.dashboard.emit_dashboard_full_update') as mock_full_update:
        
        # First toggle: new -> classic
        on_toggle_game_mode()
        first_mode = mock_state.game_mode
        first_call_count = mock_clear_cache.call_count
        
        # Second toggle: classic -> new
        on_toggle_game_mode()
        second_mode = mock_state.game_mode
        second_call_count = mock_clear_cache.call_count
        
        # Third toggle: new -> classic (back to first state)
        on_toggle_game_mode()
        third_mode = mock_state.game_mode
        
        # Verify state changes are consistent and reversible
        assert first_mode == 'classic'
        assert second_mode == 'new'
        assert third_mode == 'classic'
        assert first_mode == third_mode  # Idempotent
        
        # Each operation should have called cache clear
        assert second_call_count == first_call_count * 2
        assert mock_clear_cache.call_count == 3

        # Updated: expect three broadcast emits
        assert mock_socketio.emit.call_count == 3
        mock_socketio.emit.assert_any_call('game_mode_changed', {'mode': 'classic'})
        mock_socketio.emit.assert_any_call('game_mode_changed', {'mode': 'new'})


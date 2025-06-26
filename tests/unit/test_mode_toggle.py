import pytest
from unittest.mock import patch, MagicMock, call
from src.sockets.dashboard import on_toggle_game_mode, clear_team_caches, emit_dashboard_full_update
from src.state import state
import warnings

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
    
    with patch('src.sockets.dashboard.request', mock_req):
        yield mock_req

@pytest.fixture
def mock_state():
    """Mock application state"""
    with patch('src.sockets.dashboard.state') as mock_state:
        mock_state.dashboard_clients = MockSet(['test_dashboard_sid'])
        mock_state.active_teams = {'team1': {'players': ['p1', 'p2']}, 'team2': {'players': ['p3', 'p4']}}
        mock_state.game_mode = 'new'  # Start with new mode as default
        yield mock_state

@pytest.fixture
def mock_socketio():
    """Mock socket.io instance"""
    with patch('src.sockets.dashboard.socketio') as mock_io:
        yield mock_io

@pytest.fixture
def mock_emit():
    """Mock emit function"""
    with patch('src.sockets.dashboard.emit') as mock_emit:
        yield mock_emit

@pytest.fixture
def mock_logger():
    """Mock logger"""
    with patch('src.sockets.dashboard.logger') as mock_logger:
        yield mock_logger

@pytest.fixture(autouse=True)
def clear_caches():
    """Clear all caches before each test"""
    clear_team_caches()
    yield
    clear_team_caches()

def test_toggle_game_mode_new_to_classic(mock_request, mock_state, mock_socketio, mock_emit, mock_logger):
    """Test toggling from new mode to classic mode"""
    # Setup: Start with new mode
    mock_state.game_mode = 'new'
    
    with patch('src.sockets.dashboard.clear_team_caches') as mock_clear_cache, \
         patch('src.sockets.dashboard.emit_dashboard_full_update') as mock_full_update:
        
        # Call the function
        on_toggle_game_mode()
        
        # Verify mode was changed to classic
        assert mock_state.game_mode == 'classic'
        
        # Verify logger was called
        mock_logger.info.assert_called_once_with("Game mode toggled to: classic")
        
        # Verify caches were cleared
        mock_clear_cache.assert_called_once()
        
        # Verify all dashboard clients were notified
        mock_socketio.emit.assert_called_with('game_mode_changed', {'mode': 'classic'})
        
        # Verify full dashboard update was triggered
        mock_full_update.assert_called_once()

def test_toggle_game_mode_classic_to_new(mock_request, mock_state, mock_socketio, mock_emit, mock_logger):
    """Test toggling from classic mode to new mode"""
    # Setup: Start with classic mode
    mock_state.game_mode = 'classic'
    
    with patch('src.sockets.dashboard.clear_team_caches') as mock_clear_cache, \
         patch('src.sockets.dashboard.emit_dashboard_full_update') as mock_full_update:
        
        # Call the function
        on_toggle_game_mode()
        
        # Verify mode was changed to new
        assert mock_state.game_mode == 'new'
        
        # Verify logger was called
        mock_logger.info.assert_called_once_with("Game mode toggled to: new")
        
        # Verify caches were cleared
        mock_clear_cache.assert_called_once()
        
        # Verify all dashboard clients were notified
        mock_socketio.emit.assert_called_with('game_mode_changed', {'mode': 'new'})
        
        # Verify full dashboard update was triggered
        mock_full_update.assert_called_once()

def test_toggle_game_mode_multiple_dashboard_clients(mock_request, mock_state, mock_socketio, mock_emit, mock_logger):
    """Test that all dashboard clients are notified of mode changes"""
    # Setup multiple dashboard clients - include the request SID for authorization
    mock_state.dashboard_clients = MockSet(['test_dashboard_sid', 'client2', 'client3'])
    mock_state.game_mode = 'new'
    
    with patch('src.sockets.dashboard.clear_team_caches') as mock_clear_cache, \
         patch('src.sockets.dashboard.emit_dashboard_full_update') as mock_full_update:
        
        # Call the function
        on_toggle_game_mode()
        
        # Verify mode was changed
        assert mock_state.game_mode == 'classic'
        
        # Verify all clients were notified (one call per client)
        mock_socketio.emit.assert_called_with('game_mode_changed', {'mode': 'classic'})

def test_toggle_game_mode_unauthorized_client(mock_request, mock_state, mock_socketio, mock_emit, mock_logger):
    """Test that unauthorized clients cannot toggle game mode"""
    # Setup: Remove client from dashboard_clients
    mock_state.dashboard_clients = MockSet()  # Empty set, client not authorized
    mock_state.game_mode = 'new'
    original_mode = mock_state.game_mode
    
    # Call the function
    on_toggle_game_mode()
    
    # Verify mode was NOT changed
    assert mock_state.game_mode == original_mode
    
    # Verify error was emitted to the unauthorized client
    mock_emit.assert_called_once_with('error', {'message': 'Unauthorized: Not a dashboard client'})
    
    # Verify no socket emissions to other clients
    mock_socketio.emit.assert_not_called()
    
    # Verify logger was not called (no successful toggle)
    mock_logger.info.assert_not_called()

def test_toggle_game_mode_no_dashboard_clients(mock_request, mock_state, mock_socketio, mock_emit, mock_logger):
    """Test mode toggle with no other dashboard clients connected"""
    # Setup: Only current client is authorized
    mock_state.dashboard_clients = MockSet(['test_dashboard_sid'])
    mock_state.game_mode = 'classic'
    
    with patch('src.sockets.dashboard.clear_team_caches') as mock_clear_cache, \
         patch('src.sockets.dashboard.emit_dashboard_full_update') as mock_full_update:
        
        # Call the function
        on_toggle_game_mode()
        
        # Verify mode was changed
        assert mock_state.game_mode == 'new'
        
        # Verify only the current client was notified
        mock_socketio.emit.assert_called_with('game_mode_changed', {'mode': 'new'})

def test_toggle_game_mode_error_handling(mock_request, mock_state, mock_socketio, mock_emit, mock_logger):
    """Test error handling during mode toggle"""
    mock_state.game_mode = 'new'
    
    with patch('src.sockets.dashboard.clear_team_caches') as mock_clear_cache:
        # Mock clear_team_caches to raise an exception
        mock_clear_cache.side_effect = Exception("Cache clear failed")
        
        # Call the function - should handle the exception gracefully
        on_toggle_game_mode()
        
        # Verify error was logged
        mock_logger.error.assert_called_once()
        error_call = mock_logger.error.call_args[0][0]
        assert "Error in on_toggle_game_mode:" in error_call
        
        # Verify error was emitted to client
        mock_emit.assert_called_once_with('error', {'message': 'An error occurred while toggling game mode'})

def test_toggle_game_mode_with_emit_dashboard_full_update_error(mock_request, mock_state, mock_socketio, mock_emit, mock_logger):
    """Test error handling when emit_dashboard_full_update fails"""
    mock_state.game_mode = 'classic'
    
    with patch('src.sockets.dashboard.clear_team_caches') as mock_clear_cache, \
         patch('src.sockets.dashboard.emit_dashboard_full_update') as mock_full_update:
        
        # Mock emit_dashboard_full_update to raise an exception
        mock_full_update.side_effect = Exception("Dashboard update failed")
        
        # Call the function - should handle the exception gracefully
        on_toggle_game_mode()
        
        # Verify error was logged
        mock_logger.error.assert_called_once()
        error_call = mock_logger.error.call_args[0][0]
        assert "Error in on_toggle_game_mode:" in error_call

def test_toggle_game_mode_socket_emission_error(mock_request, mock_state, mock_socketio, mock_emit, mock_logger):
    """Test error handling when socket emission fails"""
    mock_state.game_mode = 'new'
    
    with patch('src.sockets.dashboard.clear_team_caches') as mock_clear_cache, \
         patch('src.sockets.dashboard.emit_dashboard_full_update') as mock_full_update:
        
        # Mock socketio.emit to raise an exception
        mock_socketio.emit.side_effect = Exception("Socket emission failed")
        
        # Call the function - should handle the exception gracefully
        on_toggle_game_mode()
        
        # Verify error was logged
        mock_logger.error.assert_called_once()
        error_call = mock_logger.error.call_args[0][0]
        assert "Error in on_toggle_game_mode:" in error_call

def test_game_mode_state_persistence(mock_request, mock_state, mock_socketio, mock_emit, mock_logger):
    """Test that game mode state persists correctly across multiple toggles"""
    initial_mode = 'new'
    mock_state.game_mode = initial_mode
    
    with patch('src.sockets.dashboard.clear_team_caches'), \
         patch('src.sockets.dashboard.emit_dashboard_full_update'):
        
        # First toggle: new -> classic
        on_toggle_game_mode()
        assert mock_state.game_mode == 'classic'
        
        # Second toggle: classic -> new
        on_toggle_game_mode()
        assert mock_state.game_mode == 'new'
        
        # Third toggle: new -> classic
        on_toggle_game_mode()
        assert mock_state.game_mode == 'classic'
        
        # Verify logger was called for each toggle
        assert mock_logger.info.call_count == 3
        
        # Verify the correct modes were logged
        logged_modes = [call[0][0] for call in mock_logger.info.call_args_list]
        assert "Game mode toggled to: classic" in logged_modes[0]
        assert "Game mode toggled to: new" in logged_modes[1]
        assert "Game mode toggled to: classic" in logged_modes[2]

def test_toggle_game_mode_with_active_teams(mock_request, mock_state, mock_socketio, mock_emit, mock_logger):
    """Test mode toggle when there are active teams"""
    # Setup with multiple active teams
    mock_state.active_teams = {
        'team1': {'players': ['p1', 'p2'], 'status': 'ready'},
        'team2': {'players': ['p3', 'p4'], 'status': 'waiting'},
        'team3': {'players': ['p5', 'p6'], 'status': 'ready'}
    }
    mock_state.game_mode = 'new'
    
    with patch('src.sockets.dashboard.clear_team_caches') as mock_clear_cache, \
         patch('src.sockets.dashboard.emit_dashboard_full_update') as mock_full_update:
        
        # Call the function
        on_toggle_game_mode()
        
        # Verify mode was changed
        assert mock_state.game_mode == 'classic'
        
        # Verify cache was cleared (important for recalculating metrics with new mode)
        mock_clear_cache.assert_called_once()
        
        # Verify dashboard update was triggered (will recalculate all team metrics)
        mock_full_update.assert_called_once()

def test_toggle_game_mode_integration_with_dashboard_updates(mock_request, mock_state, mock_socketio, mock_emit, mock_logger):
    """Test that mode toggle properly integrates with dashboard update system"""
    mock_state.game_mode = 'classic'
    
    # Track if functions were called in correct order
    call_order = []
    
    def track_clear_cache():
        call_order.append('clear_cache')
    
    def track_socket_emit(*args, **kwargs):
        call_order.append('socket_emit')
    
    def track_dashboard_update():
        call_order.append('dashboard_update')
    
    with patch('src.sockets.dashboard.clear_team_caches', side_effect=track_clear_cache), \
         patch('src.sockets.dashboard.emit_dashboard_full_update', side_effect=track_dashboard_update):
        
        mock_socketio.emit.side_effect = track_socket_emit
        
        # Call the function
        on_toggle_game_mode()
        
        # Verify operations happened in correct order
        assert call_order == ['clear_cache', 'socket_emit', 'dashboard_update']

def test_toggle_game_mode_invalid_initial_state(mock_request, mock_state, mock_socketio, mock_emit, mock_logger):
    """Test mode toggle with invalid initial state"""
    # Setup with invalid mode
    mock_state.game_mode = 'invalid_mode'
    
    with patch('src.sockets.dashboard.clear_team_caches') as mock_clear_cache, \
         patch('src.sockets.dashboard.emit_dashboard_full_update') as mock_full_update:
        
        # Call the function
        on_toggle_game_mode()
        
        # Should default to 'classic' since it's not 'classic'
        assert mock_state.game_mode == 'classic'
        
        # Verify logger was called
        mock_logger.info.assert_called_once_with("Game mode toggled to: classic")

def test_toggle_game_mode_concurrent_requests(mock_request, mock_state, mock_socketio, mock_emit, mock_logger):
    """Test behavior with concurrent mode toggle requests"""
    # This test simulates rapid successive calls
    mock_state.game_mode = 'new'
    
    with patch('src.sockets.dashboard.clear_team_caches') as mock_clear_cache, \
         patch('src.sockets.dashboard.emit_dashboard_full_update') as mock_full_update:
        
        # Call multiple times rapidly
        on_toggle_game_mode()  # new -> classic
        on_toggle_game_mode()  # classic -> new
        on_toggle_game_mode()  # new -> classic
        
        # Final state should be classic
        assert mock_state.game_mode == 'classic'
        
        # All operations should have been called multiple times
        assert mock_clear_cache.call_count == 3
        assert mock_full_update.call_count == 3
        assert mock_logger.info.call_count == 3
        # Updated: expect three broadcast emits
        assert mock_socketio.emit.call_count == 3
        mock_socketio.emit.assert_any_call('game_mode_changed', {'mode': 'classic'})
        mock_socketio.emit.assert_any_call('game_mode_changed', {'mode': 'new'})

def test_toggle_game_mode_with_empty_dashboard_clients(mock_request, mock_state, mock_socketio, mock_emit, mock_logger):
    """Test mode toggle when dashboard_clients set is empty"""
    # Setup: Client making request is not in dashboard_clients
    mock_state.dashboard_clients = MockSet()
    mock_state.game_mode = 'new'
    original_mode = mock_state.game_mode
    
    # Call the function
    on_toggle_game_mode()
    
    # Verify mode was NOT changed
    assert mock_state.game_mode == original_mode
    
    # Verify unauthorized error was sent
    mock_emit.assert_called_once_with('error', {'message': 'Unauthorized: Not a dashboard client'})

def test_toggle_game_mode_preserves_other_state(mock_request, mock_state, mock_socketio, mock_emit, mock_logger):
    """Test that mode toggle doesn't affect other state variables"""
    # Setup initial state
    mock_state.game_mode = 'new'
    mock_state.game_started = True
    mock_state.game_paused = False
    mock_state.answer_stream_enabled = True
    original_active_teams = mock_state.active_teams.copy()
    
    with patch('src.sockets.dashboard.clear_team_caches'), \
         patch('src.sockets.dashboard.emit_dashboard_full_update'):
        
        # Call the function
        on_toggle_game_mode()
        
        # Verify only game_mode changed
        assert mock_state.game_mode == 'classic'
        assert mock_state.game_started == True  # Unchanged
        assert mock_state.game_paused == False  # Unchanged
        assert mock_state.answer_stream_enabled == True  # Unchanged
        assert mock_state.active_teams == original_active_teams  # Unchanged
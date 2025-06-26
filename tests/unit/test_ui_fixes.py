import pytest
from unittest.mock import patch, MagicMock, call
from src.sockets.dashboard import on_toggle_game_mode, on_restart_game, on_dashboard_join
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
        mock_state.game_started = False
        mock_state.game_paused = False
        mock_state.connected_players = set(['p1', 'p2', 'p3', 'p4'])
        mock_state.answer_stream_enabled = False
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

@pytest.fixture
def mock_db_session():
    """Mock database session"""
    with patch('src.sockets.dashboard.db') as mock_db:
        mock_db.session = MagicMock()
        yield mock_db

@pytest.fixture(autouse=True)
def clear_caches():
    """Clear all caches before each test"""
    with patch('src.sockets.dashboard.clear_team_caches') as mock_clear:
        yield mock_clear

class TestGameModeToggleUI:
    """Test the UI fixes for game mode toggle functionality"""
    
    def test_toggle_game_mode_proper_error_handling(self, mock_request, mock_state, mock_socketio, mock_emit, mock_logger):
        """Test that game mode toggle properly handles server errors"""
        mock_state.game_mode = 'new'
        
        # Simulate server error during toggle
        with patch('src.sockets.dashboard.clear_team_caches', side_effect=Exception("Database error")), \
             patch('src.sockets.dashboard.emit_dashboard_full_update', side_effect=Exception("Update error")):
            
            on_toggle_game_mode()
            
            # Verify error was emitted to the client
            mock_emit.assert_called_with('error', {'message': 'An error occurred while toggling game mode'})
            
            # Verify error was logged
            mock_logger.error.assert_called()
            error_call = mock_logger.error.call_args[0][0]
            assert "Error in on_toggle_game_mode:" in error_call
    
    def test_toggle_game_mode_multiple_dashboard_synchronization(self, mock_request, mock_state, mock_socketio, mock_emit, mock_logger):
        """Test that game mode changes are properly synchronized across multiple dashboard connections"""
        # Setup multiple dashboard clients
        mock_state.dashboard_clients = MockSet(['test_dashboard_sid', 'client2', 'client3'])
        mock_state.game_mode = 'new'
        
        with patch('src.sockets.dashboard.clear_team_caches') as mock_clear_cache, \
             patch('src.sockets.dashboard.emit_dashboard_full_update') as mock_full_update:
            
            on_toggle_game_mode()
            
            # Verify mode was changed
            assert mock_state.game_mode == 'classic'
            
            # Verify all clients were notified individually
            expected_calls = [
                call('game_mode_changed', {'mode': 'classic'}, to='test_dashboard_sid'),
                call('game_mode_changed', {'mode': 'classic'}, to='client2'),
                call('game_mode_changed', {'mode': 'classic'}, to='client3')
            ]
            mock_socketio.emit.assert_has_calls(expected_calls, any_order=True)
            
            # Verify full dashboard update was triggered for all clients
            mock_full_update.assert_called_once()
    
    def test_toggle_game_mode_timeout_handling(self, mock_request, mock_state, mock_socketio, mock_emit, mock_logger):
        """Test that game mode toggle handles timeouts gracefully"""
        mock_state.game_mode = 'new'
        
        # Simulate a slow server response
        with patch('src.sockets.dashboard.clear_team_caches') as mock_clear_cache, \
             patch('src.sockets.dashboard.emit_dashboard_full_update', side_effect=Exception("Timeout")):
            
            on_toggle_game_mode()
            
            # Verify error was emitted
            mock_emit.assert_called_with('error', {'message': 'An error occurred while toggling game mode'})
            
            # Verify the mode change was still applied (server-side state is authoritative)
            assert mock_state.game_mode == 'classic'

class TestResetButtonUI:
    """Test the reset button functionality and synchronization"""
    
    def test_reset_game_proper_authorization(self, mock_request, mock_state, mock_socketio, mock_emit, mock_logger, mock_db_session):
        """Test that reset game requires proper authorization"""
        # Remove client from dashboard_clients
        mock_state.dashboard_clients = MockSet()
        
        on_restart_game()
        
        # Verify both error and game_reset_complete were emitted
        expected_calls = [
            call('error', {'message': 'Unauthorized: Not a dashboard client'}),
            call('game_reset_complete', to='test_dashboard_sid')
        ]
        mock_emit.assert_has_calls(expected_calls, any_order=True)
    
    def test_reset_game_multiple_dashboard_synchronization(self, mock_request, mock_state, mock_socketio, mock_emit, mock_logger, mock_db_session):
        """Test that reset game is properly synchronized across multiple dashboard connections"""
        # Setup multiple dashboard clients
        mock_state.dashboard_clients = MockSet(['test_dashboard_sid', 'client2', 'client3'])
        mock_state.game_started = True
        
        with patch('src.sockets.dashboard.PairQuestionRounds') as mock_rounds, \
             patch('src.sockets.dashboard.Answers') as mock_answers, \
             patch('src.sockets.dashboard.clear_team_caches') as mock_clear_cache, \
             patch('src.sockets.dashboard.emit_dashboard_full_update') as mock_full_update:
            
            # Mock database queries
            mock_rounds.query.delete.return_value = None
            mock_answers.query.delete.return_value = None
            
            on_restart_game()
            
            # Verify game state was reset
            assert mock_state.game_started == False
            
            # Verify all dashboard clients were notified of reset completion
            expected_calls = [
                call('game_reset_complete', to='test_dashboard_sid'),
                call('game_reset_complete', to='client2'),
                call('game_reset_complete', to='client3')
            ]
            mock_socketio.emit.assert_has_calls(expected_calls, any_order=True)
            
            # Verify database was cleared
            mock_rounds.query.delete.assert_called_once()
            mock_answers.query.delete.assert_called_once()
            
            # Verify caches were cleared
            mock_clear_cache.assert_called_once()
    
    def test_reset_game_database_error_handling(self, mock_request, mock_state, mock_socketio, mock_emit, mock_logger, mock_db_session):
        """Test that reset game handles database errors gracefully"""
        mock_state.game_started = True
        
        # Simulate database error by making commit raise an exception
        mock_db_session.commit.side_effect = Exception("Database connection failed")
        
        with patch('src.sockets.dashboard.PairQuestionRounds') as mock_rounds, \
             patch('src.sockets.dashboard.Answers') as mock_answers, \
             patch('src.sockets.dashboard.emit') as mock_server_emit:  # Patch the actual emit used in server code
            
            # Mock database queries
            mock_rounds.query.delete.return_value = None
            mock_answers.query.delete.return_value = None
            
            on_restart_game()
            
            # Verify error was emitted
            mock_server_emit.assert_called_with('error', {'message': 'Database error during reset'})
            
            # Verify rollback was called
            mock_db_session.rollback.assert_called_once()
    
    def test_reset_game_no_active_teams(self, mock_request, mock_state, mock_socketio, mock_emit, mock_logger, mock_db_session):
        """Test that reset game works correctly when there are no active teams"""
        mock_state.game_started = True
        mock_state.active_teams = {}  # No active teams
        
        with patch('src.sockets.dashboard.PairQuestionRounds') as mock_rounds, \
             patch('src.sockets.dashboard.Answers') as mock_answers, \
             patch('src.sockets.dashboard.clear_team_caches') as mock_clear_cache, \
             patch('src.sockets.dashboard.emit_dashboard_full_update') as mock_full_update:
            
            # Mock database queries
            mock_rounds.query.delete.return_value = None
            mock_answers.query.delete.return_value = None
            
            on_restart_game()
            
            # Verify game state was reset
            assert mock_state.game_started == False
            
            # Verify database was still cleared even with no teams
            mock_rounds.query.delete.assert_called_once()
            mock_answers.query.delete.assert_called_once()

class TestDashboardJoinSynchronization:
    """Test that dashboard join properly synchronizes state across multiple connections"""
    
    def test_dashboard_join_sends_current_game_mode(self, mock_request, mock_state, mock_socketio, mock_emit, mock_logger):
        """Test that dashboard join sends the current game mode to new clients"""
        mock_state.game_mode = 'classic'
        mock_state.game_started = True
        mock_state.game_paused = False
        
        with patch('src.sockets.dashboard.app') as mock_app, \
             patch('src.sockets.dashboard.Answers') as mock_answers, \
             patch('src.sockets.dashboard.get_all_teams') as mock_get_teams, \
             patch('src.sockets.dashboard.dashboard_teams_streaming', {}) as mock_streaming:
            
            # Mock database query
            mock_answers.query.count.return_value = 100
            
            # Mock teams data
            mock_get_teams.return_value = [
                {'is_active': True, 'player1_sid': 'p1', 'player2_sid': 'p2'},
                {'is_active': False, 'player1_sid': None, 'player2_sid': None}
            ]
            
            on_dashboard_join()
            
            # Verify the client was added to dashboard_clients
            assert 'test_dashboard_sid' in mock_state.dashboard_clients
            
            # Verify dashboard_update was sent with current game mode
            mock_socketio.emit.assert_called_once()
            call_args = mock_socketio.emit.call_args
            assert call_args[0][0] == 'dashboard_update'
            
            update_data = call_args[0][1]
            assert update_data['game_state']['mode'] == 'classic'
            assert update_data['game_state']['started'] == True
            assert 'streaming_enabled' in update_data['game_state']
    
    def test_dashboard_join_respects_streaming_preferences(self, mock_request, mock_state, mock_socketio, mock_emit, mock_logger):
        """Test that dashboard join respects individual client streaming preferences"""
        mock_state.game_mode = 'new'
        
        with patch('src.sockets.dashboard.app') as mock_app, \
             patch('src.sockets.dashboard.Answers') as mock_answers, \
             patch('src.sockets.dashboard.get_all_teams') as mock_get_teams, \
             patch('src.sockets.dashboard.dashboard_teams_streaming', {'test_dashboard_sid': True}) as mock_streaming:
            
            # Mock database query
            mock_answers.query.count.return_value = 50
            
            # Mock teams data
            mock_get_teams.return_value = [
                {'is_active': True, 'player1_sid': 'p1', 'player2_sid': 'p2'}
            ]
            
            on_dashboard_join()
            
            # Verify dashboard_update was sent with teams data (streaming enabled)
            mock_socketio.emit.assert_called_once()
            call_args = mock_socketio.emit.call_args
            update_data = call_args[0][1]
            assert len(update_data['teams']) > 0  # Teams data included
    
    def test_dashboard_join_no_streaming_preference(self, mock_request, mock_state, mock_socketio, mock_emit, mock_logger):
        """Test that dashboard join defaults to no streaming for new clients"""
        mock_state.game_mode = 'new'
        
        with patch('src.sockets.dashboard.app') as mock_app, \
             patch('src.sockets.dashboard.Answers') as mock_answers, \
             patch('src.sockets.dashboard.get_all_teams') as mock_get_teams, \
             patch('src.sockets.dashboard.dashboard_teams_streaming', {}) as mock_streaming:
            
            # Mock database query
            mock_answers.query.count.return_value = 25
            
            # Mock teams data
            mock_get_teams.return_value = [
                {'is_active': True, 'player1_sid': 'p1', 'player2_sid': 'p2'}
            ]
            
            on_dashboard_join()
            
            # Verify dashboard_update was sent without teams data (streaming disabled by default)
            mock_socketio.emit.assert_called_once()
            call_args = mock_socketio.emit.call_args
            update_data = call_args[0][1]
            assert len(update_data['teams']) == 0  # No teams data included

class TestIntegrationScenarios:
    """Test integration scenarios involving multiple dashboard connections"""
    
    def test_multiple_dashboards_game_mode_synchronization(self, mock_request, mock_state, mock_socketio, mock_emit, mock_logger):
        """Test that game mode changes are properly synchronized across multiple dashboard connections"""
        # Setup multiple dashboard clients
        mock_state.dashboard_clients = MockSet(['client1', 'client2', 'client3'])
        mock_state.game_mode = 'new'
        
        # Simulate client1 toggling game mode
        mock_request.sid = 'client1'
        
        with patch('src.sockets.dashboard.clear_team_caches') as mock_clear_cache, \
             patch('src.sockets.dashboard.emit_dashboard_full_update') as mock_full_update:
            
            on_toggle_game_mode()
            
            # Verify all clients received the mode change notification
            expected_calls = [
                call('game_mode_changed', {'mode': 'classic'}, to='client1'),
                call('game_mode_changed', {'mode': 'classic'}, to='client2'),
                call('game_mode_changed', {'mode': 'classic'}, to='client3')
            ]
            mock_socketio.emit.assert_has_calls(expected_calls, any_order=True)
            
            # Verify the mode was actually changed
            assert mock_state.game_mode == 'classic'
    
    def test_multiple_dashboards_reset_synchronization(self, mock_request, mock_state, mock_socketio, mock_emit, mock_logger, mock_db_session):
        """Test that game reset is properly synchronized across multiple dashboard connections"""
        # Setup multiple dashboard clients
        mock_state.dashboard_clients = MockSet(['client1', 'client2', 'client3'])
        mock_state.game_started = True
        
        # Simulate client2 initiating reset
        mock_request.sid = 'client2'
        
        with patch('src.sockets.dashboard.PairQuestionRounds') as mock_rounds, \
             patch('src.sockets.dashboard.Answers') as mock_answers, \
             patch('src.sockets.dashboard.clear_team_caches') as mock_clear_cache, \
             patch('src.sockets.dashboard.emit_dashboard_full_update') as mock_full_update:
            
            # Mock database queries
            mock_rounds.query.delete.return_value = None
            mock_answers.query.delete.return_value = None
            
            on_restart_game()
            
            # Verify all clients received the reset completion notification
            expected_calls = [
                call('game_reset_complete', to='client1'),
                call('game_reset_complete', to='client2'),
                call('game_reset_complete', to='client3')
            ]
            mock_socketio.emit.assert_has_calls(expected_calls, any_order=True)
            
            # Verify the game state was reset
            assert mock_state.game_started == False 
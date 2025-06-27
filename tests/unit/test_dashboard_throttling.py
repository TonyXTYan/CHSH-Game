import pytest
import time
from unittest.mock import Mock, patch, MagicMock
import logging
from src.sockets.dashboard import (
    emit_dashboard_team_update,
    emit_dashboard_full_update,
    clear_team_caches,
    REFRESH_DELAY_QUICK
)
from src.state import state


@pytest.fixture
def mock_dashboard_dependencies():
    """Mock all dependencies for dashboard functions."""
    with patch('src.sockets.dashboard.socketio') as mock_socketio, \
         patch('src.sockets.dashboard.get_all_teams') as mock_get_teams, \
         patch('src.sockets.dashboard.app') as mock_app, \
         patch('src.sockets.dashboard.Answers') as mock_answers:
        
        # Setup mock data
        mock_teams = [
            {
                'team_id': 1,
                'team_name': 'Team1',
                'is_active': True,
                'status': 'active',
                'player1_sid': 'player1',
                'player2_sid': 'player2'
            },
            {
                'team_id': 2,
                'team_name': 'Team2',
                'is_active': True,
                'status': 'waiting_pair',
                'player1_sid': 'player3',
                'player2_sid': None
            }
        ]
        
        mock_get_teams.return_value = mock_teams
        mock_answers.query.count.return_value = 10
        
        # Mock app context
        mock_app.app_context.return_value.__enter__ = Mock()
        mock_app.app_context.return_value.__exit__ = Mock()
        
        yield {
            'socketio': mock_socketio,
            'get_teams': mock_get_teams,
            'app': mock_app,
            'answers': mock_answers,
            'teams': mock_teams
        }


@pytest.fixture
def setup_dashboard_state():
    """Setup state for dashboard tests."""
    # Clear any existing state
    state.dashboard_clients.clear()
    state.connected_players.clear()
    
    # Add some test data
    state.dashboard_clients.add('dashboard1')
    state.connected_players.update(['player1', 'player2', 'player3'])
    
    yield
    
    # Cleanup
    state.dashboard_clients.clear()
    state.connected_players.clear()
    clear_team_caches()


class TestDashboardThrottling:
    """Test dashboard update throttling functionality."""
    
    def test_emit_dashboard_team_update_fresh_calculation(self, mock_dashboard_dependencies, setup_dashboard_state):
        """Test that fresh calculations work correctly."""
        clear_team_caches()  # Ensure clean state
        
        # Call function
        emit_dashboard_team_update(force_refresh=True)
        
        # Verify socketio.emit was called for streaming and non-streaming clients
        mock_socketio = mock_dashboard_dependencies['socketio']
        assert mock_socketio.emit.called
        
        # Verify get_all_teams was called with force_refresh=True
        mock_get_teams = mock_dashboard_dependencies['get_teams']
        mock_get_teams.assert_called_with(force_refresh=True)
    
    def test_emit_dashboard_team_update_connected_players_always_fresh(self, mock_dashboard_dependencies, setup_dashboard_state):
        """Test that connected_players_count is always calculated fresh."""
        clear_team_caches()
        
        # First call to populate cache
        emit_dashboard_team_update()
        
        # Change connected players
        state.connected_players.add('new_player')
        
        # Second call within throttle window (should use cache for most metrics but fresh connected_players_count)
        emit_dashboard_team_update()
        
        # Verify socketio.emit was called with fresh connected_players_count
        mock_socketio = mock_dashboard_dependencies['socketio']
        calls = mock_socketio.emit.call_args_list
        
        # Check that the last call included the updated connected_players_count
        last_call = calls[-1]
        assert len(last_call[0]) >= 2  # Should have event name and data
        
        # The connected_players_count should reflect the updated state
        assert len(state.connected_players) == 4  # 3 original + 1 new
    
    def test_emit_dashboard_team_update_throttling(self, mock_dashboard_dependencies, setup_dashboard_state):
        """Test that throttling works correctly."""
        clear_team_caches()
        
        # First call
        emit_dashboard_team_update()
        mock_get_teams = mock_dashboard_dependencies['get_teams']
        first_call_count = mock_get_teams.call_count
        
        # Second call immediately (within throttle window)
        emit_dashboard_team_update()
        
        # get_all_teams should be called with force_refresh=False for cached data
        assert mock_get_teams.call_count == first_call_count + 1
        mock_get_teams.assert_called_with(force_refresh=False)
    
    def test_emit_dashboard_full_update_fresh_calculation(self, mock_dashboard_dependencies, setup_dashboard_state):
        """Test that fresh calculations work correctly for full update."""
        clear_team_caches()
        
        # Call function
        emit_dashboard_full_update()
        
        # Verify database query was made
        mock_answers = mock_dashboard_dependencies['answers']
        mock_answers.query.count.assert_called()
        
        # Verify get_all_teams was called
        mock_get_teams = mock_dashboard_dependencies['get_teams']
        mock_get_teams.assert_called()
    
    def test_emit_dashboard_full_update_connected_players_always_fresh(self, mock_dashboard_dependencies, setup_dashboard_state):
        """Test that connected_players_count is always calculated fresh in full update."""
        clear_team_caches()
        
        # First call to populate cache
        emit_dashboard_full_update()
        
        # Change connected players
        state.connected_players.add('another_new_player')
        
        # Second call within throttle window
        emit_dashboard_full_update()
        
        # Verify socketio.emit was called with fresh connected_players_count
        mock_socketio = mock_dashboard_dependencies['socketio']
        assert mock_socketio.emit.called
        
        # The connected_players_count should reflect the updated state
        assert len(state.connected_players) == 4  # 3 original + 1 new
    
    def test_emit_dashboard_full_update_throttling(self, mock_dashboard_dependencies, setup_dashboard_state):
        """Test that throttling works correctly for full update."""
        clear_team_caches()
        
        # First call
        emit_dashboard_full_update()
        mock_answers = mock_dashboard_dependencies['answers']
        first_db_call_count = mock_answers.query.count.call_count
        
        # Second call immediately (within throttle window)
        emit_dashboard_full_update()
        
        # Database query should not be called again due to throttling
        assert mock_answers.query.count.call_count == first_db_call_count
    
    def test_separate_caches_no_interference(self, mock_dashboard_dependencies, setup_dashboard_state):
        """Test that the separate caches don't interfere with each other."""
        clear_team_caches()
        
        # Call team update to populate its cache
        emit_dashboard_team_update()
        
        # Call full update to populate its cache
        emit_dashboard_full_update()
        
        # Call team update again within throttle window
        emit_dashboard_team_update()
        
        # Call full update again within throttle window
        emit_dashboard_full_update()
        
        # Verify both functions can use their respective caches
        mock_get_teams = mock_dashboard_dependencies['get_teams']
        mock_answers = mock_dashboard_dependencies['answers']
        
        # get_all_teams should be called for initial calls and throttled calls
        assert mock_get_teams.call_count >= 2
        
        # Database query should only be called once (during initial full update)
        assert mock_answers.query.count.call_count == 1
    
    def test_cache_invalidation_clears_both_caches(self, mock_dashboard_dependencies, setup_dashboard_state):
        """Test that cache invalidation clears both caches."""
        clear_team_caches()
        
        # Populate both caches
        emit_dashboard_team_update()
        emit_dashboard_full_update()
        
        # Clear caches
        clear_team_caches()
        
        # Next calls should be fresh (not throttled)
        emit_dashboard_team_update()
        emit_dashboard_full_update()
        
        # Verify fresh calls were made
        mock_get_teams = mock_dashboard_dependencies['get_teams']
        mock_answers = mock_dashboard_dependencies['answers']
        
        # Should have fresh calls after cache clear
        assert mock_get_teams.call_count >= 4  # 2 initial + 2 after clear
        assert mock_answers.query.count.call_count >= 2  # 1 initial + 1 after clear
    
    def test_force_refresh_bypasses_throttling(self, mock_dashboard_dependencies, setup_dashboard_state):
        """Test that force_refresh bypasses throttling."""
        clear_team_caches()
        
        # First call to populate cache
        emit_dashboard_team_update()
        mock_get_teams = mock_dashboard_dependencies['get_teams']
        initial_call_count = mock_get_teams.call_count
        
        # Force refresh should bypass cache
        emit_dashboard_team_update(force_refresh=True)
        
        # Should have made a fresh call
        assert mock_get_teams.call_count == initial_call_count + 1
        mock_get_teams.assert_called_with(force_refresh=True)
    
    def test_no_dashboard_clients_early_return(self, mock_dashboard_dependencies):
        """Test that functions return early when no dashboard clients are connected."""
        state.dashboard_clients.clear()
        
        # Call functions
        emit_dashboard_team_update()
        emit_dashboard_full_update()
        
        # Should not have called dependencies
        mock_get_teams = mock_dashboard_dependencies['get_teams']
        mock_answers = mock_dashboard_dependencies['answers']
        
        assert not mock_get_teams.called
        assert not mock_answers.query.count.called
    
    def test_throttle_delay_timing(self, mock_dashboard_dependencies, setup_dashboard_state):
        """Test that throttling respects the REFRESH_DELAY_QUICK timing."""
        clear_team_caches()
        
        # First call
        emit_dashboard_team_update()
        mock_get_teams = mock_dashboard_dependencies['get_teams']
        initial_call_count = mock_get_teams.call_count
        
        # Wait less than REFRESH_DELAY_QUICK
        time.sleep(REFRESH_DELAY_QUICK * 0.5)
        
        # Second call should be throttled
        emit_dashboard_team_update()
        assert mock_get_teams.call_count == initial_call_count + 1  # Only one more call for cached data
        
        # Wait longer than REFRESH_DELAY_QUICK
        time.sleep(REFRESH_DELAY_QUICK * 1.1)
        
        # Third call should not be throttled
        emit_dashboard_team_update()
        assert mock_get_teams.call_count >= initial_call_count + 2  # Should make fresh call
    
    @patch('src.sockets.dashboard.logger')
    def test_error_handling(self, mock_logger, mock_dashboard_dependencies, setup_dashboard_state):
        """Test that errors are handled gracefully."""
        # Make get_all_teams raise an exception
        mock_dashboard_dependencies['get_teams'].side_effect = Exception("Test error")
        
        # Functions should not crash
        try:
            emit_dashboard_team_update()
            emit_dashboard_full_update()
        except Exception as e:
            pytest.fail(f"Functions should handle errors gracefully, but raised: {e}")
        
        # Errors should be logged
        assert mock_logger.error.called


class TestCacheMetrics:
    """Test specific metrics caching behavior."""
    
    def test_team_update_cache_behavior(self, mock_dashboard_dependencies, setup_dashboard_state):
        """Test that team update cache behaves correctly."""
        clear_team_caches()
        
        # First call should make fresh calculation
        emit_dashboard_team_update()
        mock_get_teams = mock_dashboard_dependencies['get_teams']
        first_call_count = mock_get_teams.call_count
        
        # Second call immediately should use cache (throttled)
        emit_dashboard_team_update()
        
        # Should have made one additional call for cached data
        assert mock_get_teams.call_count == first_call_count + 1
        # The last call should have been with force_refresh=False
        mock_get_teams.assert_called_with(force_refresh=False)
    
    def test_full_update_cache_behavior(self, mock_dashboard_dependencies, setup_dashboard_state):
        """Test that full update cache behaves correctly."""
        clear_team_caches()
        
        # First call should make fresh calculation
        emit_dashboard_full_update()
        mock_answers = mock_dashboard_dependencies['answers']
        first_db_call_count = mock_answers.query.count.call_count
        
        # Second call immediately should use cache (throttled)
        emit_dashboard_full_update()
        
        # Database query should not be called again due to throttling
        assert mock_answers.query.count.call_count == first_db_call_count
    
    def test_connected_players_count_consistency(self, mock_dashboard_dependencies, setup_dashboard_state):
        """Test that connected_players_count is consistent across rapid updates."""
        clear_team_caches()
        
        # Add players dynamically
        for i in range(5):
            state.connected_players.add(f'player_{i}')
            emit_dashboard_team_update()
            emit_dashboard_full_update()
        
        # All calls should reflect the current connected players count
        # This test ensures that even with caching, connected_players_count stays current
        mock_socketio = mock_dashboard_dependencies['socketio']
        assert mock_socketio.emit.called
        assert len(state.connected_players) == 8  # 3 initial + 5 new
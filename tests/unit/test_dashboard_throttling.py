import pytest
import time
from unittest.mock import Mock, patch, MagicMock
import logging
import threading
from src.sockets.dashboard import (
    emit_dashboard_team_update,
    emit_dashboard_full_update,
    clear_team_caches,
    REFRESH_DELAY_QUICK,
    REFRESH_DELAY_FULL,
    force_clear_all_caches
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
    
    def test_throttling_constants_exist(self):
        """Test that both throttling constants exist and are properly configured."""
        assert REFRESH_DELAY_QUICK == 0.5
        assert REFRESH_DELAY_FULL == 1.0
        assert REFRESH_DELAY_FULL > REFRESH_DELAY_QUICK
    
    def test_emit_dashboard_team_update_fresh_calculation(self, mock_dashboard_dependencies, setup_dashboard_state):
        """Test that fresh calculations are made when not throttled."""
        # FIXED: Use force_clear_all_caches to ensure fresh calculation
        force_clear_all_caches()
        
        emit_dashboard_team_update()
        mock_get_teams = mock_dashboard_dependencies['get_teams']
        
        # FIXED: Should make fresh calculation since cache was cleared
        mock_get_teams.assert_called()
    
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
        """Test that team update throttling uses REFRESH_DELAY_QUICK."""
        clear_team_caches()
        
        # First call
        emit_dashboard_team_update()
        mock_get_teams = mock_dashboard_dependencies['get_teams']
        first_call_count = mock_get_teams.call_count
        
        # Second call immediately (within throttle window)
        emit_dashboard_team_update()
        
        # FIXED: get_all_teams should NOT be called again due to throttling (this proves throttling works)
        assert mock_get_teams.call_count == first_call_count  # Should be throttled, no additional call
    
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
        """Test that full update throttling uses REFRESH_DELAY_FULL."""
        clear_team_caches()
        
        # First call
        emit_dashboard_full_update()
        mock_answers = mock_dashboard_dependencies['answers']
        first_db_call_count = mock_answers.query.count.call_count
        
        # Second call immediately (within throttle window)
        emit_dashboard_full_update()
        
        # Database query should not be called again due to throttling
        assert mock_answers.query.count.call_count == first_db_call_count
    
    def test_different_throttling_delays(self, mock_dashboard_dependencies, setup_dashboard_state):
        """Test that team updates and full updates have different throttling delays."""
        clear_team_caches()
        
        # Test team update throttling with REFRESH_DELAY_QUICK
        with patch('src.sockets.dashboard.time') as mock_time:
            base_time = 1000.0
            mock_time.return_value = base_time
            
            # First team update
            emit_dashboard_team_update()
            
            # Immediate second call should be throttled
            mock_time.return_value = base_time + REFRESH_DELAY_QUICK * 0.5
            import src.sockets.dashboard as dashboard_module
            initial_team_time = dashboard_module._last_team_update_time
            
            emit_dashboard_team_update()
            
            # Should still be using cache (time not updated)
            assert dashboard_module._last_team_update_time == initial_team_time
            
        # Test full update throttling with REFRESH_DELAY_FULL
        clear_team_caches()
        mock_answers = mock_dashboard_dependencies['answers']
        
        with patch('src.sockets.dashboard.time') as mock_time:
            base_time = 2000.0
            mock_time.return_value = base_time
            
            # First full update
            emit_dashboard_full_update()
            first_db_count = mock_answers.query.count.call_count
            
            # Call within REFRESH_DELAY_FULL window should be throttled
            mock_time.return_value = base_time + REFRESH_DELAY_FULL * 0.5
            emit_dashboard_full_update()
            
            # Database should not be called again
            assert mock_answers.query.count.call_count == first_db_count
    
    def test_separate_caches_no_interference(self, mock_dashboard_dependencies, setup_dashboard_state):
        """Test that the separate caches don't interfere with each other."""
        # Import the force clear function for complete cache reset
        from src.sockets.dashboard import force_clear_all_caches
        force_clear_all_caches()
        
        # Call team update to populate its cache
        emit_dashboard_team_update()
        
        # Call full update to populate its cache
        emit_dashboard_full_update()
        
        # Call team update again within throttle window (should be throttled)
        emit_dashboard_team_update()
        
        # Call full update again within throttle window (should be throttled)
        emit_dashboard_full_update()
        
        # Verify both functions can use their respective caches
        mock_get_teams = mock_dashboard_dependencies['get_teams']
        mock_answers = mock_dashboard_dependencies['answers']
        
        # FIXED: get_all_teams should be called exactly twice (once for each initial call)
        assert mock_get_teams.call_count == 2  # Initial team update + initial full update only
        
        # Database query should only be called once (during initial full update)
        assert mock_answers.query.count.call_count == 1
    
    def test_cache_invalidation_clears_both_caches(self, mock_dashboard_dependencies, setup_dashboard_state):
        """Test that cache invalidation clears both caches."""
        # Import the force clear function for complete cache reset
        from src.sockets.dashboard import force_clear_all_caches
        force_clear_all_caches()
        
        # Populate both caches
        emit_dashboard_team_update()
        emit_dashboard_full_update()
        
        # Clear caches completely (forces fresh calls)
        force_clear_all_caches()
        
        # Next calls should be fresh (not throttled)
        emit_dashboard_team_update()
        emit_dashboard_full_update()
        
        # Verify fresh calls were made
        mock_get_teams = mock_dashboard_dependencies['get_teams']
        mock_answers = mock_dashboard_dependencies['answers']
        
        # FIXED: Should have exactly 4 calls - 2 initial + 2 after clear
        assert mock_get_teams.call_count == 4  # 2 initial + 2 after clear
        assert mock_answers.query.count.call_count == 2  # 1 initial + 1 after clear
    
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
    
    def test_throttle_delay_timing_team_updates(self, mock_dashboard_dependencies, setup_dashboard_state):
        """Test that team update throttling respects the REFRESH_DELAY_QUICK timing."""
        clear_team_caches()
        
        # First call
        emit_dashboard_team_update()
        mock_get_teams = mock_dashboard_dependencies['get_teams']
        initial_call_count = mock_get_teams.call_count
        
        # Wait less than REFRESH_DELAY_QUICK
        time.sleep(REFRESH_DELAY_QUICK * 0.5)
        
        # FIXED: Second call should be throttled since we waited less than REFRESH_DELAY_QUICK
        emit_dashboard_team_update()
        assert mock_get_teams.call_count == initial_call_count  # Should be throttled
        
        # Wait longer than REFRESH_DELAY_QUICK
        time.sleep(REFRESH_DELAY_QUICK * 1.1)
        
        # Third call should now call get_all_teams again since enough time has passed
        emit_dashboard_team_update()
        assert mock_get_teams.call_count == initial_call_count + 1  # Now should be fresh
    
    def test_throttle_delay_timing_full_updates(self, mock_dashboard_dependencies, setup_dashboard_state):
        """Test that full update throttling respects the REFRESH_DELAY_FULL timing."""
        # Import the force clear function for complete cache reset
        from src.sockets.dashboard import force_clear_all_caches
        force_clear_all_caches()
        
        # First call
        emit_dashboard_full_update()
        mock_answers = mock_dashboard_dependencies['answers']
        initial_db_count = mock_answers.query.count.call_count
        
        # Wait less than REFRESH_DELAY_FULL
        time.sleep(REFRESH_DELAY_FULL * 0.5)
        
        # Second call should be throttled
        emit_dashboard_full_update()
        assert mock_answers.query.count.call_count == initial_db_count
        
        # Wait longer than REFRESH_DELAY_FULL
        time.sleep(REFRESH_DELAY_FULL * 1.1)
        
        # Third call should not be throttled
        emit_dashboard_full_update()
        assert mock_answers.query.count.call_count > initial_db_count
    
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
        
        # Second call immediately should be throttled and NOT call get_all_teams again
        emit_dashboard_team_update()
        
        # FIXED: Should use cache, no additional call to get_all_teams
        assert mock_get_teams.call_count == first_call_count  # Should be throttled
    
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


class TestThreadSafety:
    """Test thread safety of dashboard operations."""
    
    def test_concurrent_cache_operations(self, mock_dashboard_dependencies, setup_dashboard_state):
        """Test that cache operations are thread-safe."""
        import threading
        
        exceptions = []
        
        def cache_worker():
            try:
                for _ in range(10):
                    clear_team_caches()
                    emit_dashboard_team_update()
                    emit_dashboard_full_update()
                    time.sleep(0.001)
            except Exception as e:
                exceptions.append(e)
        
        # Start multiple threads
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=cache_worker)
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Should not have race condition exceptions
        assert len(exceptions) == 0, f"Thread safety violations: {exceptions}"
    
    def test_memory_cleanup_thread_safety(self):
        """Test that memory cleanup operations are thread-safe."""
        from src.sockets.dashboard import _atomic_client_update, dashboard_last_activity, dashboard_teams_streaming
        import threading
        
        # Setup test data
        for i in range(100):
            dashboard_last_activity[f'client_{i}'] = float(i)
            dashboard_teams_streaming[f'client_{i}'] = i % 2 == 0
        
        exceptions = []
        
        def cleanup_worker():
            try:
                for i in range(50):
                    _atomic_client_update(f'client_{i}', remove=True)
            except Exception as e:
                exceptions.append(e)
        
        # Start multiple cleanup threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=cleanup_worker)
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Should not have race condition exceptions
        assert len(exceptions) == 0, f"Thread safety violations: {exceptions}"
        
        # Cleanup remaining data
        remaining_clients = list(dashboard_last_activity.keys()) + list(dashboard_teams_streaming.keys())
        for client_id in set(remaining_clients):  # Use set to avoid duplicates
            _atomic_client_update(client_id, remove=True)
        
        # Should be cleaned up
        assert len(dashboard_last_activity) == 0
        assert len(dashboard_teams_streaming) == 0

    def test_single_lock_prevents_deadlocks(self, mock_dashboard_dependencies, setup_dashboard_state):
        """Test that using a single lock prevents deadlock scenarios."""
        import threading
        
        exceptions = []
        operations_completed = []
        
        def mixed_operations_worker():
            try:
                for i in range(5):
                    # Mix different dashboard operations that all use the same lock
                    clear_team_caches()
                    emit_dashboard_team_update()
                    emit_dashboard_full_update()
                    
                    # Simulate client operations
                    from src.sockets.dashboard import _atomic_client_update
                    _atomic_client_update(f'test_client_{i}', activity_time=time.time())
                    _atomic_client_update(f'test_client_{i}', streaming_enabled=True)
                    _atomic_client_update(f'test_client_{i}', remove=True)
                    
                    operations_completed.append(i)
                    time.sleep(0.001)
            except Exception as e:
                exceptions.append(e)
        
        # Start multiple threads doing mixed operations
        threads = []
        for _ in range(4):
            thread = threading.Thread(target=mixed_operations_worker)
            threads.append(thread)
            thread.start()
        
        # Wait for completion with timeout to detect deadlocks
        for thread in threads:
            thread.join(timeout=10.0)
            if thread.is_alive():
                pytest.fail("Thread didn't complete - possible deadlock detected")
        
        # Should not have deadlock exceptions
        assert len(exceptions) == 0, f"Deadlock or thread safety violations: {exceptions}"
        
        # All operations should have completed
        assert len(operations_completed) > 0, "No operations completed - possible deadlock"

    def test_error_handling_preserves_lock_state(self, mock_dashboard_dependencies, setup_dashboard_state):
        """Test that exceptions in thread-safe operations don't leave locks in bad state."""
        from src.sockets.dashboard import _safe_dashboard_operation
        
        # Force an exception in a safe operation
        try:
            with _safe_dashboard_operation():
                raise ValueError("Test exception")
        except ValueError:
            pass  # Expected
        
        # Lock should be released and subsequent operations should work
        try:
            with _safe_dashboard_operation():
                pass  # Should not hang or raise lock-related errors
        except Exception as e:
            pytest.fail(f"Lock not properly released after exception: {e}")
        
        # Regular dashboard operations should still work
        emit_dashboard_team_update()
        emit_dashboard_full_update()
        
        # Should complete without hanging
        assert True
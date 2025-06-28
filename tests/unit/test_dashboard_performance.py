"""
Tests for dashboard performance optimizations and lock minimization.
Tests lock contention reduction and performance with multiple clients.
"""
import pytest
import time
import threading
from unittest.mock import patch, MagicMock
from src.sockets.dashboard import (
    get_all_teams, emit_dashboard_team_update, emit_dashboard_full_update,
    clear_team_caches, force_clear_all_caches, dashboard_teams_streaming,
    dashboard_last_activity, _safe_dashboard_operation
)


class TestLockOptimizations:
    """Test that lock usage is minimized in optimized functions."""
    
    def test_get_all_teams_minimal_lock_usage(self, mock_state, mock_db_session):
        """Test that get_all_teams only locks for cache operations, not expensive computations."""
        # Clear caches first
        force_clear_all_caches()
        
        # Track lock usage
        lock_call_count = 0
        original_safe_operation = _safe_dashboard_operation
        
        def mock_safe_operation():
            nonlocal lock_call_count
            lock_call_count += 1
            return original_safe_operation()
        
        with patch('src.sockets.dashboard._safe_dashboard_operation', side_effect=mock_safe_operation), \
             patch('src.sockets.dashboard.Teams') as mock_teams, \
             patch('src.sockets.dashboard.PairQuestionRounds') as mock_rounds, \
             patch('src.sockets.dashboard.Answers') as mock_answers:
            
            # Mock database returns
            mock_teams.query.all.return_value = []
            mock_rounds.query.filter.return_value.order_by.return_value.all.return_value = []
            mock_answers.query.filter.return_value.order_by.return_value.all.return_value = []
            
            # First call should use lock twice: once for cache check, once for cache update
            result1 = get_all_teams()
            assert result1 == []
            assert lock_call_count == 2, f"Expected 2 lock calls, got {lock_call_count}"
            
            # Reset counter
            lock_call_count = 0
            
            # Second call within throttle window should use lock only once (cache check)
            result2 = get_all_teams()
            assert result2 == []
            assert lock_call_count == 1, f"Expected 1 lock call for cached result, got {lock_call_count}"
    
    def test_expensive_operations_outside_lock(self):
        """Test that database queries and computations happen outside locks."""
        force_clear_all_caches()
        
        # Track what happens inside vs outside locks
        operations_in_lock = []
        operations_outside_lock = []
        
        def track_lock_operation():
            # Mock expensive operations to track when they're called
            def mock_db_query():
                if threading.current_thread().name.endswith('_lock_thread'):
                    operations_in_lock.append('db_query')
                else:
                    operations_outside_lock.append('db_query')
                return []
            
            return mock_db_query
        
        with patch('src.sockets.dashboard.Teams') as mock_teams, \
             patch('src.sockets.dashboard.PairQuestionRounds') as mock_rounds, \
             patch('src.sockets.dashboard.Answers') as mock_answers:
            
            mock_teams.query.all = track_lock_operation()
            mock_rounds.query.filter.return_value.order_by.return_value.all = track_lock_operation()
            mock_answers.query.filter.return_value.order_by.return_value.all = track_lock_operation()
            
            get_all_teams()
            
            # Database operations should happen outside locks
            assert len(operations_in_lock) == 0, f"Database operations found inside lock: {operations_in_lock}"
            assert len(operations_outside_lock) >= 1, f"No database operations found outside lock"


class TestMultiClientPerformance:
    """Test performance with multiple dashboard clients."""
    
    def test_concurrent_get_all_teams_performance(self, mock_state, mock_db_session):
        """Test that multiple concurrent calls to get_all_teams don't block each other excessively."""
        force_clear_all_caches()
        
        # Setup
        with patch('src.sockets.dashboard.Teams') as mock_teams, \
             patch('src.sockets.dashboard.PairQuestionRounds') as mock_rounds, \
             patch('src.sockets.dashboard.Answers') as mock_answers:
            
            mock_teams.query.all.return_value = []
            mock_rounds.query.filter.return_value.order_by.return_value.all.return_value = []
            mock_answers.query.filter.return_value.order_by.return_value.all.return_value = []
            
            # Simulate multiple concurrent clients
            results = []
            exceptions = []
            start_times = []
            end_times = []
            
            def client_worker(client_id):
                try:
                    start_time = time.time()
                    start_times.append(start_time)
                    
                    result = get_all_teams()
                    results.append((client_id, len(result)))
                    
                    end_time = time.time()
                    end_times.append(end_time)
                except Exception as e:
                    exceptions.append((client_id, e))
            
            # Start 10 concurrent clients
            threads = []
            for i in range(10):
                thread = threading.Thread(target=client_worker, args=(i,))
                threads.append(thread)
                thread.start()
            
            # Wait for completion
            for thread in threads:
                thread.join(timeout=5.0)
                assert not thread.is_alive(), "Thread timed out - possible deadlock"
            
            # Verify results
            assert len(exceptions) == 0, f"Exceptions occurred: {exceptions}"
            assert len(results) == 10, f"Expected 10 results, got {len(results)}"
            
            # Performance check: operations should complete quickly
            total_time = max(end_times) - min(start_times)
            assert total_time < 2.0, f"Operations took too long: {total_time}s"
    
    def test_emit_functions_with_many_clients(self, mock_state, mock_socketio):
        """Test emit functions performance with many dashboard clients."""
        force_clear_all_caches()
        
        # Setup many clients
        many_clients = [f'client_{i}' for i in range(100)]
        mock_state.dashboard_clients = set(many_clients)
        
        # Set up streaming preferences (mix of streaming and non-streaming)
        for i, client_id in enumerate(many_clients):
            dashboard_teams_streaming[client_id] = (i % 3 == 0)  # Every 3rd client streams
            dashboard_last_activity[client_id] = time.time()
        
        # Mock dependencies
        with patch('src.sockets.dashboard.get_all_teams', return_value=[]) as mock_get_teams, \
             patch('src.sockets.dashboard.Answers') as mock_answers:
            
            mock_answers.query.count.return_value = 42
            
            start_time = time.time()
            
            # Test team update with many clients
            emit_dashboard_team_update()
            
            # Test full update with many clients  
            emit_dashboard_full_update()
            
            end_time = time.time()
            
            # Should complete quickly even with many clients
            elapsed_time = end_time - start_time
            assert elapsed_time < 1.0, f"Emit functions took too long with many clients: {elapsed_time}s"
            
            # Should emit to all clients
            assert mock_socketio.emit.call_count >= len(many_clients)
            
            # get_all_teams should be called minimal times (cached after first call)
            assert mock_get_teams.call_count <= 2, f"get_all_teams called too many times: {mock_get_teams.call_count}"
    
    def test_cache_efficiency_with_multiple_calls(self, mock_state, mock_db_session):
        """Test that caching works efficiently with multiple rapid calls."""
        force_clear_all_caches()
        
        db_call_count = 0
        
        def count_db_calls():
            nonlocal db_call_count
            db_call_count += 1
            return []
        
        with patch('src.sockets.dashboard.Teams') as mock_teams, \
             patch('src.sockets.dashboard.PairQuestionRounds') as mock_rounds, \
             patch('src.sockets.dashboard.Answers') as mock_answers:
            
            mock_teams.query.all.side_effect = count_db_calls
            mock_rounds.query.filter.return_value.order_by.return_value.all.return_value = []
            mock_answers.query.filter.return_value.order_by.return_value.all.return_value = []
            
            # Make multiple rapid calls
            for i in range(10):
                result = get_all_teams()
                assert result == []
                time.sleep(0.1)  # Small delay, but within throttle window
            
            # Should only hit database once due to caching
            assert db_call_count == 1, f"Expected 1 DB call, got {db_call_count}"


class TestLockContentionReduction:
    """Test that lock contention is reduced compared to previous implementation."""
    
    def test_concurrent_cache_operations_no_deadlock(self, mock_state):
        """Test that concurrent cache operations don't deadlock."""
        exceptions = []
        completed_operations = []
        
        def cache_worker(worker_id):
            try:
                for i in range(5):
                    # Mix different cache operations
                    if i % 3 == 0:
                        clear_team_caches()
                        completed_operations.append(f"worker_{worker_id}_clear_{i}")
                    elif i % 3 == 1:
                        get_all_teams()
                        completed_operations.append(f"worker_{worker_id}_get_{i}")
                    else:
                        emit_dashboard_team_update()
                        completed_operations.append(f"worker_{worker_id}_emit_{i}")
                    
                    time.sleep(0.01)  # Small delay
            except Exception as e:
                exceptions.append((worker_id, e))
        
        # Start multiple workers doing mixed operations
        threads = []
        for worker_id in range(5):
            thread = threading.Thread(target=cache_worker, args=(worker_id,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join(timeout=10.0)
            assert not thread.is_alive(), "Thread didn't complete - possible deadlock"
        
        # Verify no exceptions and operations completed
        assert len(exceptions) == 0, f"Exceptions during concurrent operations: {exceptions}"
        assert len(completed_operations) > 0, "No operations completed - possible deadlock"
    
    def test_socket_emissions_dont_block_cache_operations(self, mock_state, mock_socketio):
        """Test that socket emissions don't block cache operations."""
        force_clear_all_caches()
        
        # Setup clients
        mock_state.dashboard_clients = {'client1', 'client2'}
        dashboard_teams_streaming['client1'] = True
        dashboard_teams_streaming['client2'] = False
        
        # Track operation timings
        cache_operation_times = []
        emit_operation_times = []
        
        def cache_operation_worker():
            start_time = time.time()
            for _ in range(5):
                get_all_teams()
                clear_team_caches()
            end_time = time.time()
            cache_operation_times.append(end_time - start_time)
        
        def emit_operation_worker():
            start_time = time.time()
            for _ in range(5):
                emit_dashboard_team_update()
                emit_dashboard_full_update()
            end_time = time.time()
            emit_operation_times.append(end_time - start_time)
        
        # Run both types of operations concurrently
        cache_thread = threading.Thread(target=cache_operation_worker)
        emit_thread = threading.Thread(target=emit_operation_worker)
        
        cache_thread.start()
        emit_thread.start()
        
        cache_thread.join(timeout=5.0)
        emit_thread.join(timeout=5.0)
        
        # Both should complete without blocking each other
        assert not cache_thread.is_alive(), "Cache operations blocked"
        assert not emit_thread.is_alive(), "Emit operations blocked"
        assert len(cache_operation_times) == 1, "Cache operations didn't complete"
        assert len(emit_operation_times) == 1, "Emit operations didn't complete"
        
        # Operations should be fast (not blocked)
        assert cache_operation_times[0] < 2.0, f"Cache operations too slow: {cache_operation_times[0]}s"
        assert emit_operation_times[0] < 2.0, f"Emit operations too slow: {emit_operation_times[0]}s"


@pytest.fixture
def mock_state():
    """Mock the global state object."""
    with patch('src.sockets.dashboard.state') as mock_state:
        mock_state.dashboard_clients = set()
        mock_state.connected_players = set()
        mock_state.active_teams = {}
        mock_state.game_started = False
        mock_state.game_paused = False
        mock_state.answer_stream_enabled = True
        mock_state.game_mode = 'classic'
        mock_state.game_theme = 'classic'
        yield mock_state


@pytest.fixture
def mock_socketio():
    """Mock the socketio object."""
    with patch('src.sockets.dashboard.socketio') as mock_socketio:
        yield mock_socketio


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    with patch('src.sockets.dashboard.Teams') as mock_teams, \
         patch('src.sockets.dashboard.PairQuestionRounds') as mock_rounds, \
         patch('src.sockets.dashboard.Answers') as mock_answers:
        
        # Setup default returns
        mock_teams.query.all.return_value = []
        mock_teams.query.get.return_value = None
        mock_teams.query.filter_by.return_value.first.return_value = None
        
        mock_rounds.query.filter.return_value.order_by.return_value.all.return_value = []
        mock_answers.query.filter.return_value.order_by.return_value.all.return_value = []
        mock_answers.query.count.return_value = 0
        
        yield {
            'teams': mock_teams,
            'rounds': mock_rounds, 
            'answers': mock_answers
        } 
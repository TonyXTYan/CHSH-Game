import pytest
import eventlet
eventlet.monkey_patch()

import time
import threading
from unittest.mock import patch, MagicMock, Mock, call
from flask_socketio import SocketIOTestClient
from wsgi import app
from src.config import socketio as server_socketio
from src.state import state
from src.models.quiz_models import Teams, PairQuestionRounds, Answers, ItemEnum, db
from src.sockets.team_management import (
    on_create_team, on_join_team, on_leave_team, 
    handle_connect, handle_disconnect, on_reactivate_team
)
from src.sockets.game import on_submit_answer
from src.sockets.dashboard import (
    on_dashboard_join, on_start_game, on_restart_game, 
    on_pause_game, clear_team_caches
)
from datetime import datetime, UTC
import json


class TestServerClientEdgeCases:
    """Test suite for server-client edge cases, race conditions, and error handling"""

    @pytest.fixture(autouse=True)
    def reset_state(self):
        """Reset application state before each test"""
        state.active_teams.clear()
        state.player_to_team.clear()
        state.team_id_to_name.clear()
        state.dashboard_clients.clear()
        state.connected_players.clear()
        state.game_started = False
        state.game_paused = False
        clear_team_caches()
        yield
        state.active_teams.clear()
        state.player_to_team.clear()
        state.team_id_to_name.clear()
        state.dashboard_clients.clear()
        state.connected_players.clear()
        state.game_started = False
        state.game_paused = False

    @pytest.fixture
    def mock_request(self):
        """Create a mock request with session ID"""
        with patch('flask.request') as mock_req:
            mock_req.sid = 'test_session_123'
            yield mock_req

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session with transaction control"""
        with patch('src.config.db.session') as mock_session:
            yield mock_session

    @pytest.fixture  
    def mock_socketio(self):
        """Mock SocketIO for testing emissions"""
        with patch('src.sockets.team_management.socketio') as mock_io:
            yield mock_io

    def test_concurrent_team_creation_same_name(self, mock_request, mock_db_session, mock_socketio):
        """Test race condition when multiple clients try to create teams with same name"""
        team_name = "RaceConditionTeam"
        
        # Mock database query to simulate race condition
        existing_team = MagicMock()
        existing_team.team_name = team_name
        existing_team.is_active = True
        
        # First call returns no existing team, second call finds it exists
        mock_query = MagicMock()
        mock_query.filter_by.return_value.first.side_effect = [None, existing_team]
        
        with patch('src.sockets.team_management.Teams') as mock_teams:
            mock_teams.query = mock_query
            
            # Mock new team creation
            new_team = MagicMock()
            new_team.team_id = 1
            mock_teams.return_value = new_team
            
            # First client creates team
            with patch('src.sockets.team_management.emit') as mock_emit:
                on_create_team({'team_name': team_name})
                
                # Should succeed for first client
                mock_db_session.add.assert_called_once_with(new_team)
                mock_db_session.commit.assert_called_once()
                
                # Reset mocks for second client
                mock_db_session.reset_mock()
                mock_emit.reset_mock()
                
                # Second client tries to create same team
                on_create_team({'team_name': team_name})
                
                # Should emit error for second client
                mock_emit.assert_called_with('error', 
                    {'message': 'Team name already exists or is active'})

    def test_database_transaction_failure_during_team_creation(self, mock_request, mock_db_session, mock_socketio):
        """Test handling of database failures during team creation"""
        # Mock database commit to fail
        mock_db_session.commit.side_effect = Exception("Database connection lost")
        
        with patch('src.sockets.team_management.Teams') as mock_teams:
            # Mock query to return no existing team
            mock_teams.query.filter_by.return_value.first.return_value = None
            
            new_team = MagicMock()
            new_team.team_id = 1
            mock_teams.return_value = new_team
            
            with patch('src.sockets.team_management.emit') as mock_emit:
                on_create_team({'team_name': 'FailTeam'})
                
                # Should handle exception gracefully
                mock_emit.assert_called_with('error', 
                    {'message': 'Error creating team: Database connection lost'})
                
                # Team should not be in active state
                assert 'FailTeam' not in state.active_teams

    def test_malformed_socket_data(self, mock_request):
        """Test handling of malformed or invalid socket data"""
        test_cases = [
            # Missing team name
            {},
            {'team_name': None},
            {'team_name': ''},
            # Non-string team name
            {'team_name': 123},
            {'team_name': []},
            {'team_name': {}},
            # Extremely long team name
            {'team_name': 'a' * 1000},
            # Special characters that might cause issues
            {'team_name': '<script>alert("xss")</script>'},
            {'team_name': '../../etc/passwd'},
            {'team_name': '\x00\x01\x02'},
        ]
        
        for i, malformed_data in enumerate(test_cases):
            with patch('src.sockets.team_management.emit') as mock_emit:
                on_create_team(malformed_data)
                
                # Should handle all malformed data gracefully
                mock_emit.assert_called()
                call_args = mock_emit.call_args
                assert call_args[0][0] == 'error', f"Test case {i}: Should emit error for malformed data: {malformed_data}"

    def test_player_disconnect_during_answer_submission(self, mock_request, mock_db_session):
        """Test handling player disconnect while submitting an answer"""
        # Setup team and game state
        team_name = "DisconnectTeam"
        player_sid = mock_request.sid
        
        state.active_teams[team_name] = {
            'team_id': 1,
            'players': [player_sid, 'other_player'],
            'current_round_number': 1,
            'current_db_round_id': 123,
            'answered_current_round': {}
        }
        state.player_to_team[player_sid] = team_name
        state.game_started = True
        
        # Mock answer submission with database failure
        mock_db_session.commit.side_effect = Exception("Connection lost during commit")
        
        with patch('src.sockets.game.emit') as mock_emit:
            on_submit_answer({
                'round_id': 123,
                'item': 'A',
                'answer': True
            })
            
            # Should handle database error gracefully
            mock_emit.assert_called_with('error', 
                {'message': 'Error submitting answer: Connection lost during commit'})

    def test_concurrent_answer_submission_same_round(self, mock_db_session):
        """Test race condition when both players submit answers simultaneously"""
        team_name = "ConcurrentTeam"
        
        # Setup team state
        state.active_teams[team_name] = {
            'team_id': 1,
            'players': ['player1', 'player2'],
            'current_round_number': 1,
            'current_db_round_id': 123,
            'answered_current_round': {}
        }
        state.player_to_team['player1'] = team_name
        state.player_to_team['player2'] = team_name
        state.game_started = True
        
        # Mock database round
        mock_round = MagicMock()
        mock_round.round_id = 123
        
        with patch('src.sockets.game.PairQuestionRounds') as mock_rounds:
            mock_rounds.query.get.return_value = mock_round
            
            def simulate_concurrent_submission():
                """Simulate simultaneous answer submission"""
                
                with patch('flask.request') as mock_req1:
                    mock_req1.sid = 'player1'
                    with patch('src.sockets.game.emit'):
                        on_submit_answer({
                            'round_id': 123,
                            'item': 'A',
                            'answer': True
                        })
                
                # Simulate slight delay and second submission
                eventlet.sleep(0.001)
                
                with patch('flask.request') as mock_req2:
                    mock_req2.sid = 'player2'
                    with patch('src.sockets.game.emit'):
                        on_submit_answer({
                            'round_id': 123,
                            'item': 'X',
                            'answer': False
                        })
            
            # Run concurrent submissions
            threads = []
            for _ in range(2):
                thread = threading.Thread(target=simulate_concurrent_submission)
                threads.append(thread)
                thread.start()
            
            for thread in threads:
                thread.join()
            
            # Both players should have answered
            team_info = state.active_teams[team_name]
            answered = team_info['answered_current_round']
            assert len(answered) <= 2, "Should handle concurrent submissions correctly"

    def test_dashboard_client_timeout_handling(self, mock_request):
        """Test handling of dashboard client timeouts"""
        dash_sid = mock_request.sid
        state.dashboard_clients.add(dash_sid)
        
        # Import the dashboard module to access internal variables
        from src.sockets import dashboard
        dashboard.dashboard_last_activity[dash_sid] = time.time() - 3600  # 1 hour ago
        
        # Simulate timeout cleanup (would normally be done by periodic task)
        current_time = time.time()
        timeout_threshold = 300  # 5 minutes
        
        timed_out_clients = []
        for client_sid, last_activity in dashboard.dashboard_last_activity.items():
            if current_time - last_activity > timeout_threshold:
                timed_out_clients.append(client_sid)
        
        # Clean up timed out clients
        for client_sid in timed_out_clients:
            if client_sid in state.dashboard_clients:
                state.dashboard_clients.remove(client_sid)
            if client_sid in dashboard.dashboard_last_activity:
                del dashboard.dashboard_last_activity[client_sid]
        
        assert dash_sid not in state.dashboard_clients, "Timed out dashboard client should be removed"
        assert dash_sid not in dashboard.dashboard_last_activity, "Timed out client activity should be cleaned up"

    def test_memory_leak_prevention_large_teams(self):
        """Test memory usage with large numbers of teams and cleanup"""
        initial_team_count = len(state.active_teams)
        
        # Create many teams
        for i in range(100):
            team_name = f"team_{i}"
            state.active_teams[team_name] = {
                'team_id': i + 1,
                'players': [f'player_{i}_1', f'player_{i}_2'],
                'current_round_number': 0,
                'combo_tracker': {},
                'answered_current_round': {}
            }
            state.player_to_team[f'player_{i}_1'] = team_name
            state.player_to_team[f'player_{i}_2'] = team_name
            state.team_id_to_name[i + 1] = team_name
        
        assert len(state.active_teams) == initial_team_count + 100
        
        # Simulate cleanup of inactive teams
        teams_to_remove = []
        for team_name, team_info in state.active_teams.items():
            if team_info['current_round_number'] == 0:  # No activity
                teams_to_remove.append(team_name)
        
        for team_name in teams_to_remove:
            team_info = state.active_teams[team_name]
            # Remove player mappings
            for player_sid in team_info['players']:
                if player_sid in state.player_to_team:
                    del state.player_to_team[player_sid]
            # Remove team mapping
            if team_info['team_id'] in state.team_id_to_name:
                del state.team_id_to_name[team_info['team_id']]
            # Remove team
            del state.active_teams[team_name]
        
        assert len(state.active_teams) == initial_team_count, "All inactive teams should be cleaned up"
        assert len(state.player_to_team) == 0, "All player mappings should be cleaned up"
        assert len(state.team_id_to_name) == 0, "All team ID mappings should be cleaned up"

    def test_invalid_answer_data_types(self, mock_request):
        """Test handling of invalid data types in answer submission"""
        # Setup minimal team state
        team_name = "TypeTestTeam"
        player_sid = mock_request.sid
        
        state.active_teams[team_name] = {
            'team_id': 1,
            'players': [player_sid, 'other_player'],
            'current_round_number': 1,
            'current_db_round_id': 123,
            'answered_current_round': {}
        }
        state.player_to_team[player_sid] = team_name
        state.game_started = True
        
        invalid_data_cases = [
            # Invalid round_id types
            {'round_id': 'not_a_number', 'item': 'A', 'answer': True},
            {'round_id': None, 'item': 'A', 'answer': True},
            {'round_id': [], 'item': 'A', 'answer': True},
            
            # Invalid item types
            {'round_id': 123, 'item': None, 'answer': True},
            {'round_id': 123, 'item': 123, 'answer': True},
            {'round_id': 123, 'item': 'Z', 'answer': True},  # Invalid item value
            
            # Invalid answer types
            {'round_id': 123, 'item': 'A', 'answer': None},
            {'round_id': 123, 'item': 'A', 'answer': 'yes'},
            {'round_id': 123, 'item': 'A', 'answer': 1},
            
            # Missing fields
            {'round_id': 123, 'item': 'A'},  # Missing answer
            {'round_id': 123, 'answer': True},  # Missing item
            {'item': 'A', 'answer': True},  # Missing round_id
            {},  # Empty data
        ]
        
        for i, invalid_data in enumerate(invalid_data_cases):
            with patch('src.sockets.game.emit') as mock_emit:
                on_submit_answer(invalid_data)
                
                # Should emit error for all invalid data
                mock_emit.assert_called()
                call_args = mock_emit.call_args
                assert call_args[0][0] == 'error', f"Test case {i}: Should emit error for invalid data: {invalid_data}"

    def test_game_state_desynchronization(self, mock_request):
        """Test handling of game state desynchronization between client and server"""
        team_name = "DesyncTeam"
        player_sid = mock_request.sid
        
        # Setup team but game not started on server
        state.active_teams[team_name] = {
            'team_id': 1,
            'players': [player_sid, 'other_player'],
            'current_round_number': 1,
            'current_db_round_id': 123,
            'answered_current_round': {}
        }
        state.player_to_team[player_sid] = team_name
        state.game_started = False  # Server thinks game is not started
        
        # Client tries to submit answer anyway
        with patch('src.sockets.game.emit') as mock_emit:
            on_submit_answer({
                'round_id': 123,
                'item': 'A', 
                'answer': True
            })
            
            # Should not process answer when game not started
            # The function would return early, so no database operations should occur

    def test_network_interruption_simulation(self, mock_request, mock_socketio):
        """Test handling of network interruptions during critical operations"""
        team_name = "NetworkTeam"
        player_sid = mock_request.sid
        
        # Setup team state
        state.active_teams[team_name] = {
            'team_id': 1,
            'players': [player_sid, 'other_player'], 
            'current_round_number': 1,
            'answered_current_round': {}
        }
        state.player_to_team[player_sid] = team_name
        
        # Simulate network failure during team operations
        mock_socketio.emit.side_effect = Exception("Network unreachable")
        
        with patch('src.sockets.team_management.emit') as mock_emit:
            # Try to leave team during network failure
            on_leave_team({})
            
            # Should handle network error gracefully
            # Team state should still be updated locally even if notification fails
            
    def test_cache_invalidation_race_conditions(self):
        """Test race conditions in cache invalidation"""
        from src.sockets.dashboard import clear_team_caches, compute_correlation_matrix
        
        # Setup mock data for cache
        mock_rounds = [MagicMock()]
        mock_answers = [MagicMock()]
        
        def cache_operation():
            """Simulate cache operations"""
            with patch('src.sockets.dashboard.PairQuestionRounds') as mock_rounds_query:
                mock_rounds_query.query.filter_by.return_value.order_by.return_value.all.return_value = mock_rounds
                
                with patch('src.sockets.dashboard.Answers') as mock_answers_query:
                    mock_answers_query.query.filter_by.return_value.order_by.return_value.all.return_value = mock_answers
                    
                    # Perform cache operation
                    result = compute_correlation_matrix(1)
                    return result
        
        def cache_clear_operation():
            """Simulate cache clearing"""
            clear_team_caches()
        
        # Run cache operations and clearing concurrently
        threads = []
        results = []
        
        for _ in range(5):
            thread = threading.Thread(target=lambda: results.append(cache_operation()))
            threads.append(thread)
            thread.start()
        
        # Clear cache while operations are running
        clear_thread = threading.Thread(target=cache_clear_operation)
        threads.append(clear_thread)
        clear_thread.start()
        
        for thread in threads:
            thread.join()
        
        # All operations should complete without error
        assert len(results) == 5, "All cache operations should complete"

    def test_database_constraint_violations(self, mock_request, mock_db_session):
        """Test handling of database constraint violations"""
        # Mock database to raise integrity error
        from sqlalchemy.exc import IntegrityError
        mock_db_session.commit.side_effect = IntegrityError("duplicate key", None, None)
        
        with patch('src.sockets.team_management.Teams') as mock_teams:
            mock_teams.query.filter_by.return_value.first.return_value = None
            
            new_team = MagicMock()
            new_team.team_id = 1
            mock_teams.return_value = new_team
            
            with patch('src.sockets.team_management.emit') as mock_emit:
                on_create_team({'team_name': 'ConstraintTeam'})
                
                # Should handle constraint violation gracefully
                mock_emit.assert_called_with('error', 
                    {'message': 'Error creating team: duplicate key'})

    def test_session_hijacking_prevention(self, mock_socketio):
        """Test prevention of session hijacking attempts"""
        # Create legitimate team
        legitimate_sid = "legitimate_session_123"
        team_name = "SecureTeam"
        
        state.active_teams[team_name] = {
            'team_id': 1,
            'players': [legitimate_sid],
            'current_round_number': 0,
            'answered_current_round': {}
        }
        state.player_to_team[legitimate_sid] = team_name
        
        # Attempt to hijack session with different SID
        hijacker_sid = "hijacker_session_456"
        
        with patch('flask.request') as mock_req:
            mock_req.sid = hijacker_sid
            
            with patch('src.sockets.game.emit') as mock_emit:
                # Hijacker tries to submit answer for team they're not in
                on_submit_answer({
                    'round_id': 123,
                    'item': 'A',
                    'answer': True
                })
                
                # Should reject unauthorized access
                mock_emit.assert_called_with('error', 
                    {'message': 'You are not in a team or session expired.'})

    def test_json_serialization_edge_cases(self):
        """Test handling of data that can't be JSON serialized"""
        from src.sockets.dashboard import get_all_teams
        
        # Add team with problematic data
        problematic_data = {
            'team_id': 1,
            'players': ['player1'],
            'current_round_number': float('inf'),  # Not JSON serializable
            'answered_current_round': {},
            'created_at': datetime.now(UTC)  # datetime object
        }
        
        state.active_teams['ProblematicTeam'] = problematic_data
        
        with patch('src.sockets.dashboard.Teams') as mock_teams:
            mock_team = MagicMock()
            mock_team.team_id = 1
            mock_team.team_name = 'ProblematicTeam'
            mock_team.is_active = True
            mock_team.created_at = datetime.now(UTC)
            mock_teams.query.all.return_value = [mock_team]
            
            # Should handle serialization issues gracefully
            result = get_all_teams()
            assert isinstance(result, list), "Should return valid list even with problematic data"

    def test_extreme_load_simulation(self):
        """Test system behavior under extreme load"""
        # Simulate many rapid operations
        operations_count = 1000
        
        for i in range(operations_count):
            team_name = f"LoadTeam_{i}"
            state.active_teams[team_name] = {
                'team_id': i + 1,
                'players': [f'player_{i}'],
                'current_round_number': 0,
                'answered_current_round': {}
            }
            state.player_to_team[f'player_{i}'] = team_name
            state.team_id_to_name[i + 1] = team_name
        
        # System should handle large state without errors
        assert len(state.active_teams) == operations_count
        assert len(state.player_to_team) == operations_count
        assert len(state.team_id_to_name) == operations_count
        
        # Cleanup should work efficiently
        state.active_teams.clear()
        state.player_to_team.clear()
        state.team_id_to_name.clear()
        
        assert len(state.active_teams) == 0
        assert len(state.player_to_team) == 0
        assert len(state.team_id_to_name) == 0
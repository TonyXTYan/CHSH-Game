import pytest
from unittest.mock import patch, MagicMock
from src.sockets.dashboard import (
    on_pause_game, compute_correlation_matrix, on_dashboard_join,
    on_start_game, on_restart_game, get_all_teams, emit_dashboard_full_update,
    on_keep_alive, on_disconnect, emit_dashboard_team_update
)
from src.config import app
from src.state import state
from src.models.quiz_models import Teams, Answers, PairQuestionRounds
from uncertainties import ufloat
from enum import Enum
import warnings
from datetime import datetime, UTC
from datetime import datetime, UTC

class MockQuestionItem(Enum):
    A = 'A'
    B = 'B'
    X = 'X'
    Y = 'Y'

def create_mock_round(round_id, p1_item, p2_item):
    round_obj = MagicMock()
    round_obj.round_id = round_id
    round_obj.player1_item = MockQuestionItem[p1_item]
    round_obj.player2_item = MockQuestionItem[p2_item]
    round_obj.timestamp_initiated = datetime.now(UTC)
    return round_obj

def create_mock_answer(round_id, item, response, timestamp=None):
    answer = MagicMock()
    answer.question_round_id = round_id
    answer.assigned_item = MockQuestionItem[item]
    answer.response_value = response
    answer.timestamp = timestamp or datetime.now(UTC)
    return answer

@pytest.fixture
def test_client():
    return app.test_client()

@pytest.fixture
def mock_request():
    with app.test_request_context() as ctx:
        ctx.request.sid = 'test_dashboard_sid'
        yield ctx.request


@pytest.fixture
def mock_socketio():
    with patch('src.sockets.dashboard.socketio') as mock_io:
        yield mock_io

@pytest.fixture
def mock_state():
    with patch('src.sockets.dashboard.state') as mock_state:
        mock_state.dashboard_clients = {'test_dashboard_sid'}
        mock_state.active_teams = {'team1': {'players': ['p1', 'p2']}}
        mock_state.game_paused = False
        mock_state.game_started = False
        mock_state.connected_players = {'player1', 'player2'}
        mock_state.answer_stream_enabled = True
        yield mock_state

@pytest.fixture
def mock_emit():
    with patch('src.sockets.dashboard.emit') as mock_emit:
        yield mock_emit

@pytest.fixture
def mock_db_session():
    with patch('src.config.db.session') as mock_session:
        yield mock_session

@pytest.fixture
def mock_team():
    team = MagicMock()
    team.team_id = 1
    team.team_name = "Test Team"
    return team

def test_pause_game_toggles_state(mock_request, mock_state, mock_socketio, mock_emit):
    """Test that pause_game properly toggles game state and notifies clients"""
    # Initial state is unpaused
    assert not mock_state.game_paused

    # Call pause_game
    on_pause_game()

    # Verify state was toggled
    assert mock_state.game_paused

    # Verify teams were notified
    mock_socketio.emit.assert_any_call('game_state_update', 
                                    {'paused': True}, 
                                    room='team1')

    # Call pause_game again
    on_pause_game()

    # Verify state was toggled back
    assert not mock_state.game_paused

    # Verify teams were notified of unpause
    mock_socketio.emit.assert_any_call('game_state_update', 
                                    {'paused': False}, 
                                    room='team1')

def test_pause_game_unauthorized(mock_request, mock_state, mock_socketio, mock_emit):
    """Test that unauthorized clients cannot pause the game"""
    # Remove dashboard client status
    mock_state.dashboard_clients = set()
    
    # Try to pause game
    on_pause_game()

    # Verify state remained unchanged
    assert not mock_state.game_paused

    # Verify error was emitted
    mock_emit.assert_called_once_with('error', 
                                   {'message': 'Unauthorized: Not a dashboard client'})

    # Verify no team notifications were sent
    mock_socketio.emit.assert_not_called()

def test_compute_correlation_matrix_empty_team(mock_team, mock_db_session):
    """Test correlation matrix computation with no answers"""
    with patch('src.sockets.dashboard.PairQuestionRounds') as mock_rounds:
        mock_rounds.query.filter_by.return_value.order_by.return_value.all.return_value = []
        
        with patch('src.sockets.dashboard.Answers') as mock_answers:
            mock_answers.query.filter_by.return_value.order_by.return_value.all.return_value = []
            
            result = compute_correlation_matrix(mock_team.team_id)
            corr_matrix, item_values, avg_balance, balance_dict, resp_dict, corr_sums, pair_counts = result
            
            # Check matrix dimensions and default values
            assert len(corr_matrix) == 4
            assert all(len(row) == 4 for row in corr_matrix)
            assert all(all(cell == (0, 0) for cell in row) for row in corr_matrix)
            assert item_values == ['A', 'B', 'X', 'Y']
            assert avg_balance == 0.0
            assert balance_dict == {}
            assert resp_dict == {}

def test_compute_correlation_matrix_multiple_rounds(mock_team, mock_db_session):
    """Test correlation matrix computation with multiple rounds"""
    # Create mock rounds
    rounds = [
        create_mock_round(1, 'A', 'X'),
        create_mock_round(2, 'A', 'Y'),
        create_mock_round(3, 'B', 'X')
    ]
    
    # Create corresponding answers
    answers = [
        create_mock_answer(1, 'A', True),
        create_mock_answer(1, 'X', True),
        create_mock_answer(2, 'A', False),
        create_mock_answer(2, 'Y', True),
        create_mock_answer(3, 'B', True),
        create_mock_answer(3, 'X', True)
    ]
    
    with patch('src.sockets.dashboard.PairQuestionRounds') as mock_rounds:
        mock_rounds.query.filter_by.return_value.order_by.return_value.all.return_value = rounds
        
        with patch('src.sockets.dashboard.Answers') as mock_answers:
            mock_answers.query.filter_by.return_value.order_by.return_value.all.return_value = answers
            
            result = compute_correlation_matrix(mock_team.team_id)
            corr_matrix, item_values, _, _, _, corr_sums, pair_counts = result
            
            # Check specific correlations
            a_idx = item_values.index('A')
            x_idx = item_values.index('X')
            y_idx = item_values.index('Y')
            
            # A-X had one matching pair (True, True)
            assert corr_matrix[a_idx][x_idx] == (1, 1)
            
            # A-Y had one opposing pair (False, True)
            assert corr_matrix[a_idx][y_idx] == (-1, 1)

def test_compute_correlation_matrix_cross_term_stat(mock_team, mock_db_session):
    """Test cross-term combination statistic calculation"""
    rounds = [
        create_mock_round(1, 'A', 'X'),  # Perfect correlation
        create_mock_round(2, 'A', 'Y'),  # Perfect anti-correlation
        create_mock_round(3, 'B', 'X'),  # Perfect correlation
        create_mock_round(4, 'B', 'Y')   # Perfect correlation
    ]
    
    answers = [
        create_mock_answer(1, 'A', True), create_mock_answer(1, 'X', True),   # +1
        create_mock_answer(2, 'A', True), create_mock_answer(2, 'Y', False),  # -1
        create_mock_answer(3, 'B', True), create_mock_answer(3, 'X', True),   # +1
        create_mock_answer(4, 'B', True), create_mock_answer(4, 'Y', True)    # +1
    ]
    
    with patch('src.sockets.dashboard.PairQuestionRounds') as mock_rounds:
        mock_rounds.query.filter_by.return_value.order_by.return_value.all.return_value = rounds
        
        with patch('src.sockets.dashboard.Answers') as mock_answers:
            mock_answers.query.filter_by.return_value.order_by.return_value.all.return_value = answers
            
            result = compute_correlation_matrix(mock_team.team_id)
            _, _, _, _, _, corr_sums, pair_counts = result
            
            # Check pair counts are correct
            assert pair_counts[('A', 'X')] == 1
            assert pair_counts[('A', 'Y')] == 1
            assert pair_counts[('B', 'X')] == 1
            assert pair_counts[('B', 'Y')] == 1
            
            # Check correlation sums
            assert corr_sums[('A', 'X')] == 1
            assert corr_sums[('A', 'Y')] == -1
            assert corr_sums[('B', 'X')] == 1
            assert corr_sums[('B', 'Y')] == 1

def test_compute_correlation_matrix_same_item_balance_mixed(mock_team, mock_db_session):
    """Test same-item balance calculation with mixed responses"""
    rounds = [
        create_mock_round(1, 'A', 'A'),
        create_mock_round(2, 'A', 'A')
    ]
    
    answers = [
        create_mock_answer(1, 'A', True), create_mock_answer(1, 'A', True),
        create_mock_answer(2, 'A', False), create_mock_answer(2, 'A', False)
    ]
    
    with patch('src.sockets.dashboard.PairQuestionRounds') as mock_rounds:
        mock_rounds.query.filter_by.return_value.order_by.return_value.all.return_value = rounds
        
        with patch('src.sockets.dashboard.Answers') as mock_answers:
            mock_answers.query.filter_by.return_value.order_by.return_value.all.return_value = answers
            
            result = compute_correlation_matrix(mock_team.team_id)
            _, _, avg_balance, balance_dict, resp_dict, _, _ = result
            
            # Should have equal true and false responses
            assert resp_dict['A']['true'] == 2
            assert resp_dict['A']['false'] == 2
            # Perfect balance = 1.0
            assert balance_dict['A'] == 1.0
            assert avg_balance == 1.0

def test_compute_correlation_matrix_invalid_data(mock_team, mock_db_session):
    """Test handling of invalid or inconsistent data"""
    round1 = create_mock_round(1, 'A', 'X')
    
    # Create inconsistent answers (wrong items for the round)
    invalid_answers = [
        create_mock_answer(1, 'B', True),  # Wrong item
        create_mock_answer(1, 'Y', False)  # Wrong item
    ]
    
    with patch('src.sockets.dashboard.PairQuestionRounds') as mock_rounds:
        mock_rounds.query.filter_by.return_value.order_by.return_value.all.return_value = [round1]
        
        with patch('src.sockets.dashboard.Answers') as mock_answers:
            mock_answers.query.filter_by.return_value.order_by.return_value.all.return_value = invalid_answers
            
            result = compute_correlation_matrix(mock_team.team_id)
            corr_matrix, item_values, _, _, _, corr_sums, pair_counts = result
            
            # Matrix should contain all zeros due to invalid data
            assert all(all(cell == (0, 0) for cell in row) for row in corr_matrix)
            assert all(count == 0 for count in pair_counts.values())
            assert all(sum_ == 0 for sum_ in corr_sums.values())

def test_compute_correlation_matrix_error_handling(mock_team, mock_db_session):
    """Test error handling in correlation matrix computation"""
    with patch('src.sockets.dashboard.PairQuestionRounds') as mock_rounds:
        mock_rounds.query.filter_by.side_effect = Exception("Database error")
        
        result = compute_correlation_matrix(mock_team.team_id)
        corr_matrix, item_values, avg_balance, balance_dict, resp_dict, corr_sums, pair_counts = result
        
        # Should return default values on error
        assert len(corr_matrix) == 4
        assert all(len(row) == 4 for row in corr_matrix)
        assert all(all(cell == (0, 0) for cell in row) for row in corr_matrix)
        assert item_values == ['A', 'B', 'X', 'Y']
        assert avg_balance == 0.0
        assert balance_dict == {}
        assert resp_dict == {}

def test_dashboard_api_endpoint(test_client, mock_db_session):
    """Test the /api/dashboard/data endpoint"""
    mock_answer = MagicMock()
    mock_answer.answer_id = 1
    mock_answer.team_id = 1
    mock_answer.player_session_id = "player1"
    mock_answer.question_round_id = 1
    mock_answer.assigned_item = MockQuestionItem.A
    mock_answer.response_value = True
    mock_answer.timestamp = datetime.now(UTC)
    
    mock_team = MagicMock()
    mock_team.team_name = "Test Team"
    
    with patch('src.sockets.dashboard.Answers') as mock_answers:
        mock_answers.query.order_by.return_value.all.return_value = [mock_answer]
        
        with patch('src.sockets.dashboard.Teams') as mock_teams:
            mock_teams.query.get.return_value = mock_team
            
            response = test_client.get('/api/dashboard/data')
            assert response.status_code == 200
            data = response.json
            
            assert 'answers' in data
            assert len(data['answers']) == 1
            answer_data = data['answers'][0]
            assert answer_data['answer_id'] == 1
            assert answer_data['team_name'] == "Test Team"
            assert answer_data['assigned_item'] == 'A'

def test_dashboard_api_endpoint_error(test_client, mock_db_session):
    """Test error handling in the /api/dashboard/data endpoint"""
    with patch('src.sockets.dashboard.Answers') as mock_answers:
        mock_answers.query.order_by.side_effect = Exception("Database error")
        
        response = test_client.get('/api/dashboard/data')
        assert response.status_code == 500
        assert 'error' in response.json

def test_on_keep_alive(mock_request, mock_state):
    """Test keep-alive functionality"""
    with patch('src.sockets.dashboard.emit') as mock_emit:
        with patch('src.sockets.dashboard.time') as mock_time:
            mock_time.return_value = 12345
            
            mock_state.dashboard_clients = {'test_dashboard_sid'}
            on_keep_alive()
            
            # Verify acknowledgment was sent
            mock_emit.assert_called_once_with('keep_alive_ack', room='test_dashboard_sid')
            
            # Verify timestamp was updated
            from src.sockets.dashboard import dashboard_last_activity
            assert dashboard_last_activity['test_dashboard_sid'] == 12345

def test_on_disconnect(mock_request, mock_state):
    """Test disconnect handler"""
    mock_state.dashboard_clients = {'test_dashboard_sid'}
    from src.sockets.dashboard import dashboard_last_activity
    dashboard_last_activity['test_dashboard_sid'] = 12345
    
    on_disconnect()
    
    # Verify client was removed
    assert 'test_dashboard_sid' not in mock_state.dashboard_clients
    assert 'test_dashboard_sid' not in dashboard_last_activity

def test_emit_dashboard_team_update(mock_state, mock_socketio):
    """Test dashboard team update emission"""
    with patch('src.sockets.dashboard.get_all_teams') as mock_get_teams:
        mock_get_teams.return_value = [{'team_name': 'team1'}]
        
        from src.sockets.dashboard import emit_dashboard_team_update
        emit_dashboard_team_update()
        
        mock_socketio.emit.assert_called_with('team_status_changed_for_dashboard', {
            'teams': [{'team_name': 'team1'}],
            'connected_players_count': 2
        }, room='test_dashboard_sid')

def test_error_handling_in_socket_events(mock_request, mock_state, mock_emit):
    """Test error handling in socket event handlers"""
    # Test error in dashboard_join
    with patch('src.sockets.dashboard.get_all_teams') as mock_get_teams:
        mock_get_teams.side_effect = Exception("Database error")
        on_dashboard_join()
        mock_emit.assert_called_with('error', {'message': 'Error joining dashboard: Database error'})
    
    # Test error in start_game
    mock_emit.reset_mock()
    with patch('src.sockets.dashboard.start_new_round_for_pair') as mock_start_round:
        mock_start_round.side_effect = Exception("Game error")
        on_start_game()
        mock_emit.assert_called_with('error', {'message': 'Error starting game: Game error'})

def test_on_dashboard_join_with_callback(mock_request, mock_state, mock_socketio):
    """Test dashboard join with callback function"""
    mock_callback = MagicMock()
    
    with patch('src.sockets.dashboard.get_all_teams') as mock_get_teams:
        mock_get_teams.return_value = [{'team_name': 'team1'}]
        
        with patch('src.sockets.dashboard.Answers') as mock_answers:
            mock_answers.query.count.return_value = 10
            
            # Call on_dashboard_join with callback
            on_dashboard_join(callback=mock_callback)
            
            # Verify callback was called with correct data
            mock_callback.assert_called_once()
            callback_data = mock_callback.call_args[0][0]
            assert 'teams' in callback_data
            assert callback_data['total_answers_count'] == 10
            assert callback_data['connected_players_count'] == 2
            assert callback_data['game_state']['started'] == False
            assert callback_data['game_state']['streaming_enabled'] == True

def test_on_start_game(mock_request, mock_state, mock_socketio):
    """Test game start functionality"""
    with patch('src.sockets.dashboard.start_new_round_for_pair') as mock_start_round:
        on_start_game()
        
        # Verify game state was updated
        assert mock_state.game_started == True
        
        # Verify teams were notified
        mock_socketio.emit.assert_any_call('game_start', {'game_started': True}, room='team1')
        
        # Verify dashboard was notified
        mock_socketio.emit.assert_any_call('game_started', room='test_dashboard_sid')
        
        # Verify global state change notification
        mock_socketio.emit.assert_any_call('game_state_changed', {'game_started': True})
        
        # Verify new round was started for paired team
        mock_start_round.assert_called_once_with('team1')

def test_on_restart_game(mock_request, mock_state, mock_socketio, mock_db_session):
    """Test game restart functionality"""
    # Setup team state
    team_info = {
        'current_round_number': 5,
        'current_db_round_id': 123,
        'answered_current_round': {'player1': True},
        'combo_tracker': {'A-X': 3}
    }
    mock_state.active_teams = {'team1': team_info}
    
    on_restart_game()
    
    # Verify game state was updated
    assert mock_state.game_started == False
    
    # Verify database was cleared
    mock_db_session.begin_nested.assert_called_once()
    
    # Verify team state was reset
    assert team_info['current_round_number'] == 0
    assert team_info['current_db_round_id'] == None
    assert team_info['answered_current_round'] == {}
    assert team_info['combo_tracker'] == {}
    
    # Verify notifications were sent
    mock_socketio.emit.assert_any_call('game_reset', room='team1')
    mock_socketio.emit.assert_any_call('game_state_changed', {'game_started': False})
    mock_socketio.emit.assert_any_call('game_reset_complete', room='test_dashboard_sid')

def test_get_all_teams(mock_state, mock_db_session):
    """Test getting serialized team data"""
    mock_team = MagicMock()
    mock_team.team_id = 1
    mock_team.team_name = "Test Team"
    mock_team.is_active = True
    mock_team.created_at = datetime.now(UTC)
    
    with patch('src.sockets.dashboard.Teams') as mock_teams:
        mock_teams.query.all.return_value = [mock_team]
        
        # Set up compute_correlation_matrix mock return values
        corr_matrix = [[(0, 0) for _ in range(4)] for _ in range(4)]
        item_values = ['A', 'B', 'X', 'Y']
        
        with patch('src.sockets.dashboard.compute_correlation_matrix') as mock_compute:
            mock_compute.return_value = (
                corr_matrix, item_values, 0.0, {}, {}, {}, {}
            )
            
            with patch('src.sockets.dashboard.compute_team_hashes') as mock_hashes:
                mock_hashes.return_value = ('hash1', 'hash2')
                
                result = get_all_teams()
                
                assert len(result) == 1
                team_data = result[0]
                assert team_data['team_name'] == "Test Team"
                assert team_data['team_id'] == 1
                assert team_data['is_active'] == True
                assert team_data['history_hash1'] == 'hash1'
                assert team_data['history_hash2'] == 'hash2'
                assert 'correlation_matrix' in team_data
                assert 'correlation_stats' in team_data

def test_emit_dashboard_full_update(mock_state, mock_socketio):
    """Test full dashboard update emission"""
    with patch('src.sockets.dashboard.get_all_teams') as mock_get_teams:
        mock_get_teams.return_value = [{'team_name': 'team1'}]
        
        with patch('src.sockets.dashboard.Answers') as mock_answers:
            mock_answers.query.count.return_value = 10
            
            # Test update for specific client
            emit_dashboard_full_update('specific_client')
            mock_socketio.emit.assert_called_with('dashboard_update', {
                'teams': [{'team_name': 'team1'}],
                'total_answers_count': 10,
                'connected_players_count': 2,
                'game_state': {
                    'started': False,
                    'paused': False,
                    'streaming_enabled': True
                }
            }, room='specific_client')
            
            # Test update for all dashboard clients
            mock_socketio.emit.reset_mock()
            emit_dashboard_full_update()
            mock_socketio.emit.assert_called_with('dashboard_update', {
                'teams': [{'team_name': 'team1'}],
                'total_answers_count': 10,
                'connected_players_count': 2,
                'game_state': {
                    'started': False,
                    'paused': False,
                    'streaming_enabled': True
                }
            }, room='test_dashboard_sid')

def test_download_csv_endpoint(test_client, mock_db_session):
    """Test the /download CSV endpoint"""
    mock_answer = MagicMock()
    mock_answer.answer_id = 1
    mock_answer.team_id = 1
    mock_answer.player_session_id = "player1"
    mock_answer.question_round_id = 1
    mock_answer.assigned_item = MockQuestionItem.A
    mock_answer.response_value = True
    mock_answer.timestamp = datetime.now(UTC)
    
    mock_team = MagicMock()
    mock_team.team_name = "Test Team"
    
    with patch('src.sockets.dashboard.Answers') as mock_answers:
        mock_answers.query.order_by.return_value.all.return_value = [mock_answer]
        
        with patch('src.sockets.dashboard.Teams') as mock_teams:
            mock_teams.query.get.return_value = mock_team
            
            response = test_client.get('/download')
            assert response.status_code == 200
            assert response.headers['Content-Type'] == 'text/csv; charset=utf-8'
            assert 'attachment' in response.headers.get('Content-Disposition', '')
            assert 'chsh-game-data.csv' in response.headers.get('Content-Disposition', '')
            
            # Check CSV content
            csv_content = response.get_data(as_text=True)
            lines = csv_content.strip().split('\n')
            
            # Should have header + 1 data row
            assert len(lines) >= 2
            
            # Check header
            header = lines[0]
            expected_headers = ['Timestamp', 'Team Name', 'Team ID', 'Player ID', 'Round ID', 'Question Item (A/B/X/Y)', 'Answer (True/False)']
            assert all(h in header for h in expected_headers)
            
            # Check data row
            data_row = lines[1].split(',')
            assert 'Test Team' in data_row
            assert 'player1' in data_row
            assert 'A' in data_row
            assert 'True' in data_row

def test_download_csv_endpoint_error(test_client, mock_db_session):
    """Test error handling in the /download CSV endpoint"""
    with patch('src.sockets.dashboard.Answers') as mock_answers:
        mock_answers.query.order_by.side_effect = Exception("Database error")
        
        response = test_client.get('/download')
        assert response.status_code == 500
        assert 'Error generating CSV' in response.get_data(as_text=True)

def test_download_csv_endpoint_empty_data(test_client, mock_db_session):
    """Test the /download CSV endpoint with no data"""
    with patch('src.sockets.dashboard.Answers') as mock_answers:
        mock_answers.query.order_by.return_value.all.return_value = []
        
        response = test_client.get('/download')
        assert response.status_code == 200
        assert response.headers['Content-Type'] == 'text/csv; charset=utf-8'
        
        # Should still have header row
        csv_content = response.get_data(as_text=True)
        lines = csv_content.strip().split('\n')
        assert len(lines) >= 1  # At least header row
        
        # Check header is present
        header = lines[0]
        expected_headers = ['Timestamp', 'Team Name', 'Team ID', 'Player ID', 'Round ID', 'Question Item (A/B/X/Y)', 'Answer (True/False)']
        assert all(h in header for h in expected_headers)

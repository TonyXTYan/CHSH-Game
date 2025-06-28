import pytest
import eventlet
eventlet.monkey_patch()

from unittest.mock import MagicMock, patch, ANY
from datetime import datetime
from flask import request
from src.config import app, socketio
from src.sockets.game import on_submit_answer
from src.state import state
from src.models.quiz_models import Teams, PairQuestionRounds, Answers, ItemEnum
from typing import Dict, Any

@pytest.fixture
def app_context():
    with app.app_context():
        # Initialize socketio extension
        app.extensions['socketio'] = socketio
        yield app

@pytest.fixture
def mock_request_context(app_context):
    with app_context.test_request_context('/') as context:
        # Add SocketIO specific attributes to request
        context.request.sid = 'test_sid'
        context.request.namespace = '/'
        yield context.request

def test_submit_answer_invalid_team(mock_request_context):
    """Test answer submission when player is not in a team"""
    # Mock flask_socketio.emit directly where it's imported in game.py
    with patch('src.sockets.game.emit') as mock_emit:
        # Ensure player is not in any team
        state.player_to_team.clear()
        
        # Submit answer
        data = {
            'round_id': 1,
            'item': 'A',
            'answer': True
        }
        
        on_submit_answer(data)
        
        # Verify error was emitted
        mock_emit.assert_called_once_with(
            'error', 
            {'message': 'You are not in a team or session expired.'}
        )

def test_submit_answer_game_paused(mock_request_context):
    """Test answer submission when game is paused"""
    # Mock flask_socketio.emit directly where it's imported in game.py
    with patch('src.sockets.game.emit') as mock_emit:
        # Set up player in a team but game paused
        state.player_to_team['test_sid'] = 'Test Team'
        state.game_paused = True
        
        # Submit answer
        data = {
            'round_id': 1,
            'item': 'A',
            'answer': True
        }
        
        on_submit_answer(data)
        
        # Verify error was emitted
        mock_emit.assert_called_once_with(
            'error',
            {'message': 'Game is currently paused.'}
        )
        
        # Reset state for other tests
        state.game_paused = False

def test_duplicate_answer_submission(mock_request_context):
    """Test that a player cannot submit an answer twice for the same round"""
    with patch('src.sockets.game.emit') as mock_emit, \
         patch('src.sockets.game.db.session') as mock_session, \
         patch('src.sockets.game.PairQuestionRounds') as mock_rounds:
        
        # Set up valid team state
        test_team = 'Test Team'
        test_round_id = 1
        state.player_to_team['test_sid'] = test_team
        state.active_teams[test_team] = {
            'team_id': 1,
            'players': ['test_sid', 'other_player_sid'],
            'current_db_round_id': test_round_id,
            'current_round_number': 1,
            'answered_current_round': {},
            'status': 'active'
        }
        
        # Mock database round query
        mock_round = MagicMock()
        mock_rounds.query.get.return_value = mock_round
        
        # First submission should succeed
        data = {
            'round_id': test_round_id,
            'item': 'A',
            'answer': True
        }
        on_submit_answer(data)
        
        # Second submission should fail
        mock_emit.reset_mock()  # Clear previous emit calls
        on_submit_answer(data)
        
        # Verify error was emitted for duplicate submission
        mock_emit.assert_called_once_with(
            'error',
            {'message': 'You have already answered this round.'}
        )
        
        # Clean up state for other tests
        state.player_to_team.clear()
        state.active_teams.clear()

def test_round_completion_when_both_players_answer(mock_request_context):
    """Test that round completes correctly when both players submit answers"""
    with patch('src.sockets.game.emit') as mock_emit, \
         patch('src.sockets.game.socketio.emit') as mock_socketio_emit, \
         patch('src.sockets.game.db.session') as mock_session, \
         patch('src.sockets.game.PairQuestionRounds') as mock_rounds, \
         patch('src.sockets.game.Answers') as mock_answers, \
         patch('src.sockets.game.start_new_round_for_pair') as mock_start_new_round:
        
        # Set up valid team state
        test_team = 'Test Team'
        test_round_id = 1
        state.player_to_team['test_sid'] = test_team
        state.active_teams[test_team] = {
            'team_id': 1,
            'players': ['test_sid', 'other_player_sid'],
            'current_db_round_id': test_round_id,
            'current_round_number': 1,
            'answered_current_round': {},
            'status': 'active'
        }
        
        # Mock database round query
        mock_round = MagicMock()
        mock_round.player1_item.value = 'A'
        mock_round.player2_item.value = 'B'
        mock_rounds.query.get.return_value = mock_round
        
        # Mock answers query
        mock_answer1 = MagicMock()
        mock_answer1.assigned_item.value = 'A'
        mock_answer1.response_value = True
        
        mock_answer2 = MagicMock()
        mock_answer2.assigned_item.value = 'B'
        mock_answer2.response_value = False
        
        mock_answers.query.filter_by.return_value.all.return_value = [mock_answer1, mock_answer2]
        
        # First player submits answer
        data = {
            'round_id': test_round_id,
            'item': 'A',
            'answer': True
        }
        on_submit_answer(data)
        
        # Switch to second player
        request.sid = 'other_player_sid'
        state.player_to_team['other_player_sid'] = test_team
        
        # Second player submits answer
        data = {
            'round_id': test_round_id,
            'item': 'B',
            'answer': False
        }
        on_submit_answer(data)
        
        # Verify round_complete was emitted to team with enhanced data
        round_complete_calls = [call for call in mock_socketio_emit.call_args_list 
                               if call[0][0] == 'round_complete']
        assert len(round_complete_calls) > 0, "round_complete should have been emitted"
        
        round_complete_data = round_complete_calls[0][0][1]
        assert round_complete_data['team_name'] == test_team
        assert round_complete_data['round_number'] == 1
        # Enhanced version should include last_round_details
        assert 'last_round_details' in round_complete_data
        
        # Verify new round was started
        mock_start_new_round.assert_called_once_with(test_team)
        
        # Clean up state for other tests
        state.player_to_team.clear()
        state.active_teams.clear()

def test_dashboard_notifications_on_answer(mock_request_context):
    """Test that dashboard clients receive notifications when answers are submitted"""
    with patch('src.sockets.game.emit') as mock_emit, \
         patch('src.sockets.game.socketio.emit') as mock_socketio_emit, \
         patch('src.sockets.game.db.session') as mock_session, \
         patch('src.sockets.game.PairQuestionRounds') as mock_rounds, \
         patch('src.sockets.dashboard.emit_dashboard_team_update') as mock_dashboard_update:
        
        # Set up valid team state
        test_team = 'Test Team'
        test_round_id = 1
        state.player_to_team['test_sid'] = test_team
        state.active_teams[test_team] = {
            'team_id': 1,
            'players': ['test_sid', 'other_player_sid'],
            'current_db_round_id': test_round_id,
            'current_round_number': 1,
            'answered_current_round': {},
            'status': 'active'
        }
        
        # Mock database round query
        mock_round = MagicMock()
        mock_rounds.query.get.return_value = mock_round
        
        # Add some dashboard clients
        state.dashboard_clients = {'dash1', 'dash2'}
        
        # Submit answer
        data = {
            'round_id': test_round_id,
            'item': 'A',
            'answer': True
        }
        on_submit_answer(data)
        
        # Verify dashboard notifications
        mock_socketio_emit.assert_any_call(
            'new_answer_for_dashboard',
            {
                'timestamp': ANY,  # We can't predict exact timestamp
                'team_name': test_team,
                'team_id': 1,
                'player_session_id': 'test_sid',
                'question_round_id': test_round_id,
                'assigned_item': 'A',
                'response_value': True
            },
            to='dash1'
        )
        
        mock_socketio_emit.assert_any_call(
            'new_answer_for_dashboard',
            {
                'timestamp': ANY,
                'team_name': test_team,
                'team_id': 1,
                'player_session_id': 'test_sid',
                'question_round_id': test_round_id,
                'assigned_item': 'A',
                'response_value': True
            },
            to='dash2'
        )
        
        # Verify dashboard team update was called
        mock_dashboard_update.assert_called_once()
        
        # Clean up state for other tests
        state.player_to_team.clear()
        state.active_teams.clear()
        state.dashboard_clients.clear()

def test_submit_answer_round_not_found(mock_request_context):
    """Test error when round is not found in DB"""
    with patch('src.sockets.game.emit') as mock_emit, \
         patch('src.sockets.game.db.session') as mock_session, \
         patch('src.sockets.game.PairQuestionRounds') as mock_rounds:
        # Set up valid team state
        test_team = 'Test Team'
        test_round_id = 1
        state.player_to_team['test_sid'] = test_team
        state.active_teams[test_team] = {
            'team_id': 1,
            'players': ['test_sid', 'other_player_sid'],
            'current_db_round_id': test_round_id,
            'current_round_number': 1,
            'answered_current_round': {},
            'status': 'active'
        }
        # Mock database round query returns None
        mock_rounds.query.get.return_value = None
        data = {
            'round_id': test_round_id,
            'item': 'A',
            'answer': True
        }
        on_submit_answer(data)
        mock_emit.assert_called_with('error', {'message': 'Round not found in DB.'})
        # Clean up state
        state.player_to_team.clear()
        state.active_teams.clear()

def test_submit_answer_invalid_item(mock_request_context):
    """Test error when invalid item is submitted"""
    with patch('src.sockets.game.emit') as mock_emit, \
         patch('src.sockets.game.db.session') as mock_session, \
         patch('src.sockets.game.PairQuestionRounds') as mock_rounds:
        # Set up valid team state
        test_team = 'Test Team'
        test_round_id = 1
        state.player_to_team['test_sid'] = test_team
        state.active_teams[test_team] = {
            'team_id': 1,
            'players': ['test_sid', 'other_player_sid'],
            'current_db_round_id': test_round_id,
            'current_round_number': 1,
            'answered_current_round': {},
            'status': 'active'
        }
        # Mock database round query returns a valid round
        mock_round = MagicMock()
        mock_rounds.query.get.return_value = mock_round
        data = {
            'round_id': test_round_id,
            'item': 'INVALID',
            'answer': True
        }
        on_submit_answer(data)
        mock_emit.assert_called_with('error', {'message': 'Invalid item in answer.'})
        # Clean up state
        state.player_to_team.clear()
        state.active_teams.clear()

def test_submit_answer_incomplete_data(mock_request_context):
    """Test error when answer submission data is incomplete"""
    with patch('src.sockets.game.emit') as mock_emit, \
         patch('src.sockets.game.db.session') as mock_session, \
         patch('src.sockets.game.PairQuestionRounds') as mock_rounds:
        # Set up valid team state
        test_team = 'Test Team'
        test_round_id = 1
        state.player_to_team['test_sid'] = test_team
        state.active_teams[test_team] = {
            'team_id': 1,
            'players': ['test_sid', 'other_player_sid'],
            'current_db_round_id': test_round_id,
            'current_round_number': 1,
            'answered_current_round': {},
            'status': 'active'
        }
        # Mock database round query returns a valid round
        mock_round = MagicMock()
        mock_rounds.query.get.return_value = mock_round
        # Missing 'item' and 'answer'
        data = {
            'round_id': test_round_id
        }
        on_submit_answer(data)
        mock_emit.assert_called_with('error', {'message': 'Invalid answer submission data.'})
        # Clean up state
        state.player_to_team.clear()
        state.active_teams.clear()
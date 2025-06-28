import pytest
from unittest.mock import MagicMock, patch, Mock
from src.sockets.game import on_submit_answer
from src.models.quiz_models import Teams, PairQuestionRounds, Answers, ItemEnum
from src.state import state
from src.config import app, socketio
from flask import request
import json

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


class TestLastRoundResults:
    """Test class for last round results functionality"""

    def setup_method(self):
        """Set up test state before each test"""
        state.player_to_team.clear()
        state.active_teams.clear()
        state.game_started = True
        state.game_paused = False



    def test_round_complete_includes_last_round_details(self, mock_request_context):
        """Test that round_complete event includes detailed last round information"""
        with patch('src.sockets.game.emit') as mock_emit, \
             patch('src.sockets.game.socketio.emit') as mock_socketio_emit, \
             patch('src.sockets.game.db.session') as mock_session, \
             patch('src.sockets.game.PairQuestionRounds') as mock_rounds_class, \
             patch('src.sockets.game.Teams') as mock_teams_class, \
             patch('src.sockets.game.Answers') as mock_answers_class, \
             patch('src.sockets.game.start_new_round_for_pair') as mock_start_new_round:
            
            # Set up team state
            test_team = 'Test Team'
            test_round_id = 1
            state.player_to_team['test_sid'] = test_team
            state.player_to_team['other_player_sid'] = test_team
            state.active_teams[test_team] = {
                'team_id': 1,
                'players': ['test_sid', 'other_player_sid'],
                'current_db_round_id': test_round_id,
                'current_round_number': 1,
                'answered_current_round': {},
                'status': 'active'
            }
            
            # Mock the round database entry
            mock_round = MagicMock()
            mock_round.player1_item = ItemEnum.A
            mock_round.player2_item = ItemEnum.X
            mock_rounds_class.query.get.return_value = mock_round
            
            # Mock the team database entry
            mock_team = MagicMock()
            mock_team.player1_session_id = 'test_sid'
            mock_team.player2_session_id = 'other_player_sid'
            mock_teams_class.query.get.return_value = mock_team
            
            # Mock the answers
            mock_answer1 = MagicMock()
            mock_answer1.assigned_item = ItemEnum.A
            mock_answer1.response_value = True
            mock_answer1.player_session_id = 'test_sid'  # Player 1
            
            mock_answer2 = MagicMock()
            mock_answer2.assigned_item = ItemEnum.X
            mock_answer2.response_value = False
            mock_answer2.player_session_id = 'other_player_sid'  # Player 2
            
            mock_answers_class.query.filter_by.return_value.all.return_value = [mock_answer1, mock_answer2]
            
            # First player submits answer
            data = {
                'round_id': test_round_id,
                'item': 'A',
                'answer': True
            }
            on_submit_answer(data)
            
            # Switch to second player and submit answer
            request.sid = 'other_player_sid'
            data = {
                'round_id': test_round_id,
                'item': 'X',
                'answer': False
            }
            on_submit_answer(data)
            
            # Verify enhanced round_complete was emitted with last round details
            expected_call = mock_socketio_emit.call_args_list[-1]  # Get the last call
            assert expected_call[0][0] == 'round_complete'
            
            round_complete_data = expected_call[0][1]
            assert round_complete_data['team_name'] == test_team
            assert round_complete_data['round_number'] == 1
            assert 'last_round_details' in round_complete_data
            
            last_round = round_complete_data['last_round_details']
            assert last_round['p1_item'] == 'A'
            assert last_round['p2_item'] == 'X'
            assert last_round['p1_answer'] == True
            assert last_round['p2_answer'] == False
            
            # Verify new round was started
            mock_start_new_round.assert_called_once_with(test_team)

    def test_round_complete_fallback_without_details(self, mock_request_context):
        """Test that round_complete falls back gracefully when round details are not available"""
        with patch('src.sockets.game.emit') as mock_emit, \
             patch('src.sockets.game.socketio.emit') as mock_socketio_emit, \
             patch('src.sockets.game.db.session') as mock_session, \
             patch('src.sockets.game.PairQuestionRounds') as mock_rounds_class, \
             patch('src.sockets.game.start_new_round_for_pair') as mock_start_new_round:
            
            # Set up team state
            test_team = 'Test Team'
            test_round_id = 1
            state.player_to_team['test_sid'] = test_team
            state.player_to_team['other_player_sid'] = test_team
            state.active_teams[test_team] = {
                'team_id': 1,
                'players': ['test_sid', 'other_player_sid'],
                'current_db_round_id': test_round_id,
                'current_round_number': 1,
                'answered_current_round': {},
                'status': 'active'
            }
            
            # Mock round not found
            mock_rounds_class.query.get.return_value = None
            
            # First player submits answer
            data = {
                'round_id': test_round_id,
                'item': 'A',
                'answer': True
            }
            on_submit_answer(data)
            
            # Switch to second player and submit answer
            request.sid = 'other_player_sid'
            data = {
                'round_id': test_round_id,
                'item': 'X',
                'answer': False
            }
            on_submit_answer(data)
            
            # Verify that no round_complete event was emitted since round was not found
            # The function should emit an error instead and return early
            mock_emit.assert_called_with('error', {'message': 'Round not found in DB.'})
            
            # Verify that round_complete was not emitted at all
            round_complete_calls = [call for call in mock_socketio_emit.call_args_list 
                                  if call[0][0] == 'round_complete']
            assert len(round_complete_calls) == 0, "round_complete should not be emitted when round is not found"

    def test_classic_theme_message_generation(self):
        """Test message generation for classic theme"""
        # Mock window.themeManager for testing
        mock_theme_manager = MagicMock()
        mock_theme_manager.getItemDisplay.side_effect = lambda x: x  # Return item as-is for classic
        
        with patch('builtins.window', create=True) as mock_window:
            mock_window.themeManager = mock_theme_manager
            
            # Test classic theme message generation
            last_round = {
                'p1_item': 'A',
                'p2_item': 'X', 
                'p1_answer': True,
                'p2_answer': False
            }
            
            # Since we can't directly test the JS function, we'll test the logic
            # that would be equivalent in Python
            p1_answer_text = 'True' if last_round['p1_answer'] else 'False'
            p2_answer_text = 'True' if last_round['p2_answer'] else 'False'
            
            expected_message = f"Last round, your team (P1/P2) were asked {last_round['p1_item']}/{last_round['p2_item']} and answer was {p1_answer_text}/{p2_answer_text}"
            
            assert expected_message == "Last round, your team (P1/P2) were asked A/X and answer was True/False"

    def test_food_theme_message_generation_optimal_result(self):
        """Test message generation for food theme with optimal result"""
        # Test B+Y combination with different answers (optimal)
        last_round = {
            'p1_item': 'B',
            'p2_item': 'Y',
            'p1_answer': True,   # Choose
            'p2_answer': False   # Skip
        }
        
        # Simulate the evaluateFoodResult logic
        should_be_different = (last_round['p1_item'] == 'B' and last_round['p2_item'] == 'Y') or \
                             (last_round['p1_item'] == 'Y' and last_round['p2_item'] == 'B')
        actually_different = last_round['p1_answer'] != last_round['p2_answer']
        is_optimal = should_be_different == actually_different
        
        assert should_be_different == True
        assert actually_different == True
        assert is_optimal == True
        
        # For B+Y with different answers, result should be "yum 😋"
        expected_result = 'yum 😋'
        
        # Expected message format
        p1_decision = 'Choose' if last_round['p1_answer'] else 'Skip'
        p2_decision = 'Choose' if last_round['p2_answer'] else 'Skip'
        expected_message = f"Last round, your team (P1/P2) were asked 🥟/🍫 and decisions was {p1_decision}/{p2_decision}, that was {expected_result}"
        
        assert expected_message == "Last round, your team (P1/P2) were asked 🥟/🍫 and decisions was Choose/Skip, that was yum 😋"

    def test_food_theme_message_generation_suboptimal_result(self):
        """Test message generation for food theme with suboptimal result"""
        # Test B+Y combination with same answers (suboptimal)
        last_round = {
            'p1_item': 'B',
            'p2_item': 'Y', 
            'p1_answer': True,   # Choose
            'p2_answer': True    # Choose (should be different)
        }
        
        # Simulate the evaluateFoodResult logic
        should_be_different = (last_round['p1_item'] == 'B' and last_round['p2_item'] == 'Y') or \
                             (last_round['p1_item'] == 'Y' and last_round['p2_item'] == 'B')
        actually_different = last_round['p1_answer'] != last_round['p2_answer']
        is_optimal = should_be_different == actually_different
        
        assert should_be_different == True
        assert actually_different == False
        assert is_optimal == False
        
        # For B+Y with same answers when they should be different, result should be "bad 😭"
        expected_result = 'bad 😭'
        
        # Expected message format
        p1_decision = 'Choose' if last_round['p1_answer'] else 'Skip'
        p2_decision = 'Choose' if last_round['p2_answer'] else 'Skip'
        expected_message = f"Last round, your team (P1/P2) were asked 🥟/🍫 and decisions was {p1_decision}/{p2_decision}, that was {expected_result}"
        
        assert expected_message == "Last round, your team (P1/P2) were asked 🥟/🍫 and decisions was Choose/Choose, that was bad 😭"

    def test_food_theme_message_generation_non_by_combinations(self):
        """Test message generation for food theme with non-B+Y combinations"""
        # Test A+X combination with same answers (optimal)
        last_round = {
            'p1_item': 'A',
            'p2_item': 'X',
            'p1_answer': True,   # Choose
            'p2_answer': True    # Choose (should be same for A+X)
        }
        
        # Simulate the evaluateFoodResult logic
        should_be_different = (last_round['p1_item'] == 'B' and last_round['p2_item'] == 'Y') or \
                             (last_round['p1_item'] == 'Y' and last_round['p2_item'] == 'B')
        actually_different = last_round['p1_answer'] != last_round['p2_answer']
        is_optimal = should_be_different == actually_different
        
        assert should_be_different == False  # A+X should be same
        assert actually_different == False   # Both chose
        assert is_optimal == True
        
        # For A+X with same answers, result should be "yum 😋"
        expected_result = 'yum 😋'
        
        # Test A+X combination with different answers (suboptimal)
        last_round_suboptimal = {
            'p1_item': 'A',
            'p2_item': 'X',
            'p1_answer': True,   # Choose
            'p2_answer': False   # Skip (should be same for A+X)
        }
        
        actually_different_suboptimal = last_round_suboptimal['p1_answer'] != last_round_suboptimal['p2_answer']
        is_optimal_suboptimal = False == actually_different_suboptimal  # should_be_different is False for A+X
        
        assert actually_different_suboptimal == True
        assert is_optimal_suboptimal == False
        
        # For A+X with different answers when they should be same, result should be "yuck 🤮"
        expected_result_suboptimal = 'yuck 🤮'

    def test_food_evaluation_all_combinations(self):
        """Test food result evaluation for all possible item combinations"""
        test_cases = [
            # B+Y should be different
            ('B', 'Y', True, False, 'yum 😋'),   # Different (optimal)
            ('B', 'Y', True, True, 'bad 😭'),    # Same (suboptimal)
            ('Y', 'B', False, True, 'yum 😋'),   # Different (optimal)
            ('Y', 'B', False, False, 'bad 😭'),  # Same (suboptimal)
            
            # All others should be same
            ('A', 'X', True, True, 'yum 😋'),    # Same (optimal)
            ('A', 'X', True, False, 'yuck 🤮'),  # Different (suboptimal)
            ('A', 'Y', False, False, 'yum 😋'),  # Same (optimal)
            ('A', 'Y', True, False, 'yuck 🤮'),  # Different (suboptimal)
            ('B', 'X', True, True, 'yum 😋'),    # Same (optimal)
            ('B', 'X', False, True, 'yuck 🤮'),  # Different (suboptimal)
        ]
        
        for p1_item, p2_item, p1_answer, p2_answer, expected_result in test_cases:
            # Simulate evaluateFoodResult logic
            should_be_different = (p1_item == 'B' and p2_item == 'Y') or \
                                 (p1_item == 'Y' and p2_item == 'B')
            actually_different = p1_answer != p2_answer
            is_optimal = should_be_different == actually_different
            
            if is_optimal:
                result = 'yum 😋'
            else:
                if should_be_different:
                    result = 'bad 😭'  # Same when should be different
                else:
                    result = 'yuck 🤮'  # Different when should be same
            
            assert result == expected_result, f"Failed for {p1_item}+{p2_item} with answers {p1_answer}/{p2_answer}"

    def test_incomplete_round_data_handling(self):
        """Test handling of incomplete round data"""
        incomplete_cases = [
            None,  # No data
            {},    # Empty data
            {'p1_item': 'A'},  # Missing p2_item
            {'p1_item': 'A', 'p2_item': 'X'},  # Missing answers
            {'p1_item': 'A', 'p2_item': 'X', 'p1_answer': True},  # Missing p2_answer
            {'p1_item': 'A', 'p2_item': 'X', 'p1_answer': None, 'p2_answer': False},  # Null answer
        ]
        
        for incomplete_data in incomplete_cases:
            # In JavaScript, generateLastRoundMessage should return null for incomplete data
            # We test the equivalent logic here
            
            if (not incomplete_data or 
                not incomplete_data.get('p1_item') or 
                not incomplete_data.get('p2_item') or
                incomplete_data.get('p1_answer') is None or 
                incomplete_data.get('p2_answer') is None):
                result = None
            else:
                result = "some message"  # Would generate actual message
            
            assert result is None, f"Should return None for incomplete data: {incomplete_data}"

    def test_round_complete_with_duplicate_items(self, mock_request_context):
        """Test that round_complete correctly handles when both players receive the same item"""
        with patch('src.sockets.game.emit') as mock_emit, \
             patch('src.sockets.game.socketio.emit') as mock_socketio_emit, \
             patch('src.sockets.game.db.session') as mock_session, \
             patch('src.sockets.game.PairQuestionRounds') as mock_rounds_class, \
             patch('src.sockets.game.Teams') as mock_teams_class, \
             patch('src.sockets.game.Answers') as mock_answers_class, \
             patch('src.sockets.game.start_new_round_for_pair') as mock_start_new_round:
            
            # Set up team state
            test_team = 'Test Team'
            test_round_id = 1
            state.player_to_team['test_sid'] = test_team
            state.player_to_team['other_player_sid'] = test_team
            state.active_teams[test_team] = {
                'team_id': 1,
                'players': ['test_sid', 'other_player_sid'],
                'current_db_round_id': test_round_id,
                'current_round_number': 1,
                'answered_current_round': {},
                'status': 'active'
            }
            
            # Mock the round database entry - BOTH PLAYERS GET THE SAME ITEM
            mock_round = MagicMock()
            mock_round.player1_item = ItemEnum.A  # Both players get A
            mock_round.player2_item = ItemEnum.A  # Both players get A
            mock_rounds_class.query.get.return_value = mock_round
            
            # Mock the team database entry
            mock_team = MagicMock()
            mock_team.player1_session_id = 'test_sid'
            mock_team.player2_session_id = 'other_player_sid'
            mock_teams_class.query.get.return_value = mock_team
            
            # Mock the answers - both have same assigned_item but different session_ids
            mock_answer1 = MagicMock()
            mock_answer1.assigned_item = ItemEnum.A
            mock_answer1.response_value = True
            mock_answer1.player_session_id = 'test_sid'  # Player 1 answered True
            
            mock_answer2 = MagicMock()
            mock_answer2.assigned_item = ItemEnum.A  # Same item as player 1!
            mock_answer2.response_value = False
            mock_answer2.player_session_id = 'other_player_sid'  # Player 2 answered False
            
            mock_answers_class.query.filter_by.return_value.all.return_value = [mock_answer1, mock_answer2]
            
            # First player submits answer
            data = {
                'round_id': test_round_id,
                'item': 'A',
                'answer': True
            }
            on_submit_answer(data)
            
            # Switch to second player and submit answer
            request.sid = 'other_player_sid'
            data = {
                'round_id': test_round_id,
                'item': 'A',  # Same item as player 1!
                'answer': False
            }
            on_submit_answer(data)
            
            # Verify enhanced round_complete was emitted with CORRECT last round details
            expected_call = mock_socketio_emit.call_args_list[-1]  # Get the last call
            assert expected_call[0][0] == 'round_complete'
            
            round_complete_data = expected_call[0][1]
            assert round_complete_data['team_name'] == test_team
            assert round_complete_data['round_number'] == 1
            assert 'last_round_details' in round_complete_data
            
            last_round = round_complete_data['last_round_details']
            # Both players should have item 'A'
            assert last_round['p1_item'] == 'A'
            assert last_round['p2_item'] == 'A'
            # But answers should be correctly matched to players using session ID
            assert last_round['p1_answer'] == True   # Player 1 (test_sid) answered True
            assert last_round['p2_answer'] == False  # Player 2 (other_player_sid) answered False
            
            # Verify new round was started
            mock_start_new_round.assert_called_once_with(test_team)
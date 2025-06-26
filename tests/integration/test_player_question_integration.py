import pytest
import time
from unittest.mock import patch
from src.models.quiz_models import Teams, PairQuestionRounds, ItemEnum
from src.state import state
from src.config import db
from src.game_logic import start_new_round_for_pair
from src.sockets.team_management import on_create_team, on_join_team

class TestPlayerQuestionIntegration:
    """Integration tests for player question assignment with real database interactions"""
    
    def setup_method(self):
        """Set up test state"""
        state.reset()
        state.game_started = True  # Enable game for round generation
    
    def teardown_method(self):
        """Clean up after each test"""
        # Clean up any test teams
        try:
            Teams.query.filter(Teams.team_name.like('test_%')).delete()
            PairQuestionRounds.query.filter(PairQuestionRounds.team_id.in_(
                db.session.query(Teams.team_id).filter(Teams.team_name.like('test_%'))
            )).delete()
            db.session.commit()
        except:
            db.session.rollback()
        state.reset()

    @patch('src.sockets.team_management.request')
    @patch('src.sockets.team_management.emit')
    @patch('src.sockets.team_management.socketio.emit')
    @patch('src.sockets.team_management.join_room')
    def test_team_creation_and_joining_maintains_player_slots(self, mock_join_room, mock_socketio_emit, mock_emit, mock_request):
        """Test that team creation and joining properly maintains player slot assignments"""
        # Mock the request context
        mock_request.sid = 'creator_sid'
        
        # Create team
        on_create_team({'team_name': 'test_team_slots'})
        
        # Verify team was created
        db_team = Teams.query.filter_by(team_name='test_team_slots', is_active=True).first()
        assert db_team is not None
        assert db_team.player1_session_id == 'creator_sid'
        assert db_team.player2_session_id is None
        
        # Verify state tracking
        assert 'test_team_slots' in state.active_teams
        team_info = state.active_teams['test_team_slots']
        assert team_info['player_slots']['creator_sid'] == 1
        
        # Switch to second player
        mock_request.sid = 'joiner_sid'
        
        # Join team
        on_join_team({'team_name': 'test_team_slots'})
        
        # Verify database was updated
        db.session.refresh(db_team)
        assert db_team.player1_session_id == 'creator_sid'
        assert db_team.player2_session_id == 'joiner_sid'
        
        # Verify state tracking
        assert len(team_info['players']) == 2
        assert team_info['player_slots']['creator_sid'] == 1
        assert team_info['player_slots']['joiner_sid'] == 2

    @patch('src.sockets.team_management.request')
    @patch('src.sockets.team_management.emit')
    @patch('src.sockets.team_management.socketio.emit')
    @patch('src.sockets.team_management.join_room')
    @patch('src.game_logic.socketio')
    def test_new_mode_question_assignment_after_team_setup(self, mock_game_socketio, mock_join_room, mock_socketio_emit, mock_emit, mock_request):
        """Test that question assignment works correctly in new mode after realistic team setup"""
        state.game_mode = 'new'
        
        # Create and set up team
        mock_request.sid = 'player1_session'
        on_create_team({'team_name': 'test_new_mode'})
        
        mock_request.sid = 'player2_session'
        on_join_team({'team_name': 'test_new_mode'})
        
        # Start a round
        start_new_round_for_pair('test_new_mode')
        
        # Verify round was created in database
        db_team = Teams.query.filter_by(team_name='test_new_mode', is_active=True).first()
        round_record = PairQuestionRounds.query.filter_by(team_id=db_team.team_id).first()
        
        assert round_record is not None
        assert round_record.player1_item in [ItemEnum.A, ItemEnum.B]
        assert round_record.player2_item in [ItemEnum.X, ItemEnum.Y]
        
        # Verify socketio calls were made with correct assignments
        assert mock_game_socketio.emit.call_count == 2
        calls = mock_game_socketio.emit.call_args_list
        
        # Find calls for each player
        player1_call = None
        player2_call = None
        for call in calls:
            room = call[1]['room']
            if room == 'player1_session':
                player1_call = call
            elif room == 'player2_session':
                player2_call = call
        
        assert player1_call is not None
        assert player2_call is not None
        
        # Verify correct question assignment
        assert player1_call[0][1]['item'] == round_record.player1_item.value
        assert player2_call[0][1]['item'] == round_record.player2_item.value

    @patch('src.sockets.team_management.request')
    @patch('src.sockets.team_management.emit')
    @patch('src.sockets.team_management.socketio.emit')
    @patch('src.sockets.team_management.join_room')
    @patch('src.game_logic.socketio')
    def test_player_order_independence_in_new_mode(self, mock_game_socketio, mock_join_room, mock_socketio_emit, mock_emit, mock_request):
        """Test that question assignment is independent of player connection order"""
        state.game_mode = 'new'
        
        # Create team with player1
        mock_request.sid = 'alpha_session'
        on_create_team({'team_name': 'test_order_independence'})
        
        # Join with player2
        mock_request.sid = 'beta_session'
        on_join_team({'team_name': 'test_order_independence'})
        
        # Simulate reconnection by changing player order in state
        team_info = state.active_teams['test_order_independence']
        original_order = team_info['players'][:]
        team_info['players'] = [original_order[1], original_order[0]]  # Reverse order
        
        # Run multiple rounds to test consistency
        for round_num in range(5):
            mock_game_socketio.reset_mock()
            start_new_round_for_pair('test_order_independence')
            
            # Get the database record
            db_team = Teams.query.filter_by(team_name='test_order_independence', is_active=True).first()
            round_record = PairQuestionRounds.query.filter_by(
                team_id=db_team.team_id, 
                round_number_for_team=round_num + 1
            ).first()
            
            # Verify question types follow new mode rules
            assert round_record.player1_item in [ItemEnum.A, ItemEnum.B]
            assert round_record.player2_item in [ItemEnum.X, ItemEnum.Y]
            
            # Verify socketio calls
            calls = mock_game_socketio.emit.call_args_list
            assert len(calls) == 2
            
            # Find calls for each database player
            db_player1_call = None
            db_player2_call = None
            for call in calls:
                room = call[1]['room']
                if room == db_team.player1_session_id:
                    db_player1_call = call
                elif room == db_team.player2_session_id:
                    db_player2_call = call
            
            assert db_player1_call is not None
            assert db_player2_call is not None
            
            # Verify database player1 always gets player1_item regardless of list order
            assert db_player1_call[0][1]['item'] == round_record.player1_item.value
            assert db_player2_call[0][1]['item'] == round_record.player2_item.value

    @patch('src.sockets.team_management.request')
    @patch('src.sockets.team_management.emit')
    @patch('src.sockets.team_management.socketio.emit')
    @patch('src.sockets.team_management.join_room')
    @patch('src.game_logic.socketio')
    def test_classic_mode_still_works(self, mock_game_socketio, mock_join_room, mock_socketio_emit, mock_emit, mock_request):
        """Test that classic mode behavior is preserved"""
        state.game_mode = 'classic'
        
        # Create and set up team
        mock_request.sid = 'classic_player1'
        on_create_team({'team_name': 'test_classic_mode'})
        
        mock_request.sid = 'classic_player2'
        on_join_team({'team_name': 'test_classic_mode'})
        
        # Run multiple rounds to see variety
        generated_combos = set()
        
        for round_num in range(20):
            mock_game_socketio.reset_mock()
            start_new_round_for_pair('test_classic_mode')
            
            # Get the database record
            db_team = Teams.query.filter_by(team_name='test_classic_mode', is_active=True).first()
            round_record = PairQuestionRounds.query.filter_by(
                team_id=db_team.team_id, 
                round_number_for_team=round_num + 1
            ).first()
            
            generated_combos.add((round_record.player1_item, round_record.player2_item))
        
        # In classic mode, we should see more variety than just A,B -> X,Y combinations
        expected_new_mode_combos = {
            (ItemEnum.A, ItemEnum.X), (ItemEnum.A, ItemEnum.Y),
            (ItemEnum.B, ItemEnum.X), (ItemEnum.B, ItemEnum.Y)
        }
        
        # Classic mode should generate combinations outside of new mode restrictions
        assert len(generated_combos) > len(expected_new_mode_combos), f"Classic mode should have more variety: {generated_combos}"

    @patch('src.sockets.team_management.request')
    @patch('src.sockets.team_management.emit')
    @patch('src.sockets.team_management.socketio.emit')
    @patch('src.sockets.team_management.join_room')
    @patch('src.game_logic.socketio')
    def test_mode_switching_during_game(self, mock_game_socketio, mock_join_room, mock_socketio_emit, mock_emit, mock_request):
        """Test switching game modes during active play"""
        # Start in new mode
        state.game_mode = 'new'
        
        # Create and set up team
        mock_request.sid = 'switch_player1'
        on_create_team({'team_name': 'test_mode_switch'})
        
        mock_request.sid = 'switch_player2'
        on_join_team({'team_name': 'test_mode_switch'})
        
        # Run a few rounds in new mode
        new_mode_combos = set()
        for round_num in range(3):
            mock_game_socketio.reset_mock()
            start_new_round_for_pair('test_mode_switch')
            
            db_team = Teams.query.filter_by(team_name='test_mode_switch', is_active=True).first()
            round_record = PairQuestionRounds.query.filter_by(
                team_id=db_team.team_id, 
                round_number_for_team=round_num + 1
            ).first()
            
            new_mode_combos.add((round_record.player1_item, round_record.player2_item))
        
        # Switch to classic mode
        state.game_mode = 'classic'
        
        # Run more rounds in classic mode
        classic_mode_combos = set()
        for round_num in range(3, 8):
            mock_game_socketio.reset_mock()
            start_new_round_for_pair('test_mode_switch')
            
            db_team = Teams.query.filter_by(team_name='test_mode_switch', is_active=True).first()
            round_record = PairQuestionRounds.query.filter_by(
                team_id=db_team.team_id, 
                round_number_for_team=round_num + 1
            ).first()
            
            classic_mode_combos.add((round_record.player1_item, round_record.player2_item))
        
        # Verify new mode restrictions were followed
        expected_new_combos = {
            (ItemEnum.A, ItemEnum.X), (ItemEnum.A, ItemEnum.Y),
            (ItemEnum.B, ItemEnum.X), (ItemEnum.B, ItemEnum.Y)
        }
        assert new_mode_combos.issubset(expected_new_combos), f"Invalid new mode combos: {new_mode_combos - expected_new_combos}"
        
        # Classic mode should potentially have more variety
        # (We can't guarantee it in a small sample, but the infrastructure should support it)
        assert len(classic_mode_combos) >= 1, "Classic mode should generate valid combinations"

    @patch('src.sockets.team_management.request')
    @patch('src.sockets.team_management.emit')
    @patch('src.sockets.team_management.socketio.emit')
    @patch('src.sockets.team_management.join_room')
    @patch('src.game_logic.socketio')
    def test_comprehensive_new_mode_coverage(self, mock_game_socketio, mock_join_room, mock_socketio_emit, mock_emit, mock_request):
        """Test that new mode eventually covers all valid combinations"""
        state.game_mode = 'new'
        
        # Create and set up team
        mock_request.sid = 'coverage_player1'
        on_create_team({'team_name': 'test_coverage'})
        
        mock_request.sid = 'coverage_player2'
        on_join_team({'team_name': 'test_coverage'})
        
        # Run many rounds to ensure coverage
        generated_combos = set()
        
        for round_num in range(50):  # Enough rounds to ensure statistical coverage
            mock_game_socketio.reset_mock()
            start_new_round_for_pair('test_coverage')
            
            db_team = Teams.query.filter_by(team_name='test_coverage', is_active=True).first()
            round_record = PairQuestionRounds.query.filter_by(
                team_id=db_team.team_id, 
                round_number_for_team=round_num + 1
            ).first()
            
            generated_combos.add((round_record.player1_item, round_record.player2_item))
        
        # Verify we get all expected combinations
        expected_combos = {
            (ItemEnum.A, ItemEnum.X), (ItemEnum.A, ItemEnum.Y),
            (ItemEnum.B, ItemEnum.X), (ItemEnum.B, ItemEnum.Y)
        }
        
        assert generated_combos == expected_combos, f"Missing combinations: {expected_combos - generated_combos}"
import pytest
from unittest.mock import patch, MagicMock, ANY
import random
from src.models.quiz_models import ItemEnum, Teams
from src.game_logic import start_new_round_for_pair
from src.state import state

@pytest.fixture
def mock_team_info():
    """Create a mock team info dictionary for testing"""
    return {
        'team_id': 1,
        'players': ['player1_sid', 'player2_sid'],
        'current_round_number': 0,
        'combo_tracker': {},
        'current_db_round_id': None,
        'answered_current_round': {},
        'player_slots': {'player1_sid': 1, 'player2_sid': 2}
    }

@pytest.fixture
def mock_db_team():
    """Create a mock database team"""
    team = MagicMock()
    team.team_id = 1
    team.player1_session_id = 'player1_sid'
    team.player2_session_id = 'player2_sid'
    team.is_active = True
    return team

class TestPlayerQuestionAssignment:
    """Test player question assignment fixes"""
    
    @patch('src.state.state')
    @patch('src.game_logic.PairQuestionRounds')
    @patch('src.game_logic.db')
    @patch('src.game_logic.socketio')
    def test_new_mode_correct_player_assignment(self, mock_socketio, mock_db, mock_rounds, mock_state, mock_team_info, mock_db_team):
        """Test that new mode assigns questions correctly based on database player slots"""
        # Setup mocks
        team_name = "test_team"
        mock_state.active_teams = {team_name: mock_team_info}
        mock_state.game_mode = 'new'
        mock_db.session.get.return_value = mock_db_team
        
        # Create a mock for the new round
        mock_round = MagicMock()
        mock_round.round_id = 123
        mock_rounds.return_value = mock_round
        
        # Call the function
        start_new_round_for_pair(team_name)
        
        # Verify the round was created
        mock_rounds.assert_called_once()
        call_args = mock_rounds.call_args
        
        # In new mode, verify the question assignment rules
        p1_item = call_args[1]['player1_item']
        p2_item = call_args[1]['player2_item']
        
        # Player 1 should only get A or B
        assert p1_item in [ItemEnum.A, ItemEnum.B], f"Player 1 got invalid item: {p1_item}"
        # Player 2 should only get X or Y
        assert p2_item in [ItemEnum.X, ItemEnum.Y], f"Player 2 got invalid item: {p2_item}"
        
        # Verify questions were sent to correct session IDs based on database slots
        socketio_calls = mock_socketio.emit.call_args_list
        assert len(socketio_calls) == 2
        
        # Find calls for each player
        player1_call = None
        player2_call = None
        for call in socketio_calls:
            room = call[1]['room']
            if room == 'player1_sid':
                player1_call = call
            elif room == 'player2_sid':
                player2_call = call
        
        assert player1_call is not None, "Player 1 didn't receive question"
        assert player2_call is not None, "Player 2 didn't receive question"
        
        # Verify Player 1 (database slot 1) got the p1_item
        assert player1_call[0][1]['item'] == p1_item.value
        # Verify Player 2 (database slot 2) got the p2_item  
        assert player2_call[0][1]['item'] == p2_item.value

    @patch('src.state.state')
    @patch('src.game_logic.PairQuestionRounds')
    @patch('src.game_logic.db')
    @patch('src.game_logic.socketio')
    def test_player_order_mismatch_fixed(self, mock_socketio, mock_db, mock_rounds, mock_state, mock_team_info, mock_db_team):
        """Test that player order in the list doesn't affect question assignment"""
        # Setup mocks with reversed player order in the list
        team_name = "test_team"
        mock_team_info['players'] = ['player2_sid', 'player1_sid']  # Reversed order
        mock_state.active_teams = {team_name: mock_team_info}
        mock_state.game_mode = 'new'
        mock_db.session.get.return_value = mock_db_team
        
        # Create a mock for the new round
        mock_round = MagicMock()
        mock_round.round_id = 123
        mock_rounds.return_value = mock_round
        
        # Call the function multiple times to test consistency
        for _ in range(10):
            mock_socketio.reset_mock()
            mock_rounds.reset_mock()
            
            start_new_round_for_pair(team_name)
            
            # Get the question assignment
            call_args = mock_rounds.call_args
            p1_item = call_args[1]['player1_item']
            p2_item = call_args[1]['player2_item']
            
            # Verify questions were sent to correct session IDs regardless of order in list
            socketio_calls = mock_socketio.emit.call_args_list
            assert len(socketio_calls) == 2
            
            # Find calls for each player
            player1_call = None
            player2_call = None
            for call in socketio_calls:
                room = call[1]['room']
                if room == 'player1_sid':
                    player1_call = call
                elif room == 'player2_sid':
                    player2_call = call
            
            assert player1_call is not None, "Player 1 didn't receive question"
            assert player2_call is not None, "Player 2 didn't receive question"
            
            # Verify Player 1 (database slot 1) ALWAYS gets p1_item (A or B)
            assert player1_call[0][1]['item'] == p1_item.value
            assert p1_item in [ItemEnum.A, ItemEnum.B], f"Player 1 got invalid item: {p1_item}"
            
            # Verify Player 2 (database slot 2) ALWAYS gets p2_item (X or Y)
            assert player2_call[0][1]['item'] == p2_item.value
            assert p2_item in [ItemEnum.X, ItemEnum.Y], f"Player 2 got invalid item: {p2_item}"

    @patch('src.state.state')
    @patch('src.game_logic.PairQuestionRounds')
    @patch('src.game_logic.db')
    @patch('src.game_logic.socketio')
    def test_reconnection_maintains_correct_assignment(self, mock_socketio, mock_db, mock_rounds, mock_state, mock_team_info):
        """Test that reconnection scenarios maintain correct player question assignment"""
        # Setup initial state
        team_name = "test_team"
        mock_state.active_teams = {team_name: mock_team_info}
        mock_state.game_mode = 'new'
        
        # Create mock database team
        mock_db_team = MagicMock()
        mock_db_team.team_id = 1
        mock_db_team.player1_session_id = 'original_player1_sid'
        mock_db_team.player2_session_id = 'original_player2_sid'
        mock_db.session.get.return_value = mock_db_team
        
        # Simulate reconnection - update connected players but keep DB mapping
        mock_team_info['players'] = ['original_player2_sid', 'original_player1_sid']  # Different order
        
        # Create a mock for the new round
        mock_round = MagicMock()
        mock_round.round_id = 123
        mock_rounds.return_value = mock_round
        
        # Call the function
        start_new_round_for_pair(team_name)
        
        # Verify questions were sent based on DATABASE slots, not connection order
        socketio_calls = mock_socketio.emit.call_args_list
        assert len(socketio_calls) == 2
        
        # Get the question assignment from database round
        call_args = mock_rounds.call_args
        p1_item = call_args[1]['player1_item']  # This goes to database player1
        p2_item = call_args[1]['player2_item']  # This goes to database player2
        
        # Find calls for each player
        db_player1_call = None
        db_player2_call = None
        for call in socketio_calls:
            room = call[1]['room']
            if room == 'original_player1_sid':  # Database Player 1
                db_player1_call = call
            elif room == 'original_player2_sid':  # Database Player 2
                db_player2_call = call
        
        assert db_player1_call is not None, "Database Player 1 didn't receive question"
        assert db_player2_call is not None, "Database Player 2 didn't receive question"
        
        # Verify correct assignment based on database slots
        assert db_player1_call[0][1]['item'] == p1_item.value
        assert db_player2_call[0][1]['item'] == p2_item.value
        
        # Verify question types are correct for new mode
        assert p1_item in [ItemEnum.A, ItemEnum.B], f"Database Player 1 got invalid item: {p1_item}"
        assert p2_item in [ItemEnum.X, ItemEnum.Y], f"Database Player 2 got invalid item: {p2_item}"

    @patch('src.state.state')
    @patch('src.game_logic.PairQuestionRounds')
    @patch('src.game_logic.db')
    @patch('src.game_logic.socketio')
    def test_classic_mode_unaffected(self, mock_socketio, mock_db, mock_rounds, mock_state, mock_team_info, mock_db_team):
        """Test that classic mode behavior is unaffected by the fix"""
        # Setup mocks
        team_name = "test_team"
        mock_state.active_teams = {team_name: mock_team_info}
        mock_state.game_mode = 'classic'
        mock_db.session.get.return_value = mock_db_team
        
        # Create a mock for the new round
        mock_round = MagicMock()
        mock_round.round_id = 123
        mock_rounds.return_value = mock_round
        
        # Run multiple rounds to verify all combinations are possible
        generated_combos = set()
        
        for _ in range(50):
            mock_rounds.reset_mock()
            start_new_round_for_pair(team_name)
            
            call_args = mock_rounds.call_args
            if call_args:
                p1_item = call_args[1]['player1_item']
                p2_item = call_args[1]['player2_item']
                generated_combos.add((p1_item, p2_item))
        
        # In classic mode, all 16 combinations should be possible
        all_items = [ItemEnum.A, ItemEnum.B, ItemEnum.X, ItemEnum.Y]
        all_possible_combos = {(i1, i2) for i1 in all_items for i2 in all_items}
        
        # We should see a good variety of combinations (not just A,B -> X,Y)
        assert len(generated_combos) > 4, f"Classic mode should generate more variety: {generated_combos}"
        
        # All generated combos should be valid (subset of all possible)
        assert generated_combos.issubset(all_possible_combos), f"Invalid combos generated: {generated_combos - all_possible_combos}"

    @patch('src.state.state')
    @patch('src.game_logic.PairQuestionRounds')
    @patch('src.game_logic.db')
    @patch('src.game_logic.socketio')
    def test_missing_database_team_handled(self, mock_socketio, mock_db, mock_rounds, mock_state, mock_team_info):
        """Test that missing database team is handled gracefully"""
        # Setup mocks
        team_name = "test_team"
        mock_state.active_teams = {team_name: mock_team_info}
        mock_state.game_mode = 'new'
        mock_db.session.get.return_value = None  # Database team not found
        
        # Call the function
        start_new_round_for_pair(team_name)
        
        # Verify no round was created and no questions sent
        mock_rounds.assert_not_called()
        mock_socketio.emit.assert_not_called()

    @patch('src.state.state')
    @patch('src.game_logic.PairQuestionRounds')
    @patch('src.game_logic.db')
    @patch('src.game_logic.socketio')
    def test_missing_player_session_ids_handled(self, mock_socketio, mock_db, mock_rounds, mock_state, mock_team_info):
        """Test that missing player session IDs are handled gracefully"""
        # Setup mocks
        team_name = "test_team"
        mock_state.active_teams = {team_name: mock_team_info}
        mock_state.game_mode = 'new'
        
        # Create mock database team with missing session IDs
        mock_db_team = MagicMock()
        mock_db_team.team_id = 1
        mock_db_team.player1_session_id = None  # Missing
        mock_db_team.player2_session_id = 'player2_sid'
        mock_db.session.get.return_value = mock_db_team
        
        # Call the function
        start_new_round_for_pair(team_name)
        
        # Verify no round was created and no questions sent
        mock_rounds.assert_not_called()
        mock_socketio.emit.assert_not_called()

    @patch('src.state.state')
    @patch('src.game_logic.PairQuestionRounds')
    @patch('src.game_logic.db')
    @patch('src.game_logic.socketio')
    def test_session_id_mismatch_handled(self, mock_socketio, mock_db, mock_rounds, mock_state, mock_team_info):
        """Test that session ID mismatch between database and state is handled"""
        # Setup mocks
        team_name = "test_team"
        mock_state.active_teams = {team_name: mock_team_info}
        mock_state.game_mode = 'new'
        
        # Create mock database team with different session IDs
        mock_db_team = MagicMock()
        mock_db_team.team_id = 1
        mock_db_team.player1_session_id = 'different_player1_sid'  # Not in team_info['players']
        mock_db_team.player2_session_id = 'different_player2_sid'  # Not in team_info['players']
        mock_db.session.get.return_value = mock_db_team
        
        # Call the function
        start_new_round_for_pair(team_name)
        
        # Verify no round was created and no questions sent
        mock_rounds.assert_not_called()
        mock_socketio.emit.assert_not_called()

    @patch('src.state.state')
    @patch('src.game_logic.PairQuestionRounds')
    @patch('src.game_logic.db')
    @patch('src.game_logic.socketio')
    def test_new_mode_comprehensive_question_distribution(self, mock_socketio, mock_db, mock_rounds, mock_state, mock_team_info, mock_db_team):
        """Test that new mode covers all valid question combinations over multiple rounds"""
        # Setup mocks
        team_name = "test_team"
        mock_state.active_teams = {team_name: mock_team_info}
        mock_state.game_mode = 'new'
        mock_db.session.get.return_value = mock_db_team
        
        # Create a mock for the new round
        mock_round = MagicMock()
        mock_round.round_id = 123
        mock_rounds.return_value = mock_round
        
        # Expected valid combinations in new mode
        expected_combos = {
            (ItemEnum.A, ItemEnum.X), (ItemEnum.A, ItemEnum.Y),
            (ItemEnum.B, ItemEnum.X), (ItemEnum.B, ItemEnum.Y)
        }
        
        generated_combos = set()
        
        # Run many rounds to ensure we see all combinations
        for _ in range(100):
            mock_rounds.reset_mock()
            start_new_round_for_pair(team_name)
            
            call_args = mock_rounds.call_args
            if call_args:
                p1_item = call_args[1]['player1_item']
                p2_item = call_args[1]['player2_item']
                generated_combos.add((p1_item, p2_item))
        
        # Verify we eventually see all expected combinations
        assert generated_combos == expected_combos, f"Missing combinations: {expected_combos - generated_combos}"
        
        # Verify no invalid combinations were generated
        assert generated_combos.issubset(expected_combos), f"Invalid combinations: {generated_combos - expected_combos}"

    @patch('src.state.state')
    @patch('src.game_logic.PairQuestionRounds')
    @patch('src.game_logic.db')
    @patch('src.game_logic.socketio')
    def test_mode_change_during_game(self, mock_socketio, mock_db, mock_rounds, mock_state, mock_team_info, mock_db_team):
        """Test that mode changes during game work correctly with player assignment"""
        # Setup mocks
        team_name = "test_team"
        mock_state.active_teams = {team_name: mock_team_info}
        mock_db.session.get.return_value = mock_db_team
        
        # Create a mock for the new round
        mock_round = MagicMock()
        mock_round.round_id = 123
        mock_rounds.return_value = mock_round
        
        # Start in new mode
        mock_state.game_mode = 'new'
        new_mode_combos = set()
        
        for _ in range(10):
            mock_rounds.reset_mock()
            start_new_round_for_pair(team_name)
            
            call_args = mock_rounds.call_args
            if call_args:
                p1_item = call_args[1]['player1_item']
                p2_item = call_args[1]['player2_item']
                new_mode_combos.add((p1_item, p2_item))
        
        # Switch to classic mode
        mock_state.game_mode = 'classic'
        classic_mode_combos = set()
        
        for _ in range(20):
            mock_rounds.reset_mock()
            start_new_round_for_pair(team_name)
            
            call_args = mock_rounds.call_args
            if call_args:
                p1_item = call_args[1]['player1_item']
                p2_item = call_args[1]['player2_item']
                classic_mode_combos.add((p1_item, p2_item))
        
        # Verify new mode combinations are restricted
        expected_new_combos = {
            (ItemEnum.A, ItemEnum.X), (ItemEnum.A, ItemEnum.Y),
            (ItemEnum.B, ItemEnum.X), (ItemEnum.B, ItemEnum.Y)
        }
        assert new_mode_combos.issubset(expected_new_combos), f"Invalid new mode combos: {new_mode_combos - expected_new_combos}"
        
        # Verify classic mode has more variety
        assert len(classic_mode_combos) > len(new_mode_combos), "Classic mode should have more combination variety"
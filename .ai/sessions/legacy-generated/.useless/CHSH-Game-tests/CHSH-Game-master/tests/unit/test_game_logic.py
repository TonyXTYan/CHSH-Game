import pytest
from unittest.mock import patch, MagicMock
import random
from src.models.quiz_models import ItemEnum
from src.game_logic import start_new_round_for_pair, QUESTION_ITEMS, TARGET_COMBO_REPEATS

@pytest.fixture
def mock_team_info():
    """Create a mock team info dictionary for testing"""
    return {
        'team_id': 1,
        'players': ['player1_sid', 'player2_sid'],
        'current_round_number': 0,
        'combo_tracker': {},
        'current_db_round_id': None,
        'answered_current_round': {}
    }

@patch('src.game_logic.state')
@patch('src.game_logic.PairQuestionRounds')
@patch('src.game_logic.db')
@patch('src.game_logic.socketio')
def test_start_new_round_for_pair_basic(mock_socketio, mock_db, mock_rounds, mock_state, mock_team_info):
    """Test basic round generation for a team"""
    # Setup mocks
    team_name = "test_team"
    mock_state.active_teams = {team_name: mock_team_info}
    
    # Create a mock for the new round
    mock_round = MagicMock()
    mock_round.round_id = 123
    mock_rounds.return_value = mock_round
    
    # Call the function
    start_new_round_for_pair(team_name)
    
    # Verify round number was incremented
    assert mock_state.active_teams[team_name]['current_round_number'] == 1
    
    # Verify a new round was created in the database
    mock_rounds.assert_called_once()
    mock_db.session.add.assert_called_once_with(mock_round)
    mock_db.session.commit.assert_called_once()
    
    # Verify the round ID was stored
    assert mock_state.active_teams[team_name]['current_db_round_id'] == 123
    
    # Verify questions were sent to both players
    assert mock_socketio.emit.call_count == 2
    
    # Verify combo tracker was updated
    assert len(mock_state.active_teams[team_name]['combo_tracker']) == 1

@patch('src.game_logic.state')
@patch('src.game_logic.PairQuestionRounds')
@patch('src.game_logic.db')
@patch('src.game_logic.socketio')
def test_start_new_round_for_pair_invalid_team(mock_socketio, mock_db, mock_rounds, mock_state):
    """Test round generation with invalid team"""
    # Setup mocks
    team_name = "nonexistent_team"
    mock_state.active_teams = {}
    
    # Call the function
    start_new_round_for_pair(team_name)
    
    # Verify no round was created
    mock_rounds.assert_not_called()
    mock_db.session.add.assert_not_called()
    mock_db.session.commit.assert_not_called()
    
    # Verify no questions were sent
    mock_socketio.emit.assert_not_called()

@patch('src.game_logic.state')
@patch('src.game_logic.PairQuestionRounds')
@patch('src.game_logic.db')
@patch('src.game_logic.socketio')
def test_start_new_round_for_pair_incomplete_team(mock_socketio, mock_db, mock_rounds, mock_state, mock_team_info):
    """Test round generation with incomplete team (less than 2 players)"""
    # Setup mocks
    team_name = "incomplete_team"
    incomplete_team_info = mock_team_info.copy()
    incomplete_team_info['players'] = ['player1_sid']  # Only one player
    mock_state.active_teams = {team_name: incomplete_team_info}
    
    # Call the function
    start_new_round_for_pair(team_name)
    
    # Verify no round was created
    mock_rounds.assert_not_called()
    mock_db.session.add.assert_not_called()
    mock_db.session.commit.assert_not_called()
    
    # Verify no questions were sent
    mock_socketio.emit.assert_not_called()

@patch('src.game_logic.state')
@patch('src.game_logic.PairQuestionRounds')
@patch('src.game_logic.db')
@patch('src.game_logic.socketio')
@patch('random.shuffle')
def test_combo_distribution(mock_shuffle, mock_socketio, mock_db, mock_rounds, mock_state, mock_team_info):
    """Test that combo distribution works correctly over multiple rounds"""
    # Setup mocks
    team_name = "test_team"
    mock_state.active_teams = {team_name: mock_team_info}
    
    # Create a mock for the new round
    mock_round = MagicMock()
    mock_round.round_id = 123
    mock_rounds.return_value = mock_round
    
    # Make random.shuffle predictable
    mock_shuffle.side_effect = lambda x: x
    
    # Run multiple rounds
    num_rounds = 20
    for _ in range(num_rounds):
        start_new_round_for_pair(team_name)
    
    # Verify combo tracker has entries
    combo_tracker = mock_state.active_teams[team_name]['combo_tracker']
    assert len(combo_tracker) > 0
    
    # Verify round number was incremented correctly
    assert mock_state.active_teams[team_name]['current_round_number'] == num_rounds
    
    # Verify database calls
    assert mock_db.session.add.call_count == num_rounds
    assert mock_db.session.commit.call_count == num_rounds

@patch('src.game_logic.state')
@patch('src.game_logic.PairQuestionRounds')
@patch('src.game_logic.db')
@patch('src.game_logic.socketio')
def test_deterministic_phase(mock_socketio, mock_db, mock_rounds, mock_state, mock_team_info):
    """Test that deterministic phase is entered when approaching round limit"""
    # Setup mocks
    team_name = "test_team"
    team_info = mock_team_info.copy()
    
    # Set round number close to limit
    all_possible_combos = [(i1, i2) for i1 in QUESTION_ITEMS for i2 in QUESTION_ITEMS]
    round_limit = (TARGET_COMBO_REPEATS + 1) * len(all_possible_combos)
    team_info['current_round_number'] = round_limit - len(all_possible_combos)
    
    # Setup combo tracker with some combos already at target
    combo_tracker = {}
    for i, combo in enumerate(all_possible_combos):
        if i % 2 == 0:  # Half the combos are at target
            combo_tracker[(combo[0].value, combo[1].value)] = TARGET_COMBO_REPEATS
        else:
            combo_tracker[(combo[0].value, combo[1].value)] = TARGET_COMBO_REPEATS - 1
    
    team_info['combo_tracker'] = combo_tracker
    mock_state.active_teams = {team_name: team_info}
    
    # Create a mock for the new round
    mock_round = MagicMock()
    mock_round.round_id = 123
    mock_rounds.return_value = mock_round
    
    # Call the function
    start_new_round_for_pair(team_name)
    
    # Verify a new round was created
    mock_rounds.assert_called_once()
    
    # Verify combo tracker was updated
    assert len(team_info['combo_tracker']) == len(all_possible_combos)
    
    # Verify round number was incremented
    assert team_info['current_round_number'] == round_limit - len(all_possible_combos) + 1

@patch('src.game_logic.state')
@patch('src.game_logic.PairQuestionRounds')
@patch('src.game_logic.db')
@patch('src.game_logic.socketio')
def test_exception_handling(mock_socketio, mock_db, mock_rounds, mock_state, mock_team_info):
    """Test exception handling in start_new_round_for_pair"""
    # Setup mocks
    team_name = "test_team"
    mock_state.active_teams = {team_name: mock_team_info}
    
    # Make db.session.commit raise an exception
    mock_db.session.commit.side_effect = Exception("Test exception")
    
    # Call the function
    start_new_round_for_pair(team_name)
    
    # Function should not raise an exception
    # But the exception should be logged (we can't easily test this)
    
    # Verify a round was attempted to be created
    mock_rounds.assert_called_once()
    mock_db.session.add.assert_called_once()

import pytest
from unittest.mock import patch, MagicMock
from src.models.quiz_models import ItemEnum
from src.game_logic import start_new_round_for_pair


@patch('src.state.state')
@patch('src.game_logic.PairQuestionRounds')
@patch('src.game_logic.db')
@patch('src.game_logic.socketio')
def test_aqmjoe_mode_classic_style_assignment(mock_socketio, mock_db, mock_rounds, mock_state):
    """AQM Joe mode should allow any of A/B/X/Y to either player (classic-style)."""
    team_name = "test_team"
    team_info = {
        'team_id': 1,
        'players': ['player1_sid', 'player2_sid'],
        'current_round_number': 0,
        'combo_tracker': {},
        'current_db_round_id': None,
        'answered_current_round': {}
    }
    mock_state.active_teams = {team_name: team_info}
    mock_state.game_mode = 'aqmjoe'

    mock_db_team = MagicMock()
    mock_db_team.team_id = 1
    mock_db_team.player1_session_id = 'player1_sid'
    mock_db_team.player2_session_id = 'player2_sid'
    mock_db.session.get.return_value = mock_db_team

    mock_round = MagicMock()
    mock_round.round_id = 123
    mock_rounds.return_value = mock_round

    generated_combos = set()
    player1_items = set()
    player2_items = set()

    # Run many rounds to collect variety
    for _ in range(200):
        start_new_round_for_pair(team_name)
        call_args = mock_rounds.call_args
        if call_args:
            p1_item = call_args[1]['player1_item']
            p2_item = call_args[1]['player2_item']
            generated_combos.add((p1_item, p2_item))
            player1_items.add(p1_item)
            player2_items.add(p2_item)
        mock_rounds.reset_mock()

    all_items = {ItemEnum.A, ItemEnum.B, ItemEnum.X, ItemEnum.Y}
    # Both players should draw from full set over time (variety, not guaranteed full coverage)
    assert player1_items.issubset(all_items)
    assert player2_items.issubset(all_items)
    assert len(player1_items) >= 2
    assert len(player2_items) >= 2

    # There should be at least one non-simplified combo (e.g., same-category or reversed pairing)
    simplified_only = {
        (ItemEnum.A, ItemEnum.X), (ItemEnum.A, ItemEnum.Y),
        (ItemEnum.B, ItemEnum.X), (ItemEnum.B, ItemEnum.Y)
    }
    assert not generated_combos.issubset(simplified_only), "AQM Joe should generate combos beyond simplified set"
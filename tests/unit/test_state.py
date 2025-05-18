import pytest
from src.state import AppState

def test_app_state_initialization():
    """Test that AppState initializes with correct default values"""
    state = AppState()
    
    assert isinstance(state.active_teams, dict)
    assert len(state.active_teams) == 0
    
    assert isinstance(state.player_to_team, dict)
    assert len(state.player_to_team) == 0
    
    assert isinstance(state.dashboard_clients, set)
    assert len(state.dashboard_clients) == 0
    
    assert state.game_started is False
    assert state.answer_stream_enabled is False
    
    assert isinstance(state.previous_sessions, dict)
    assert len(state.previous_sessions) == 0
    
    assert isinstance(state.team_id_to_name, dict)
    assert len(state.team_id_to_name) == 0

def test_app_state_reset():
    """Test that AppState.reset() properly clears all state"""
    state = AppState()
    
    # Set some state
    state.active_teams = {"team1": {"players": ["player1", "player2"]}}
    state.player_to_team = {"player1": "team1", "player2": "team1"}
    state.dashboard_clients = {"dashboard1", "dashboard2"}
    state.game_started = True
    state.answer_stream_enabled = True
    state.previous_sessions = {"old_sid": "new_sid"}
    state.team_id_to_name = {1: "team1"}
    
    # Reset state
    state.reset()
    
    # Verify everything is cleared
    assert len(state.active_teams) == 0
    assert len(state.player_to_team) == 0
    assert len(state.dashboard_clients) == 0
    assert state.game_started is False
    assert state.answer_stream_enabled is False
    assert len(state.previous_sessions) == 0
    assert len(state.team_id_to_name) == 0

def test_app_state_team_tracking():
    """Test adding and removing teams from state"""
    state = AppState()
    
    # Add a team
    team_name = "test_team"
    team_id = 1
    player1 = "player1_sid"
    player2 = "player2_sid"
    
    state.active_teams[team_name] = {
        "players": [player1, player2],
        "team_id": team_id,
        "current_round_number": 0,
        "combo_tracker": {},
        "current_db_round_id": None,
        "answered_current_round": {}
    }
    
    state.player_to_team[player1] = team_name
    state.player_to_team[player2] = team_name
    state.team_id_to_name[team_id] = team_name
    
    # Verify team was added correctly
    assert team_name in state.active_teams
    assert state.active_teams[team_name]["players"] == [player1, player2]
    assert state.active_teams[team_name]["team_id"] == team_id
    
    assert state.player_to_team[player1] == team_name
    assert state.player_to_team[player2] == team_name
    
    assert state.team_id_to_name[team_id] == team_name
    
    # Remove a player
    del state.player_to_team[player2]
    state.active_teams[team_name]["players"] = [player1]
    
    # Verify player was removed
    assert player1 in state.player_to_team
    assert player2 not in state.player_to_team
    assert state.active_teams[team_name]["players"] == [player1]
    
    # Remove the team
    del state.active_teams[team_name]
    del state.player_to_team[player1]
    del state.team_id_to_name[team_id]
    
    # Verify team was removed
    assert team_name not in state.active_teams
    assert player1 not in state.player_to_team
    assert team_id not in state.team_id_to_name

def test_app_state_session_mapping():
    """Test previous session mapping functionality"""
    state = AppState()
    
    # Add session mappings
    old_sid1 = "old_sid1"
    new_sid1 = "new_sid1"
    old_sid2 = "old_sid2"
    new_sid2 = "new_sid2"
    
    state.previous_sessions[old_sid1] = new_sid1
    state.previous_sessions[old_sid2] = new_sid2
    
    # Verify mappings
    assert state.previous_sessions[old_sid1] == new_sid1
    assert state.previous_sessions[old_sid2] == new_sid2
    
    # Update a mapping
    newer_sid1 = "newer_sid1"
    state.previous_sessions[new_sid1] = newer_sid1
    
    # Verify chain of mappings
    assert state.previous_sessions[old_sid1] == new_sid1
    assert state.previous_sessions[new_sid1] == newer_sid1
    
    # Clear mappings
    state.previous_sessions.clear()
    
    # Verify cleared
    assert len(state.previous_sessions) == 0

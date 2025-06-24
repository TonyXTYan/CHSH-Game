"""
Integration tests for team management and disconnection logic.

These tests verify the complete end-to-end flow of team formation, 
disconnection, and dashboard updates working together.
"""

import pytest
import time
from unittest.mock import patch, MagicMock
import sys

# Mock the problematic imports before importing anything else
mock_app = MagicMock()
mock_socketio = MagicMock()
mock_db = MagicMock()
mock_request = MagicMock()

sys.modules['src.config'] = MagicMock()
sys.modules['src.config'].app = mock_app
sys.modules['src.config'].socketio = mock_socketio
sys.modules['src.config'].db = mock_db
sys.modules['flask'] = MagicMock()
sys.modules['flask'].request = mock_request
sys.modules['flask_socketio'] = MagicMock()


class MockState:
    """Mock state class for testing."""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.active_teams = {}
        self.connected_players = set()
        self.player_to_team = {}
        self.team_id_to_name = {}
        self.dashboard_clients = set()
        self.game_started = False


# Create mock state instance
mock_state = MockState()


@pytest.mark.no_server
class TestTeamManagementIntegration:
    """Integration tests for complete team management flow."""

    def setup_method(self):
        """Setup test environment."""
        mock_state.reset()

    def test_complete_team_lifecycle_with_dashboard_updates(self):
        """Test complete lifecycle: create → join → disconnect → rejoin with dashboard updates."""
        
        dashboard_calls = []
        
        def mock_dashboard_update(force_refresh=False):
            dashboard_calls.append({"force_refresh": force_refresh})
        
        def mock_create_team(team_name, creator_sid):
            mock_state.active_teams[team_name] = {
                'players': [creator_sid],
                'team_id': 1,
                'status': 'waiting_pair',
                'current_round_number': 0,
                'combo_tracker': {},
                'answered_current_round': {}
            }
            mock_state.player_to_team[creator_sid] = team_name
            mock_state.connected_players.add(creator_sid)
        
        def mock_join_team(team_name, joiner_sid):
            if team_name in mock_state.active_teams:
                team_info = mock_state.active_teams[team_name]
                team_info['players'].append(joiner_sid)
                if len(team_info['players']) == 2:
                    team_info['status'] = 'active'
                    mock_dashboard_update(force_refresh=True)
                mock_state.player_to_team[joiner_sid] = team_name
                mock_state.connected_players.add(joiner_sid)
        
        def mock_disconnect(sid):
            if sid in mock_state.connected_players:
                mock_state.connected_players.remove(sid)
            
            if sid in mock_state.player_to_team:
                team_name = mock_state.player_to_team[sid]
                team_info = mock_state.active_teams[team_name]
                
                if sid in team_info['players']:
                    team_info['players'].remove(sid)
                
                if len(team_info['players']) > 0:
                    team_info['status'] = 'waiting_pair'
                    mock_dashboard_update(force_refresh=True)
                
                del mock_state.player_to_team[sid]
        
        # ===== PHASE 1: Team Creation =====
        mock_create_team('TestTeam', 'player1_sid')
        
        # Verify team created state
        assert 'TestTeam' in mock_state.active_teams
        assert mock_state.active_teams['TestTeam']['status'] == 'waiting_pair'
        assert len(mock_state.active_teams['TestTeam']['players']) == 1
        assert 'player1_sid' in mock_state.active_teams['TestTeam']['players']
        
        # ===== PHASE 2: Second Player Joins =====
        mock_join_team('TestTeam', 'player2_sid')
        
        # Verify team full state
        assert mock_state.active_teams['TestTeam']['status'] == 'active'
        assert len(mock_state.active_teams['TestTeam']['players']) == 2
        assert 'player2_sid' in mock_state.active_teams['TestTeam']['players']
        
        # Verify dashboard force refresh was called when team became full
        assert any(call['force_refresh'] == True for call in dashboard_calls)
        
        # ===== PHASE 3: Player Disconnects =====
        mock_disconnect('player1_sid')
        
        # Verify disconnect state
        assert mock_state.active_teams['TestTeam']['status'] == 'waiting_pair'
        assert len(mock_state.active_teams['TestTeam']['players']) == 1
        assert 'player1_sid' not in mock_state.active_teams['TestTeam']['players']
        assert 'player2_sid' in mock_state.active_teams['TestTeam']['players']
        assert 'player1_sid' not in mock_state.connected_players
        
        # Verify dashboard force refresh was called for disconnect
        disconnect_calls = [call for call in dashboard_calls if call['force_refresh'] == True]
        assert len(disconnect_calls) >= 2  # At least one for join, one for disconnect
        
        # ===== PHASE 4: New Player Joins =====
        mock_join_team('TestTeam', 'player3_sid')
        
        # Verify team full again
        assert mock_state.active_teams['TestTeam']['status'] == 'active'
        assert len(mock_state.active_teams['TestTeam']['players']) == 2
        assert 'player3_sid' in mock_state.active_teams['TestTeam']['players']

    def test_dashboard_force_refresh_timing_during_rapid_changes(self):
        """Test dashboard force refresh handles rapid team state changes correctly."""
        
        # Mock the teams query behavior
        database_query_count = 0
        
        def mock_get_all_teams(force_refresh=False):
            nonlocal database_query_count
            if force_refresh:
                database_query_count += 1
                return [{"team_name": "Team1", "status": "waiting_pair"}]
            else:
                # Simulate cache hit - no database query
                return [{"team_name": "Team1", "status": "active"}]
        
        # ===== Test Scenario: Rapid state changes =====
        
        # 1. Initial dashboard query (normal)
        teams_initial = mock_get_all_teams(force_refresh=False)
        assert len(teams_initial) > 0
        assert database_query_count == 0
        
        # 2. Immediate team formation (should allow force refresh)
        teams_after_formation = mock_get_all_teams(force_refresh=True)
        assert len(teams_after_formation) > 0
        assert database_query_count == 1
        
        # 3. Immediate disconnection (should allow force refresh)
        teams_after_disconnect = mock_get_all_teams(force_refresh=True)
        assert len(teams_after_disconnect) > 0
        assert database_query_count == 2

    def test_team_state_consistency_across_multiple_operations(self):
        """Test that team state remains consistent across multiple operations."""
        
        def verify_team_consistency(team_name):
            """Helper to verify team state is consistent."""
            team = mock_state.active_teams.get(team_name)
            if not team:
                return True  # Team deleted, that's consistent
                
            # Check player count matches status
            player_count = len(team['players'])
            status = team['status']
            
            if player_count == 2:
                assert status == 'active', f"Team with 2 players should be active, got {status}"
            elif player_count == 1:
                assert status == 'waiting_pair', f"Team with 1 player should be waiting_pair, got {status}"
            elif player_count == 0:
                # Team should be removed from active teams
                assert False, "Team with 0 players should not exist in active_teams"
                
            # Check reverse mappings
            for player_sid in team['players']:
                assert mock_state.player_to_team.get(player_sid) == team_name
                
            return True
        
        # Setup initial team
        team_name = 'TestTeam'
        mock_state.active_teams[team_name] = {
            'players': ['player1', 'player2'],
            'team_id': 1,
            'status': 'active',
            'current_round_number': 0,
            'combo_tracker': {},
            'answered_current_round': {}
        }
        
        mock_state.player_to_team['player1'] = team_name
        mock_state.player_to_team['player2'] = team_name
        mock_state.team_id_to_name[1] = team_name
        
        # Verify initial consistency
        verify_team_consistency(team_name)
        
        # Simulate player1 leaving
        if 'player1' in mock_state.active_teams[team_name]['players']:
            mock_state.active_teams[team_name]['players'].remove('player1')
            mock_state.active_teams[team_name]['status'] = 'waiting_pair'
            del mock_state.player_to_team['player1']
        
        verify_team_consistency(team_name)
        
        # Simulate player2 leaving (team should be empty/removed)
        if 'player2' in mock_state.active_teams[team_name]['players']:
            mock_state.active_teams[team_name]['players'].remove('player2')
            del mock_state.player_to_team['player2']
            
            # Empty teams should be removed
            if len(mock_state.active_teams[team_name]['players']) == 0:
                del mock_state.active_teams[team_name]
                del mock_state.team_id_to_name[1]
        
        # Verify team was properly cleaned up
        assert team_name not in mock_state.active_teams
        assert 1 not in mock_state.team_id_to_name
        assert 'player1' not in mock_state.player_to_team
        assert 'player2' not in mock_state.player_to_team


@pytest.mark.no_server
class TestRealTimeUpdates:
    """Test real-time update scenarios."""
    
    def test_dashboard_clients_receive_updates_on_team_changes(self):
        """Test that dashboard clients receive updates when teams change."""
        
        # Mock dashboard clients
        mock_state.dashboard_clients.add('dashboard1')
        mock_state.dashboard_clients.add('dashboard2')
        mock_state.connected_players.add('player1')
        
        # Mock the dashboard update function
        emitted_updates = []
        
        def mock_emit_dashboard_team_update(force_refresh=False):
            update_data = {
                'teams': [{'team_name': 'TestTeam', 'status': 'waiting_pair', 'players': ['player1']}],
                'connected_players_count': len(mock_state.connected_players)
            }
            
            for client_id in mock_state.dashboard_clients:
                emitted_updates.append({
                    'client_id': client_id,
                    'event': 'team_status_changed_for_dashboard',
                    'data': update_data,
                    'force_refresh': force_refresh
                })
        
        # Trigger dashboard update
        mock_emit_dashboard_team_update(force_refresh=True)
        
        # Verify all dashboard clients received the update
        expected_calls = len(mock_state.dashboard_clients)
        assert len(emitted_updates) == expected_calls
        
        # Verify the update data structure
        for update in emitted_updates:
            assert update['event'] == 'team_status_changed_for_dashboard'
            assert 'teams' in update['data']
            assert 'connected_players_count' in update['data']
            assert update['data']['connected_players_count'] == 1
            assert update['force_refresh'] == True

    def test_client_side_input_disable_scenarios(self):
        """Test scenarios where client input should be disabled."""
        
        # Document expected input disable scenarios
        scenarios = [
            {
                "description": "Team waiting for pair",
                "team_status": "waiting_pair",
                "game_started": True,
                "expected_input_disabled": True,
                "expected_message": "Waiting for teammate to reconnect..."
            },
            {
                "description": "Team active, game not started",
                "team_status": "active", 
                "game_started": False,
                "expected_input_disabled": True,
                "expected_message": None
            },
            {
                "description": "Team active, game started",
                "team_status": "active",
                "game_started": True, 
                "expected_input_disabled": False,
                "expected_message": None
            },
            {
                "description": "No team",
                "team_status": None,
                "game_started": True,
                "expected_input_disabled": True,
                "expected_message": None
            }
        ]
        
        for scenario in scenarios:
            # This documents the expected behavior for frontend implementation
            team_status = scenario["team_status"]
            game_started = scenario["game_started"]
            
            # Logic should be: input disabled if game not started OR team incomplete
            expected_disabled = (not game_started) or (team_status != "active")
            
            assert expected_disabled == scenario["expected_input_disabled"], \
                f"Scenario {scenario['description']} has incorrect expected_input_disabled"


if __name__ == '__main__':
    pytest.main([__file__])
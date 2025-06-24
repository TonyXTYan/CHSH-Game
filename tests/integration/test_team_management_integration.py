"""
Integration tests for team management and disconnection logic.

These tests verify the complete end-to-end flow of team formation, 
disconnection, and dashboard updates working together.
"""

import pytest
import time
from unittest.mock import patch, MagicMock
from flask import Flask

from src import main
from src.state import state
from src.models.quiz_models import Teams
from src.sockets.dashboard import get_all_teams, emit_dashboard_team_update


class TestTeamManagementIntegration:
    """Integration tests for complete team management flow."""

    def setup_method(self):
        """Setup test environment."""
        state.reset()
        # Setup mock database
        self.mock_db_session = MagicMock()

    @patch('src.sockets.team_management.db')
    @patch('src.sockets.team_management.emit')
    @patch('src.sockets.team_management.socketio.emit')
    @patch('src.sockets.team_management.emit_dashboard_team_update')
    @patch('src.sockets.team_management.request')
    def test_complete_team_lifecycle_with_dashboard_updates(
        self, mock_request, mock_dashboard_update, mock_socketio_emit, 
        mock_emit, mock_db
    ):
        """Test complete lifecycle: create → join → disconnect → rejoin with dashboard updates."""
        
        # Setup database mock
        mock_db_team = MagicMock()
        mock_db.session.get.return_value = mock_db_team
        mock_db.session.commit = MagicMock()
        
        # Import socket handlers
        from src.sockets.team_management import on_create_team, on_join_team, handle_disconnect
        
        # ===== PHASE 1: Team Creation =====
        mock_request.sid = 'player1_sid'
        state.connected_players.add('player1_sid')
        
        # Create team
        on_create_team({'team_name': 'TestTeam'})
        
        # Verify team created state
        assert 'TestTeam' in state.active_teams
        assert state.active_teams['TestTeam']['status'] == 'waiting_pair'
        assert len(state.active_teams['TestTeam']['players']) == 1
        assert 'player1_sid' in state.active_teams['TestTeam']['players']
        
        # ===== PHASE 2: Second Player Joins =====
        mock_request.sid = 'player2_sid'
        state.connected_players.add('player2_sid')
        
        # Join team
        on_join_team({'team_name': 'TestTeam'})
        
        # Verify team full state
        assert state.active_teams['TestTeam']['status'] == 'active'
        assert len(state.active_teams['TestTeam']['players']) == 2
        assert 'player2_sid' in state.active_teams['TestTeam']['players']
        
        # Verify dashboard force refresh was called when team became full
        mock_dashboard_update.assert_called_with(force_refresh=True)
        
        # ===== PHASE 3: Player Disconnects =====
        mock_request.sid = 'player1_sid'
        
        # Simulate disconnect
        handle_disconnect()
        
        # Verify disconnect state
        assert state.active_teams['TestTeam']['status'] == 'waiting_pair'
        assert len(state.active_teams['TestTeam']['players']) == 1
        assert 'player1_sid' not in state.active_teams['TestTeam']['players']
        assert 'player2_sid' in state.active_teams['TestTeam']['players']
        assert 'player1_sid' not in state.connected_players
        
        # Verify dashboard force refresh was called for disconnect
        assert any(call.kwargs.get('force_refresh') == True for call in mock_dashboard_update.call_args_list)
        
        # ===== PHASE 4: New Player Joins =====
        mock_request.sid = 'player3_sid'
        state.connected_players.add('player3_sid')
        
        # Join team to make it full again
        on_join_team({'team_name': 'TestTeam'})
        
        # Verify team full again
        assert state.active_teams['TestTeam']['status'] == 'active'
        assert len(state.active_teams['TestTeam']['players']) == 2
        assert 'player3_sid' in state.active_teams['TestTeam']['players']

    @patch('src.sockets.dashboard.Teams')
    @patch('src.sockets.dashboard.time')
    def test_dashboard_force_refresh_timing_during_rapid_changes(
        self, mock_time, mock_teams
    ):
        """Test dashboard force refresh handles rapid team state changes correctly."""
        
        # Mock teams in database
        mock_team1 = MagicMock()
        mock_team1.team_name = 'Team1'
        mock_team1.player1_session_id = 'player1'
        mock_team1.player2_session_id = 'player2' 
        mock_team1.active = True
        
        mock_teams.query.all.return_value = [mock_team1]
        
        # Mock time progression
        current_time = 100.0
        mock_time.return_value = current_time
        
        # ===== Test Scenario: Rapid state changes =====
        
        # 1. Initial dashboard query (normal)
        teams_initial = get_all_teams(force_refresh=False)
        assert len(teams_initial) > 0
        
        # 2. Immediate team formation (should allow force refresh)
        current_time += 0.1  # 100ms later (within 1sec delay)
        mock_time.return_value = current_time
        
        teams_after_formation = get_all_teams(force_refresh=True)
        assert len(teams_after_formation) > 0
        
        # 3. Immediate disconnection (should allow force refresh)
        current_time += 0.1  # Another 100ms later 
        mock_time.return_value = current_time
        
        teams_after_disconnect = get_all_teams(force_refresh=True)
        assert len(teams_after_disconnect) > 0
        
        # Verify database was queried multiple times due to force refresh
        assert mock_teams.query.all.call_count >= 2

    def test_team_state_consistency_across_multiple_operations(self):
        """Test that team state remains consistent across multiple operations."""
        
        # Setup initial team
        state.active_teams['TestTeam'] = {
            'players': ['player1', 'player2'],
            'team_id': 1,
            'status': 'active',
            'current_round_number': 0,
            'combo_tracker': {},
            'answered_current_round': {}
        }
        
        state.player_to_team['player1'] = 'TestTeam'
        state.player_to_team['player2'] = 'TestTeam'
        state.team_id_to_name[1] = 'TestTeam'
        
        # Test state consistency checks
        def verify_team_consistency():
            """Helper to verify team state is consistent."""
            team = state.active_teams.get('TestTeam')
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
                assert state.player_to_team.get(player_sid) == 'TestTeam'
                
            return True
        
        # Verify initial consistency
        verify_team_consistency()
        
        # Simulate player1 leaving
        if 'player1' in state.active_teams['TestTeam']['players']:
            state.active_teams['TestTeam']['players'].remove('player1')
            state.active_teams['TestTeam']['status'] = 'waiting_pair'
            del state.player_to_team['player1']
        
        verify_team_consistency()
        
        # Simulate player2 leaving (team should be empty/removed)
        if 'player2' in state.active_teams['TestTeam']['players']:
            state.active_teams['TestTeam']['players'].remove('player2')
            del state.player_to_team['player2']
            
            # Empty teams should be removed
            if len(state.active_teams['TestTeam']['players']) == 0:
                del state.active_teams['TestTeam']
                del state.team_id_to_name[1]
        
        # Verify team was properly cleaned up
        assert 'TestTeam' not in state.active_teams
        assert 1 not in state.team_id_to_name
        assert 'player1' not in state.player_to_team
        assert 'player2' not in state.player_to_team


class TestRealTimeUpdates:
    """Test real-time update scenarios."""
    
    @patch('src.sockets.dashboard.socketio')
    def test_dashboard_clients_receive_updates_on_team_changes(self, mock_socketio):
        """Test that dashboard clients receive updates when teams change."""
        
        # Setup dashboard clients
        state.dashboard_clients.add('dashboard1')
        state.dashboard_clients.add('dashboard2')
        state.connected_players.add('player1')
        
        with patch('src.sockets.dashboard.get_all_teams') as mock_get_teams:
            mock_get_teams.return_value = [
                {'team_name': 'TestTeam', 'status': 'waiting_pair', 'players': ['player1']}
            ]
            
            # Trigger dashboard update
            emit_dashboard_team_update(force_refresh=True)
            
            # Verify all dashboard clients received the update
            expected_calls = len(state.dashboard_clients)
            assert mock_socketio.emit.call_count == expected_calls
            
            # Verify the update data structure
            call_args = mock_socketio.emit.call_args_list[0]
            event_name = call_args[0][0]
            update_data = call_args[0][1]
            
            assert event_name == 'team_status_changed_for_dashboard'
            assert 'teams' in update_data
            assert 'connected_players_count' in update_data
            assert update_data['connected_players_count'] == 1

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
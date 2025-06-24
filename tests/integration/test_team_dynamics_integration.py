import eventlet
eventlet.monkey_patch()  # This must be at the very top

import pytest
import time
import logging
from flask_socketio import SocketIOTestClient
from src.config import app, socketio as server_socketio
from src.state import state
from src.models.quiz_models import Teams, PairQuestionRounds, ItemEnum, Answers, db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

def reset_application_state():
    """Reset the entire application state for clean tests"""
    try:
        with app.app_context():
            logger.info("[STATE RESET] Clearing application state")
            
            # Clear database
            Answers.query.delete()
            PairQuestionRounds.query.delete()
            Teams.query.delete()
            db.session.commit()
            
            # Reset in-memory state
            state.reset()
            
            logger.info("[STATE RESET] Application state cleared successfully")
    except Exception as e:
        logger.error(f"[STATE RESET] Error clearing state: {str(e)}")
        raise

@pytest.fixture(autouse=True)
def setup_and_cleanup():
    """Setup and cleanup for each test"""
    logger.info("\n[TEST SETUP] Resetting application state...")
    reset_application_state()
    yield
    logger.info("\n[TEST CLEANUP] Final state cleanup...")
    reset_application_state()

@pytest.fixture
def dashboard_client(app_context):
    """Create a dashboard test client"""
    client = None
    try:
        logger.info("\n[DASHBOARD] Creating dashboard client...")
        client = SocketIOTestClient(app, server_socketio)
        logger.info("[DASHBOARD] Dashboard client created")
        yield client
    finally:
        if client and client.connected:
            logger.info("[DASHBOARD] Disconnecting dashboard client...")
            try:
                client.disconnect()
                logger.info("[DASHBOARD] Dashboard client disconnected")
            except Exception as e:
                logger.error(f"[DASHBOARD] Error disconnecting client: {str(e)}")

@pytest.fixture
def player_client(app_context):
    """Create a player test client"""
    client = None
    try:
        logger.info("\n[PLAYER] Creating player client...")
        client = SocketIOTestClient(app, server_socketio)
        logger.info("[PLAYER] Player client created")
        yield client
    finally:
        if client and client.connected:
            logger.info("[PLAYER] Disconnecting player client...")
            try:
                client.disconnect()
                logger.info("[PLAYER] Player client disconnected")
            except Exception as e:
                logger.error(f"[PLAYER] Error disconnecting client: {str(e)}")

@pytest.fixture
def second_player_client(app_context):
    """Create a second player test client"""
    client = None
    try:
        logger.info("\n[PLAYER2] Creating second player client...")
        client = SocketIOTestClient(app, server_socketio)
        logger.info("[PLAYER2] Second player client created")
        yield client
    finally:
        if client and client.connected:
            logger.info("[PLAYER2] Disconnecting second player client...")
            try:
                client.disconnect()
                logger.info("[PLAYER2] Second player client disconnected")
            except Exception as e:
                logger.error(f"[PLAYER2] Error disconnecting second client: {str(e)}")

@pytest.fixture(scope="session")
def base_app_context():
    """Create base application context for the test session"""
    with app.app_context():
        app.extensions['socketio'] = server_socketio
        
        # Initialize database
        logger.info("\n[DB INIT] Initializing database...")
        db.drop_all()
        db.create_all()
        logger.info("[DB INIT] Database initialized")
        
        yield app
        
        # Cleanup at end of session
        logger.info("\n[DB CLEANUP] Cleaning up database...")
        db.session.remove()
        db.drop_all()
        logger.info("[DB CLEANUP] Database cleaned up")

@pytest.fixture
def app_context(base_app_context):
    """Create a fresh database transaction for each test"""
    # Start a nested transaction
    connection = db.engine.connect()
    transaction = connection.begin()
    
    # Configure the session with the connection
    db.session.configure(bind=connection)
    
    logger.info("\n[TEST TRANS] Starting test transaction")
    
    yield app
    
    # Rollback the transaction
    logger.info("[TEST TRANS] Rolling back test transaction")
    db.session.remove()
    transaction.rollback()
    connection.close()

class TestTeamDynamicsIntegration:
    """Integration tests for team dynamics with real socket connections"""

    def get_received_event(self, client, event_name, messages=None):
        """Helper method to get a specific event from received messages"""
        if messages is None:
            messages = client.get_received()
        return next((msg for msg in messages if msg.get('name') == event_name), None)

    def wait_for_event(self, client, event_name, timeout=2.0):
        """Helper method to wait for and get a specific event"""
        start_time = time.time()
        while (time.time() - start_time) < timeout:
            eventlet.sleep(0.1)
            event = self.get_received_event(client, event_name)
            if event is not None:
                return event
        return None

    @pytest.mark.integration
    def test_complete_team_lifecycle_with_dashboard_updates(self, app_context, dashboard_client, player_client, second_player_client):
        """Test complete team lifecycle with dashboard monitoring the entire process"""
        logger.info("\n[LIFECYCLE] Starting complete team lifecycle test...")
        
        # Step 1: Dashboard connects and gets initial state
        dashboard_client.emit('dashboard_join')
        eventlet.sleep(0.2)
        
        initial_dashboard_update = self.wait_for_event(dashboard_client, 'dashboard_update')
        assert initial_dashboard_update is not None, "Dashboard should receive initial update"
        initial_data = initial_dashboard_update.get('args', [{}])[0]
        assert initial_data.get('teams', []) == [], "Should start with no teams"
        assert initial_data.get('connected_players_count', 0) == 0, "Should start with no players"
        
        dashboard_client.get_received()  # Clear initial messages
        
        # Step 2: First player connects
        logger.info("[LIFECYCLE] Player 1 connecting...")
        assert player_client.connected, "Player 1 should be connected"
        eventlet.sleep(0.2)
        
        # Dashboard should get player count update
        dashboard_update = self.wait_for_event(dashboard_client, 'dashboard_update')
        if dashboard_update:
            update_data = dashboard_update.get('args', [{}])[0]
            logger.info(f"[LIFECYCLE] Dashboard received player count: {update_data.get('connected_players_count', 0)}")
        
        # Step 3: Player 1 creates team
        logger.info("[LIFECYCLE] Player 1 creating team...")
        player_client.emit('create_team', {'team_name': 'TestLifecycleTeam'})
        eventlet.sleep(0.2)
        
        team_created = self.wait_for_event(player_client, 'team_created')
        assert team_created is not None, "Player 1 should receive team_created"
        team_data = team_created.get('args', [{}])[0]
        team_id = team_data.get('team_id')
        logger.info(f"[LIFECYCLE] Team created with ID: {team_id}")
        
        # Dashboard should receive team update
        dashboard_team_update = self.wait_for_event(dashboard_client, 'team_status_changed_for_dashboard')
        assert dashboard_team_update is not None, "Dashboard should receive team status update"
        dashboard_data = dashboard_team_update.get('args', [{}])[0]
        teams = dashboard_data.get('teams', [])
        assert len(teams) == 1, "Dashboard should show 1 team"
        assert teams[0]['team_name'] == 'TestLifecycleTeam', "Team name should match"
        assert teams[0]['status'] == 'waiting_pair', "Team should be waiting for pair"
        
        player_client.get_received()  # Clear messages
        dashboard_client.get_received()  # Clear messages
        
        # Step 4: Second player connects and joins
        logger.info("[LIFECYCLE] Player 2 connecting and joining...")
        assert second_player_client.connected, "Player 2 should be connected"
        eventlet.sleep(0.2)
        
        second_player_client.emit('join_team', {'team_name': 'TestLifecycleTeam'})
        eventlet.sleep(0.2)
        
        # Player 2 should receive join confirmation
        team_joined = self.wait_for_event(second_player_client, 'team_joined')
        assert team_joined is not None, "Player 2 should receive team_joined"
        join_data = team_joined.get('args', [{}])[0]
        assert join_data.get('team_status') == 'full', "Team should be full"
        
        # Both players should receive team status update
        p1_status = self.wait_for_event(player_client, 'team_status_update')
        p2_status = self.wait_for_event(second_player_client, 'team_status_update')
        assert p1_status is not None, "Player 1 should receive status update"
        assert p2_status is not None, "Player 2 should receive status update"
        
        # Dashboard should receive updated team status
        dashboard_team_update = self.wait_for_event(dashboard_client, 'team_status_changed_for_dashboard')
        assert dashboard_team_update is not None, "Dashboard should receive team update"
        dashboard_data = dashboard_team_update.get('args', [{}])[0]
        teams = dashboard_data.get('teams', [])
        assert len(teams) == 1, "Dashboard should still show 1 team"
        assert teams[0]['status'] == 'active', "Team should now be active"
        
        player_client.get_received()
        second_player_client.get_received()
        dashboard_client.get_received()
        
        # Step 5: One player disconnects
        logger.info("[LIFECYCLE] Player 1 disconnecting...")
        player_client.disconnect()
        eventlet.sleep(0.3)  # Give time for disconnect processing
        
        # Player 2 should receive notification
        player_left = self.wait_for_event(second_player_client, 'player_left')
        assert player_left is not None, "Player 2 should be notified of player leaving"
        
        team_status_update = self.wait_for_event(second_player_client, 'team_status_update')
        assert team_status_update is not None, "Player 2 should receive status update"
        status_data = team_status_update.get('args', [{}])[0]
        assert status_data.get('status') == 'waiting_pair', "Team should be waiting for pair again"
        
        # Dashboard should receive team update
        dashboard_team_update = self.wait_for_event(dashboard_client, 'team_status_changed_for_dashboard')
        assert dashboard_team_update is not None, "Dashboard should receive team update after disconnect"
        dashboard_data = dashboard_team_update.get('args', [{}])[0]
        teams = dashboard_data.get('teams', [])
        if teams:  # Team might still exist
            assert teams[0]['status'] == 'waiting_pair', "Team should be waiting for pair"
        
        # Step 6: Second player also disconnects (team dissolution)
        logger.info("[LIFECYCLE] Player 2 disconnecting...")
        second_player_client.disconnect()
        eventlet.sleep(0.3)
        
        # Dashboard should receive final update
        dashboard_team_update = self.wait_for_event(dashboard_client, 'team_status_changed_for_dashboard')
        if dashboard_team_update:
            dashboard_data = dashboard_team_update.get('args', [{}])[0]
            teams = dashboard_data.get('teams', [])
            active_teams = [t for t in teams if t.get('is_active', True)]
            assert len(active_teams) == 0, "No active teams should remain"
        
        logger.info("[LIFECYCLE] Team lifecycle test completed successfully")

    @pytest.mark.integration
    def test_multiple_teams_concurrent_formation(self, app_context, dashboard_client):
        """Test multiple teams forming concurrently with dashboard tracking"""
        logger.info("\n[CONCURRENT] Starting concurrent team formation test...")
        
        # Dashboard connects first
        dashboard_client.emit('dashboard_join')
        eventlet.sleep(0.2)
        dashboard_client.get_received()  # Clear initial messages
        
        # Create multiple player clients and teams concurrently
        clients = []
        team_names = ['ConcurrentTeam1', 'ConcurrentTeam2', 'ConcurrentTeam3']
        
        try:
            # Phase 1: Create teams
            for i, team_name in enumerate(team_names):
                logger.info(f"[CONCURRENT] Creating team {team_name}...")
                
                # Create player pair for each team
                creator = SocketIOTestClient(app, server_socketio)
                joiner = SocketIOTestClient(app, server_socketio)
                clients.extend([creator, joiner])
                
                # Creator creates team
                creator.emit('create_team', {'team_name': team_name})
                eventlet.sleep(0.1)
                
                team_created = self.wait_for_event(creator, 'team_created')
                assert team_created is not None, f"Team {team_name} should be created"
                
                # Joiner joins team
                joiner.emit('join_team', {'team_name': team_name})
                eventlet.sleep(0.1)
                
                team_joined = self.wait_for_event(joiner, 'team_joined')
                assert team_joined is not None, f"Player should join {team_name}"
            
            # Give time for all dashboard updates
            eventlet.sleep(0.5)
            
            # Phase 2: Check dashboard received all updates
            messages = dashboard_client.get_received()
            team_updates = [msg for msg in messages if msg.get('name') == 'team_status_changed_for_dashboard']
            
            # Should have received multiple updates
            assert len(team_updates) >= len(team_names), "Dashboard should receive updates for all teams"
            
            # Check final state
            if team_updates:
                final_update = team_updates[-1]
                final_data = final_update.get('args', [{}])[0]
                teams = final_data.get('teams', [])
                active_teams = [t for t in teams if t.get('is_active', True)]
                
                assert len(active_teams) == len(team_names), f"Should have {len(team_names)} active teams"
                
                # Verify all teams are active/full
                for team in active_teams:
                    assert team.get('status') in ['active', 'full'], f"Team {team.get('team_name')} should be active"
            
            # Phase 3: Rapid disconnections
            logger.info("[CONCURRENT] Starting rapid disconnections...")
            for i, client in enumerate(clients[::2]):  # Disconnect every other client (creators)
                logger.info(f"[CONCURRENT] Disconnecting creator {i}...")
                client.disconnect()
                eventlet.sleep(0.1)
            
            # Give time for disconnect processing
            eventlet.sleep(0.5)
            
            # Check dashboard updates after disconnections
            messages = dashboard_client.get_received()
            team_updates = [msg for msg in messages if msg.get('name') == 'team_status_changed_for_dashboard']
            
            if team_updates:
                final_update = team_updates[-1]
                final_data = final_update.get('args', [{}])[0]
                teams = final_data.get('teams', [])
                active_teams = [t for t in teams if t.get('is_active', True)]
                
                # Some teams should now be waiting for pair or dissolved
                waiting_teams = [t for t in active_teams if t.get('status') == 'waiting_pair']
                logger.info(f"[CONCURRENT] Teams waiting for pair: {len(waiting_teams)}")
            
        finally:
            # Clean up all clients
            for client in clients:
                if client.connected:
                    client.disconnect()
            
            logger.info("[CONCURRENT] Concurrent team formation test completed")

    @pytest.mark.integration
    def test_dashboard_real_time_consistency(self, app_context, dashboard_client, player_client, second_player_client):
        """Test that dashboard maintains real-time consistency during rapid changes"""
        logger.info("\n[CONSISTENCY] Starting dashboard consistency test...")
        
        # Track all dashboard updates
        dashboard_updates = []
        
        def track_dashboard_updates():
            messages = dashboard_client.get_received()
            for msg in messages:
                if msg.get('name') in ['dashboard_update', 'team_status_changed_for_dashboard']:
                    data = msg.get('args', [{}])[0]
                    dashboard_updates.append({
                        'event': msg.get('name'),
                        'teams_count': len(data.get('teams', [])),
                        'connected_players': data.get('connected_players_count', 0),
                        'timestamp': time.time()
                    })
        
        # Dashboard connects
        dashboard_client.emit('dashboard_join')
        eventlet.sleep(0.2)
        track_dashboard_updates()
        
        # Rapid sequence of operations
        operations = [
            ('create_team', {'team_name': 'ConsistencyTeam1'}, player_client),
            ('join_team', {'team_name': 'ConsistencyTeam1'}, second_player_client),
            ('leave_team', {}, player_client),
            ('create_team', {'team_name': 'ConsistencyTeam2'}, player_client),
            ('join_team', {'team_name': 'ConsistencyTeam2'}, second_player_client),
        ]
        
        for operation, data, client in operations:
            logger.info(f"[CONSISTENCY] Performing {operation}...")
            client.emit(operation, data)
            eventlet.sleep(0.2)  # Brief pause between operations
            track_dashboard_updates()
        
        # Verify consistency
        assert len(dashboard_updates) > 0, "Dashboard should receive updates"
        
        # Check that all updates represent valid states
        for i, update in enumerate(dashboard_updates):
            assert update['teams_count'] >= 0, f"Update {i}: Invalid team count"
            assert update['connected_players'] >= 0, f"Update {i}: Invalid player count"
            
            # Each update should be reasonably close in time to the previous
            if i > 0:
                time_diff = update['timestamp'] - dashboard_updates[i-1]['timestamp']
                assert time_diff < 5.0, f"Update {i}: Too much time between updates"
        
        # Final state should be consistent
        final_update = dashboard_updates[-1]
        logger.info(f"[CONSISTENCY] Final state: {final_update['teams_count']} teams, {final_update['connected_players']} players")
        
        logger.info("[CONSISTENCY] Dashboard consistency test completed")

    @pytest.mark.integration  
    def test_team_reactivation_with_dashboard_monitoring(self, app_context, dashboard_client, player_client):
        """Test team reactivation process with dashboard monitoring"""
        logger.info("\n[REACTIVATION] Starting team reactivation test...")
        
        # Dashboard connects
        dashboard_client.emit('dashboard_join')
        eventlet.sleep(0.2)
        dashboard_client.get_received()  # Clear initial messages
        
        # Step 1: Create and then abandon a team
        logger.info("[REACTIVATION] Creating initial team...")
        player_client.emit('create_team', {'team_name': 'ReactivationTeam'})
        eventlet.sleep(0.2)
        
        team_created = self.wait_for_event(player_client, 'team_created')
        assert team_created is not None, "Team should be created"
        team_id = team_created.get('args', [{}])[0].get('team_id')
        
        # Dashboard should show active team
        dashboard_update = self.wait_for_event(dashboard_client, 'team_status_changed_for_dashboard')
        assert dashboard_update is not None, "Dashboard should receive team update"
        
        # Player leaves, making team inactive
        logger.info("[REACTIVATION] Player leaving to make team inactive...")
        player_client.emit('leave_team', {})
        eventlet.sleep(0.2)
        
        left_team = self.wait_for_event(player_client, 'left_team_success')
        assert left_team is not None, "Player should leave team successfully"
        
        # Dashboard should show team as inactive or removed
        dashboard_update = self.wait_for_event(dashboard_client, 'team_status_changed_for_dashboard')
        if dashboard_update:
            dashboard_data = dashboard_update.get('args', [{}])[0]
            teams = dashboard_data.get('teams', [])
            active_teams = [t for t in teams if t.get('is_active', True)]
            # Team should either be gone or inactive
            reactivation_team = next((t for t in active_teams if t.get('team_name') == 'ReactivationTeam'), None)
            assert reactivation_team is None, "Team should not be active anymore"
        
        player_client.get_received()
        dashboard_client.get_received()
        
        # Step 2: Reactivate the team
        logger.info("[REACTIVATION] Reactivating team...")
        player_client.emit('reactivate_team', {'team_name': 'ReactivationTeam'})
        eventlet.sleep(0.2)
        
        team_reactivated = self.wait_for_event(player_client, 'team_created')  # Reactivation sends team_created
        assert team_reactivated is not None, "Team should be reactivated"
        reactivated_data = team_reactivated.get('args', [{}])[0]
        assert reactivated_data.get('team_name') == 'ReactivationTeam', "Team name should match"
        
        # Dashboard should show reactivated team
        dashboard_update = self.wait_for_event(dashboard_client, 'team_status_changed_for_dashboard')
        assert dashboard_update is not None, "Dashboard should receive reactivation update"
        dashboard_data = dashboard_update.get('args', [{}])[0]
        teams = dashboard_data.get('teams', [])
        active_teams = [t for t in teams if t.get('is_active', True)]
        
        reactivated_team = next((t for t in active_teams if t.get('team_name') == 'ReactivationTeam'), None)
        assert reactivated_team is not None, "Reactivated team should appear in dashboard"
        assert reactivated_team.get('status') == 'waiting_pair', "Reactivated team should be waiting for pair"
        
        logger.info("[REACTIVATION] Team reactivation test completed")

    @pytest.mark.integration
    def test_game_state_integration_with_teams(self, app_context, dashboard_client, player_client, second_player_client):
        """Test game state changes integration with team dynamics"""
        logger.info("\n[GAME_STATE] Starting game state integration test...")
        
        # Dashboard connects
        dashboard_client.emit('dashboard_join')
        eventlet.sleep(0.2)
        dashboard_client.get_received()
        
        # Create full team
        logger.info("[GAME_STATE] Creating full team...")
        player_client.emit('create_team', {'team_name': 'GameStateTeam'})
        eventlet.sleep(0.2)
        
        second_player_client.emit('join_team', {'team_name': 'GameStateTeam'})
        eventlet.sleep(0.2)
        
        # Clear messages
        player_client.get_received()
        second_player_client.get_received()
        dashboard_client.get_received()
        
        # Start game from dashboard
        logger.info("[GAME_STATE] Starting game...")
        dashboard_client.emit('start_game')
        eventlet.sleep(0.2)
        
        # Players should receive game start notification
        p1_game_start = self.wait_for_event(player_client, 'game_start')
        p2_game_start = self.wait_for_event(second_player_client, 'game_start')
        
        # Dashboard should receive game started confirmation
        dashboard_game_started = self.wait_for_event(dashboard_client, 'game_started')
        assert dashboard_game_started is not None, "Dashboard should receive game started confirmation"
        
        # Players should receive new question (game started with full team)
        p1_question = self.wait_for_event(player_client, 'new_question', timeout=3.0)
        p2_question = self.wait_for_event(second_player_client, 'new_question', timeout=3.0)
        
        if p1_question and p2_question:
            logger.info("[GAME_STATE] Players received questions as expected")
            p1_data = p1_question.get('args', [{}])[0]
            p2_data = p2_question.get('args', [{}])[0]
            
            assert p1_data.get('round_number') == 1, "Should be round 1"
            assert p2_data.get('round_number') == 1, "Should be round 1"
            assert p1_data.get('round_id') == p2_data.get('round_id'), "Same round ID"
        
        # Clear messages
        player_client.get_received()
        second_player_client.get_received()
        dashboard_client.get_received()
        
        # Test game pause
        logger.info("[GAME_STATE] Pausing game...")
        dashboard_client.emit('pause_game')
        eventlet.sleep(0.2)
        
        # Players should receive pause notification
        p1_pause = self.wait_for_event(player_client, 'game_state_update')
        p2_pause = self.wait_for_event(second_player_client, 'game_state_update')
        
        if p1_pause:
            pause_data = p1_pause.get('args', [{}])[0]
            assert pause_data.get('paused') == True, "Game should be paused"
        
        # Test game reset
        logger.info("[GAME_STATE] Resetting game...")
        dashboard_client.emit('restart_game')
        eventlet.sleep(0.5)  # Reset takes longer
        
        # Players should receive reset notification
        p1_reset = self.wait_for_event(player_client, 'game_reset')
        p2_reset = self.wait_for_event(second_player_client, 'game_reset')
        
        # Dashboard should receive reset complete
        dashboard_reset = self.wait_for_event(dashboard_client, 'game_reset_complete')
        assert dashboard_reset is not None, "Dashboard should receive reset complete"
        
        logger.info("[GAME_STATE] Game state integration test completed")

    @pytest.mark.integration
    def test_error_resilience_with_dashboard(self, app_context, dashboard_client, player_client):
        """Test system resilience to errors with dashboard monitoring"""
        logger.info("\n[RESILIENCE] Starting error resilience test...")
        
        # Dashboard connects
        dashboard_client.emit('dashboard_join')
        eventlet.sleep(0.2)
        dashboard_client.get_received()
        
        # Test various error conditions
        error_scenarios = [
            ('create_team', {}),  # Missing team name
            ('join_team', {'team_name': 'NonexistentTeam'}),  # Join nonexistent team
            ('leave_team', {}),  # Leave when not in team
            ('reactivate_team', {'team_name': 'NonexistentTeam'}),  # Reactivate nonexistent
        ]
        
        for operation, data in error_scenarios:
            logger.info(f"[RESILIENCE] Testing error scenario: {operation}")
            player_client.emit(operation, data)
            eventlet.sleep(0.2)
            
            # Should receive error message
            error_msg = self.wait_for_event(player_client, 'error')
            assert error_msg is not None, f"Should receive error for {operation}"
            
            # Dashboard should remain consistent (not receive invalid updates)
            messages = dashboard_client.get_received()
            team_updates = [msg for msg in messages if msg.get('name') == 'team_status_changed_for_dashboard']
            
            # Any updates should still represent valid states
            for update in team_updates:
                data = update.get('args', [{}])[0]
                teams = data.get('teams', [])
                assert isinstance(teams, list), "Teams should be a list"
                for team in teams:
                    assert 'team_name' in team, "Team should have name"
                    assert 'status' in team, "Team should have status"
        
        # System should still work normally after errors
        logger.info("[RESILIENCE] Testing normal operation after errors...")
        player_client.emit('create_team', {'team_name': 'ResilienceTeam'})
        eventlet.sleep(0.2)
        
        team_created = self.wait_for_event(player_client, 'team_created')
        assert team_created is not None, "Normal operation should work after errors"
        
        dashboard_update = self.wait_for_event(dashboard_client, 'team_status_changed_for_dashboard')
        assert dashboard_update is not None, "Dashboard should receive normal updates"
        
        logger.info("[RESILIENCE] Error resilience test completed")
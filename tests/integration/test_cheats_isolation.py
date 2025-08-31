"""Integration tests to ensure non-cheat teams are not affected by cheat features."""

import eventlet
eventlet.monkey_patch()  # This must be at the very top

import pytest
import os
import time
import logging
from flask_socketio import SocketIOTestClient
from src.config import app, db, socketio as server_socketio
from src.models.quiz_models import Teams, ItemEnum
from src.state import state

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
            
            # Clear all database data
            db.session.query(Teams).delete()
            db.session.commit()
            
            # Reset in-memory state
            state.reset()
            
            logger.info(f"[STATE RESET] Active teams: {len(state.active_teams)}")
            logger.info(f"[STATE RESET] Player mappings: {len(state.player_to_team)}")
            logger.info(f"[STATE RESET] Connected players: {len(state.connected_players)}")
            logger.info(f"[STATE RESET] Dashboard clients: {len(state.dashboard_clients)}")
            logger.info("[STATE RESET] Application state reset complete")
    except Exception as e:
        logger.error(f"[STATE RESET] Error resetting state: {str(e)}", exc_info=True)


@pytest.fixture(autouse=True)
def setup_and_cleanup():
    """Setup and cleanup for each test"""
    logger.info("\n[TEST SETUP] Resetting application state...")
    reset_application_state()
    yield
    logger.info("[TEST CLEANUP] Test completed")


@pytest.fixture
def socket_client(app_context):
    """Create a test client for SocketIO with proper cleanup"""
    client = None
    try:
        logger.info("\n[CLIENT] Creating test client...")
        client = SocketIOTestClient(app, server_socketio)
        client.connect()  # Explicitly connect
        logger.info("[CLIENT] Test client created and connected")
        yield client
    finally:
        if client and client.connected:
            logger.info("[CLIENT] Disconnecting test client...")
            client.disconnect()
            logger.info("[CLIENT] Test client disconnected")


@pytest.fixture
def second_client(app_context):
    """Create a second test client for team interactions with proper cleanup"""
    client = None
    try:
        logger.info("\n[CLIENT] Creating second test client...")
        client = SocketIOTestClient(app, server_socketio)
        client.connect()  # Explicitly connect
        logger.info("[CLIENT] Second test client created and connected")
        yield client
    finally:
        if client and client.connected:
            logger.info("[CLIENT] Disconnecting second test client...")
            client.disconnect()
            logger.info("[CLIENT] Second test client disconnected")


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


class TestCheatsIsolation:
    """Test that non-cheat teams remain completely unaffected by cheat features."""
    
    def wait_for_event(self, client, event_name, timeout=5):
        """Helper to wait for specific event"""
        import time
        start_time = time.time()
        while time.time() - start_time < timeout:
            received = client.get_received()
            for event in received:
                if event['name'] == event_name:
                    return event
            eventlet.sleep(0.1)
        return None
    
    def verify_connection(self, client):
        """Helper method to verify client connection"""
        assert client.connected, "Client failed to connect to server"
        time.sleep(0.2)  # Give more time
        
        # Get received messages
        messages = client.get_received()
        logger.info(f"[VERIFY] Received {len(messages)} messages: {[m.get('name') for m in messages]}")
        
        # Verify connection_established event
        msg = next((msg for msg in messages if msg.get('name') == 'connection_established'), None)
        if msg is None:
            # Try again with more time
            eventlet.sleep(0.5)
            messages = client.get_received()
            logger.info(f"[VERIFY] After retry, received {len(messages)} messages: {[m.get('name') for m in messages]}")
            msg = next((msg for msg in messages if msg.get('name') == 'connection_established'), None)
        
        assert msg is not None, f"Did not receive connection_established event. Got: {[m.get('name') for m in messages]}"
        data = msg.get('args', [{}])[0]
        
        logger.info(f"[VERIFY] Connection established: {data}")
        return data
    
    @pytest.mark.integration
    def test_normal_team_creation_unaffected(self, app_context, socket_client):
        """Test that normal team creation works exactly as before."""
        # Verify connection
        self.verify_connection(socket_client)
        socket_client.get_received()  # Clear initial messages
        
        # Create a normal team
        team_name = "Normal Team"
        socket_client.emit('create_team', {'team_name': team_name})
        
        # Verify team was created successfully
        event = self.wait_for_event(socket_client, 'team_created')
        assert event is not None
        assert event['args'][0]['team_name'] == team_name
        
        # Verify team state doesn't have cheat_type or has it as 'none'
        team_info = state.active_teams.get(team_name)
        assert team_info is not None
        assert team_info.get('cheat_type', 'none') == 'none'
    
    @pytest.mark.integration
    def test_normal_team_join_unaffected(self, app_context, socket_client, second_client):
        """Test that joining a normal team works exactly as before."""
        # Verify connections
        self.verify_connection(socket_client)
        self.verify_connection(second_client)
        socket_client.get_received()  # Clear initial messages
        second_client.get_received()  # Clear initial messages
        
        # Create team with first player
        team_name = "Test Team Normal"
        socket_client.emit('create_team', {'team_name': team_name})
        self.wait_for_event(socket_client, 'team_created')
        
        # Second player joins
        second_client.emit('join_team', {'team_name': team_name})
        
        # Verify join was successful
        event = self.wait_for_event(second_client, 'team_joined')
        assert event is not None
        
        # Verify team is now full
        team_info = state.active_teams.get(team_name)
        assert len(team_info['players']) == 2
        assert team_info['status'] == 'active'
    
    @pytest.mark.integration
    def test_cheats_ban_does_not_affect_normal_teams(self, app_context, socket_client):
        """Test that enabling cheats ban doesn't affect normal teams."""
        # Verify connection
        self.verify_connection(socket_client)
        socket_client.get_received()  # Clear initial messages
        
        team_name = "Regular Team"
        
        # Enable cheats ban
        state.cheats_banned = True
        
        try:
            # Should still be able to create normal team
            socket_client.emit('create_team', {'team_name': team_name})
            
            event = self.wait_for_event(socket_client, 'team_created')
            assert event is not None
        finally:
            # Disable ban for cleanup
            state.cheats_banned = False
    
    @pytest.mark.integration
    def test_cheat_teams_blocked_when_banned(self, app_context, socket_client):
        """Test that cheat teams are properly blocked when cheats are banned."""
        # Verify connection
        self.verify_connection(socket_client)
        socket_client.get_received()  # Clear initial messages
        
        # Enable cheats ban
        state.cheats_banned = True
        
        try:
            # Try to create various cheat teams
            cheat_names = ["cheat-com", "cheat-hint-team", "CHEAT-TONY_123", "cheat-kevin test"]
            
            for team_name in cheat_names:
                socket_client.emit('create_team', {'team_name': team_name})
                
                error_event = self.wait_for_event(socket_client, 'error')
                assert error_event is not None
                assert 'cheat prefixes are not allowed' in error_event['args'][0]['message']
                
                # Clear events for next iteration
                socket_client.get_received()
        finally:
            # Disable ban for cleanup
            state.cheats_banned = False
    
    @pytest.mark.integration
    def test_environment_variable_ban(self, app_context, socket_client):
        """Test that CHEATS_DISABLED environment variable works."""
        # Verify connection
        self.verify_connection(socket_client)
        socket_client.get_received()  # Clear initial messages
        
        # Temporarily set the environment variable
        original_value = os.environ.get('CHEATS_DISABLED')
        os.environ['CHEATS_DISABLED'] = 'true'
        
        try:
            # Reset state to pick up env var
            state.reset()
            assert state.cheats_banned == True
            
            # Try to create a cheat team
            socket_client.emit('create_team', {'team_name': 'cheat-com-test'})
            
            error_event = self.wait_for_event(socket_client, 'error')
            assert error_event is not None
        finally:
            # Restore original environment
            if original_value is None:
                os.environ.pop('CHEATS_DISABLED', None)
            else:
                os.environ['CHEATS_DISABLED'] = original_value
            state.reset()
    
    @pytest.mark.integration
    def test_reactivate_cheat_team_blocked_when_banned(self, app_context, socket_client):
        """Test that reactivating a cheat team is blocked when cheats are banned."""
        # Verify connection
        self.verify_connection(socket_client)
        socket_client.get_received()  # Clear initial messages
        
        team_name = "cheat-hint-old"
        
        # Create team while cheats are allowed
        state.cheats_banned = False
        socket_client.emit('create_team', {'team_name': team_name})
        self.wait_for_event(socket_client, 'team_created')
        
        # Manually deactivate the team
        team_info = state.active_teams.get(team_name)
        if team_info:
            db_team = Teams.query.get(team_info['team_id'])
            db_team.is_active = False
            db.session.commit()
            del state.active_teams[team_name]
        
        # Disconnect and reconnect to simulate fresh connection
        socket_client.disconnect()
        eventlet.sleep(0.1)
        socket_client.connect()
        
        # Now try to reactivate with cheats banned
        state.cheats_banned = True
        try:
            socket_client.emit('reactivate_team', {'team_name': team_name})
            
            error_event = self.wait_for_event(socket_client, 'error')
            assert error_event is not None
            assert 'cheat prefixes are not allowed' in error_event['args'][0]['message']
        finally:
            # Cleanup
            state.cheats_banned = False
    
    @pytest.mark.integration
    def test_join_existing_cheat_team_blocked_when_banned(self, app_context, socket_client, second_client):
        """Test that joining an existing cheat team is blocked when cheats are banned."""
        # Verify connections
        self.verify_connection(socket_client)
        self.verify_connection(second_client)
        socket_client.get_received()  # Clear initial messages
        second_client.get_received()  # Clear initial messages
        
        team_name = "cheat-tony-team"
        
        # Create a cheat team while cheats are allowed
        state.cheats_banned = False
        socket_client.emit('create_team', {'team_name': team_name})
        self.wait_for_event(socket_client, 'team_created')
        
        # Now ban cheats and try to join
        state.cheats_banned = True
        try:
            second_client.emit('join_team', {'team_name': team_name})
            
            error_event = self.wait_for_event(second_client, 'error')
            assert error_event is not None
            assert 'Cannot join teams with cheat prefixes' in error_event['args'][0]['message']
        finally:
            # Cleanup
            state.cheats_banned = False
import pytest
import threading
import time
import socketio

def test_player_refresh_before_joining(player_client, reset_state):
    """Test player browser refresh before joining a team."""
    # Connect and then disconnect to simulate refresh
    assert player_client.connected
    player_client.disconnect()
    time.sleep(0.5)
    
    # Reconnect
    player_client.connect('http://127.0.0.1:8080')
    assert player_client.connected
    
    # Verify can still create team after refresh
    team_created = threading.Event()
    team_data = {}
    
    @player_client.on('team_created')
    def on_team_created(data):
        team_data.update(data)
        team_created.set()
    
    player_client.emit('create_team', {'team_name': 'RefreshTeam'})
    assert team_created.wait(timeout=2), "Team creation after refresh timed out"
    assert team_data.get('team_name') == 'RefreshTeam'

def test_player_refresh_after_creating_team(player_client, reset_state):
    """Test player browser refresh after creating a team."""
    # Create a team first
    team_created = threading.Event()
    team_data = {}
    
    @player_client.on('team_created')
    def on_team_created(data):
        team_data.update(data)
        team_created.set()
    
    player_client.emit('create_team', {'team_name': 'RefreshTeam'})
    assert team_created.wait(timeout=2), "Team creation timed out"
    team_id = team_data.get('team_id')
    
    # Disconnect to simulate refresh
    player_client.disconnect()
    time.sleep(0.5)
    
    # Reconnect
    player_client.connect('http://127.0.0.1:8080')
    assert player_client.connected
    
    # Try to reactivate the team
    reactivated = threading.Event()
    reactivate_data = {}
    
    @player_client.on('team_created')
    def on_reactivated(data):
        reactivate_data.update(data)
        reactivated.set()
    
    player_client.emit('reactivate_team', {'team_name': 'RefreshTeam'})
    assert reactivated.wait(timeout=2), "Team reactivation after refresh timed out"
    
    assert reactivate_data.get('team_name') == 'RefreshTeam'
    assert reactivate_data.get('team_id') == team_id

def test_player_refresh_during_game(complete_team, dashboard_client, reset_state):
    """Test player browser refresh during an active game."""
    player1, player2, team_name, team_data = complete_team
    team_id = team_data.get('team_id')
    
    # Start the game
    game_started = threading.Event()
    new_round_received = threading.Event()
    round_data = {}
    
    @player1.on('game_started')
    def on_game_started(data):
        game_started.set()
    
    @player1.on('new_round')
    def on_new_round(data):
        round_data.update(data)
        new_round_received.set()
    
    dashboard_client.emit('start_game')
    assert game_started.wait(timeout=2), "Game start notification timed out"
    assert new_round_received.wait(timeout=2), "New round notification timed out"
    
    # Disconnect player1 to simulate refresh
    player1.disconnect()
    time.sleep(0.5)
    
    # Reconnect player1
    player1 = socketio.Client()
    player1.connect('http://127.0.0.1:8080')
    
    # Try to reactivate the team
    reactivated = threading.Event()
    reactivate_data = {}
    new_round_after_refresh = threading.Event()
    new_round_data = {}
    
    @player1.on('team_created')
    def on_reactivated(data):
        reactivate_data.update(data)
        reactivated.set()
    
    @player1.on('new_round')
    def on_new_round_after_refresh(data):
        new_round_data.update(data)
        new_round_after_refresh.set()
    
    player1.emit('reactivate_team', {'team_name': team_name})
    assert reactivated.wait(timeout=2), "Team reactivation after refresh timed out"
    assert new_round_after_refresh.wait(timeout=2), "New round after refresh timed out"
    
    assert reactivate_data.get('team_name') == team_name
    assert reactivate_data.get('team_id') == team_id
    assert reactivate_data.get('game_started') is True
    assert new_round_data.get('round_number') > 0

def test_host_refresh_during_game(complete_team, dashboard_client, reset_state):
    """Test host dashboard refresh during an active game."""
    player1, player2, team_name, _ = complete_team
    
    # Start the game
    game_started = threading.Event()
    
    @player1.on('game_started')
    def on_game_started(data):
        game_started.set()
    
    dashboard_client.emit('start_game')
    assert game_started.wait(timeout=2), "Game start notification timed out"
    
    # Disconnect dashboard to simulate refresh
    dashboard_client.disconnect()
    time.sleep(0.5)
    
    # Reconnect dashboard
    dashboard_client = socketio.Client()
    dashboard_client.connect('http://127.0.0.1:8080')
    
    # Register as dashboard
    dashboard_registered = threading.Event()
    
    @dashboard_client.on('dashboard_registered')
    def on_dashboard_registered(data):
        dashboard_registered.set()
    
    dashboard_client.emit('register_dashboard')
    assert dashboard_registered.wait(timeout=2), "Dashboard registration after refresh timed out"
    
    # Verify dashboard can still control the game
    game_paused = threading.Event()
    game_state_update = {}
    
    @player1.on('game_state_update')
    def on_game_state_update(data):
        game_state_update.update(data)
        game_paused.set()
    
    dashboard_client.emit('pause_game')
    assert game_paused.wait(timeout=2), "Game pause after dashboard refresh timed out"
    assert game_state_update.get('paused') is True

def test_both_players_refresh(server_thread, reset_state):
    """Test both players refreshing browsers during a game."""
    # Create two players and a team
    player1 = socketio.Client()
    player2 = socketio.Client()
    
    player1.connect('http://127.0.0.1:8080')
    player2.connect('http://127.0.0.1:8080')
    
    team_created = threading.Event()
    team_joined = threading.Event()
    team_data = {}
    team_name = "RefreshTeam"
    
    @player1.on('team_created')
    def on_team_created(data):
        team_data.update(data)
        team_created.set()
    
    @player2.on('joined_team')
    def on_joined_team(data):
        team_joined.set()
    
    player1.emit('create_team', {'team_name': team_name})
    assert team_created.wait(timeout=2), "Team creation timed out"
    
    player2.emit('join_team', {'team_name': team_name})
    assert team_joined.wait(timeout=2), "Team joining timed out"
    
    team_id = team_data.get('team_id')
    
    # Create dashboard and start game
    dashboard = socketio.Client()
    dashboard.connect('http://127.0.0.1:8080')
    dashboard.emit('register_dashboard')
    time.sleep(0.5)
    
    game_started = threading.Event()
    
    @player1.on('game_started')
    def on_game_started(data):
        game_started.set()
    
    dashboard.emit('start_game')
    assert game_started.wait(timeout=2), "Game start notification timed out"
    
    # Disconnect both players to simulate refresh
    player1.disconnect()
    player2.disconnect()
    time.sleep(0.5)
    
    # Reconnect both players
    new_player1 = socketio.Client()
    new_player2 = socketio.Client()
    
    new_player1.connect('http://127.0.0.1:8080')
    new_player2.connect('http://127.0.0.1:8080')
    
    # First player reactivates the team
    reactivated = threading.Event()
    reactivate_data = {}
    
    @new_player1.on('team_created')
    def on_reactivated(data):
        reactivate_data.update(data)
        reactivated.set()
    
    new_player1.emit('reactivate_team', {'team_name': team_name})
    assert reactivated.wait(timeout=2), "Team reactivation after refresh timed out"
    
    # Second player joins the team
    joined_after_refresh = threading.Event()
    
    @new_player2.on('joined_team')
    def on_joined_after_refresh(data):
        joined_after_refresh.set()
    
    new_player2.emit('join_team', {'team_name': team_name})
    assert joined_after_refresh.wait(timeout=2), "Team joining after refresh timed out"
    
    # Verify both players can submit answers
    answer_confirmed1 = threading.Event()
    answer_confirmed2 = threading.Event()
    
    @new_player1.on('new_round')
    def on_new_round1(data):
        round_data = data
        
        @new_player1.on('answer_confirmed')
        def on_answer_confirmed1(data):
            answer_confirmed1.set()
        
        new_player1.emit('submit_answer', {
            'round_id': round_data.get('round_id'),
            'item': round_data.get('assigned_item'),
            'answer': True
        })
    
    @new_player2.on('new_round')
    def on_new_round2(data):
        round_data = data
        
        @new_player2.on('answer_confirmed')
        def on_answer_confirmed2(data):
            answer_confirmed2.set()
        
        new_player2.emit('submit_answer', {
            'round_id': round_data.get('round_id'),
            'item': round_data.get('assigned_item'),
            'answer': False
        })
    
    # Wait for both players to submit answers
    assert answer_confirmed1.wait(timeout=5), "Answer confirmation for player 1 after refresh timed out"
    assert answer_confirmed2.wait(timeout=5), "Answer confirmation for player 2 after refresh timed out"
    
    # Clean up
    new_player1.disconnect()
    new_player2.disconnect()
    dashboard.disconnect()

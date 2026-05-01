import pytest
import threading
import time
import socketio

def test_create_team(player_client, reset_state):
    """Test creating a team."""
    team_created = threading.Event()
    team_data = {}
    
    @player_client.on('team_created')
    def on_team_created(data):
        team_data.update(data)
        team_created.set()
    
    player_client.emit('create_team', {'team_name': 'TestTeam'})
    
    assert team_created.wait(timeout=2), "Team creation timed out"
    assert team_data.get('team_name') == 'TestTeam'
    assert 'team_id' in team_data
    assert team_data.get('message') is not None

def test_join_team(two_player_clients, reset_state):
    """Test joining an existing team."""
    player1, player2 = two_player_clients
    
    # Events for tracking responses
    team_created = threading.Event()
    team_joined = threading.Event()
    team_status_updated = threading.Event()
    team_data = {}
    join_data = {}
    status_data = {}
    
    @player1.on('team_created')
    def on_team_created(data):
        team_data.update(data)
        team_created.set()
    
    @player2.on('joined_team')
    def on_joined_team(data):
        join_data.update(data)
        team_joined.set()
    
    @player1.on('team_status_update')
    def on_team_status_update(data):
        status_data.update(data)
        team_status_updated.set()
    
    # Create team with player1
    player1.emit('create_team', {'team_name': 'TestTeam'})
    assert team_created.wait(timeout=2), "Team creation timed out"
    
    # Join team with player2
    player2.emit('join_team', {'team_name': 'TestTeam'})
    assert team_joined.wait(timeout=2), "Team joining timed out"
    assert team_status_updated.wait(timeout=2), "Team status update timed out"
    
    assert join_data.get('team_name') == 'TestTeam'
    assert status_data.get('status') == 'ready'
    assert len(status_data.get('members', [])) == 2

def test_leave_team(complete_team, reset_state):
    """Test leaving a team."""
    player1, player2, team_name, _ = complete_team
    
    # Events for tracking responses
    player_left = threading.Event()
    left_success = threading.Event()
    team_status_updated = threading.Event()
    left_data = {}
    status_data = {}
    
    @player1.on('player_left')
    def on_player_left(data):
        player_left.set()
    
    @player2.on('left_team_success')
    def on_left_success(data):
        left_success.set()
    
    @player1.on('team_status_update')
    def on_team_status_update(data):
        status_data.update(data)
        team_status_updated.set()
    
    # Player2 leaves the team
    player2.emit('leave_team')
    
    assert left_success.wait(timeout=2), "Leave team confirmation timed out"
    assert player_left.wait(timeout=2), "Player left notification timed out"
    assert team_status_updated.wait(timeout=2), "Team status update timed out"
    
    assert status_data.get('status') == 'waiting_pair'
    assert len(status_data.get('members', [])) == 1

def test_team_reactivation(player_client, reset_state):
    """Test reactivating a team after all players leave."""
    # First create a team
    team_created = threading.Event()
    team_data = {}
    
    @player_client.on('team_created')
    def on_team_created(data):
        team_data.update(data)
        team_created.set()
    
    player_client.emit('create_team', {'team_name': 'ReactivateTeam'})
    assert team_created.wait(timeout=2), "Team creation timed out"
    
    # Leave the team to make it inactive
    left_success = threading.Event()
    
    @player_client.on('left_team_success')
    def on_left_success(data):
        left_success.set()
    
    player_client.emit('leave_team')
    assert left_success.wait(timeout=2), "Leave team confirmation timed out"
    
    # Disconnect and reconnect
    player_client.disconnect()
    time.sleep(0.5)
    player_client.connect('http://127.0.0.1:5000')
    
    # Try to reactivate the team
    reactivated = threading.Event()
    reactivate_data = {}
    
    @player_client.on('team_created')
    def on_reactivated(data):
        reactivate_data.update(data)
        reactivated.set()
    
    player_client.emit('reactivate_team', {'team_name': 'ReactivateTeam'})
    assert reactivated.wait(timeout=2), "Team reactivation timed out"
    
    assert reactivate_data.get('team_name') == 'ReactivateTeam'
    assert 'team_id' in reactivate_data

def test_duplicate_team_names(two_player_clients, reset_state):
    """Test handling of duplicate team names."""
    player1, player2 = two_player_clients
    
    # Events for tracking responses
    team1_created = threading.Event()
    team2_error = threading.Event()
    team1_data = {}
    error_data = {}
    
    @player1.on('team_created')
    def on_team1_created(data):
        team1_data.update(data)
        team1_created.set()
    
    @player2.on('error')
    def on_error(data):
        error_data.update(data)
        team2_error.set()
    
    # Create first team
    player1.emit('create_team', {'team_name': 'DuplicateTeam'})
    assert team1_created.wait(timeout=2), "First team creation timed out"
    
    # Try to create second team with same name
    player2.emit('create_team', {'team_name': 'DuplicateTeam'})
    assert team2_error.wait(timeout=2), "Error for duplicate team name timed out"
    
    assert 'already exists' in error_data.get('message', '').lower()

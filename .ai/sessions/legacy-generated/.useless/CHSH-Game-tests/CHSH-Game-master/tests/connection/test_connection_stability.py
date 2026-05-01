import pytest
import threading
import time
import socketio
import random

class SlowClient(socketio.Client):
    """A Socket.IO client that simulates slow connections."""
    
    def __init__(self, delay_min=0.1, delay_max=0.5):
        super().__init__()
        self.delay_min = delay_min
        self.delay_max = delay_max
        
    def emit(self, event, data=None, *args, **kwargs):
        """Override emit to add random delay."""
        delay = random.uniform(self.delay_min, self.delay_max)
        time.sleep(delay)
        return super().emit(event, data, *args, **kwargs)

@pytest.fixture(scope="function")
def slow_client(server_thread):
    """Create a Socket.IO client with simulated slow connection."""
    client = SlowClient(delay_min=0.2, delay_max=0.8)
    client.connect('http://127.0.0.1:5000')
    yield client
    if client.connected:
        client.disconnect()

def test_slow_client_team_creation(slow_client, reset_state):
    """Test team creation with a slow client connection."""
    team_created = threading.Event()
    team_data = {}
    
    @slow_client.on('team_created')
    def on_team_created(data):
        team_data.update(data)
        team_created.set()
    
    slow_client.emit('create_team', {'team_name': 'SlowTeam'})
    
    assert team_created.wait(timeout=5), "Team creation with slow client timed out"
    assert team_data.get('team_name') == 'SlowTeam'
    assert 'team_id' in team_data

def test_slow_client_answer_submission(server_thread, reset_state):
    """Test answer submission with slow client connections."""
    # Create regular client for dashboard
    dashboard = socketio.Client()
    dashboard.connect('http://127.0.0.1:5000')
    dashboard.emit('register_dashboard')
    time.sleep(0.5)
    
    # Create one regular and one slow client
    player1 = socketio.Client()
    player2 = SlowClient(delay_min=0.3, delay_max=1.0)
    
    player1.connect('http://127.0.0.1:5000')
    player2.connect('http://127.0.0.1:5000')
    
    # Create team with regular client
    team_created = threading.Event()
    team_joined = threading.Event()
    team_data = {}
    team_name = "MixedSpeedTeam"
    
    @player1.on('team_created')
    def on_team_created(data):
        team_data.update(data)
        team_created.set()
    
    @player2.on('joined_team')
    def on_joined_team(data):
        team_joined.set()
    
    player1.emit('create_team', {'team_name': team_name})
    assert team_created.wait(timeout=2), "Team creation timed out"
    
    # Slow client joins team
    player2.emit('join_team', {'team_name': team_name})
    assert team_joined.wait(timeout=5), "Team joining with slow client timed out"
    
    # Start game
    game_started = threading.Event()
    
    @player1.on('game_started')
    def on_game_started(data):
        game_started.set()
    
    dashboard.emit('start_game')
    assert game_started.wait(timeout=2), "Game start notification timed out"
    
    # Track rounds and answers
    p1_round_data = {}
    p2_round_data = {}
    p1_round_received = threading.Event()
    p2_round_received = threading.Event()
    
    @player1.on('new_round')
    def on_p1_round(data):
        p1_round_data.update(data)
        p1_round_received.set()
    
    @player2.on('new_round')
    def on_p2_round(data):
        p2_round_data.update(data)
        p2_round_received.set()
    
    assert p1_round_received.wait(timeout=2), "Round notification for player 1 timed out"
    assert p2_round_received.wait(timeout=5), "Round notification for slow player 2 timed out"
    
    # Submit answers - regular client first, then slow client
    p1_answer_confirmed = threading.Event()
    p2_answer_confirmed = threading.Event()
    round_complete = threading.Event()
    
    @player1.on('answer_confirmed')
    def on_p1_answer_confirmed(data):
        p1_answer_confirmed.set()
    
    @player2.on('answer_confirmed')
    def on_p2_answer_confirmed(data):
        p2_answer_confirmed.set()
    
    @player1.on('round_complete')
    def on_round_complete(data):
        round_complete.set()
    
    player1.emit('submit_answer', {
        'round_id': p1_round_data.get('round_id'),
        'item': p1_round_data.get('assigned_item'),
        'answer': True
    })
    
    assert p1_answer_confirmed.wait(timeout=2), "Answer confirmation for player 1 timed out"
    
    # Slow client submits answer with delay
    player2.emit('submit_answer', {
        'round_id': p2_round_data.get('round_id'),
        'item': p2_round_data.get('assigned_item'),
        'answer': False
    })
    
    assert p2_answer_confirmed.wait(timeout=5), "Answer confirmation for slow player 2 timed out"
    assert round_complete.wait(timeout=5), "Round complete notification timed out"
    
    # Clean up
    player1.disconnect()
    player2.disconnect()
    dashboard.disconnect()

def test_delayed_server_response(server_thread, reset_state):
    """Test client behavior with delayed server responses."""
    # This test simulates server delay by having multiple clients and operations
    # Create multiple clients to increase server load
    clients = []
    for i in range(5):
        client = socketio.Client()
        client.connect('http://127.0.0.1:5000')
        clients.append(client)
    
    # Create dashboard
    dashboard = socketio.Client()
    dashboard.connect('http://127.0.0.1:5000')
    dashboard.emit('register_dashboard')
    
    # Create teams with all clients simultaneously to increase server load
    team_created_events = []
    team_data_list = []
    
    for i, client in enumerate(clients):
        team_created = threading.Event()
        team_created_events.append(team_created)
        team_data = {}
        team_data_list.append(team_data)
        
        @client.on('team_created')
        def on_team_created(data, idx=i):
            team_data_list[idx].update(data)
            team_created_events[idx].set()
        
        client.emit('create_team', {'team_name': f'LoadTeam{i}'})
    
    # Wait for all teams to be created
    for i, event in enumerate(team_created_events):
        assert event.wait(timeout=5), f"Team creation {i} timed out under load"
        assert team_data_list[i].get('team_name') == f'LoadTeam{i}'
    
    # Clean up
    for client in clients:
        client.disconnect()
    dashboard.disconnect()

def test_connection_timeout_recovery(server_thread, reset_state):
    """Test recovery from connection timeout."""
    # Create client and team
    client = socketio.Client()
    client.connect('http://127.0.0.1:5000')
    
    team_created = threading.Event()
    team_data = {}
    
    @client.on('team_created')
    def on_team_created(data):
        team_data.update(data)
        team_created.set()
    
    client.emit('create_team', {'team_name': 'TimeoutTeam'})
    assert team_created.wait(timeout=2), "Team creation timed out"
    team_name = team_data.get('team_name')
    
    # Simulate connection timeout by disconnecting without proper leave
    client.disconnect()
    time.sleep(2)  # Wait longer than normal to simulate timeout
    
    # Reconnect and try to reactivate team
    new_client = socketio.Client()
    new_client.connect('http://127.0.0.1:5000')
    
    reactivated = threading.Event()
    reactivate_data = {}
    
    @new_client.on('team_created')
    def on_reactivated(data):
        reactivate_data.update(data)
        reactivated.set()
    
    new_client.emit('reactivate_team', {'team_name': team_name})
    assert reactivated.wait(timeout=2), "Team reactivation after timeout timed out"
    
    assert reactivate_data.get('team_name') == team_name
    
    # Clean up
    new_client.disconnect()

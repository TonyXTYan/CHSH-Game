import pytest
import threading
import time
import socketio
import concurrent.futures
import random

@pytest.fixture(scope="function")
def many_clients(server_thread, request):
    """Create many Socket.IO clients for stress testing."""
    num_clients = getattr(request, 'param', 10)  # Default to 10 clients if not specified
    clients = []
    
    for i in range(num_clients):
        client = socketio.Client()
        try:
            client.connect('http://127.0.0.1:8080')
            clients.append(client)
        except Exception as e:
            print(f"Failed to connect client {i}: {e}")
    
    yield clients
    
    # Clean up
    for client in clients:
        try:
            if client.connected:
                client.disconnect()
        except:
            pass

def test_many_concurrent_teams(many_clients, dashboard_client, reset_state):
    """Test creating many teams concurrently."""
    # Create teams with all clients
    team_created_events = []
    team_data_list = []
    
    for i, client in enumerate(many_clients):
        team_created = threading.Event()
        team_created_events.append(team_created)
        team_data = {}
        team_data_list.append(team_data)
        
        @client.on('team_created')
        def on_team_created(data, idx=i):
            team_data_list[idx].update(data)
            team_created_events[idx].set()
        
        client.emit('create_team', {'team_name': f'StressTeam{i}'})
    
    # Wait for all teams to be created
    success_count = 0
    for i, event in enumerate(team_created_events):
        if event.wait(timeout=5):
            success_count += 1
            assert team_data_list[i].get('team_name') == f'StressTeam{i}'
    
    # Verify most teams were created successfully
    assert success_count >= len(many_clients) * 0.8, f"Only {success_count} of {len(many_clients)} teams created successfully"

@pytest.mark.parametrize('many_clients', [50], indirect=True)
def test_fifty_concurrent_teams(many_clients, dashboard_client, reset_state):
    """Test creating 50 teams concurrently."""
    # Create teams with all clients
    team_created_events = []
    team_data_list = []
    
    for i, client in enumerate(many_clients):
        team_created = threading.Event()
        team_created_events.append(team_created)
        team_data = {}
        team_data_list.append(team_data)
        
        @client.on('team_created')
        def on_team_created(data, idx=i):
            team_data_list[idx].update(data)
            team_created_events[idx].set()
        
        client.emit('create_team', {'team_name': f'MediumStressTeam{i}'})
    
    # Wait for all teams to be created
    success_count = 0
    for i, event in enumerate(team_created_events):
        if event.wait(timeout=10):  # Longer timeout for more clients
            success_count += 1
    
    # Verify most teams were created successfully
    assert success_count >= len(many_clients) * 0.7, f"Only {success_count} of {len(many_clients)} teams created successfully"

def test_rapid_answer_submissions(server_thread, reset_state):
    """Test rapid answer submissions from multiple teams."""
    # Create dashboard
    dashboard = socketio.Client()
    dashboard.connect('http://127.0.0.1:8080')
    dashboard.emit('register_dashboard')
    time.sleep(0.5)
    
    # Create 5 teams with 2 players each
    teams = []
    for i in range(5):
        player1 = socketio.Client()
        player2 = socketio.Client()
        
        player1.connect('http://127.0.0.1:8080')
        player2.connect('http://127.0.0.1:8080')
        
        team_created = threading.Event()
        team_joined = threading.Event()
        team_data = {}
        team_name = f"RapidTeam{i}"
        
        @player1.on('team_created')
        def on_team_created(data):
            team_data.update(data)
            team_created.set()
        
        @player2.on('joined_team')
        def on_joined_team(data):
            team_joined.set()
        
        player1.emit('create_team', {'team_name': team_name})
        assert team_created.wait(timeout=2), f"Team {i} creation timed out"
        
        player2.emit('join_team', {'team_name': team_name})
        assert team_joined.wait(timeout=2), f"Team {i} joining timed out"
        
        teams.append((player1, player2, team_name, team_data.copy()))
    
    # Start game
    game_started = threading.Event()
    
    @teams[0][0].on('game_started')
    def on_game_started(data):
        game_started.set()
    
    dashboard.emit('start_game')
    assert game_started.wait(timeout=2), "Game start notification timed out"
    
    # Wait for all teams to receive rounds
    time.sleep(2)
    
    # Track rounds and answers for all teams
    round_data = [{}, {}, {}, {}, {}]  # One dict per team
    answer_confirmed = [threading.Event() for _ in range(10)]  # Two events per team (one per player)
    
    # Set up listeners for each team
    for i, (player1, player2, _, _) in enumerate(teams):
        @player1.on('new_round')
        def on_p1_round(data, idx=i):
            round_data[idx]['p1'] = data.copy()
        
        @player2.on('new_round')
        def on_p2_round(data, idx=i):
            round_data[idx]['p2'] = data.copy()
        
        @player1.on('answer_confirmed')
        def on_p1_answer_confirmed(data, idx=i):
            answer_confirmed[idx*2].set()
        
        @player2.on('answer_confirmed')
        def on_p2_answer_confirmed(data, idx=i):
            answer_confirmed[idx*2+1].set()
    
    # Wait a bit for all round data to be received
    time.sleep(2)
    
    # Submit answers rapidly from all players
    for i, (player1, player2, _, _) in enumerate(teams):
        if 'p1' in round_data[i] and 'p2' in round_data[i]:
            player1.emit('submit_answer', {
                'round_id': round_data[i]['p1'].get('round_id'),
                'item': round_data[i]['p1'].get('assigned_item'),
                'answer': random.choice([True, False])
            })
            
            player2.emit('submit_answer', {
                'round_id': round_data[i]['p2'].get('round_id'),
                'item': round_data[i]['p2'].get('assigned_item'),
                'answer': random.choice([True, False])
            })
    
    # Check how many answers were confirmed
    success_count = 0
    for i, event in enumerate(answer_confirmed):
        if event.wait(timeout=5):
            success_count += 1
    
    # Verify most answers were submitted successfully
    assert success_count >= 7, f"Only {success_count} of 10 answers submitted successfully"
    
    # Clean up
    dashboard.disconnect()
    for player1, player2, _, _ in teams:
        player1.disconnect()
        player2.disconnect()

def test_concurrent_game_actions(server_thread, reset_state):
    """Test concurrent game actions from multiple clients."""
    # Create dashboard
    dashboard = socketio.Client()
    dashboard.connect('http://127.0.0.1:8080')
    dashboard.emit('register_dashboard')
    time.sleep(0.5)
    
    # Create 3 teams with 2 players each
    teams = []
    for i in range(3):
        player1 = socketio.Client()
        player2 = socketio.Client()
        
        player1.connect('http://127.0.0.1:8080')
        player2.connect('http://127.0.0.1:8080')
        
        team_created = threading.Event()
        team_joined = threading.Event()
        team_data = {}
        team_name = f"ConcurrentTeam{i}"
        
        @player1.on('team_created')
        def on_team_created(data):
            team_data.update(data)
            team_created.set()
        
        @player2.on('joined_team')
        def on_joined_team(data):
            team_joined.set()
        
        player1.emit('create_team', {'team_name': team_name})
        assert team_created.wait(timeout=2), f"Team {i} creation timed out"
        
        player2.emit('join_team', {'team_name': team_name})
        assert team_joined.wait(timeout=2), f"Team {i} joining timed out"
        
        teams.append((player1, player2, team_name, team_data.copy()))
    
    # Start game
    game_started = threading.Event()
    
    @teams[0][0].on('game_started')
    def on_game_started(data):
        game_started.set()
    
    dashboard.emit('start_game')
    assert game_started.wait(timeout=2), "Game start notification timed out"
    
    # Wait for all teams to receive rounds
    time.sleep(2)
    
    # Perform multiple concurrent actions
    # 1. Dashboard pauses game
    # 2. Players submit answers
    # 3. Dashboard resumes game
    # 4. More players submit answers
    
    pause_event = threading.Event()
    resume_event = threading.Event()
    
    @teams[0][0].on('game_state_update')
    def on_game_state_update(data):
        if data.get('paused'):
            pause_event.set()
        else:
            resume_event.set()
    
    # Set up round data collection
    round_data = [{}, {}, {}]  # One dict per team
    answer_confirmed = [threading.Event() for _ in range(6)]  # Two events per team
    
    for i, (player1, player2, _, _) in enumerate(teams):
        @player1.on('new_round')
        def on_p1_round(data, idx=i):
            round_data[idx]['p1'] = data.copy()
        
        @player2.on('new_round')
        def on_p2_round(data, idx=i):
            round_data[idx]['p2'] = data.copy()
        
        @player1.on('answer_confirmed')
        def on_p1_answer_confirmed(data, idx=i):
            answer_confirmed[idx*2].set()
        
        @player2.on('answer_confirmed')
        def on_p2_answer_confirmed(data, idx=i):
            answer_confirmed[idx*2+1].set()
    
    # Wait for round data
    time.sleep(1)
    
    # Execute concurrent actions
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        # Pause game
        executor.submit(dashboard.emit, 'pause_game')
        
        # Submit answers from first team during pause transition
        if 'p1' in round_data[0] and 'p2' in round_data[0]:
            executor.submit(teams[0][0].emit, 'submit_answer', {
                'round_id': round_data[0]['p1'].get('round_id'),
                'item': round_data[0]['p1'].get('assigned_item'),
                'answer': True
            })
            
            executor.submit(teams[0][1].emit, 'submit_answer', {
                'round_id': round_data[0]['p2'].get('round_id'),
                'item': round_data[0]['p2'].get('assigned_item'),
                'answer': False
            })
        
        # Wait for pause to take effect
        assert pause_event.wait(timeout=3), "Game pause notification timed out"
        
        # Resume game
        executor.submit(dashboard.emit, 'pause_game')  # Toggle pause state
        
        # Submit answers from other teams after resume
        for i in range(1, 3):
            if 'p1' in round_data[i] and 'p2' in round_data[i]:
                executor.submit(teams[i][0].emit, 'submit_answer', {
                    'round_id': round_data[i]['p1'].get('round_id'),
                    'item': round_data[i]['p1'].get('assigned_item'),
                    'answer': random.choice([True, False])
                })
                
                executor.submit(teams[i][1].emit, 'submit_answer', {
                    'round_id': round_data[i]['p2'].get('round_id'),
                    'item': round_data[i]['p2'].get('assigned_item'),
                    'answer': random.choice([True, False])
                })
    
    # Wait for resume to take effect
    assert resume_event.wait(timeout=3), "Game resume notification timed out"
    
    # Check how many answers were confirmed
    success_count = 0
    for i, event in enumerate(answer_confirmed):
        if event.wait(timeout=5):
            success_count += 1
    
    # Verify some answers were submitted successfully
    # We don't expect all to succeed due to pausing/resuming and potential race conditions
    assert success_count > 0, "No answers were submitted successfully"
    
    # Clean up
    dashboard.disconnect()
    for player1, player2, _, _ in teams:
        player1.disconnect()
        player2.disconnect()

@pytest.mark.skip(reason="This test is resource-intensive and should be run separately")
@pytest.mark.parametrize('many_clients', [100], indirect=True)
def test_hundred_concurrent_players(many_clients, dashboard_client, reset_state):
    """Test with 100 concurrent players (50 teams)."""
    # This test is marked as skipped by default due to resource constraints
    # It can be run explicitly when needed
    
    # Create 50 teams with 2 players each
    teams = []
    for i in range(0, len(many_clients), 2):
        if i+1 >= len(many_clients):
            break  # Skip if we don't have a pair
            
        player1 = many_clients[i]
        player2 = many_clients[i+1]
        
        team_created = threading.Event()
        team_joined = threading.Event()
        team_data = {}
        team_name = f"MassiveTeam{i//2}"
        
        @player1.on('team_created')
        def on_team_created(data):
            team_data.update(data)
            team_created.set()
        
        @player2.on('joined_team')
        def on_joined_team(data):
            team_joined.set()
        
        player1.emit('create_team', {'team_name': team_name})
        if team_created.wait(timeout=5):  # Longer timeout for stress test
            player2.emit('join_team', {'team_name': team_name})
            if team_joined.wait(timeout=5):
                teams.append((player1, player2, team_name))
    
    # Verify we have at least some teams
    assert len(teams) > 0, "Failed to create any teams"
    print(f"Successfully created {len(teams)} teams")
    
    # Start game
    game_started = threading.Event()
    
    @teams[0][0].on('game_started')
    def on_game_started(data):
        game_started.set()
    
    dashboard_client.emit('start_game')
    assert game_started.wait(timeout=5), "Game start notification timed out"
    
    # Wait for rounds to be distributed
    time.sleep(5)
    
    # Let the game run for a while to observe server behavior
    time.sleep(10)
    
    # Success if we got this far without crashes
    assert True

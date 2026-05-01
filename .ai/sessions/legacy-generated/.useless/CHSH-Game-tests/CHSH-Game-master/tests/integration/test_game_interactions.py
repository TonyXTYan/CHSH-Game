import pytest
import threading
import time
import socketio

def test_start_game(complete_team, dashboard_client, reset_state):
    """Test starting a game from the dashboard."""
    player1, player2, team_name, _ = complete_team
    
    # Events for tracking responses
    game_started = threading.Event()
    game_state_changed = threading.Event()
    new_round_received = threading.Event()
    game_data = {}
    round_data = {}
    
    @player1.on('game_started')
    def on_game_started(data):
        game_data.update(data)
        game_started.set()
    
    @dashboard_client.on('game_state_changed')
    def on_game_state_changed(data):
        game_state_changed.set()
    
    @player1.on('new_round')
    def on_new_round(data):
        round_data.update(data)
        new_round_received.set()
    
    # Start the game from dashboard
    dashboard_client.emit('start_game')
    
    assert game_started.wait(timeout=2), "Game start notification timed out"
    assert game_state_changed.wait(timeout=2), "Game state change notification timed out"
    assert new_round_received.wait(timeout=2), "New round notification timed out"
    
    assert game_data.get('message') is not None
    assert round_data.get('round_number') == 1
    assert 'assigned_item' in round_data

def test_submit_answer(complete_team, dashboard_client, reset_state):
    """Test submitting answers during a game."""
    player1, player2, team_name, _ = complete_team
    
    # Start the game
    game_started = threading.Event()
    new_round_received = [threading.Event(), threading.Event()]
    round_data = [{}, {}]
    
    @player1.on('game_started')
    @player2.on('game_started')
    def on_game_started(data):
        game_started.set()
    
    @player1.on('new_round')
    def on_new_round_p1(data):
        round_data[0].update(data)
        new_round_received[0].set()
    
    @player2.on('new_round')
    def on_new_round_p2(data):
        round_data[1].update(data)
        new_round_received[1].set()
    
    dashboard_client.emit('start_game')
    assert game_started.wait(timeout=2), "Game start notification timed out"
    assert new_round_received[0].wait(timeout=2), "New round notification for player 1 timed out"
    assert new_round_received[1].wait(timeout=2), "New round notification for player 2 timed out"
    
    # Submit answers
    answer_confirmed = [threading.Event(), threading.Event()]
    round_complete = threading.Event()
    next_round_received = [threading.Event(), threading.Event()]
    next_round_data = [{}, {}]
    
    @player1.on('answer_confirmed')
    def on_answer_confirmed_p1(data):
        answer_confirmed[0].set()
    
    @player2.on('answer_confirmed')
    def on_answer_confirmed_p2(data):
        answer_confirmed[1].set()
    
    @player1.on('round_complete')
    @player2.on('round_complete')
    def on_round_complete(data):
        round_complete.set()
    
    @player1.on('new_round')
    def on_next_round_p1(data):
        if data.get('round_number') == 2:
            next_round_data[0].update(data)
            next_round_received[0].set()
    
    @player2.on('new_round')
    def on_next_round_p2(data):
        if data.get('round_number') == 2:
            next_round_data[1].update(data)
            next_round_received[1].set()
    
    # Submit answers for both players
    player1.emit('submit_answer', {
        'round_id': round_data[0].get('round_id'),
        'item': round_data[0].get('assigned_item'),
        'answer': True
    })
    
    player2.emit('submit_answer', {
        'round_id': round_data[1].get('round_id'),
        'item': round_data[1].get('assigned_item'),
        'answer': False
    })
    
    assert answer_confirmed[0].wait(timeout=2), "Answer confirmation for player 1 timed out"
    assert answer_confirmed[1].wait(timeout=2), "Answer confirmation for player 2 timed out"
    assert round_complete.wait(timeout=2), "Round complete notification timed out"
    assert next_round_received[0].wait(timeout=2), "Next round notification for player 1 timed out"
    assert next_round_received[1].wait(timeout=2), "Next round notification for player 2 timed out"
    
    assert next_round_data[0].get('round_number') == 2
    assert next_round_data[1].get('round_number') == 2

def test_pause_game(complete_team, dashboard_client, reset_state):
    """Test pausing and resuming a game from the dashboard."""
    player1, player2, team_name, _ = complete_team
    
    # Start the game
    game_started = threading.Event()
    
    @player1.on('game_started')
    def on_game_started(data):
        game_started.set()
    
    dashboard_client.emit('start_game')
    assert game_started.wait(timeout=2), "Game start notification timed out"
    
    # Pause the game
    game_paused = threading.Event()
    game_state_update = {}
    
    @player1.on('game_state_update')
    def on_game_state_update(data):
        game_state_update.update(data)
        game_paused.set()
    
    dashboard_client.emit('pause_game')
    assert game_paused.wait(timeout=2), "Game pause notification timed out"
    assert game_state_update.get('paused') is True
    
    # Resume the game
    game_resumed = threading.Event()
    game_resume_update = {}
    
    @player1.on('game_state_update')
    def on_game_resumed(data):
        game_resume_update.update(data)
        game_resumed.set()
    
    dashboard_client.emit('pause_game')  # Toggle pause state
    assert game_resumed.wait(timeout=2), "Game resume notification timed out"
    assert game_resume_update.get('paused') is False

def test_restart_game(complete_team, dashboard_client, reset_state):
    """Test restarting a game from the dashboard."""
    player1, player2, team_name, _ = complete_team
    
    # Start the game
    game_started = threading.Event()
    
    @player1.on('game_started')
    def on_game_started(data):
        game_started.set()
    
    dashboard_client.emit('start_game')
    assert game_started.wait(timeout=2), "Game start notification timed out"
    
    # Restart the game
    game_reset = threading.Event()
    game_state_changed = threading.Event()
    game_reset_complete = threading.Event()
    
    @player1.on('game_reset')
    def on_game_reset(data):
        game_reset.set()
    
    @dashboard_client.on('game_state_changed')
    def on_game_state_changed(data):
        game_state_changed.set()
    
    @dashboard_client.on('game_reset_complete')
    def on_game_reset_complete(data):
        game_reset_complete.set()
    
    dashboard_client.emit('restart_game')
    
    assert game_reset.wait(timeout=2), "Game reset notification timed out"
    assert game_state_changed.wait(timeout=2), "Game state change notification timed out"
    assert game_reset_complete.wait(timeout=2), "Game reset complete notification timed out"

def test_invalid_answer_submission(complete_team, dashboard_client, reset_state):
    """Test submitting invalid answers during a game."""
    player1, player2, team_name, _ = complete_team
    
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
    
    # Submit invalid answer (wrong round_id)
    error_received = threading.Event()
    error_data = {}
    
    @player1.on('error')
    def on_error(data):
        error_data.update(data)
        error_received.set()
    
    player1.emit('submit_answer', {
        'round_id': 9999,  # Invalid round ID
        'item': round_data.get('assigned_item'),
        'answer': True
    })
    
    assert error_received.wait(timeout=2), "Error notification timed out"
    assert 'invalid' in error_data.get('message', '').lower()
    
    # Submit duplicate answer
    error_received.clear()
    error_data.clear()
    
    # First submit a valid answer
    answer_confirmed = threading.Event()
    
    @player1.on('answer_confirmed')
    def on_answer_confirmed(data):
        answer_confirmed.set()
    
    player1.emit('submit_answer', {
        'round_id': round_data.get('round_id'),
        'item': round_data.get('assigned_item'),
        'answer': True
    })
    
    assert answer_confirmed.wait(timeout=2), "Answer confirmation timed out"
    
    # Then try to submit again
    player1.emit('submit_answer', {
        'round_id': round_data.get('round_id'),
        'item': round_data.get('assigned_item'),
        'answer': False
    })
    
    assert error_received.wait(timeout=2), "Error notification for duplicate answer timed out"
    assert 'already answered' in error_data.get('message', '').lower()

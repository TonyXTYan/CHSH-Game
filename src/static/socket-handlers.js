// Socket event handlers
function initializeSocketHandlers(socket, callbacks) {
    let heartbeatInterval = null;
    let serverInstance = null;
    
    // Start heartbeat system
    function startHeartbeat(interval = 10000) { // Default 10 seconds
        if (heartbeatInterval) {
            clearInterval(heartbeatInterval);
        }
        
        heartbeatInterval = setInterval(() => {
            socket.emit('heartbeat');
        }, interval);
    }
    
    // Stop heartbeat system
    function stopHeartbeat() {
        if (heartbeatInterval) {
            clearInterval(heartbeatInterval);
            heartbeatInterval = null;
        }
    }
    
    socket.on('connect', () => {
        callbacks.updateConnectionStatus('Connected to server!');
        callbacks.sessionId = socket.id;
        callbacks.updateSessionInfo(socket.id);
        callbacks.showStatus('Connected to server!', 'success');
        
        // Request state sync on every connection
        socket.emit('sync_request');
    });

    socket.on('disconnect', () => {
        stopHeartbeat();
        callbacks.updateConnectionStatus('Disconnected from server');
        // Call resetToInitialView to clear state and show appropriate message
        if (typeof callbacks.resetToInitialView === 'function') {
            callbacks.resetToInitialView();
        } else {
            callbacks.showStatus('Disconnected, try refreshing the page.', 'error');
        }
    });

    socket.on('server_shutdown', () => {
        callbacks.updateConnectionStatus('Server is shutting down');
        callbacks.showStatus('Server is shutting down. Please wait for restart...', 'error');
        // Clear game state and UI
        if (typeof callbacks.onGameReset === 'function') {
            callbacks.onGameReset();
        }
        // Reset all controls
        if (typeof callbacks.resetGameControls === 'function') {
            callbacks.resetGameControls();
        }
    });

    socket.on('reconnecting', () => {
        callbacks.updateConnectionStatus('Reconnecting...');
        callbacks.showStatus('Reconnecting to server...', 'warning');
    });

    socket.on('reconnect', () => {
        callbacks.updateConnectionStatus('Connected to server!');
        callbacks.showStatus('Reconnected to server! Please create or join a team.', 'success');
        // No longer trying to restore session, player starts fresh.
    });

    socket.on('connection_established', (data) => {
        console.log('Connection established with game state:', data);
        
        // Start heartbeat if interval provided
        if (data.heartbeat_interval) {
            startHeartbeat(data.heartbeat_interval * 1000); // Convert to milliseconds
        }
        
        // Track server instance for disconnect detection
        if (data.server_instance && serverInstance && serverInstance !== data.server_instance) {
            callbacks.showStatus('Server restarted, reconnecting...', 'warning');
        }
        serverInstance = data.server_instance;
        
        if (callbacks.onConnectionEstablished) {
            callbacks.onConnectionEstablished(data);
        } else {
            // Fallback to direct calls if callback not available
            callbacks.updateGameState(data.game_started);
            callbacks.updateTeamsList(data.available_teams);
        }
    });
    
    // Heartbeat acknowledgment
    socket.on('heartbeat_ack', () => {
        // Optional: Could update connection quality indicator here
    });
    
    // State synchronization response
    socket.on('state_sync', (data) => {
        console.log('Received state sync:', data);
        
        // Update game state
        if (data.game_started !== undefined) {
            callbacks.updateGameState(data.game_started);
        }
        
        // Update game mode if provided
        if (data.game_mode && callbacks.onGameModeChanged) {
            callbacks.onGameModeChanged({ mode: data.game_mode });
        }
        
        // Update teams list
        if (data.available_teams) {
            callbacks.updateTeamsList(data.available_teams);
        }
        
        // Restore team state if client was in a team
        if (data.team_status) {
            const teamData = data.team_status;
            if (callbacks.onTeamJoined) {
                // Simulate team join to restore UI state
                callbacks.onTeamJoined({
                    team_name: teamData.team_name,
                    message: 'Reconnected to team',
                    game_started: data.game_started,
                    team_status: teamData.status,
                    is_reconnection: true
                });
            }
        }
    });

    socket.on('error', (data) => {
        callbacks.showStatus(data.message, 'error');
    });

    socket.on('team_created', (data) => {
        callbacks.onTeamCreated(data);
    });

    socket.on('team_joined', (data) => {
        callbacks.onTeamJoined(data);
    });

    socket.on('player_joined', (data) => {
        callbacks.onPlayerJoined(data);
    });

    socket.on('team_status_update', (data) => {
        callbacks.onTeamStatusUpdate(data);
    });

    socket.on('teams_updated', (data) => {
        console.log('Teams updated:', data);
        callbacks.updateGameState(data.game_started);
        callbacks.updateTeamsList(data.teams);
    });

    socket.on('game_start', (data) => {
        console.log('Game started:', data);
        callbacks.onGameStart();
    });

    socket.on('game_state_changed', (data) => {
        console.log('Game state changed:', data);
        callbacks.updateGameState(data.game_started);
    });

    socket.on('game_state_update', (data) => {
        console.log('Game state update:', data);
        if (data.hasOwnProperty('paused')) {
            if (data.paused) {
                callbacks.showStatus('Game is paused', 'warning');
                // Disable answer buttons when game is paused
                if (typeof callbacks.setAnswerButtonsEnabled === 'function') {
                    callbacks.setAnswerButtonsEnabled(false);
                }
            } else {
                // Get current round info from app.js
                if (typeof callbacks.getCurrentRoundInfo === 'function') {
                    const roundInfo = callbacks.getCurrentRoundInfo();
                    if (roundInfo) {
                        callbacks.showStatus(`Game resumed, current round is: ${roundInfo.round_number}`, 'success');
                    } else {
                        callbacks.showStatus('Game resumed', 'success');
                    }
                }
                // Re-enable answer buttons when game is resumed
                if (typeof callbacks.setAnswerButtonsEnabled === 'function') {
                    callbacks.setAnswerButtonsEnabled(true);
                }
            }
        }
    });

    socket.on('new_question', (data) => {
        callbacks.onNewQuestion(data);
    });

    socket.on('answer_confirmed', (data) => {
        callbacks.onAnswerConfirmed(data);
    });

    socket.on('round_complete', (data) => {
        callbacks.showStatus(`Round ${data.round_number} complete! Next round coming up...`, 'success');
    });

    socket.on('player_left', (data) => {
        callbacks.showStatus(data.message, 'warning');
    });

    socket.on('team_disbanded', (data) => {
        callbacks.onTeamDisbanded(data);
    });

    socket.on('left_team_success', (data) => {
        callbacks.onLeftTeam(data);
    });

    socket.on('game_reset', () => {
        // Reset client-side state
        callbacks.showStatus('Game has been reset. Ready to start new game.', 'info');
        
        // Reset round and answer display
        if (typeof callbacks.onAnswerConfirmed === 'function') {
            callbacks.onAnswerConfirmed({ message: '' });
        }
        if (typeof callbacks.resetRoundDisplay === 'function') {
            callbacks.resetRoundDisplay();
        }
        
        // Clear game state and re-enable controls
        if (typeof callbacks.updateGameState === 'function') {
            callbacks.updateGameState(false, true); // Added true to indicate this is a reset
        }
        
        // Clear game UI elements and ensure controls are enabled
        if (typeof callbacks.onGameReset === 'function') {
            callbacks.onGameReset();
        }

        // Ensure all game controls are re-enabled
        if (typeof callbacks.resetGameControls === 'function') {
            callbacks.resetGameControls();
        }
    });

    // Handle team reactivation response
    socket.on('team_reactivated', (data) => {
        if (data.success) {
            if (callbacks.onTeamCreated) {
                callbacks.onTeamCreated(data);
            }
            if (callbacks.showStatus) {
                callbacks.showStatus(data.message, 'success');
            }
        } else {
            if (callbacks.showStatus) {
                callbacks.showStatus(data.message || 'Failed to reactivate team', 'error');
            }
        }
    });

    // Handle game mode changes
    socket.on('game_mode_changed', (data) => {
        console.log('Game mode changed:', data);
        if (callbacks.onGameModeChanged) {
            callbacks.onGameModeChanged(data);
        }
    });
}

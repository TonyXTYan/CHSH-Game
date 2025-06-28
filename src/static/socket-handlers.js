// Socket event handlers
function initializeSocketHandlers(socket, callbacks) {
    socket.on('connect', () => {
        callbacks.updateConnectionStatus('Connected to server!');
        callbacks.sessionId = socket.id;
        callbacks.updateSessionInfo(socket.id);
        callbacks.showStatus('Connected to server!', 'success');
    });

    socket.on('disconnect', () => {
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
        if (callbacks.onConnectionEstablished) {
            callbacks.onConnectionEstablished(data);
        } else {
            // Fallback to direct calls if callback not available
            callbacks.updateGameState(data.game_started);
            callbacks.updateTeamsList(data.available_teams);
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
        
        // Store previous round data for display in waiting message
        if (data.previous_round) {
            callbacks.onRoundComplete(data);
        }
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

    // Handle game theme changes
    socket.on('game_theme_changed', (data) => {
        console.log('Game theme changed:', data);
        if (callbacks.onGameThemeChanged) {
            callbacks.onGameThemeChanged(data);
        }
    });

    // Handle complete game state sync
    socket.on('game_state_sync', (data) => {
        console.log('Game state sync:', data);
        if (callbacks.onGameStateSync) {
            callbacks.onGameStateSync(data);
        }
    });
}

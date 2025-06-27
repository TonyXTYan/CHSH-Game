// Socket event handlers with improved connection stability
function initializeSocketHandlers(socket, callbacks) {
    // Store connection state for stability
    let connectionStable = false;
    let reconnectionAttempts = 0;
    let maxReconnectionAttempts = 10;
    let reconnectionToken = null;
    
    // Store team info for reconnection
    let lastTeamInfo = null;
    
    socket.on('connect', () => {
        reconnectionAttempts = 0;
        callbacks.updateConnectionStatus('Connected to server!');
        callbacks.sessionId = socket.id;
        callbacks.updateSessionInfo(socket.id);
        callbacks.showStatus('Connected to server!', 'success');
        
        // If we have a reconnection token, try to use it
        if (reconnectionToken && lastTeamInfo) {
            setTimeout(() => {
                socket.emit('reconnect_with_token', { token: reconnectionToken });
            }, 1000); // Small delay to ensure server is ready
        }
    });

    socket.on('disconnect', (reason) => {
        connectionStable = false;
        callbacks.updateConnectionStatus('Disconnected from server');
        
        // Different handling based on disconnect reason
        if (reason === 'io server disconnect') {
            // Server initiated disconnect - likely deliberate
            callbacks.showStatus('Server disconnected the connection. Please refresh.', 'error');
        } else if (reason === 'transport close' || reason === 'transport error') {
            // Network issues - try to reconnect gracefully
            callbacks.showStatus('Connection lost. Attempting to reconnect...', 'warning');
        } else {
            // Other reasons - generic handling
            callbacks.showStatus('Disconnected from server. Reconnecting...', 'warning');
        }
        
        // Don't immediately reset view - wait for reconnection attempts
        setTimeout(() => {
            if (!socket.connected && typeof callbacks.resetToInitialView === 'function') {
                callbacks.resetToInitialView();
            }
        }, 10000); // Wait 10 seconds before resetting view
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
        // Clear reconnection data
        reconnectionToken = null;
        lastTeamInfo = null;
    });

    socket.on('reconnecting', (attempt) => {
        reconnectionAttempts = attempt;
        callbacks.updateConnectionStatus(`Reconnecting... (attempt ${attempt}/${maxReconnectionAttempts})`);
        
        if (attempt <= 3) {
            callbacks.showStatus('Reconnecting to server...', 'warning');
        } else if (attempt <= 7) {
            callbacks.showStatus('Connection issues detected. Still trying to reconnect...', 'warning');
        } else {
            callbacks.showStatus('Having trouble reconnecting. Please check your connection.', 'error');
        }
    });

    socket.on('reconnect', (attempt) => {
        callbacks.updateConnectionStatus('Connected to server!');
        callbacks.showStatus(`Reconnected after ${attempt} attempts!`, 'success');
        reconnectionAttempts = 0;
    });

    socket.on('reconnect_failed', () => {
        callbacks.updateConnectionStatus('Reconnection failed');
        callbacks.showStatus('Could not reconnect to server. Please refresh the page.', 'error');
        if (typeof callbacks.resetToInitialView === 'function') {
            callbacks.resetToInitialView();
        }
        // Clear reconnection data
        reconnectionToken = null;
        lastTeamInfo = null;
    });

    socket.on('connection_established', (data) => {
        console.log('Connection established with game state:', data);
        connectionStable = data.connection_stable !== false;
        
        if (callbacks.onConnectionEstablished) {
            callbacks.onConnectionEstablished(data);
        } else {
            // Fallback to direct calls if callback not available
            callbacks.updateGameState(data.game_started);
            callbacks.updateTeamsList(data.available_teams);
        }
        
        // Show connection stability status if needed
        if (!connectionStable) {
            callbacks.showStatus('Connection established but server may be under load.', 'warning');
        }
    });

    socket.on('error', (data) => {
        callbacks.showStatus(data.message, 'error');
        
        // If reconnection failed, clear token
        if (data.message.includes('reconnection') || data.message.includes('token')) {
            reconnectionToken = null;
            lastTeamInfo = null;
        }
    });

    socket.on('team_created', (data) => {
        // Store team info for potential reconnection
        lastTeamInfo = {
            team_name: data.team_name,
            player_slot: data.player_slot
        };
        callbacks.onTeamCreated(data);
    });

    socket.on('team_joined', (data) => {
        // Store team info for potential reconnection
        lastTeamInfo = {
            team_name: data.team_name,
            player_slot: data.player_slot,
            is_reconnection: data.is_reconnection
        };
        
        // If this was a successful reconnection, clear the token
        if (data.is_reconnection) {
            reconnectionToken = null;
        }
        
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
        // Clear team info when leaving team
        lastTeamInfo = null;
        reconnectionToken = null;
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
    
    // Add utility functions for connection management
    window.socketConnectionUtils = {
        isConnectionStable: () => connectionStable,
        getReconnectionAttempts: () => reconnectionAttempts,
        hasTeamInfo: () => lastTeamInfo !== null,
        getTeamInfo: () => lastTeamInfo,
        forceReconnect: () => {
            if (socket && !socket.connected) {
                socket.connect();
            }
        },
        clearReconnectionData: () => {
            reconnectionToken = null;
            lastTeamInfo = null;
        }
    };
}

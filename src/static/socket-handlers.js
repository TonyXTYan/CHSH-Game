// Socket event handlers
function initializeSocketHandlers(socket, callbacks) {
    socket.on('connect', () => {
        callbacks.updateConnectionStatus('Connected to server!');
        callbacks.sessionId = socket.id;
        callbacks.updateSessionInfo('Session ID: ' + socket.id);
        
        // If not restoring session, show ready status
        if (!callbacks.tryRestoreSession()) {
            callbacks.showStatus('Connected to server!', 'success');
        }
    });

    socket.on('disconnect', () => {
        callbacks.updateConnectionStatus('Disconnected from server');
        callbacks.showStatus('Disconnected from server. Attempting to reconnect...', 'error');
    });

    socket.on('reconnecting', () => {
        callbacks.updateConnectionStatus('Reconnecting...');
        callbacks.showStatus('Reconnecting to server...', 'warning');
    });

    socket.on('reconnect', () => {
        callbacks.updateConnectionStatus('Connected to server!');
        callbacks.showStatus('Reconnected to server!', 'success');
        callbacks.tryRestoreSession();
    });

    socket.on('connection_established', (data) => {
        console.log('Connection established with game state:', data);
        callbacks.updateGameState(data.game_started);
        callbacks.updateTeamsList(data.available_teams);
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

    socket.on('partner_joined', (data) => {
        callbacks.onPartnerJoined(data);
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

    socket.on('new_question', (data) => {
        callbacks.onNewQuestion(data);
    });

    socket.on('answer_confirmed', (data) => {
        callbacks.onAnswerConfirmed(data);
    });

    socket.on('round_complete', (data) => {
        callbacks.showStatus(`Round ${data.round_number} complete! Next round coming up...`, 'success');
    });

    socket.on('partner_left', (data) => {
        callbacks.showStatus(data.message, 'warning');
    });

    socket.on('team_disbanded', (data) => {
        callbacks.onTeamDisbanded(data);
    });

    socket.on('left_team_success', (data) => {
        callbacks.onLeftTeam(data);
    });

    socket.on('partner_reconnected', (data) => {
        callbacks.showStatus(data.message, 'success');
    });

    socket.on('rejoin_team_success', (data) => {
        callbacks.onRejoinTeamSuccess(data);
    });

    socket.on('rejoin_team_failed', (data) => {
        callbacks.onRejoinTeamFailed(data);
    });

    socket.on('game_reset', () => {
        // Reset client-side state
        callbacks.showStatus('Game has been reset. Ready to start new game.', 'info');
        
        // Clear answer display if it exists
        if (typeof callbacks.onAnswerConfirmed === 'function') {
            callbacks.onAnswerConfirmed({ message: '' });
        }
        
        // Reset round display
        if (typeof callbacks.resetRoundDisplay === 'function') {
            callbacks.resetRoundDisplay();
        }
        
        // Reset game state
        if (typeof callbacks.updateGameState === 'function') {
            callbacks.updateGameState(false);
        }
        
        // Clear any ongoing game UI elements
        if (typeof callbacks.onGameReset === 'function') {
            callbacks.onGameReset();
        }
    });
    
    socket.on('game_state_changed', (data) => {
        // Update game state only if callback exists
        if (typeof callbacks.updateGameState === 'function') {
            callbacks.updateGameState(data.game_started);
        }
        // Show appropriate status message
        callbacks.showStatus(
            data.game_started ? 'Game has started!' : 'Game has been stopped.',
            'info'
        );
    });
}

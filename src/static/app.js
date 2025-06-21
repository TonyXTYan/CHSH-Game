// Application state
let currentTeam = null;
let isCreator = false;
let currentRound = null;
let gameStarted = false;
let gamePaused = false;
let lastClickedButton = null;
let sessionId = null;
let teamId = null;

// DOM elements
const statusMessage = document.getElementById('statusMessage');
const teamSection = document.getElementById('teamSection');
const questionSection = document.getElementById('questionSection');
const teamNameInput = document.getElementById('teamNameInput');
const createTeamBtn = document.getElementById('createTeamBtn');
const availableTeams = document.getElementById('availableTeams');
const inactiveTeams = document.getElementById('inactiveTeams');
const gameHeader = document.getElementById('gameHeader');
const questionItem = document.getElementById('questionItem');
const trueBtn = document.getElementById('trueBtn');
const falseBtn = document.getElementById('falseBtn');
const waitingMessage = document.getElementById('waitingMessage');
const sessionInfo = document.getElementById('sessionInfo');
const connectionStatus = document.getElementById('connectionStatus');

// Connection status handling
function updateConnectionStatus(status) {
    connectionStatus.textContent = status;
    connectionStatus.className = 'connection-status';
    
    switch(status) {
        case 'Connected to server!':
            connectionStatus.classList.add('connected');
            break;
        case 'Disconnected from server':
            connectionStatus.classList.add('disconnected');
            break;
        case 'Reconnecting...':
            connectionStatus.classList.add('reconnecting');
            break;
    }
}

// Show status message with appropriate styling
function showStatus(message, type = 'info') {
    statusMessage.textContent = message;
    statusMessage.className = 'status-message ' + type;

    // Add visual feedback for success, error, or warning
    if (type === 'success') {
        statusMessage.style.border = '2px solid #4CAF50';
    } else if (type === 'error') {
        statusMessage.style.border = '2px solid #F44336';
    } else if (type === 'warning') {
        statusMessage.style.border = '2px solid #FFC107';
    } else {
        statusMessage.style.border = '2px solid #1565C0';
    }
}

// Function to reset UI to initial state
function resetToInitialView() {
    currentTeam = null;
    isCreator = false;
    currentRound = null;
    teamId = null;
    localStorage.removeItem('quizSessionData');
    gameHeader.textContent = 'CHSH Game';
    updateGameState(); // This will show team creation/joining
    showStatus('Disconnected, try refreshing the page.', 'info');
}

// Update UI based on game state
function updateGameState(newGameStarted = null, isReset = false) {
    if (newGameStarted !== null) {
        gameStarted = newGameStarted;
        if (!newGameStarted) {
            gamePaused = false; // Reset pause state when game stops
        }
    }

    if (isReset) {
        // Ensure all controls are in their initial state after reset
        currentRound = null;
        lastClickedButton = null;  // Reset on game reset
        trueBtn.disabled = false;
        falseBtn.disabled = false;
        waitingMessage.classList.remove('visible');
        questionItem.textContent = '';
    }

    if (!currentTeam) {
        teamSection.style.display = 'block';
        questionSection.style.display = 'none';
        return;
    }
    
    if (gameStarted && currentRound) {
        // Show question section
        teamSection.style.display = 'none';
        questionSection.style.display = 'block';
        questionItem.textContent = currentRound.item;
        
        // If already answered this round
        if (currentRound.alreadyAnswered) {
            trueBtn.disabled = true;
            falseBtn.disabled = true;
            waitingMessage.classList.add('visible');
        } else {
            trueBtn.disabled = gamePaused;
            falseBtn.disabled = gamePaused;
            waitingMessage.classList.remove('visible');
            if (gamePaused) {
                waitingMessage.textContent = "Game is paused";
                waitingMessage.classList.add('visible');
            } else {
                waitingMessage.textContent = "Waiting for next round...";
            }
        }
    } else if (gameStarted) {
        // Game started but waiting for first question
        teamSection.style.display = 'none';
        questionSection.style.display = 'block';
        questionItem.textContent = "...";
        trueBtn.disabled = true;
        falseBtn.disabled = true;
        waitingMessage.classList.remove('visible');
    } else {
        // In team but game not started
        teamSection.style.display = 'block';
        questionSection.style.display = 'none';
        // Ensure controls are enabled when not in game
        trueBtn.disabled = false;
        falseBtn.disabled = false;
    }
}

// Reset all game controls to their initial state
function resetGameControls() {
    trueBtn.disabled = false;
    falseBtn.disabled = false;
    waitingMessage.classList.remove('visible');
    questionItem.textContent = '';
    currentRound = null;
}

// Update available teams list
function updateTeamsList(teams) {
    if (!teams || teams.length === 0) {
        availableTeams.innerHTML = '<div class="team-item">No active teams available to join currently. Create one or wait!</div>';
        inactiveTeams.innerHTML = '<div class="team-item inactive">No inactive teams available. Reactivate a team to join!';
        return;
    }

    // Add visual feedback for empty lists
    if (teams.length === 0) {
        availableTeams.style.border = '2px dashed #FFC107';
        inactiveTeams.style.border = '2px dashed #FFC107';
    } else {
        availableTeams.style.border = 'none';
        inactiveTeams.style.border = 'none';
    }
    
    // Split teams into active and inactive
    const activeTeamsList = teams.filter(team => team.is_active);
    const inactiveTeamsList = teams.filter(team => !team.is_active);
    
    // Update active teams
    if (activeTeamsList.length === 0) {
        availableTeams.innerHTML = '<div class="team-item">No active teams available to join currently.</div>';
    } else {
        availableTeams.innerHTML = '';
        activeTeamsList.forEach(team => {
            const teamElement = document.createElement('div');
            teamElement.className = 'team-item';
            
            const nameSpan = document.createElement('span');
            nameSpan.textContent = team.team_name;
            
            const joinButton = document.createElement('button');
            joinButton.className = 'join-btn';
            joinButton.textContent = 'Join Team';
            joinButton.onclick = (e) => {
                e.stopPropagation();
                joinTeam(team.team_name);
            };
            
            teamElement.appendChild(nameSpan);
            teamElement.appendChild(joinButton);
            availableTeams.appendChild(teamElement);
        });
    }
    
    // Update inactive teams
    if (inactiveTeamsList.length === 0) {
        inactiveTeams.innerHTML = '<div class="team-item inactive">No inactive teams available.</div>';
    } else {
        inactiveTeams.innerHTML = '';
        inactiveTeamsList.forEach(team => {
            const teamElement = document.createElement('div');
            teamElement.className = 'team-item inactive';
            
            const nameSpan = document.createElement('span');
            nameSpan.textContent = team.team_name;
            
            const reactivateButton = document.createElement('button');
            reactivateButton.className = 'reactivate-btn';
            reactivateButton.textContent = 'Reactivate & Join';
            reactivateButton.onclick = (e) => {
                e.stopPropagation();
                reactivateTeam(team.team_name);
            };
            
            teamElement.appendChild(nameSpan);
            teamElement.appendChild(reactivateButton);
            inactiveTeams.appendChild(teamElement);
        });
    }
}

function reactivateTeam(teamName) {
    socket.emit('reactivate_team', { team_name: teamName });
    showStatus('Reactivating team...', 'info');
}

// Create a new team
function createTeam() {
    const teamName = teamNameInput.value.trim();
    if (!teamName) {
        showStatus('Please enter a team name', 'error');
        return;
    }
    
    socket.emit('create_team', { team_name: teamName });
    showStatus('Creating team...', 'info');
}

// Join an existing team
function joinTeam(teamName) {
    socket.emit('join_team', { team_name: teamName });
    showStatus('Joining team...', 'info');
}

// Submit an answer
function submitAnswer(answer) {
    if (!currentRound) return;
    
    socket.emit('submit_answer', {
        round_id: currentRound.round_id,
        item: currentRound.item,
        answer: answer
    });
    
    // Track which button was clicked
    lastClickedButton = answer ? trueBtn : falseBtn;
    
    trueBtn.disabled = true;
    falseBtn.disabled = true;
    waitingMessage.classList.add('visible');
    showStatus(`Round ${currentRound.round_number} answer received`, 'success');
}

// Update team status header text
function updateTeamStatus(status) {
    const header = document.getElementById('teamStatusHeader');
    if (status === 'created') {
        header.textContent = 'Team Created!';
    } else if (status === 'full' || status === 'active') { // 'active' is internal server state for full
        header.textContent = 'Team Paired Up!';
    } else if (status === 'waiting_pair') {
        header.textContent = 'Waiting for Player...';
    } else {
        header.textContent = 'Team Up!'; // Default or initial state
    }
}

// Enable or disable answer buttons
function setAnswerButtonsEnabled(enabled) {
    gamePaused = !enabled;
    
    if (currentRound?.alreadyAnswered) {
        // Keep both buttons disabled if round was answered
        trueBtn.disabled = true;
        falseBtn.disabled = true;
        trueBtn.classList.remove('paused');
        falseBtn.classList.remove('paused');
    } else if (gamePaused) {
        // If game is paused, keep last clicked button disabled
        trueBtn.classList.add('paused');
        falseBtn.classList.add('paused');
        if (lastClickedButton) {
            lastClickedButton.disabled = true;
            // Enable other button in case it was disabled
            (lastClickedButton === trueBtn ? falseBtn : trueBtn).disabled = true;
        } else {
            // If no button was clicked, disable both
            trueBtn.disabled = true;
            falseBtn.disabled = true;
        }
    } else {
        // Normal state - enable both buttons unless round was answered
        trueBtn.disabled = false;
        falseBtn.disabled = false;
        trueBtn.classList.remove('paused');
        falseBtn.classList.remove('paused');
    }
    
    if (gamePaused) {
        waitingMessage.textContent = "Game is paused";
        waitingMessage.classList.add('visible');
    } else {
        waitingMessage.textContent = "Waiting for next round...";
        if (!currentRound?.alreadyAnswered) {
            waitingMessage.classList.remove('visible');
        }
    }
}

// Socket.io event handlers callbacks
const callbacks = {
    updateTeamStatus,
    updateConnectionStatus,
    showStatus,
    updateGameState,
    updateTeamsList,
    resetGameControls,
    updateSessionInfo: (id) => sessionInfo.innerHTML = `Session ID: <span class="session-id">${id}</span>`,
    setAnswerButtonsEnabled,
    getCurrentRoundInfo: () => currentRound,
    resetToInitialView,

    onTeamCreated: (data) => {
        currentTeam = data.team_name;
        teamId = data.team_id;
        isCreator = true;
        gameStarted = data.game_started;
        
        // Hide both create and join team sections when creating a new team
        document.getElementById('joinTeamSection').style.display = 'none';
        document.getElementById('createTeamSection').style.display = 'none';
        
        // Update header with team name
        gameHeader.textContent = `Team: ${data.team_name}`;
        
        showStatus(data.message, 'success');
        updateGameState();
    },

    onTeamJoined: (data) => { // For the player who just joined
        currentTeam = data.team_name;
        isCreator = false; // Player joining is never the creator of an existing team
        gameStarted = data.game_started;
        teamId = data.team_id; // Assuming team_id is sent, if not, it might be part of team_status_update

        gameHeader.textContent = `Team: ${data.team_name}`;
        showStatus(data.message, 'success');
        
        // The 'team_status_update' event will follow and handle UI based on whether team is full
        // So, updateGameState() here might be premature for showing question section if game started
        // but we can hide the join/create sections.
        document.getElementById('joinTeamSection').style.display = 'none';
        document.getElementById('createTeamSection').style.display = 'none';
        
        // If the team_status is part of this event, we can use it
        if (data.team_status) {
            updateTeamStatus(data.team_status);
            if (data.team_status === 'full' && gameStarted) {
                 // If game started and team is full, expect new_question soon
            } else if (data.team_status === 'waiting_pair') {
                // Still waiting
            }
        }
        updateGameState(); // Call to ensure UI reflects currentTeam being set
    },

    onPlayerJoined: (data) => { // Generic notification, less critical now with team_status_update
        showStatus(data.message, 'success');
        // gameStarted = data.game_started; // This should come from team_status_update
        // updateGameState(); // team_status_update will handle this
    },

    onTeamStatusUpdate: (data) => { // For all members of a team when its status changes
        console.log('Team status update:', data);
        gameStarted = data.game_started; // Update global gameStarted state

        if (currentTeam === data.team_name) { // Ensure this update is for the current player's team
            updateTeamStatus(data.status); // Update the "Team Paired Up!" or "Waiting for Player..." header

            if (data.status === 'full') {
                if (gameStarted) {
                    showStatus('Your team is paired up! Game is active.', 'success');
                } else {
                    showStatus('Your team is paired up! Waiting for game to start.', 'success');
                }
            } else if (data.status === 'waiting_pair') {
                showStatus('Waiting for another player to join...', 'info');
            }
        }
        updateGameState(); // Refresh main game UI (team vs question section)
    },

    onGameStart: () => { // Global game start event from dashboard
        gameStarted = true;
        showStatus('Game has started! Get ready for questions.', 'success');
        updateGameState();
    },

    onNewQuestion: (data) => {
        console.log('New question received:', data);
        currentRound = data;
        currentRound.alreadyAnswered = false;
        lastClickedButton = null; // Reset last clicked button for new round
        showStatus(`Round ${data.round_number}`, 'info');
        updateGameState();
    },

    onAnswerConfirmed: (data) => {
        if (currentRound) currentRound.alreadyAnswered = true;
        showStatus(data.message, 'success');
    },

    onTeamDisbanded: (data) => {
        currentTeam = null;
        isCreator = false;
        currentRound = null;
        lastClickedButton = null;
        localStorage.removeItem('quizSessionData');
        // Reset header
        gameHeader.textContent = 'CHSH Game';
        showStatus(data.message, 'error');
        updateGameState();
    },

    onLeftTeam: (data) => {
        currentTeam = null;
        isCreator = false;
        currentRound = null;
        localStorage.removeItem('quizSessionData');
        // Reset header
        gameHeader.textContent = 'CHSH Game';
        showStatus(data.message, 'success');
        updateGameState();
    }
};

// Initialize Socket.io
const socket = io();
initializeSocketHandlers(socket, callbacks);

// Debug socket events
socket.on('team_status_update', (data) => {
    console.log('Received team_status_update:', data);
    if (callbacks.updateTeamStatus) {
        callbacks.updateTeamStatus(data.status);
    }
});

// Event listeners
createTeamBtn.addEventListener('click', createTeam);
trueBtn.addEventListener('click', () => submitAnswer(true));
falseBtn.addEventListener('click', () => submitAnswer(false));

// Initialize collapsible inactive teams section
document.addEventListener('DOMContentLoaded', function() {
    const collapsibleHeader = document.querySelector('.collapsible-header');
    const toggleIndicator = document.querySelector('.toggle-indicator');
    const inactiveTeams = document.getElementById('inactiveTeams');
    
    if (collapsibleHeader && inactiveTeams) {
        collapsibleHeader.addEventListener('click', function() {
            toggleIndicator.classList.toggle('collapsed');
            if (inactiveTeams.style.display === 'none') {
                inactiveTeams.style.display = 'block';
            } else {
                inactiveTeams.style.display = 'none';
            }
        });
        
        // Initialize as collapsed
        toggleIndicator.classList.add('collapsed');
    }
});

// Initialize UI
updateGameState();

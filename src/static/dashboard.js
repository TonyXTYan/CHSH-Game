// Initialize socket with ping timeout settings
const socket = io(window.location.origin, {
    pingTimeout: 60000, // Increase ping timeout to 60 seconds
    pingInterval: 25000 // Ping every 25 seconds
});
const connectionStatusDiv = document.getElementById("connection-status-dash");

// Handle page visibility changes
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
        console.log('Page became visible - requesting update');
        socket.emit('dashboard_join');
    }
});

// Keep socket alive and handle background state
setInterval(() => {
    if (socket.connected) {
        socket.emit('keep_alive');
    }
}, 30000); // Send keep-alive ping every 30 seconds

const activeTeamsCountEl = document.getElementById("active-teams-count");
const readyPlayersCountEl = document.getElementById("ready-players-count");
const connectedPlayersCountEl = document.getElementById("connected-players-count");
const totalResponsesCountEl = document.getElementById("total-responses-count");

const activeTeamsTableBody = document.querySelector("#active-teams-table tbody");
const noActiveTeamsMsg = document.getElementById("no-active-teams");
const answerLogTableBody = document.querySelector("#answer-log-table tbody");
const noAnswersLogMsg = document.getElementById("no-answers-log");

let currentAnswersCount = 0;

// Utility function to reset button to initial state
function resetButtonToInitialState(btn) {
    if (!btn) return;
    console.log(`Resetting button from ${btn.textContent} to Start Game`);
    btn.disabled = false;
    btn.textContent = "Start Game";
    btn.className = "";  // Remove all classes to get default blue styling
    btn.onclick = startGame;
    confirmingStop = false;
    document.getElementById("game-control-text").textContent = "Game Control";
}

socket.on("connect", async () => {
    connectionStatusDiv.textContent = "Connected to server";
    connectionStatusDiv.className = "status-connected";
    
    try {
        // Get server instance ID
        const response = await fetch('/api/server/id');
        const {instance_id} = await response.json();
        
        // Check against stored ID
        const lastId = localStorage.getItem('server_instance_id');
        if (lastId !== instance_id) {
            // New server instance - clear UI
            clearAllUITables();
            localStorage.setItem('server_instance_id', instance_id);
        }
    } catch (error) {
        console.error('Error checking server ID:', error);
    }
    
    // Reset game button state on reconnect
    const startBtn = document.getElementById("start-game-btn");
    resetButtonToInitialState(startBtn);
    socket.emit("dashboard_join"); // Notify backend that a dashboard client has joined
});

function clearAllUITables() {
    activeTeamsTableBody.innerHTML = "";
    answerLogTableBody.innerHTML = "";
    noActiveTeamsMsg.style.display = "block";
    noAnswersLogMsg.style.display = "block";
    activeTeamsCountEl.textContent = "0";
    readyPlayersCountEl.textContent = "0";
    connectedPlayersCountEl.textContent = "0";
    totalResponsesCountEl.textContent = "0";
    document.getElementById("pause-game-btn").style.display = "none";
}

socket.on("disconnect", () => {
    connectionStatusDiv.textContent = "Disconnected from server";
    connectionStatusDiv.className = "status-disconnected";
    // Clear current state
    activeTeamsTableBody.innerHTML = "";
    noActiveTeamsMsg.style.display = "block";
    activeTeamsCountEl.textContent = "0";
    readyPlayersCountEl.textContent = "0";
    connectedPlayersCountEl.textContent = "0";
    currentAnswersCount = 0;
    totalResponsesCountEl.textContent = "0";
});

socket.on("server_shutdown", () => {
    connectionStatusDiv.textContent = "Server is shutting down";
    connectionStatusDiv.className = "status-disconnected";
    // Clear all UI elements
    activeTeamsTableBody.innerHTML = "";
    answerLogTableBody.innerHTML = "";
    noActiveTeamsMsg.style.display = "block";
    noAnswersLogMsg.style.display = "block";
    activeTeamsCountEl.textContent = "0";
    totalPlayersCountEl.textContent = "0";
    totalResponsesCountEl.textContent = "0";
    // Reset game button state
    const startBtn = document.getElementById("start-game-btn");
    resetButtonToInitialState(startBtn);
    // Clear any localStorage data
    localStorage.removeItem('chsh_game_state');
});

// Handle page load - restore game state from localStorage
window.addEventListener('load', () => {
    // Clear any stale state but preserve game state
    const gameStarted = localStorage.getItem('game_started') === 'true';
    const gamePaused = localStorage.getItem('game_paused') === 'true';
    // const lastUpdate = parseInt(localStorage.getItem('game_state_last_update') || '0'); // Not strictly needed for initial UI render
    
    // Clear old storage format if present
    localStorage.removeItem('chsh_game_state'); // Keep this if migrating from an old format
    
    const startBtn = document.getElementById("start-game-btn");
    const pauseBtn = document.getElementById("pause-game-btn");
    const gameControlText = document.getElementById("game-control-text");

    if (gameStarted) {
        if (startBtn) {
            startBtn.disabled = false;
            startBtn.textContent = "Reset game stats";
            startBtn.className = "reset-game";
            startBtn.onclick = handleResetGame;
        }
        
        if (pauseBtn) {
            pauseBtn.style.display = "inline-block";
            updatePauseButtonState(gamePaused); // Use the existing function to set text and class
        }
        
        if (gameControlText) {
            gameControlText.textContent = gamePaused ? "Game paused" : "Game in progress";
        }
    } else {
        // If game not started, ensure pause button is hidden and start button is in initial state
        if (startBtn) {
             resetButtonToInitialState(startBtn); // Resets text, class, onclick
        }
        if (pauseBtn) {
            pauseBtn.style.display = "none";
        }
        if (gameControlText) {
            gameControlText.textContent = "Game Control";
        }
    }
});

let confirmingStop = false;
let countdownActive = false;
let countdownInterval = null;
let currentConfirmMouseOutListener = null; // To manage the mouseout listener

// Global cleanup function for reset confirmation
function cleanupResetConfirmation(startBtn) {
    countdownActive = false;
    if (countdownInterval) {
        clearInterval(countdownInterval);
        countdownInterval = null;
    }

    // Remove the mouseout listener if it's active
    if (startBtn && currentConfirmMouseOutListener) {
        startBtn.removeEventListener('mouseout', currentConfirmMouseOutListener);
        currentConfirmMouseOutListener = null;
    }
    // The 'beforeunload' listener is {once: true}, it handles itself.

    let wasConfirming = confirmingStop;
    confirmingStop = false; // Always mark confirmation as ended

    if (wasConfirming && startBtn) { // Only reset button text if it was in confirmation mode
        startBtn.textContent = "Reset game stats";
        startBtn.className = "reset-game";
    }
}

socket.on("game_started", () => {
    const startBtn = document.getElementById("start-game-btn");
    const gameControlText = document.getElementById("game-control-text");
    
    cleanupResetConfirmation(startBtn); // Ensure any prior confirmation state is cleared

    gameControlText.textContent = "Game in progress";
    document.getElementById("pause-game-btn").style.display = "inline-block";
    startBtn.disabled = false;
    startBtn.textContent = "Reset game stats";
    startBtn.className = "reset-game";
    startBtn.onclick = handleResetGame;

    // Persist game started state
    localStorage.setItem('game_started', 'true');
    localStorage.setItem('game_state_last_update', Date.now().toString());
});

socket.on("game_reset_complete", () => {
    console.log("Received game_reset_complete event");
    
    if (resetTimeout) {
        clearTimeout(resetTimeout);
        resetTimeout = null;
    }
    
    const startBtn = document.getElementById("start-game-btn");
    const gameControlText = document.getElementById("game-control-text");
    
    cleanupResetConfirmation(startBtn); // Crucial to clear any confirmation state
    
    startBtn.disabled = false;
    startBtn.textContent = "Start Game";
    startBtn.className = "";
    startBtn.onclick = startGame;
    gameControlText.textContent = "Game Control";
    document.getElementById("pause-game-btn").style.display = "none";
    
    answerLogTableBody.innerHTML = "";
    noAnswersLogMsg.style.display = "block";
    currentAnswersCount = 0;
    totalResponsesCountEl.textContent = "0";

    // Clear game state from localStorage
    localStorage.removeItem('game_started');
    localStorage.removeItem('game_paused');
    localStorage.removeItem('game_state_last_update');
    
    socket.emit('dashboard_join');
});

function handleResetGame() {
    const startBtn = document.getElementById("start-game-btn");
    if (!startBtn || startBtn.disabled) {
        console.error("Invalid button state");
        return;
    }

    if (!confirmingStop) {
        // Count inactive teams with players
        const inactiveTeamsCount = lastReceivedTeams.filter(team =>
            team.is_active && (!team.player1_sid && !team.player2_sid)
        ).length;

        // Ensure any previous mouseout listener is removed before adding a new one
        if (currentConfirmMouseOutListener && startBtn) {
            startBtn.removeEventListener('mouseout', currentConfirmMouseOutListener);
            currentConfirmMouseOutListener = null;
        }
        
        // Clear any existing interval (defensive)
        if (countdownInterval) {
            clearInterval(countdownInterval);
            countdownInterval = null;
        }

        startBtn.className = "confirm-reset";
        confirmingStop = true;
        let secondsLeft = 3;
        countdownActive = true;
        
        const message = inactiveTeamsCount > 0 ?
            `Reset game stats and remove ${inactiveTeamsCount} inactive team${inactiveTeamsCount !== 1 ? 's' : ''}? (${secondsLeft})` :
            `Reset game stats? (${secondsLeft})`;
        
        startBtn.textContent = message;
        
        countdownInterval = setInterval(() => {
            if (!countdownActive) {
                clearInterval(countdownInterval);
                countdownInterval = null;
                return;
            }
            
            secondsLeft--;
            if (secondsLeft > 0) {
                if (confirmingStop) {
                    const message = inactiveTeamsCount > 0 ?
                        `Reset game stats and remove ${inactiveTeamsCount} inactive team${inactiveTeamsCount !== 1 ? 's' : ''}? (${secondsLeft})` :
                        `Reset game stats? (${secondsLeft})`;
                    startBtn.textContent = message;
                }
            } else {
                cleanupResetConfirmation(startBtn);
            }
        }, 1000);

        // Define and add the mouseout listener
        currentConfirmMouseOutListener = () => {
            cleanupResetConfirmation(startBtn);
        };
        startBtn.addEventListener('mouseout', currentConfirmMouseOutListener);
        
        // Add beforeunload listener
        window.addEventListener('beforeunload', () => {
            cleanupResetConfirmation(startBtn);
        }, { once: true });
        
    } else {
        cleanupResetConfirmation(startBtn);
        startBtn.disabled = true;
        startBtn.textContent = "Resetting...";
        startResetTimeout();
        socket.emit("restart_game");
    }
}

// Add reset timeout to prevent stuck states
let resetTimeout;
function startResetTimeout() {
    clearTimeout(resetTimeout);
    resetTimeout = setTimeout(() => {
        const startBtn = document.getElementById("start-game-btn");
        if (startBtn && startBtn.disabled) {
            console.log("Reset timeout triggered - resetting button state");
            resetButtonToInitialState(startBtn);
        }
    }, 5000); // 5 seconds timeout
}

socket.on("error", (data) => {
    console.error("Socket Error:", data);
    connectionStatusDiv.textContent = `Error: ${data.message}`;
    connectionStatusDiv.className = "status-disconnected";

    // Reset button state in case of errors
    const startBtn = document.getElementById("start-game-btn");
    if (startBtn && startBtn.disabled) {
        resetButtonToInitialState(startBtn);
    }
});

socket.on("dashboard_update", (data) => {
    console.log("Dashboard update received:", data);
    lastReceivedTeams = data.teams;
    if (data.game_state) {
        console.log(`Game state update - started: ${data.game_state.started}, paused: ${data.game_state.paused}, streaming: ${data.game_state.streaming_enabled}`);
        
        // Persist full game state from server
        localStorage.setItem('game_started', data.game_state.started.toString());
        if (data.game_state.paused !== undefined) {
            localStorage.setItem('game_paused', data.game_state.paused.toString());
        } else {
            localStorage.removeItem('game_paused'); // Clear if undefined
        }
        localStorage.setItem('game_state_last_update', Date.now().toString());

        // Update pause button visibility and state
        const pauseBtn = document.getElementById("pause-game-btn");
        if (data.game_state.started) {
            pauseBtn.style.display = "inline-block";
            updatePauseButtonState(data.game_state.paused);
            document.getElementById("game-control-text").textContent =
                data.game_state.paused ? "Game paused" : "Game in progress";
        } else {
            pauseBtn.style.display = "none";
            // Also ensure game control text is reset if game is not started
            document.getElementById("game-control-text").textContent = "Game Control";
        }
    }
    updateActiveTeams(data.teams);
    updateAnswerLog(data.recent_answers); // Assuming backend sends recent answers on update
    updateMetrics(data.active_teams, data.total_answers_count, data.connected_players_count);
    
    // Sync streaming state with server
    if (data.game_state && data.game_state.streaming_enabled !== undefined) {
        answerStreamEnabled = data.game_state.streaming_enabled;
        updateStreamingUI();
    }

    // Refresh team details popup if open
    if (data.active_teams) {
        refreshTeamDetailsIfOpen(data.active_teams);
    }
    
    // Update button state based on game state
    const startBtn = document.getElementById("start-game-btn");
    if (!confirmingStop) {
        if (data.game_state) {
            if (data.game_state.started && startBtn.textContent === "Start Game") {
                console.log("Updating button to Reset state");
                startBtn.disabled = false;
                startBtn.textContent = "Reset game stats";
                startBtn.className = "reset-game";
                startBtn.onclick = handleResetGame;
            } else if (!data.game_state.started && startBtn.textContent === "Reset game stats") {
                console.log("Resetting button to Start Game state");
                startBtn.disabled = false;
                startBtn.textContent = "Start Game";
                startBtn.className = "";
                startBtn.onclick = startGame;
            }
        }
    }
});

socket.on("new_answer_for_dashboard", (data) => {
    console.log("New answer for dashboard:", data);
    currentAnswersCount++;
    totalResponsesCountEl.textContent = currentAnswersCount;
    
    if (answerStreamEnabled) {
        // The answer data is directly in the data object, not nested under 'answer'
        addAnswerToLog(data);
    } else {
        console.log("Answer received but streaming is disabled - not showing in log");
    }

    // Refresh team details if this answer is from the currently viewed team
    if (data.team_id === currentlyViewedTeamId) {
        // Get fresh team data
        socket.emit('dashboard_join');
    }
});

socket.on("team_status_changed_for_dashboard", (data) => {
    console.log("Team status changed for dashboard:", data);
    lastReceivedTeams = data.teams;
    updateActiveTeams(data.teams);
    updateMetrics(data.teams, currentAnswersCount, data.connected_players_count);
    
    // Refresh team details popup if open
    if (data.teams) {
        refreshTeamDetailsIfOpen(data.teams);
    }
});

function updateMetrics(teams, totalAnswers, connectedCount) {
    if (teams) {
        // Count active teams
        const activeTeams = teams.filter(team => team.is_active);
        activeTeamsCountEl.textContent = activeTeams.length;
        
        // Count ready players (only from active teams)
        let readyPlayerCount = 0;
        activeTeams.forEach(team => {
            if(team.player1_sid) readyPlayerCount++;
            if(team.player2_sid) readyPlayerCount++;
        });
        readyPlayersCountEl.textContent = readyPlayerCount;
    }
    
    // Update connected players count
    if (typeof connectedCount === 'number') {
        console.log('Updating connected players count:', connectedCount);
        connectedPlayersCountEl.textContent = connectedCount;
    }
    
    if (totalAnswers !== undefined) {
        currentAnswersCount = totalAnswers;
        totalResponsesCountEl.textContent = currentAnswersCount;
    }
}


// Add event listener for show-inactive toggle
document.getElementById('show-inactive').addEventListener('change', () => {
    if (lastReceivedTeams) {
        updateActiveTeams(lastReceivedTeams);
    }
});

function updateActiveTeams(teams) {
    if (!teams) {
        teams = [];
    }

    const showInactive = document.getElementById('show-inactive').checked;
    const sortBy = document.getElementById('sort-teams').value;
    
    // Filter teams based on status
    let filteredTeams = showInactive ? teams : teams.filter(team =>
        team.is_active || team.status === 'waiting_pair'
    );
    
    // Sort teams
    filteredTeams.sort((a, b) => {
        if (sortBy === 'status') {
            if (a.is_active === b.is_active) return 0;
            return a.is_active ? -1 : 1;
        } else if (sortBy === 'date') {
            return new Date(b.created_at || 0) - new Date(a.created_at || 0);
        }
        return a.team_name.localeCompare(b.team_name);
    });
    
    // Show/hide no teams message
    noActiveTeamsMsg.style.display = filteredTeams.length === 0 ? "block" : "none";
    activeTeamsTableBody.innerHTML = ""; // Clear existing rows
    
    filteredTeams.forEach(team => {
        const row = activeTeamsTableBody.insertRow();
        row.className = team.is_active ? 'team-row active' : 'team-row inactive';
        
        // Team name cell with status indicator
        const nameCell = row.insertCell();
        const statusDot = document.createElement('span');
        let statusClass = 'inactive';
        if (team.is_active) {
            statusClass = team.status === 'waiting_pair' ? 'waiting' : 'active';
        }
        statusDot.className = `team-status ${statusClass}`;
        nameCell.appendChild(statusDot);
        nameCell.appendChild(document.createTextNode(team.team_name));
        
        // Status cell
        let statusText = 'Inactive';
        if (team.is_active) {
            statusText = team.status === 'waiting_pair' ? 'Waiting Pair' : 'Active';
        }
        row.insertCell().textContent = statusText;
        row.insertCell().textContent = team.current_round_number || 0;
        
        // Statistics significance column
        const statsCell = row.insertCell();
        statsCell.textContent = team.min_stats_sig ? '✅' : '⏳';
        statsCell.style.textAlign = 'center';
        
        // Add trace_avg column with robust error handling
        const traceAvgCell = row.insertCell();
        if (team.correlation_stats && team.correlation_stats.trace_avg !== undefined && 
            team.correlation_stats.trace_avg !== null && !isNaN(team.correlation_stats.trace_avg)) {
            try {
                const traceAvg = parseFloat(team.correlation_stats.trace_avg);
                traceAvgCell.textContent = traceAvg.toFixed(3);
                
                // Add visual indicator for interesting values
                if (Math.abs(traceAvg) > 0.7) {
                    traceAvgCell.style.fontWeight = "bold";
                }
            } catch (e) {
                console.error("Error formatting trace_avg", e);
                traceAvgCell.textContent = "Error";
            }
        } else {
            traceAvgCell.textContent = "—";
        }
        
        // Add Same Item Balance column with robust error handling
        const balanceCell = row.insertCell();
        if (team.correlation_stats && team.correlation_stats.same_item_balance !== undefined && 
            team.correlation_stats.same_item_balance !== null && !isNaN(team.correlation_stats.same_item_balance)) {
            try {
                const balance = parseFloat(team.correlation_stats.same_item_balance);
                balanceCell.textContent = balance.toFixed(3);
                
                // Add visual indicator for interesting values (close to 1.0 is good balance)
                if (balance > 0.8) {
                    balanceCell.style.fontWeight = "bold";
                    balanceCell.style.color = "#0066cc";
                }
            } catch (e) {
                console.error("Error formatting same_item_balance", e);
                balanceCell.textContent = "Error";
            }
        } else {
            balanceCell.textContent = "—";
        }

        // Add Balanced Random column with robust error handling
        const balancedRandomCell = row.insertCell();
        if (team.correlation_stats && 
            team.correlation_stats.trace_avg !== undefined && 
            team.correlation_stats.trace_avg !== null && 
            !isNaN(team.correlation_stats.trace_avg) &&
            team.correlation_stats.same_item_balance !== undefined && 
            team.correlation_stats.same_item_balance !== null && 
            !isNaN(team.correlation_stats.same_item_balance)) {
            try {
                const traceAvg = parseFloat(team.correlation_stats.trace_avg);
                const balance = parseFloat(team.correlation_stats.same_item_balance);
                const balancedRandom = (traceAvg + balance) / 2;
                balancedRandomCell.textContent = balancedRandom.toFixed(3);
                
                // Add visual indicator for interesting values (close to 1.0 is good)
                if (balancedRandom > 0.7) {
                    balancedRandomCell.style.fontWeight = "bold";
                    balancedRandomCell.style.color = "#0066cc";
                }
            } catch (e) {
                console.error("Error calculating Balanced Random", e);
                balancedRandomCell.textContent = "Error";
            }
        } else {
            balancedRandomCell.textContent = "—";
        }
        
        // Add CHSH value column with robust error handling
        const chshValueCell = row.insertCell();
        if (team.correlation_stats && team.correlation_stats.chsh_value !== undefined && 
            team.correlation_stats.chsh_value !== null && !isNaN(team.correlation_stats.chsh_value)) {
            try {
                const chshValue = parseFloat(team.correlation_stats.chsh_value);
                chshValueCell.textContent = chshValue.toFixed(3);
                
                // Add visual indicator for interesting values (CHSH inequality violation is > 2)
                if (Math.abs(chshValue) > 2) {
                    chshValueCell.style.fontWeight = "bold";
                    chshValueCell.style.color = Math.abs(chshValue) > 2.8 ? "#cc0000" : "#0066cc";
                }
            } catch (e) {
                console.error("Error formatting chsh_value", e);
                chshValueCell.textContent = "Error";
            }
        } else {
            chshValueCell.textContent = "—";
        }
        
        // Details button cell
        const detailsCell = row.insertCell();
        const detailsBtn = document.createElement('button');
        detailsBtn.className = 'view-details-btn';
        detailsBtn.textContent = 'View Details';
        detailsBtn.onclick = () => showTeamDetails(team);
        detailsCell.appendChild(detailsBtn);
    });
}

function addAnswerToLog(answer) {
    if (!answer) {
        console.error("Received null or undefined answer object");
        return;
    }
    
    try {
        noAnswersLogMsg.style.display = "none";
        const row = answerLogTableBody.insertRow(0); // Add to top
        
        // Handle timestamp with fallback to current time
        const timestamp = answer.timestamp ? new Date(answer.timestamp) : new Date();
        row.insertCell().textContent = timestamp.toLocaleTimeString();
        
        // Add other fields with null checks
        row.insertCell().textContent = answer.team_name || '—';
        row.insertCell().textContent = (answer.player_session_id || '').substring(0, 8) + "...";
        row.insertCell().textContent = answer.question_round_id || '—';
        row.insertCell().textContent = answer.assigned_item || '—';
        row.insertCell().textContent = answer.response_value !== undefined ? answer.response_value : '—';
        
        // Limit log size if needed
        if (answerLogTableBody.rows.length > 100) { // Keep last 100 answers
            answerLogTableBody.deleteRow(-1);
        }
    } catch (error) {
        console.error("Error adding answer to log:", error, "Answer:", answer);
    }
}

function updateAnswerLog(answers) {
    if (answers && answers.length > 0) {
        noAnswersLogMsg.style.display = "none";
        answers.forEach(addAnswerToLog);
    }
}

let answerStreamEnabled = false;
const answerTable = document.getElementById('answer-log-table');
const noAnswersMsg = document.getElementById('no-answers-log');
const toggleBtn = document.getElementById('toggle-answers-btn');
const toggleChevron = document.getElementById('toggle-chevron');

// Initialize to OFF state
toggleBtn.textContent = 'OFF';
toggleBtn.className = 'toggle-off';
answerTable.style.display = 'none';
noAnswersMsg.style.display = 'none';
toggleChevron.textContent = '▶';

function updateStreamingUI() {
    if (answerStreamEnabled) {
        toggleBtn.textContent = 'ON';
        toggleBtn.className = 'toggle-on';
        answerTable.style.display = 'table';
        toggleChevron.textContent = '▼';
    } else {
        toggleBtn.textContent = 'OFF';
        toggleBtn.className = 'toggle-off';
        answerTable.style.display = 'none';
        toggleChevron.textContent = '▶';
    }
}

function toggleAnswerStream() {
    answerStreamEnabled = !answerStreamEnabled;
    updateStreamingUI();
}

function togglePause() {
    const pauseBtn = document.getElementById("pause-game-btn");
    if (pauseBtn && !pauseBtn.disabled) {
        pauseBtn.disabled = true;  // Prevent double-click
        socket.emit("pause_game");
    }
}

function updatePauseButtonState(isPaused) {
    const pauseBtn = document.getElementById("pause-game-btn");
    if (pauseBtn) {
        pauseBtn.disabled = false;
        if (isPaused) {
            pauseBtn.textContent = "Resume";
            pauseBtn.classList.add("resume");
        } else {
            pauseBtn.textContent = "Pause";
            pauseBtn.classList.remove("resume");
        }
    }
}

socket.on("game_state_update", (data) => {
    console.log("Game state update received:", data);
    if (data.hasOwnProperty('paused')) {
        updatePauseButtonState(data.paused);
        document.getElementById("game-control-text").textContent =
            data.paused ? "Game paused" : "Game in progress";
        
        // Persist the current state
        localStorage.setItem('game_paused', data.paused.toString());
        localStorage.setItem('game_state_last_update', Date.now().toString());
    }
});

function startGame() {
    const startBtn = document.getElementById("start-game-btn");
    if (startBtn && !startBtn.disabled) {
        startBtn.disabled = true;  // Prevent double-click
        socket.emit("start_game");
    }
}

async function downloadData() {
    try {
        const response = await fetch('/api/dashboard/data');
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        const data = await response.json();
        
        // Convert data to CSV
        const csvRows = [];
        csvRows.push(['Timestamp', 'Team Name', 'Team ID', 'Player ID', 'Round ID', 'Question Item (A/B/X/Y)', 'Answer (True/False)']);
        
        data.answers.forEach(answer => {
            csvRows.push([
                new Date(answer.timestamp).toLocaleString(),
                answer.team_name,
                answer.team_id,
                answer.player_session_id, // Use full SID for CSV export
                answer.question_round_id,
                answer.assigned_item,
                answer.response_value
            ]);
        });
        
        // Generate CSV content
        const csvContent = csvRows.map(row => row.join(',')).join('\n');
        
        // Create and trigger download
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.setAttribute('download', 'chsh-game-data.csv');
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    } catch (error) {
        console.error('Error downloading data:', error);
        alert('Error downloading data. Please try again.');
    }
}

// Track current team details popup state
let currentlyViewedTeamId = null;
let isDetailsPopupOpen = false;

// Function to update team details modal content
function updateModalContent(team) {
    const modalTeamName = document.getElementById('modal-team-name');
    const modalTeamId = document.getElementById('modal-team-id');
    const modalPlayer1Sid = document.getElementById('modal-player1-sid');
    const modalPlayer2Sid = document.getElementById('modal-player2-sid');
    const modalHash1 = document.getElementById('modal-hash1');
    const modalHash2 = document.getElementById('modal-hash2');
    const correlationTable = document.getElementById('correlation-matrix-table');
    
    // Set team name in modal
    modalTeamName.textContent = team.team_name;

    // Set team details
    modalTeamId.textContent = team.team_id;
    modalPlayer1Sid.textContent = team.player1_sid || "—";
    modalPlayer2Sid.textContent = team.player2_sid || "—";
    
    // Set hash values
    modalHash1.textContent = team.history_hash1 || "—";
    modalHash2.textContent = team.history_hash2 || "—";
    
    // Clear existing correlation matrix
    correlationTable.innerHTML = '';
    
    // Populate correlation matrix table if available with validation
    if (team.correlation_matrix && team.correlation_labels && 
        Array.isArray(team.correlation_matrix) && Array.isArray(team.correlation_labels) &&
        team.correlation_matrix.length > 0) {
        
        try {
            // Add header row with labels
            const headerRow = correlationTable.insertRow();
            headerRow.insertCell(); // Empty corner cell
            
            // Validate and add column headers
            team.correlation_labels.forEach(label => {
                const th = document.createElement('th');
                th.textContent = label || '?'; // Fallback if label is undefined
                headerRow.appendChild(th);
            });
            
            // Add data rows with row labels - only process rows that match the label count
            team.correlation_matrix.forEach((row, rowIdx) => {
                // Skip if we've run out of labels
                if (rowIdx >= team.correlation_labels.length) {
                    return;
                }
                
                const tableRow = correlationTable.insertRow();
                
                // Add row label
                const rowLabelCell = document.createElement('th');
                rowLabelCell.textContent = team.correlation_labels[rowIdx] || '?';
                tableRow.appendChild(rowLabelCell);
                
                // Add correlation values with validation
                if (Array.isArray(row)) {
                    row.forEach(value => {
                        const cell = tableRow.insertCell();
                        
                        // Handle potential null/undefined/NaN values gracefully
                        if (value === null || value === undefined || isNaN(value)) {
                            cell.textContent = "—";
                        } else {
                            // Ensure value is treated as a number and limit to 3 decimal places
                            const numValue = parseFloat(value);
                            cell.textContent = numValue.toFixed(3);
                        }
                    });
                }
            });
        } catch (error) {
            console.error("Error rendering correlation matrix:", error);
            const errorRow = correlationTable.insertRow();
            const errorCell = errorRow.insertCell();
            errorCell.colSpan = 5;
            errorCell.textContent = "Error rendering correlation data";
            errorCell.style.textAlign = "center";
            errorCell.style.padding = "10px";
        }
    } else {
        const errorRow = correlationTable.insertRow();
        const errorCell = errorRow.insertCell();
        errorCell.colSpan = 5;
        errorCell.textContent = "No correlation data available";
        errorCell.style.textAlign = "center";
        errorCell.style.padding = "10px";
    }
}

// Function to close team details modal
function closeTeamDetails() {
    const modal = document.getElementById('team-details-modal');
    currentlyViewedTeamId = null;
    isDetailsPopupOpen = false;
    modal.style.display = 'none';
    
    // Clean up event listener
    if (window._modalClickHandler) {
        window.removeEventListener('click', window._modalClickHandler);
        window._modalClickHandler = null;
    }
}

// Function to refresh team details if modal is open
function refreshTeamDetailsIfOpen(teams) {
    if (!isDetailsPopupOpen || !currentlyViewedTeamId) return;
    
    const updatedTeam = teams.find(t => t.team_id === currentlyViewedTeamId);
    if (updatedTeam) {
        updateModalContent(updatedTeam);
    }
}

// Function to show team details in modal
function showTeamDetails(team) {
    const modal = document.getElementById('team-details-modal');
    
    // Update tracking state
    currentlyViewedTeamId = team.team_id;
    isDetailsPopupOpen = true;
    
    // Update modal content
    updateModalContent(team);
    
    // Show the modal
    modal.style.display = 'block';
    
    // Close button functionality
    const closeBtn = document.querySelector('.close-modal');
    closeBtn.onclick = closeTeamDetails;
    
    // Close modal when clicking outside of it
    // Remove previous event listener if exists to avoid duplicate handlers
    if (window._modalClickHandler) {
        window.removeEventListener('click', window._modalClickHandler);
    }
    
    // Create and store a reference to the handler
    window._modalClickHandler = (event) => {
        if (event.target === modal) {
            closeTeamDetails();
        }
    };
    
    // Add the event listener
    window.addEventListener('click', window._modalClickHandler);
}

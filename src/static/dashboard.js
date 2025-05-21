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
let lastReceivedTeams = []; // Store last received teams data

// Helper function to format statistics with uncertainty
function formatStatWithUncertainty(magnitude, uncertainty, precision = 2) {
    if (typeof magnitude !== 'number' || isNaN(magnitude)) {
        return "—";
    }
    let magStr = magnitude.toFixed(precision);
    let uncStr;

    if (typeof uncertainty === 'number' && uncertainty > 9.9999) {
        uncStr = '∞'; // Use ∞ for large uncertainty
    } else if (typeof uncertainty === 'number' && !isNaN(uncertainty)) {
        uncStr = uncertainty.toFixed(precision);
    } else {
        uncStr = "?"; // Use ? for invalid or missing uncertainty
    }
    return `${magStr}<span style="font-size: 0.8em; vertical-align: baseline; opacity: 0.5;">±${uncStr}</span>`;
}

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
    const refreshBtn = document.getElementById("refresh-dashboard-btn");

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
    
    // Initialize refresh button
    if (refreshBtn) {
        refreshBtn.onclick = requestDashboardRefresh;
    }
});

// Function to request immediate dashboard refresh
function requestDashboardRefresh() {
    console.log("Requesting dashboard refresh");
    const refreshBtn = document.getElementById("refresh-dashboard-btn");
    if (refreshBtn) {
        refreshBtn.disabled = true;
        refreshBtn.textContent = "Refreshing...";
        
        // Request refresh from server
        socket.emit("request_dashboard_refresh");
        
        // Re-enable button after a short delay
        setTimeout(() => {
            refreshBtn.disabled = false;
            refreshBtn.textContent = "Refresh Dashboard";
        }, 2000);
    }
}

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
    
    // Reset refresh button if needed
    const refreshBtn = document.getElementById("refresh-dashboard-btn");
    if (refreshBtn && refreshBtn.disabled) {
        refreshBtn.disabled = false;
        refreshBtn.textContent = "Refresh Dashboard";
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
                console.log("Updating button to Start state");
                startBtn.disabled = false;
                startBtn.textContent = "Start Game";
                startBtn.className = "";
                startBtn.onclick = startGame;
            }
        }
    }
    
    // Reset refresh button if it was in refreshing state
    const refreshBtn = document.getElementById("refresh-dashboard-btn");
    if (refreshBtn && refreshBtn.disabled) {
        refreshBtn.disabled = false;
        refreshBtn.textContent = "Refresh Dashboard";
    }
});

// Handle partial team updates
socket.on("team_status_changed_for_dashboard", (data) => {
    console.log("Team status update received:", data);
    
    // Update metrics
    if (data.connected_players_count !== undefined) {
        connectedPlayersCountEl.textContent = data.connected_players_count;
    }
    
    if (data.total_answers_count !== undefined) {
        totalResponsesCountEl.textContent = data.total_answers_count;
        currentAnswersCount = data.total_answers_count;
    }
    
    // Update teams that have changed
    if (data.teams && data.teams.length > 0) {
        // Merge updated teams into lastReceivedTeams
        data.teams.forEach(updatedTeam => {
            const existingIndex = lastReceivedTeams.findIndex(team => team.team_id === updatedTeam.team_id);
            if (existingIndex >= 0) {
                lastReceivedTeams[existingIndex] = updatedTeam;
            } else {
                lastReceivedTeams.push(updatedTeam);
            }
        });
        
        // Update the UI with all teams
        updateActiveTeams(lastReceivedTeams);
    }
    
    // Update game state if provided
    if (data.game_state) {
        if (data.game_state.started !== undefined) {
            localStorage.setItem('game_started', data.game_state.started.toString());
        }
        if (data.game_state.paused !== undefined) {
            localStorage.setItem('game_paused', data.game_state.paused.toString());
            
            // Update pause button state
            updatePauseButtonState(data.game_state.paused);
            
            // Update game control text
            const gameControlText = document.getElementById("game-control-text");
            if (gameControlText) {
                gameControlText.textContent = data.game_state.paused ? "Game paused" : "Game in progress";
            }
        }
        localStorage.setItem('game_state_last_update', Date.now().toString());
    }
});

function updatePauseButtonState(isPaused) {
    const pauseBtn = document.getElementById("pause-game-btn");
    if (!pauseBtn) return;
    
    if (isPaused) {
        pauseBtn.textContent = "Resume";
        pauseBtn.className = "resume-game";
    } else {
        pauseBtn.textContent = "Pause";
        pauseBtn.className = "";
    }
}

function startGame() {
    const startBtn = document.getElementById("start-game-btn");
    startBtn.disabled = true;
    startBtn.textContent = "Starting...";
    socket.emit("start_game");
}

function togglePause() {
    socket.emit("pause_game");
}

// Update active teams table
function updateActiveTeams(teams) {
    if (!teams || !Array.isArray(teams)) {
        console.error("Invalid teams data:", teams);
        return;
    }
    
    // Filter teams based on checkbox
    const showInactive = document.getElementById("show-inactive").checked;
    const filteredTeams = showInactive ? teams : teams.filter(team => team.is_active);
    
    // Sort teams based on dropdown
    const sortBy = document.getElementById("sort-teams").value;
    filteredTeams.sort((a, b) => {
        if (sortBy === "name") {
            return a.team_name.localeCompare(b.team_name);
        } else if (sortBy === "date") {
            return new Date(b.created_at || 0) - new Date(a.created_at || 0);
        } else { // status
            // First by active/inactive
            if (a.is_active !== b.is_active) {
                return a.is_active ? -1 : 1;
            }
            // Then by paired/unpaired
            const aPaired = a.player1_sid && a.player2_sid;
            const bPaired = b.player1_sid && b.player2_sid;
            if (aPaired !== bPaired) {
                return aPaired ? -1 : 1;
            }
            // Then by name
            return a.team_name.localeCompare(b.team_name);
        }
    });
    
    // Update table
    activeTeamsTableBody.innerHTML = "";
    
    if (filteredTeams.length === 0) {
        noActiveTeamsMsg.style.display = "block";
        activeTeamsCountEl.textContent = "0";
    } else {
        noActiveTeamsMsg.style.display = "none";
        
        // Count active teams and ready players
        const activeTeams = teams.filter(team => team.is_active);
        activeTeamsCountEl.textContent = activeTeams.length;
        
        // Count players in active teams
        let readyPlayersCount = 0;
        for (const team of activeTeams) {
            if (team.player1_sid) readyPlayersCount++;
            if (team.player2_sid) readyPlayersCount++;
        }
        readyPlayersCountEl.textContent = readyPlayersCount;
        
        // Populate table
        for (const team of filteredTeams) {
            const row = document.createElement("tr");
            
            // Determine status text and class
            let statusText, statusClass;
            if (!team.is_active) {
                statusText = "Inactive";
                statusClass = "status-inactive";
            } else if (team.status === "waiting_pair") {
                statusText = "Waiting for pair";
                statusClass = "status-waiting";
            } else if (team.status === "active") {
                statusText = "Active";
                statusClass = "status-active";
            } else {
                statusText = team.status || "Unknown";
                statusClass = "status-unknown";
            }
            
            // Format statistics with uncertainty
            const traceAvg = formatStatWithUncertainty(
                team.correlation_stats?.trace_average_statistic,
                team.correlation_stats?.trace_average_statistic_uncertainty
            );
            
            const balance = formatStatWithUncertainty(
                team.correlation_stats?.same_item_balance,
                team.correlation_stats?.same_item_balance_uncertainty
            );
            
            // Calculate balanced trace (trace * balance)
            let balancedTrace = "—";
            if (typeof team.correlation_stats?.trace_average_statistic === 'number' &&
                typeof team.correlation_stats?.same_item_balance === 'number') {
                const balancedValue = team.correlation_stats.trace_average_statistic * 
                                     team.correlation_stats.same_item_balance;
                
                // Simplified uncertainty calculation (product rule)
                let balancedUncertainty = null;
                if (typeof team.correlation_stats?.trace_average_statistic_uncertainty === 'number' &&
                    typeof team.correlation_stats?.same_item_balance_uncertainty === 'number') {
                    
                    const relUncTrace = team.correlation_stats.trace_average_statistic_uncertainty / 
                                       Math.abs(team.correlation_stats.trace_average_statistic || 1);
                    
                    const relUncBalance = team.correlation_stats.same_item_balance_uncertainty /
                                         Math.abs(team.correlation_stats.same_item_balance || 1);
                    
                    balancedUncertainty = Math.abs(balancedValue) * Math.sqrt(relUncTrace*relUncTrace + relUncBalance*relUncBalance);
                }
                
                balancedTrace = formatStatWithUncertainty(balancedValue, balancedUncertainty);
            }
            
            const chshValue = formatStatWithUncertainty(
                team.correlation_stats?.chsh_value_statistic,
                team.correlation_stats?.chsh_value_statistic_uncertainty
            );
            
            // Create row content
            row.innerHTML = `
                <td>${team.team_name}</td>
                <td class="${statusClass}">${statusText}</td>
                <td>${team.current_round_number || 0}</td>
                <td>${team.min_stats_sig ? "✓" : "✗"}</td>
                <td>${traceAvg}</td>
                <td>${balance}</td>
                <td>${balancedTrace}</td>
                <td>${chshValue}</td>
                <td><button class="details-btn" onclick="showTeamDetails('${team.team_id}')">Details</button></td>
            `;
            
            activeTeamsTableBody.appendChild(row);
        }
    }
}

// Global variable to track current team details being viewed
let currentTeamDetailsId = null;

// Show team details in modal
function showTeamDetails(teamId) {
    const team = lastReceivedTeams.find(t => t.team_id === teamId);
    if (!team) {
        console.error(`Team with ID ${teamId} not found`);
        return;
    }
    
    currentTeamDetailsId = teamId;
    
    // Populate modal with team details
    document.getElementById("modal-team-name").textContent = team.team_name;
    document.getElementById("modal-team-id").textContent = team.team_id;
    document.getElementById("modal-player1-sid").textContent = team.player1_sid || "—";
    document.getElementById("modal-player2-sid").textContent = team.player2_sid || "—";
    document.getElementById("modal-hash1").textContent = team.history_hash1 || "—";
    document.getElementById("modal-hash2").textContent = team.history_hash2 || "—";
    
    // Format CHSH values with uncertainty
    document.getElementById("modal-chsh-value").innerHTML = formatStatWithUncertainty(
        team.correlation_stats?.chsh_value_statistic,
        team.correlation_stats?.chsh_value_statistic_uncertainty
    );
    
    document.getElementById("modal-cross-term-chsh").innerHTML = formatStatWithUncertainty(
        team.correlation_stats?.cross_term_combination_statistic,
        team.correlation_stats?.cross_term_combination_statistic_uncertainty
    );
    
    // Populate correlation matrix
    const matrixTable = document.getElementById("correlation-matrix-table");
    matrixTable.innerHTML = "";
    
    if (team.correlation_matrix && team.correlation_labels) {
        // Create header row with labels
        const headerRow = document.createElement("tr");
        headerRow.innerHTML = "<th></th>"; // Empty corner cell
        
        for (const label of team.correlation_labels) {
            headerRow.innerHTML += `<th>${label}</th>`;
        }
        matrixTable.appendChild(headerRow);
        
        // Create data rows
        for (let i = 0; i < team.correlation_matrix.length; i++) {
            const row = document.createElement("tr");
            row.innerHTML = `<th>${team.correlation_labels[i]}</th>`;
            
            for (let j = 0; j < team.correlation_matrix[i].length; j++) {
                const [num, den] = team.correlation_matrix[i][j];
                let cellContent;
                
                if (den === 0) {
                    cellContent = "—";
                } else {
                    const value = num / den;
                    const uncertainty = 1 / Math.sqrt(den);
                    cellContent = formatStatWithUncertainty(value, uncertainty);
                }
                
                row.innerHTML += `<td>${cellContent}</td>`;
            }
            
            matrixTable.appendChild(row);
        }
    } else {
        matrixTable.innerHTML = "<tr><td>No correlation data available</td></tr>";
    }
    
    // Show modal
    document.getElementById("team-details-modal").style.display = "block";
}

// Refresh team details if modal is open
function refreshTeamDetailsIfOpen(teams) {
    if (currentTeamDetailsId) {
        const updatedTeam = teams.find(t => t.team_id === currentTeamDetailsId);
        if (updatedTeam) {
            showTeamDetails(currentTeamDetailsId);
        }
    }
}

// Close modal when clicking X or outside
document.querySelector(".close-modal").addEventListener("click", () => {
    document.getElementById("team-details-modal").style.display = "none";
    currentTeamDetailsId = null;
});

window.addEventListener("click", (event) => {
    const modal = document.getElementById("team-details-modal");
    if (event.target === modal) {
        modal.style.display = "none";
        currentTeamDetailsId = null;
    }
});

// Update metrics
function updateMetrics(activeTeams, totalAnswers, connectedPlayers) {
    if (typeof connectedPlayers === 'number') {
        connectedPlayersCountEl.textContent = connectedPlayers;
    }
    
    if (typeof totalAnswers === 'number') {
        totalResponsesCountEl.textContent = totalAnswers;
        currentAnswersCount = totalAnswers;
    }
}

// Handle answer log
let answerStreamEnabled = false;

function toggleAnswerStream() {
    answerStreamEnabled = !answerStreamEnabled;
    updateStreamingUI();
    socket.emit("toggle_answer_stream", { enabled: answerStreamEnabled });
}

function updateStreamingUI() {
    const toggleBtn = document.getElementById("toggle-answers-btn");
    const chevron = document.getElementById("toggle-chevron");
    
    if (answerStreamEnabled) {
        toggleBtn.textContent = "ON";
        toggleBtn.className = "toggle-on";
        chevron.textContent = "▼";
    } else {
        toggleBtn.textContent = "OFF";
        toggleBtn.className = "toggle-off";
        chevron.textContent = "▶";
    }
}

// Add new answer to log
socket.on("new_answer", (data) => {
    if (!answerStreamEnabled) return;
    
    const row = document.createElement("tr");
    const timestamp = new Date(data.timestamp).toLocaleTimeString();
    
    row.innerHTML = `
        <td>${timestamp}</td>
        <td>${data.team_name}</td>
        <td>${data.player_sid.substring(0, 6)}...</td>
        <td>${data.round_id}</td>
        <td>${data.item}</td>
        <td>${data.response ? "True" : "False"}</td>
    `;
    
    // Add to top of table
    if (answerLogTableBody.firstChild) {
        answerLogTableBody.insertBefore(row, answerLogTableBody.firstChild);
    } else {
        answerLogTableBody.appendChild(row);
    }
    
    // Limit to 100 rows
    while (answerLogTableBody.children.length > 100) {
        answerLogTableBody.removeChild(answerLogTableBody.lastChild);
    }
    
    // Hide "no answers" message
    noAnswersLogMsg.style.display = "none";
    
    // Update total count
    currentAnswersCount++;
    totalResponsesCountEl.textContent = currentAnswersCount;
});

// Update answer log with recent answers
function updateAnswerLog(answers) {
    if (!answers || !Array.isArray(answers) || !answerStreamEnabled) return;
    
    // Clear existing log if we're getting a full refresh
    if (answers.length > 0) {
        answerLogTableBody.innerHTML = "";
        noAnswersLogMsg.style.display = "none";
    }
    
    // Add answers in reverse order (newest first)
    for (let i = answers.length - 1; i >= 0; i--) {
        const data = answers[i];
        const row = document.createElement("tr");
        const timestamp = new Date(data.timestamp).toLocaleTimeString();
        
        row.innerHTML = `
            <td>${timestamp}</td>
            <td>${data.team_name}</td>
            <td>${data.player_sid.substring(0, 6)}...</td>
            <td>${data.round_id}</td>
            <td>${data.item}</td>
            <td>${data.response ? "True" : "False"}</td>
        `;
        
        answerLogTableBody.appendChild(row);
    }
    
    // Limit to 100 rows
    while (answerLogTableBody.children.length > 100) {
        answerLogTableBody.removeChild(answerLogTableBody.lastChild);
    }
}

// Filter and sort handlers
document.getElementById("show-inactive").addEventListener("change", () => {
    updateActiveTeams(lastReceivedTeams);
});

document.getElementById("sort-teams").addEventListener("change", () => {
    updateActiveTeams(lastReceivedTeams);
});

// Download data as CSV
function downloadData() {
    socket.emit("request_data_download", {}, (response) => {
        if (response && response.csv_data) {
            // Create blob and download
            const blob = new Blob([response.csv_data], { type: 'text/csv' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = 'chsh_game_data.csv';
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
        } else {
            alert("Error downloading data. Please try again.");
        }
    });
}

// Make functions available globally
window.showTeamDetails = showTeamDetails;
window.toggleAnswerStream = toggleAnswerStream;
window.downloadData = downloadData;
window.startGame = startGame;
window.togglePause = togglePause;
window.handleResetGame = handleResetGame;
window.requestDashboardRefresh = requestDashboardRefresh;

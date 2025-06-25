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
        
        // Display full server ID at the bottom
        const sessionInfo = document.getElementById('sessionInfo');
        if (sessionInfo) {
            const sessionIdSpan = sessionInfo.querySelector('.session-id');
            if (sessionIdSpan) {
                sessionIdSpan.textContent = instance_id;
            }
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
    
    // Only show "no teams" message if teams streaming is enabled
    if (teamsStreamEnabled) {
        noActiveTeamsMsg.style.display = "block";
    } else {
        noActiveTeamsMsg.style.display = "none";
    }
    
    // Only show "no answers" message if answer streaming is enabled
    if (answerStreamEnabled) {
        noAnswersLogMsg.style.display = "block";
    } else {
        noAnswersLogMsg.style.display = "none";
    }
    
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
    
    // Initialize streaming UI states
    updateStreamingUI();
    updateTeamsStreamingUI();
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
        startBtn.style.border = '2px solid #FFC107'; // Add visual feedback for confirmation

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
        startBtn.style.border = '2px solid #4CAF50'; // Add visual feedback for resetting
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
    
    // Only update teams if streaming is enabled
    if (teamsStreamEnabled) {
        updateActiveTeams(data.teams);
        // Refresh team details popup if open
        if (data.teams) {
            refreshTeamDetailsIfOpen(data.teams);
        }
    }
    
    updateAnswerLog(data.recent_answers); // Assuming backend sends recent answers on update
    
    // Update metrics using dedicated fields from backend (not dependent on teams streaming)
    updateMetrics(data.active_teams_count, data.ready_players_count, data.total_answers_count, data.connected_players_count);
    
    // Sync streaming state with server
    if (data.game_state && data.game_state.streaming_enabled !== undefined) {
        answerStreamEnabled = data.game_state.streaming_enabled;
        updateStreamingUI();
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
    
    // Only update teams if streaming is enabled
    if (teamsStreamEnabled) {
        updateActiveTeams(data.teams);
        // Refresh team details popup if open
        if (data.teams) {
            refreshTeamDetailsIfOpen(data.teams);
        }
    }
    
    // Use metrics provided by backend when available, otherwise calculate from teams data
    let activeTeamsCount, readyPlayersCount;
    
    if (typeof data.active_teams_count === 'number' && typeof data.ready_players_count === 'number') {
        // Backend provides metrics directly - use them for accuracy
        activeTeamsCount = data.active_teams_count;
        readyPlayersCount = data.ready_players_count;
    } else {
        // Fallback: calculate metrics from teams data (for backwards compatibility)
        // Use same definition as backend: active teams are those with is_active=true OR status='waiting_pair'
        const activeTeams = data.teams ? data.teams.filter(team => 
            team.is_active || team.status === 'waiting_pair'
        ) : [];
        activeTeamsCount = activeTeams.length;
        readyPlayersCount = activeTeams.reduce((count, team) => {
            return count + (team.player1_sid ? 1 : 0) + (team.player2_sid ? 1 : 0);
        }, 0);
    }
    
    updateMetrics(activeTeamsCount, readyPlayersCount, currentAnswersCount, data.connected_players_count);
});

function updateMetrics(activeTeamsCount, readyPlayersCount, totalAnswers, connectedCount) {
    // Update team metrics if provided
    if (typeof activeTeamsCount === 'number') {
        activeTeamsCountEl.textContent = activeTeamsCount;
    }
    
    if (typeof readyPlayersCount === 'number') {
        readyPlayersCountEl.textContent = readyPlayersCount;
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
    if (lastReceivedTeams && teamsStreamEnabled) {
        updateActiveTeams(lastReceivedTeams);
    }
});

// Add event listener for sort teams dropdown
document.getElementById('sort-teams').addEventListener('change', () => {
    if (lastReceivedTeams && teamsStreamEnabled) {
        updateActiveTeams(lastReceivedTeams);
    }
});

function updateActiveTeams(teams) {
    // If teams streaming is disabled, don't update the UI
    if (!teamsStreamEnabled) {
        return;
    }
    
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

    // --- BEGIN MODIFICATION: Determine top performers ---
    let highestBalancedTrTeamId = null;
    let maxBalancedTrValue = -Infinity;
    let highestChshTeamId = null;
    let maxChshValue = -Infinity;

    const eligibleTeams = teams.filter(team => team.min_stats_sig === true);

    eligibleTeams.forEach(team => {
        const stats = team.correlation_stats;

        // Calculate Balanced |Tr|
        if (stats && typeof stats.trace_average_statistic === 'number' && typeof stats.same_item_balance === 'number') {
            const traceAvg = stats.trace_average_statistic;
            const balance = stats.same_item_balance;
            const balancedTr = (traceAvg + balance) / 2;
            if (balancedTr > maxBalancedTrValue) {
                maxBalancedTrValue = balancedTr;
                highestBalancedTrTeamId = team.team_id;
            }
        }

        // Calculate CHSH Value
        if (stats && typeof stats.cross_term_combination_statistic === 'number') {
            const chshValue = stats.cross_term_combination_statistic;
            if (chshValue > maxChshValue) {
                maxChshValue = chshValue;
                highestChshTeamId = team.team_id;
            }
        }
    });
    // --- END MODIFICATION ---
    
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
        let baseStatus = team.min_stats_sig ? '✅' : '⏳';
        let awardsString = "";

        if (team.team_id === highestBalancedTrTeamId && highestBalancedTrTeamId !== null) {
            awardsString += "🎯";
        }
        if (team.team_id === highestChshTeamId && highestChshTeamId !== null) {
            awardsString += (awardsString ? " " : "") + "🏆";
        }
        statsCell.textContent = baseStatus + (awardsString ? " " + awardsString : "");
        statsCell.style.textAlign = 'center';
        
        // Add trace_avg column (now Trace Average Statistic)
        const traceAvgCell = row.insertCell();
        if (team.correlation_stats) {
            traceAvgCell.innerHTML = formatStatWithUncertainty(
                team.correlation_stats.trace_average_statistic,
                team.correlation_stats.trace_average_statistic_uncertainty
            );
            // Retain visual indicator logic if desired, e.g., based on nominal value
            if (typeof team.correlation_stats.trace_average_statistic === 'number' &&
                Math.abs(team.correlation_stats.trace_average_statistic) >= 0.5) { // Example, adjust as needed
                traceAvgCell.style.fontWeight = "bold";
                traceAvgCell.style.color = "#0022aa"; // Blue
            }
        } else {
            traceAvgCell.innerHTML = "—";
        }
        
        // Add Same Item Balance column
        const balanceCell = row.insertCell();
        if (team.correlation_stats && 
            team.correlation_stats.same_item_balance !== undefined && 
            team.correlation_stats.same_item_balance !== null && 
            !isNaN(team.correlation_stats.same_item_balance)) {
            try {
                const balanceValue = parseFloat(team.correlation_stats.same_item_balance);
                const balanceUncertainty = team.correlation_stats.same_item_balance_uncertainty !== undefined ? 
                                           parseFloat(team.correlation_stats.same_item_balance_uncertainty) : null;
                balanceCell.innerHTML = formatStatWithUncertainty(balanceValue, balanceUncertainty);
                
                // Add visual indicator for interesting values
                if (Math.abs(balanceValue) >= 0.5) {
                    balanceCell.style.fontWeight = "bold";
                    balanceCell.style.color = "#0022aa";                }
            } catch (e) {
                console.error("Error formatting same_item_balance", e);
                balanceCell.innerHTML = "Error";
            }
        } else {
            balanceCell.innerHTML = "—";
        }

        // Add Balanced Random column with robust error handling
        const balancedRandomCell = row.insertCell();
        if (team.correlation_stats && 
            team.correlation_stats.trace_average_statistic !== undefined && 
            team.correlation_stats.trace_average_statistic !== null && 
            !isNaN(team.correlation_stats.trace_average_statistic) &&
            team.correlation_stats.same_item_balance !== undefined && 
            team.correlation_stats.same_item_balance !== null && 
            !isNaN(team.correlation_stats.same_item_balance) &&
            team.correlation_stats.trace_average_statistic_uncertainty !== undefined &&
            team.correlation_stats.same_item_balance_uncertainty !== undefined) { 
            try {
                const traceAvg = parseFloat(team.correlation_stats.trace_average_statistic);
                const balance = parseFloat(team.correlation_stats.same_item_balance);
                const balancedRandom = (traceAvg + balance) / 2;
                
                const traceAvgUncInput = team.correlation_stats.trace_average_statistic_uncertainty;
                const balanceUncInput = team.correlation_stats.same_item_balance_uncertainty;
                let uncBalancedRandom = null;

                if (typeof traceAvgUncInput === 'number' && !isNaN(traceAvgUncInput) &&
                    typeof balanceUncInput === 'number' && !isNaN(balanceUncInput)) {
                    const traceAvgUnc = parseFloat(traceAvgUncInput);
                    const balanceUnc = parseFloat(balanceUncInput);
                    uncBalancedRandom = Math.sqrt(Math.pow(traceAvgUnc, 2) + Math.pow(balanceUnc, 2)) / 2;
                }
                
                balancedRandomCell.innerHTML = formatStatWithUncertainty(balancedRandom, uncBalancedRandom);
            } catch (e) {
                console.error("Error calculating or formatting balancedRandom", e);
                balancedRandomCell.innerHTML = "Error";
            }
        } else {
            balancedRandomCell.innerHTML = "—";
        }
        
        // Add CHSH Value column (which is now the Cross-Term Combination Statistic)
        const crossTermChshCell = row.insertCell(); // This cell now represents the single "CHSH Value"
        if (team.correlation_stats) {
            crossTermChshCell.innerHTML = formatStatWithUncertainty(
                team.correlation_stats.cross_term_combination_statistic,
                team.correlation_stats.cross_term_combination_statistic_uncertainty
            );
             if (typeof team.correlation_stats.cross_term_combination_statistic === 'number') {
                // Example: Highlight significant CHSH values
                if (Math.abs(team.correlation_stats.cross_term_combination_statistic) > 2) {
                    crossTermChshCell.style.fontWeight = "bold";
                    crossTermChshCell.style.color = team.correlation_stats.cross_term_combination_statistic > 2 ? "green" : "red"; // Green for >2, Red for < -2
                }
             }
        } else {
            crossTermChshCell.innerHTML = "—";
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
let teamsStreamEnabled = false;
const answerTable = document.getElementById('answer-log-table');
const noAnswersMsg = document.getElementById('no-answers-log');
const toggleBtn = document.getElementById('toggle-answers-btn');
const toggleChevron = document.getElementById('toggle-chevron');

const teamsTable = document.getElementById('active-teams-table');
const noTeamsMsg = document.getElementById('no-active-teams');
const teamsToggleBtn = document.getElementById('toggle-teams-btn');
const teamsToggleChevron = document.getElementById('teams-toggle-chevron');

// Initialize to OFF state
toggleBtn.textContent = 'OFF';
answerTable.style.display = 'none';
noAnswersMsg.style.display = 'none';
toggleChevron.textContent = '▶';

// Initialize teams streaming to OFF state
teamsToggleBtn.textContent = 'OFF';
teamsTable.style.display = 'none';
noTeamsMsg.style.display = 'none';
teamsToggleChevron.textContent = '▶';

function updateStreamingUI() {
    if (answerStreamEnabled) {
        toggleBtn.textContent = 'ON';
        answerTable.style.display = 'table';
        toggleChevron.textContent = '▼';
    } else {
        toggleBtn.textContent = 'OFF';
        answerTable.style.display = 'none';
        toggleChevron.textContent = '▶';
    }
}

function updateTeamsStreamingUI() {
    if (teamsStreamEnabled) {
        teamsToggleBtn.textContent = 'ON';
        teamsTable.style.display = 'table';
        teamsToggleChevron.textContent = '▼';
        
        // Show appropriate message based on teams data
        if (lastReceivedTeams && lastReceivedTeams.length > 0) {
            // Check if any teams will be displayed after filtering
            const showInactive = document.getElementById('show-inactive').checked;
            const filteredTeams = showInactive ? lastReceivedTeams : lastReceivedTeams.filter(team =>
                team.is_active || team.status === 'waiting_pair'
            );
            noTeamsMsg.style.display = filteredTeams.length === 0 ? 'block' : 'none';
        } else {
            noTeamsMsg.style.display = 'block';
        }
    } else {
        teamsToggleBtn.textContent = 'OFF';
        teamsTable.style.display = 'none';
        teamsToggleChevron.textContent = '▶';
        noTeamsMsg.style.display = 'none';
    }
}

function toggleAnswerStream() {
    answerStreamEnabled = !answerStreamEnabled;
    updateStreamingUI();
}

function toggleTeamsStream() {
    teamsStreamEnabled = !teamsStreamEnabled;
    updateTeamsStreamingUI();
    
    // Notify server about teams streaming preference
    socket.emit('set_teams_streaming', { enabled: teamsStreamEnabled });
    
    // If enabling, request current teams data
    if (teamsStreamEnabled) {
        socket.emit('request_teams_update');
    }
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
                new Date(answer.timestamp).toLocaleString().replace(/,/g, ' -'),
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
    const modalChshValue = document.getElementById('modal-chsh-value'); // New ID from HTML (was modal-chsh-stat2)
    const modalCrossTermChsh = document.getElementById('modal-cross-term-chsh'); // New ID from HTML (was modal-chsh-stat3)
    
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
        team.correlation_matrix.length > 0 && team.correlation_labels.length > 0 &&
        team.correlation_matrix.length === team.correlation_labels.length &&
        team.correlation_matrix.every(row => Array.isArray(row) && row.length === team.correlation_labels.length)) {
        
        try {
            const labels = team.correlation_labels;
            const numLabels = labels.length;
            const matrixData = team.correlation_matrix;

            // Create thead and tbody elements for better structure (optional but good practice)
            // However, to minimize changes to existing patterns, we'll append rows directly to the table.

            // Row 0: Player 2 Label
            const player2LabelRow = correlationTable.insertRow();
            player2LabelRow.insertCell(); // Empty cell for Player 1 vertical label column
            player2LabelRow.insertCell(); // Empty cell above Row Item Labels for Player 1
            const player2Th = document.createElement('th');
            player2Th.colSpan = numLabels;
            player2Th.textContent = 'Player 2';
            player2Th.style.textAlign = 'center';
            player2LabelRow.appendChild(player2Th);

            // Row 1: Column Item Labels (A, B, X, Y for Player 2)
            const columnItemLabelRow = correlationTable.insertRow();
            columnItemLabelRow.insertCell(); // Empty cell for Player 1 vertical label column
            const cornerTh = document.createElement('th'); // Empty top-left cell of the actual data matrix part
            columnItemLabelRow.appendChild(cornerTh);

            labels.forEach(label => {
                const th = document.createElement('th');
                th.textContent = label || '?';
                th.classList.add('corr-matrix-col-item-label'); // Added class
                columnItemLabelRow.appendChild(th);
            });
            
            // Add data rows
            matrixData.forEach((rowData, rowIndex) => {
                if (rowIndex >= numLabels) return; // Should be caught by earlier checks

                const dataRow = correlationTable.insertRow();

                // Player 1 Vertical Label (only in the first data row, spans all data rows)
                if (rowIndex === 0) {
                    const player1Th = document.createElement('th');
                    player1Th.rowSpan = numLabels;
                    player1Th.textContent = 'Player 1';
                    player1Th.classList.add('corr-matrix-player1-label');
                    dataRow.appendChild(player1Th);
                }

                // Row Item Label (A, B, X, Y for Player 1)
                const rowItemLabelTh = document.createElement('th');
                rowItemLabelTh.textContent = labels[rowIndex] || '?';
                rowItemLabelTh.classList.add('corr-matrix-row-item-label'); // Added class
                dataRow.appendChild(rowItemLabelTh);
                
                // Add correlation values
                if (Array.isArray(rowData)) {
                    rowData.forEach(cellTuple => { // cellTuple is [numerator, denominator]
                        const cell = dataRow.insertCell();
                        cell.classList.add('corr-matrix-data-cell'); // Added class
                        if (Array.isArray(cellTuple) && cellTuple.length === 2) {
                            const num = parseFloat(cellTuple[0]);
                            const den = parseFloat(cellTuple[1]);

                            if (isNaN(num) || isNaN(den)) {
                                cell.textContent = "—"; // Invalid data in tuple
                            } else if (den !== 0) {
                                cell.textContent = (num / den).toFixed(3);
                            } else if (num !== 0 && den === 0) {
                                cell.textContent = "Inf"; // Infinity
                            } else { // num is 0 and den is 0, or other unhandled cases
                                cell.textContent = "—"; // Or "0.000" if 0/0 should be 0
                            }
                        } else {
                             // Fallback if cellTuple is not the expected [num, den] array
                            cell.textContent = "—";
                        }
                    });
                } else {
                    // Fill row with placeholders if rowData is not an array
                    for (let i = 0; i < numLabels; i++) {
                        const cell = dataRow.insertCell();
                        cell.classList.add('corr-matrix-data-cell'); // Added class
                        cell.textContent = "—";
                    }
                }
            });
        } catch (error) {
            console.error("Error rendering correlation matrix:", error);
            correlationTable.innerHTML = ''; // Clear partially rendered table on error
            const errorRow = correlationTable.insertRow();
            const errorCell = errorRow.insertCell();
            // Adjust colspan based on the new table structure: 1 (P1) + 1 (Row Labels) + numLabels (Data)
            errorCell.colSpan = team.correlation_labels ? team.correlation_labels.length + 2 : 3; 
            errorCell.textContent = "Error rendering correlation data";
            errorCell.style.textAlign = "center";
            errorCell.style.padding = "10px";
        }
    } else {
        const errorRow = correlationTable.insertRow();
        const errorCell = errorRow.insertCell();
        // Adjust colspan based on the new table structure (assuming 0 labels if none provided)
        errorCell.colSpan = team.correlation_labels ? team.correlation_labels.length + 2 : 2;
        errorCell.textContent = "No correlation data available";
        errorCell.classList.add('corr-matrix-error-cell');
    }

    // Populate CHSH Statistics in modal
    if (team.correlation_stats) {
        modalChshValue.innerHTML = formatStatWithUncertainty(
            team.correlation_stats.chsh_value_statistic,
            team.correlation_stats.chsh_value_statistic_uncertainty
        );
        modalCrossTermChsh.innerHTML = formatStatWithUncertainty(
            team.correlation_stats.cross_term_combination_statistic,
            team.correlation_stats.cross_term_combination_statistic_uncertainty
        );
    } else {
        modalChshValue.innerHTML = "—";
        modalCrossTermChsh.innerHTML = "—";
    }
}

// Function to close team details modal
function closeTeamDetails() {
    const modal = document.getElementById('team-details-modal');
    currentlyViewedTeamId = null;
    isDetailsPopupOpen = false;
    if (modal) {
        modal.style.display = 'none';
    }
    
    // Clean up event listener
    if (window._modalClickHandler) {
        window.removeEventListener('click', window._modalClickHandler);
        window._modalClickHandler = null; // Clear the stored handler
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
    currentlyViewedTeamId = team.team_id;
    isDetailsPopupOpen = true;

    // Show the modal first
    const modal = document.getElementById('team-details-modal');

    // Re‑use the existing helper to populate every field (team info, CHSH stats,
    // correlation matrix, etc.) instead of duplicating that logic here.
    updateModalContent(team);

    modal.style.display = 'block';

    // Close‑button handler
    const closeModalBtn = modal.querySelector('.close-modal');
    closeModalBtn.onclick = closeTeamDetails;

    // Click‑outside‑to‑close logic (ensure only one listener)
    if (window._modalClickHandler) {
        window.removeEventListener('click', window._modalClickHandler);
    }
    window._modalClickHandler = function (event) {
        if (event.target === modal) {
            closeTeamDetails();
        }
    };
    window.addEventListener('click', window._modalClickHandler);
}

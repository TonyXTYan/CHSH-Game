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
const totalPlayersCountEl = document.getElementById("total-players-count");
const totalAnswersCountEl = document.getElementById("total-answers-count");

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
    totalPlayersCountEl.textContent = "0";
    totalAnswersCountEl.textContent = "0";
}

socket.on("disconnect", () => {
    connectionStatusDiv.textContent = "Disconnected from server";
    connectionStatusDiv.className = "status-disconnected";
    // Clear current state
    activeTeamsTableBody.innerHTML = "";
    noActiveTeamsMsg.style.display = "block";
    activeTeamsCountEl.textContent = "0";
    totalPlayersCountEl.textContent = "0";
    currentAnswersCount = 0;
    totalAnswersCountEl.textContent = "0";
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
    totalAnswersCountEl.textContent = "0";
    // Reset game button state
    const startBtn = document.getElementById("start-game-btn");
    resetButtonToInitialState(startBtn);
    // Clear any localStorage data
    localStorage.removeItem('chsh_game_state');
});

// Handle page load - clear any stale state
window.addEventListener('load', () => {
    localStorage.removeItem('chsh_game_state');
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
    startBtn.disabled = false;
    startBtn.textContent = "Reset game stats";
    startBtn.className = "reset-game";
    startBtn.onclick = handleResetGame;
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
    
    answerLogTableBody.innerHTML = "";
    noAnswersLogMsg.style.display = "block";
    currentAnswersCount = 0;
    totalAnswersCountEl.textContent = "0";
    
    socket.emit('dashboard_join');
});

function handleResetGame() {
    const startBtn = document.getElementById("start-game-btn");
    if (!startBtn || startBtn.disabled) {
        console.error("Invalid button state");
        return;
    }

    if (!confirmingStop) {
        // Start confirmation phase
        
        // Ensure any previous mouseout listener is removed before adding a new one.
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
        
        startBtn.textContent = `Are you sure? (${secondsLeft})`;
        
        countdownInterval = setInterval(() => {
            if (!countdownActive) { // If cleanup was called (e.g., by mouseout)
                clearInterval(countdownInterval); // Ensure interval is stopped
                countdownInterval = null;
                return;
            }
            
            secondsLeft--;
            if (secondsLeft > 0) {
                if (confirmingStop) {  // Only update if still confirming
                    startBtn.textContent = `Are you sure? (${secondsLeft})`;
                }
            } else {
                // Countdown finished, cleanup.
                cleanupResetConfirmation(startBtn); 
            }
        }, 1000);

        // Define and add the mouseout listener for this confirmation attempt
        currentConfirmMouseOutListener = () => {
            cleanupResetConfirmation(startBtn); // This will also remove this listener
        };
        startBtn.addEventListener('mouseout', currentConfirmMouseOutListener);
        
        // Add beforeunload listener for page navigation during confirmation
        window.addEventListener('beforeunload', () => {
            cleanupResetConfirmation(startBtn);
        }, { once: true });
        
    } else {
        // Confirmation click received (confirmingStop is true)
        
        // Cleanup the confirmation UI (timer, "Are you sure?" text, listeners)
        // This will also set confirmingStop = false and remove currentConfirmMouseOutListener.
        cleanupResetConfirmation(startBtn);
        
        // Start actual reset process
        startBtn.disabled = true;
        startBtn.textContent = "Resetting...";
        // confirmingStop is already false due to cleanupResetConfirmation.
        
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
    if (data.game_state) {
        console.log(`Game state update - started: ${data.game_state.started}, streaming: ${data.game_state.streaming_enabled}`);
    }
    updateActiveTeams(data.active_teams);
    updateAnswerLog(data.recent_answers); // Assuming backend sends recent answers on update
    updateMetrics(data.active_teams, data.total_answers_count);
    
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

socket.on("new_answer_for_dashboard", (answer) => {
    console.log("New answer for dashboard:", answer);
    currentAnswersCount++;
    totalAnswersCountEl.textContent = currentAnswersCount;
    
    if (answerStreamEnabled) {
        addAnswerToLog(answer);
    } else {
        console.log("Answer received but streaming is disabled - not showing in log");
    }
});

socket.on("team_status_changed_for_dashboard", (teams_data) => {
    console.log("Team status changed for dashboard:", teams_data);
    updateActiveTeams(teams_data);
    updateMetrics(teams_data, currentAnswersCount);
});

function updateMetrics(teams, totalAnswers) {
    if (teams) {
        activeTeamsCountEl.textContent = teams.length;
        let playerCount = 0;
        teams.forEach(team => {
            if(team.player1_sid) playerCount++;
            if(team.player2_sid) playerCount++;
        });
        totalPlayersCountEl.textContent = playerCount;
    }
    if (totalAnswers !== undefined) {
        currentAnswersCount = totalAnswers;
        totalAnswersCountEl.textContent = currentAnswersCount;
    }
}

function updateActiveTeams(teams) {
    activeTeamsTableBody.innerHTML = ""; // Clear existing rows
    if (teams && teams.length > 0) {
        noActiveTeamsMsg.style.display = "none";
        teams.forEach(team => {
            const row = activeTeamsTableBody.insertRow();
            row.insertCell().textContent = team.team_name;
            row.insertCell().textContent = team.team_id;
            const sid1Cell = row.insertCell();
            sid1Cell.textContent = team.player1_sid ? team.player1_sid.substring(0, 8) + "..." : 'N/A';
            sid1Cell.style.fontFamily = 'monospace';
            const sid2Cell = row.insertCell();
            sid2Cell.textContent = team.player2_sid ? team.player2_sid.substring(0, 8) + "..." : 'N/A';
            sid2Cell.style.fontFamily = 'monospace';
            row.insertCell().textContent = team.current_round_number || 0;
            const statsCell = row.insertCell();
            statsCell.textContent = team.min_stats_sig ? '✅' : '⏳';
            statsCell.style.textAlign = 'center';
            const hash1Cell = row.insertCell();
            hash1Cell.textContent = team.history_hash1;
            hash1Cell.style.fontFamily = 'monospace';
            const hash2Cell = row.insertCell();
            hash2Cell.textContent = team.history_hash2;
            hash2Cell.style.fontFamily = 'monospace';
        });
    } else {
        noActiveTeamsMsg.style.display = "block";
    }
}

function addAnswerToLog(answer) {
    noAnswersLogMsg.style.display = "none";
    const row = answerLogTableBody.insertRow(0); // Add to top
    row.insertCell().textContent = new Date(answer.timestamp).toLocaleTimeString();
    row.insertCell().textContent = answer.team_name;
    row.insertCell().textContent = answer.player_session_id.substring(0, 8) + "...";
    row.insertCell().textContent = answer.question_round_id;
    row.insertCell().textContent = answer.assigned_item;
    row.insertCell().textContent = answer.response_value;
    // Limit log size if needed
    if (answerLogTableBody.rows.length > 100) { // Keep last 100 answers
        answerLogTableBody.deleteRow(-1);
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
        csvRows.push(['Timestamp', 'Team Name', 'Team ID', 'Player ID', 'Round ID', 'Question Item (A/B/C/D)', 'Answer (True/False)']);
        
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

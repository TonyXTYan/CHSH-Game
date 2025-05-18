// Dashboard-specific socket handlers and UI functions

let socket; // Make socket available in wider scope
let answerStreamEnabled = false;
let confirmingStop = false;
let countdownActive = false;
let countdownInterval = null;
let currentConfirmMouseOutListener = null;
let resetTimeout = null;
let currentAnswersCount = 0;

// Initialize dashboard socket connection
function initializeDashboardSocket() {
    // Initialize socket with ping timeout settings
    socket = io(window.location.origin, {
        pingTimeout: 60000,
        pingInterval: 25000
    });
    
    // Attach event listeners to buttons
    document.getElementById('start-game-btn').addEventListener('click', startGame);
    document.getElementById('download-data-btn').addEventListener('click', downloadData);
    document.getElementById('toggle-answers-btn').addEventListener('click', (event) => {
        event.stopPropagation();
        toggleAnswerStream();
    });
    document.querySelector('.answer-log-header').addEventListener('click', toggleAnswerStream);

    // DOM elements
    const connectionStatusDiv = document.getElementById("connection-status-dash");
    const activeTeamsCountEl = document.getElementById("active-teams-count");
    const totalPlayersCountEl = document.getElementById("total-players-count");
    const totalAnswersCountEl = document.getElementById("total-answers-count");
    const activeTeamsTableBody = document.querySelector("#active-teams-table tbody");
    const noActiveTeamsMsg = document.getElementById("no-active-teams");
    const answerLogTableBody = document.querySelector("#answer-log-table tbody");
    const noAnswersLogMsg = document.getElementById("no-answers-log");

    // Handle page visibility changes
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') {
            socket.emit('dashboard_join');
        }
    });

    // Keep socket alive
    setInterval(() => {
        if (socket.connected) {
            socket.emit('keep_alive');
        }
    }, 30000);

    // Socket event handlers
    socket.on("connect", async () => {
        connectionStatusDiv.textContent = "Connected to server";
        connectionStatusDiv.className = "status-connected";
        
        try {
            const response = await fetch('/api/server/id');
            const {instance_id} = await response.json();
            const lastId = localStorage.getItem('server_instance_id');
            if (lastId !== instance_id) {
                clearAllUITables();
                localStorage.setItem('server_instance_id', instance_id);
            }
        } catch (error) {
            console.error('Error checking server ID:', error);
        }
        
        const startBtn = document.getElementById("start-game-btn");
        resetButtonToInitialState(startBtn);
        socket.emit("dashboard_join");
    });

    socket.on("disconnect", () => {
        connectionStatusDiv.textContent = "Disconnected from server";
        connectionStatusDiv.className = "status-disconnected";
        clearTeamUI();
    });

    socket.on("server_shutdown", () => {
        connectionStatusDiv.textContent = "Server is shutting down";
        connectionStatusDiv.className = "status-disconnected";
        clearAllUITables();
        const startBtn = document.getElementById("start-game-btn");
        resetButtonToInitialState(startBtn);
        localStorage.removeItem('chsh_game_state');
    });

    socket.on("dashboard_update", (data) => {
        updateActiveTeams(data.active_teams);
        updateAnswerLog(data.recent_answers);
        updateMetrics(data.active_teams, data.total_answers_count);
        
        if (data.game_state && data.game_state.streaming_enabled !== undefined) {
            answerStreamEnabled = data.game_state.streaming_enabled;
            updateStreamingUI();
        }
        
        const startBtn = document.getElementById("start-game-btn");
        if (!confirmingStop) {
            if (data.game_state) {
                if (data.game_state.started && startBtn.textContent === "Start Game") {
                    updateGameButtonToReset(startBtn);
                } else if (!data.game_state.started && startBtn.textContent === "Reset game stats") {
                    resetButtonToInitialState(startBtn);
                }
            }
        }
    });

    socket.on("new_answer_for_dashboard", (answer) => {
        currentAnswersCount++;
        totalAnswersCountEl.textContent = currentAnswersCount;
        if (answerStreamEnabled) {
            addAnswerToLog(answer);
        }
    });

    socket.on("team_status_changed_for_dashboard", (teams_data) => {
        updateActiveTeams(teams_data);
        updateMetrics(teams_data, currentAnswersCount);
    });

    socket.on("game_started", () => {
        const startBtn = document.getElementById("start-game-btn");
        const gameControlText = document.getElementById("game-control-text");
        cleanupResetConfirmation(startBtn);
        gameControlText.textContent = "Game in progress";
        updateGameButtonToReset(startBtn);
    });

    socket.on("game_reset_complete", () => {
        const startBtn = document.getElementById("start-game-btn");
        const gameControlText = document.getElementById("game-control-text");
        cleanupResetConfirmation(startBtn);
        resetButtonToInitialState(startBtn);
        gameControlText.textContent = "Game Control";
        answerLogTableBody.innerHTML = "";
        noAnswersLogMsg.style.display = "block";
        currentAnswersCount = 0;
        totalAnswersCountEl.textContent = "0";
        socket.emit('dashboard_join');
    });

    socket.on("error", (data) => {
        console.error("Socket Error:", data);
        connectionStatusDiv.textContent = `Error: ${data.message}`;
        connectionStatusDiv.className = "status-disconnected";
        const startBtn = document.getElementById("start-game-btn");
        if (startBtn && startBtn.disabled) {
            resetButtonToInitialState(startBtn);
        }
    });

    // Initialize streaming UI
    const answerTable = document.getElementById('answer-log-table');
    const toggleBtn = document.getElementById('toggle-answers-btn');
    const toggleChevron = document.getElementById('toggle-chevron');
    toggleBtn.textContent = 'OFF';
    toggleBtn.className = 'toggle-off';
    answerTable.style.display = 'none';
    noAnswersLogMsg.style.display = 'none';
    toggleChevron.textContent = '▶';

    // Clear any stale state
    window.addEventListener('load', () => {
        localStorage.removeItem('chsh_game_state');
    });
}

// UI Update Functions
function updateActiveTeams(teams) {
    const activeTeamsTableBody = document.querySelector("#active-teams-table tbody");
    const noActiveTeamsMsg = document.getElementById("no-active-teams");
    
    activeTeamsTableBody.innerHTML = "";
    if (teams && teams.length > 0) {
        noActiveTeamsMsg.style.display = "none";
        teams.forEach(team => {
            const row = activeTeamsTableBody.insertRow();
            row.insertCell().textContent = team.team_name;
            row.insertCell().textContent = team.team_id;
            row.insertCell().textContent = team.player1_sid ? team.player1_sid.substring(0, 8) + "..." : 'N/A';
            row.insertCell().textContent = team.player2_sid ? team.player2_sid.substring(0, 8) + "..." : 'N/A';
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
    const answerLogTableBody = document.querySelector("#answer-log-table tbody");
    const noAnswersLogMsg = document.getElementById("no-answers-log");
    
    noAnswersLogMsg.style.display = "none";
    const row = answerLogTableBody.insertRow(0);
    row.insertCell().textContent = new Date(answer.timestamp).toLocaleTimeString();
    row.insertCell().textContent = answer.team_name;
    row.insertCell().textContent = answer.player_session_id.substring(0, 8) + "...";
    row.insertCell().textContent = answer.question_round_id;
    row.insertCell().textContent = answer.assigned_item;
    row.insertCell().textContent = answer.response_value;
    
    if (answerLogTableBody.rows.length > 100) {
        answerLogTableBody.deleteRow(-1);
    }
}

function updateAnswerLog(answers) {
    if (answers && answers.length > 0) {
        const noAnswersLogMsg = document.getElementById("no-answers-log");
        noAnswersLogMsg.style.display = "none";
        answers.forEach(addAnswerToLog);
    }
}

function updateMetrics(teams, totalAnswers) {
    const activeTeamsCountEl = document.getElementById("active-teams-count");
    const totalPlayersCountEl = document.getElementById("total-players-count");
    const totalAnswersCountEl = document.getElementById("total-answers-count");
    
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

function updateStreamingUI() {
    const toggleBtn = document.getElementById('toggle-answers-btn');
    const answerTable = document.getElementById('answer-log-table');
    const toggleChevron = document.getElementById('toggle-chevron');
    
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

// Game Control Functions
function resetButtonToInitialState(btn) {
    if (!btn) return;
    btn.disabled = false;
    btn.textContent = "Start Game";
    btn.className = "";
    btn.onclick = startGame;
    confirmingStop = false;
    document.getElementById("game-control-text").textContent = "Game Control";
}

function updateGameButtonToReset(btn) {
    btn.disabled = false;
    btn.textContent = "Reset game stats";
    btn.className = "reset-game";
    btn.onclick = handleResetGame;
}

function cleanupResetConfirmation(startBtn) {
    countdownActive = false;
    if (countdownInterval) {
        clearInterval(countdownInterval);
        countdownInterval = null;
    }

    if (startBtn && currentConfirmMouseOutListener) {
        startBtn.removeEventListener('mouseout', currentConfirmMouseOutListener);
        currentConfirmMouseOutListener = null;
    }

    let wasConfirming = confirmingStop;
    confirmingStop = false;

    if (wasConfirming && startBtn) {
        startBtn.textContent = "Reset game stats";
        startBtn.className = "reset-game";
    }
}

function handleResetGame() {
    const startBtn = document.getElementById("start-game-btn");
    if (!startBtn || startBtn.disabled) return;

    if (!confirmingStop) {
        if (currentConfirmMouseOutListener && startBtn) {
            startBtn.removeEventListener('mouseout', currentConfirmMouseOutListener);
            currentConfirmMouseOutListener = null;
        }
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
            if (!countdownActive) {
                clearInterval(countdownInterval);
                countdownInterval = null;
                return;
            }
            
            secondsLeft--;
            if (secondsLeft > 0) {
                if (confirmingStop) {
                    startBtn.textContent = `Are you sure? (${secondsLeft})`;
                }
            } else {
                cleanupResetConfirmation(startBtn);
            }
        }, 1000);

        currentConfirmMouseOutListener = () => {
            cleanupResetConfirmation(startBtn);
        };
        startBtn.addEventListener('mouseout', currentConfirmMouseOutListener);
        
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

function startResetTimeout() {
    clearTimeout(resetTimeout);
    resetTimeout = setTimeout(() => {
        const startBtn = document.getElementById("start-game-btn");
        if (startBtn && startBtn.disabled) {
            resetButtonToInitialState(startBtn);
        }
    }, 5000);
}

function clearAllUITables() {
    const activeTeamsTableBody = document.querySelector("#active-teams-table tbody");
    const answerLogTableBody = document.querySelector("#answer-log-table tbody");
    const noActiveTeamsMsg = document.getElementById("no-active-teams");
    const noAnswersLogMsg = document.getElementById("no-answers-log");
    const activeTeamsCountEl = document.getElementById("active-teams-count");
    const totalPlayersCountEl = document.getElementById("total-players-count");
    const totalAnswersCountEl = document.getElementById("total-answers-count");
    
    activeTeamsTableBody.innerHTML = "";
    answerLogTableBody.innerHTML = "";
    noActiveTeamsMsg.style.display = "block";
    noAnswersLogMsg.style.display = "block";
    activeTeamsCountEl.textContent = "0";
    totalPlayersCountEl.textContent = "0";
    totalAnswersCountEl.textContent = "0";
}

function clearTeamUI() {
    const activeTeamsTableBody = document.querySelector("#active-teams-table tbody");
    const noActiveTeamsMsg = document.getElementById("no-active-teams");
    const activeTeamsCountEl = document.getElementById("active-teams-count");
    const totalPlayersCountEl = document.getElementById("total-players-count");
    const totalAnswersCountEl = document.getElementById("total-answers-count");
    
    activeTeamsTableBody.innerHTML = "";
    noActiveTeamsMsg.style.display = "block";
    activeTeamsCountEl.textContent = "0";
    totalPlayersCountEl.textContent = "0";
    currentAnswersCount = 0;
    totalAnswersCountEl.textContent = "0";
}

// Public functions
function toggleAnswerStream() {
    answerStreamEnabled = !answerStreamEnabled;
    updateStreamingUI();
}

function startGame() {
    const startBtn = document.getElementById("start-game-btn");
    if (startBtn && !startBtn.disabled) {
        startBtn.disabled = true;
        socket.emit("start_game");
    }
}

async function downloadData() {
    try {
        const response = await fetch('/api/dashboard/data');
        if (!response.ok) throw new Error('Network response was not ok');
        const data = await response.json();
        
        const csvRows = [];
        csvRows.push(['Timestamp', 'Team Name', 'Team ID', 'Player ID', 'Round ID', 'Question Item (A/B/C/D)', 'Answer (True/False)']);
        
        data.answers.forEach(answer => {
            csvRows.push([
                new Date(answer.timestamp).toLocaleString(),
                answer.team_name,
                answer.team_id,
                answer.player_session_id,
                answer.question_round_id,
                answer.assigned_item,
                answer.response_value
            ]);
        });
        
        const csvContent = csvRows.map(row => row.join(',')).join('\n');
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

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', initializeDashboardSocket);

# CHSH Game

## Project Overview

The CHSH Game is a real-time, interactive web application designed to demonstrate concepts related to the Clauser-Horne-Shimony-Holt (CHSH) inequality, often discussed in the context of quantum mechanics and Bell's theorem. The game involves participants forming teams and answering a series of true/false questions, while a presenter dashboard monitors game progress, team statistics, and controls the game flow.

The application features two main interfaces:
*   **Participant Client:** Allows users to create or join teams, and once paired, answer questions presented to them.
*   **Presenter Dashboard:** Provides a comprehensive overview of active teams, player counts, game statistics (including CHSH-related metrics), and controls to manage the game (start, pause, reset).

## Features

### Participant Client (`index.html`, `app.js`)
*   **Team Creation:** Users can create new teams by providing a team name.
*   **Team Joining:** Users can join existing active teams or reactivate previously inactive teams.
*   **Real-time Updates:** Dynamically updates available teams and game status.
*   **Question Answering:** Once a team is paired and the game starts, participants receive items (A, B, X, or Y) and must answer "True" or "False".
*   **Status Messages:** Provides feedback on connection status, team status, and game events.
*   **Session Management:** Displays a unique session ID for each participant.

### Presenter Dashboard (`dashboard.html`, `dashboard.js`)
*   **Game Control:**
    *   **Start Game:** Initiates the game for all paired teams.
    *   **Pause/Resume Game:** Allows the presenter to temporarily halt and resume the game.
    *   **Reset Game Stats:** Clears current game statistics and round data, preparing for a new game session.
*   **Live Monitoring:**
    *   **Active Teams Count:** Displays the number of currently active teams.
    *   **Player Counts:** Shows total connected players and paired (ready) players.
    *   **Total Responses:** Tracks the cumulative number of answers submitted.
*   **Team Statistics Table:**
    *   Lists all teams (active and optionally inactive).
    *   Displays team status (active, waiting for pair, inactive).
    *   Shows current round number for each team.
    *   Indicates statistical significance (`min_stats_sig`).
    *   Calculates and displays key metrics:
        *   **Trace Average (`|<Tr>|`)**: Average of diagonal elements of the correlation matrix.
        *   **Balance**: Metric related to the consistency of answers for the same item.
        *   **Balanced `|<Tr>|`**: A combined metric of trace average and balance.
        *   **CHSH Value**: The primary statistic related to the CHSH inequality, calculated from cross-term correlations.
    *   Provides a "View Details" button for each team to inspect:
        *   Team and Player SIDs.
        *   History Hashes (SHA-256, MD5 - currently disabled in backend).
        *   Detailed Correlation Matrix.
        *   Specific CHSH statistics (Actual CHSH Value, Cross-Term CHSH).
*   **Live Answer Log:** Streams answers from participants in real-time, showing timestamp, team, player, round, item, and response. Can be toggled on/off.
*   **Data Download:** Allows the presenter to download all game data (answers) as a CSV file.
*   **Connection Status:** Indicates the dashboard's connection state to the server.
*   **Responsive UI:** Adapts to different screen sizes.

### Backend & Core Logic
*   **Real-time Communication:** Utilizes Flask-SocketIO for bidirectional communication between the server and clients.
*   **State Management:** In-memory state (`src/state.py`) tracks active teams, players, and game status.
*   **Database Integration:** Uses SQLAlchemy for data persistence.
    *   Models: `Teams`, `Answers`, `PairQuestionRounds`.
    *   Supports SQLite (default) and PostgreSQL.
*   **Game Logic (`src/game_logic.py`):**
    *   Manages round progression for teams.
    *   Selects question items (A, B, X, Y) for players, aiming for a target number of repeats for each item combination.
*   **Statistical Calculations (`src/sockets/dashboard.py`):**
    *   Computes correlation matrices for each team based on answers.
    *   Calculates CHSH values and other relevant statistics, including uncertainties using the `uncertainties` library.
*   **Server Initialization (`src/main.py`):**
    *   Cleans up old data (answers, rounds, inactive teams) upon server startup.
    *   Assigns a unique server instance ID.

## Technologies Used

*   **Backend:**
    *   Python 3
    *   Flask: Micro web framework.
    *   Flask-SocketIO: For real-time WebSocket communication.
    *   Flask-SQLAlchemy: ORM for database interaction.
    *   Eventlet: Asynchronous networking library for SocketIO.
    *   `uncertainties`: Python library for calculations with uncertainties.
*   **Frontend:**
    *   HTML5
    *   CSS3
    *   JavaScript (ES6+)
    *   Socket.IO Client: For client-side WebSocket communication.
*   **Database:**
    *   SQLite (default development database)
    *   PostgreSQL (configurable for production)
*   **Analytics:**
    *   Google Analytics (gtag.js) integrated into HTML pages.

## Project Structure

```
CHSH-Game/
├── .gitignore
├── Dockerfile
├── README.md
├── requirements.txt
├── wsgi.py
├── src/
│   ├── __init__.py
│   ├── config.py           # Flask app, SocketIO, DB configuration
│   ├── game_logic.py       # Core game round and question logic
│   ├── main.py             # Application entry point, server startup
│   ├── state.py            # In-memory application state
│   ├── models/
│   │   ├── __init__.py
│   │   ├── quiz_models.py  # SQLAlchemy models for game (Teams, Answers, Rounds)
│   │   └── user.py         # SQLAlchemy model for User (seems separate from core game)
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── static.py       # Flask routes for serving static files (frontend)
│   │   └── user.py         # Flask routes for user CRUD (seems separate)
│   ├── sockets/
│   │   ├── __init__.py
│   │   ├── dashboard.py    # SocketIO handlers for presenter dashboard
│   │   ├── game.py         # SocketIO handlers for game events (e.g., submit_answer)
│   │   └── team_management.py # SocketIO handlers for team creation, joining, leaving
│   └── static/             # Frontend assets
│       ├── app.js              # JS for participant client
│       ├── dashboard.css       # CSS for presenter dashboard
│       ├── dashboard.html      # HTML for presenter dashboard
│       ├── dashboard.js        # JS for presenter dashboard
│       ├── index.html          # HTML for participant client
│       ├── socket-handlers.js  # Shared JS for client-side SocketIO event handling
│       └── styles.css          # CSS for participant client
└── ... (tests, design docs, etc.)
```

## Setup and Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/TonyXTYan/CHSH-Game.git
    cd CHSH-Game
    ```
2.  **Create and activate a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Configure Environment Variables (optional, defaults are provided):**
    *   `SECRET_KEY`: A secret key for Flask session management.
    *   `DATABASE_URL`: Database connection string (e.g., `postgresql://user:password@host:port/database` or defaults to `sqlite:///quiz_app.db`).
5.  **Run the application:**
    ```bash
    python src/main.py
    ```
    The application will typically be available at `http://localhost:5000`.

## Usage

*   **Participant Client:** Open a web browser and navigate to `http://localhost:5000/`.
    *   Enter a team name to create a new team or select an existing team to join/reactivate.
    *   Wait for a partner if your team is not full.
    *   Once paired and the game starts, you will receive items (A, B, X, or Y) and must choose "True" or "False".
*   **Presenter Dashboard:** Open a web browser and navigate to `http://localhost:5000/dashboard`.
    *   Monitor connected teams and players.
    *   Use the "Start Game" button to begin the game for all paired teams.
    *   Use "Pause/Resume" and "Reset game stats" as needed.
    *   View live statistics and the answer log.
    *   Download game data using the "Download CSV" button.

## Key Functionality Details

### Team Management
Players connect to the server and can either create a new team or join an existing one. The `team_management.py` socket handlers manage these interactions, updating the central `state` and the database. Teams can be active (with 0, 1, or 2 players) or inactive (stored in the DB, can be reactivated).

### Game Flow
Once a presenter starts the game via the dashboard, `game_logic.py` is invoked for each paired team to `start_new_round_for_pair`. This function:
1.  Increments the team's round number.
2.  Selects a pair of items (e.g., (A, X), (B, Y)) for the two players in the team. The selection strategy aims to ensure each of the 16 possible item combinations (AA, AB, AX, AY, BA, ..., YY) is presented a `TARGET_COMBO_REPEATS` number of times, with some randomization.
3.  Stores this round information in the `PairQuestionRounds` database table.
4.  Emits a `new_question` event via Socket.IO to each player with their assigned item and the round ID.

When a player submits an answer (`submit_answer` in `sockets/game.py`):
1.  The answer (item, True/False) is recorded in the `Answers` database table.
2.  The dashboard is updated with the new answer.
3.  If both players in a team have answered, `round_complete` is emitted, and `start_new_round_for_pair` is called again to proceed to the next round for that team.

### Dashboard Statistics
The dashboard (`sockets/dashboard.py`) periodically fetches data and computes statistics:
*   **Correlation Matrix:** For each team, a 4x4 matrix is computed based on the answers. The (i, j)-th cell represents the correlation between Player 1 being assigned item `i` and Player 2 being assigned item `j`. Correlation is +1 if answers match (True/True or False/False) and -1 if they differ. The matrix stores (numerator, denominator) for each cell, where numerator is the sum of correlations and denominator is the count of such pairings.
*   **Trace Average (`|<Tr>|`)**: The absolute average of the diagonal elements of the correlation matrix.
*   **Same Item Balance**: Measures how balanced (close to 0.5 probability for True/False) the responses are when both players receive the same item.
*   **Balanced `|<Tr>|`**: A combination of Trace Average and Same Item Balance.
*   **CHSH Value**: Calculated using the CHSH formula: `(C(A,X) + C(A,Y) + C(B,X) - C(B,Y) + C(X,A) + C(X,B) + C(Y,A) - C(Y,B)) / 2`, where `C(i,j)` is the correlation for items `i` and `j`. The dashboard also shows a `Cross-Term Combination Statistic` which is `C(A,X) + C(A,Y) + C(B,X) - C(B,Y)`.
*   Uncertainties for these statistics are calculated using the `uncertainties` library, typically assuming Poisson statistics where the standard deviation `σ = 1/√N` for a count `N`.

These statistics are updated live on the dashboard, providing insights into team performance and potential violations of local realism (if CHSH values exceed classical bounds).

# Live Quiz Application Architecture Design

## 1. Overview

The application will be a real-time, web-based quiz platform designed for approximately 100 concurrent participants organized into pairs. Participants will answer True/False questions on items (A, B, C, D) presented to them. The system will feature a presenter dashboard for live monitoring and displaying results from a custom calculation script.

The architecture will consist of three main components:
1.  **Frontend (Participant Interface):** A lightweight web interface for participants to join teams, receive questions, and submit answers.
2.  **Frontend (Presenter Dashboard):** A web interface for the presenter to view live quiz statistics and custom analytics.
3.  **Backend Server:** A Python-based server (using FastAPI or Flask with WebSockets) to manage game logic, communication, data storage, and integration with the calculation script.

## 2. Frontend - Participant Interface

*   **Technology:** HTML, CSS, JavaScript. Focus on simplicity and responsiveness for various devices (smartphones, tablets, laptops).
*   **Key Features:**
    *   **Landing Page:** Instructions, QR code/link to join.
    *   **Team Formation:**
        *   A participant can create a new team by entering a unique `team_name`.
        *   Other participants can see a list of created teams that are not yet full (i.e., have only one member).
        *   A participant can join an existing team from the list. Once a second participant joins, the team is considered "formed" and locked, preventing others from joining.
        *   An option to "unpair" or "leave team" will be available before the quiz starts or if a mistake is made, re-opening the team for another participant or allowing the creator to wait for a new partner.
    *   **Quiz Interface:**
        *   Displays the single question item (e.g., "A", "B", "C", or "D") assigned to the participant for the current round.
        *   Provides "True" and "False" buttons for submitting their answer.
        *   After submitting, the interface will show a waiting state until their partner also submits an answer.
        *   Once both partners have answered, the interface will automatically update to show the next question item for the new round.
    *   **Communication:** Uses WebSockets to receive questions and game state updates from the backend in real-time.

## 3. Frontend - Presenter Dashboard

*   **Technology:** HTML, CSS, JavaScript (potentially with a simple charting library for visualizations if needed before custom script integration).
*   **Key Features:**
    *   **Live Updates:** Displays real-time statistics (e.g., number of active pairs, questions answered).
    *   **Customizable Views:** Accessed via specific URLs (e.g., `/dashboard/correlation_view_X`, `/dashboard/speed_analysis_Y`). The backend will serve data based on these URL parameters.
    *   **Calculation Script Integration:** The dashboard will display results processed by the external Python/Mathematica script. This might involve fetching pre-calculated data or triggering calculations and then fetching results.
    *   **Communication:** Uses WebSockets or periodic polling to get updated data from the backend.

## 4. Backend Server

*   **Technology:** Python (FastAPI recommended for its asynchronous capabilities and performance, or Flask with extensions like Flask-SocketIO). WebSockets for real-time bidirectional communication.
*   **Core Responsibilities:**
    *   **Session Management:** Manages anonymous participant sessions (e.g., using WebSocket connection IDs or short-lived tokens).
    *   **Team Management API:**
        *   `POST /teams`: Create a new team (participant 1 joins).
        *   `GET /teams`: List available (not full) teams.
        *   `PUT /teams/{team_name}/join`: Participant 2 joins a team.
        *   `PUT /teams/{team_name}/leave`: A participant leaves a team.
    *   **Quiz Logic:**
        *   **Pair Synchronization:** Ensures both participants in a pair submit answers before the pair proceeds to the next question.
        *   **Question Item Assignment:** For each round and each pair:
            *   Randomly select one item (A, B, C, or D) for participant 1 of the pair.
            *   Randomly select one item (A, B, C, or D) for participant 2 of the pair.
            *   These two items form the "question" for the pair in that round.
        *   **Pseudo-Random Combo Coverage:** Implement logic to track the 16 possible combinations of items assigned to a pair (e.g., P1 gets A, P2 gets A; P1 gets A, P2 gets B; ...; P1 gets D, P2 gets D). The system will strive to ensure each pair encounters each of these 16 combinations at least three times over the course of the quiz. This might involve a weighted random selection or a queueing system for combos per pair.
    *   **Answer Handling API/WebSocket Message:**
        *   Receives answers (participant_id, team_id, assigned_item, answer_value: True/False).
        *   Records answers with timestamps.
    *   **WebSocket Communication:**
        *   Broadcasts available teams to new participants.
        *   Notifies participants of team status (waiting for partner, partner joined, partner left).
        *   Pushes new question items to individual participants within a pair once both have answered the previous round.
        *   Sends aggregated data or triggers to the Presenter Dashboard.
    *   **Calculation Script Interface:**
        *   Provides an API endpoint or a mechanism (e.g., a message queue or scheduled task) to feed data (raw answers, timestamps, pair info) to the Python/Mathematica script.
        *   Provides an API endpoint for the dashboard to fetch the results produced by the script.
*   **Performance:** Designed to handle ~100 participants (50 pairs) with response rates faster than 1 per second per participant. Asynchronous operations (FastAPI) or efficient worker management (Flask) will be crucial.

## 5. Data Storage

*   **Technology:** A relational database (e.g., PostgreSQL or MySQL for robustness, SQLite for simplicity if sufficient). SQLAlchemy can be used as the ORM with the Python backend.
*   **Proposed Schema (Simplified):**
    *   `Teams`:
        *   `team_id` (PK)
        *   `team_name` (UNIQUE)
        *   `participant1_session_id` (FK to a conceptual Sessions table, or just stores the WebSocket ID)
        *   `participant2_session_id` (FK)
        *   `is_active` (Boolean)
        *   `created_at`
    *   `Answers`:
        *   `answer_id` (PK)
        *   `team_id` (FK)
        *   `participant_session_id`
        *   `question_round_number`
        *   `assigned_item` (Enum: 'A', 'B', 'C', 'D')
        *   `response_value` (Boolean: True/False)
        *   `timestamp`
    *   `PairQuestionRounds` (to track items assigned to a pair and combo coverage):
        *   `round_id` (PK)
        *   `team_id` (FK)
        *   `round_number_for_team`
        *   `participant1_item` (Enum: 'A', 'B', 'C', 'D')
        *   `participant2_item` (Enum: 'A', 'B', 'C', 'D')
        *   `p1_answered_at`, `p2_answered_at`
        *   `timestamp_initiated`

## 6. Deployment

*   The Python backend (Flask/FastAPI application) can be packaged and deployed. If Flask is chosen, it can be deployed using the `deploy_apply_deployment` tool if it adheres to the required structure.
*   Static frontend assets (HTML, CSS, JS) will be served by the backend or a separate static file server.

## 7. Key Flows

*   **Participant Joins & Pairs:**
    1.  User visits URL -> Loads Participant Interface.
    2.  Option to Create Team (enters name) or Join Team (selects from list).
    3.  Backend validates, updates team status, notifies relevant parties via WebSocket.
*   **Quiz Round:**
    1.  Backend determines question items for P1 and P2 in a pair (ensuring combo coverage logic).
    2.  Backend sends item_P1 to P1, item_P2 to P2 via WebSocket.
    3.  Participants submit True/False answers.
    4.  Backend receives answers, records them.
    5.  Once both answers from a pair are received, backend triggers the next round for that pair.
*   **Dashboard View:**
    1.  Presenter opens dashboard URL (possibly with specific view parameters).
    2.  Dashboard connects to backend (WebSocket/HTTP) to fetch initial data and receive live updates.
    3.  Backend provides data, potentially after querying DB or triggering/getting results from the calculation script.

This architecture provides a foundation for building the live quiz application as per the requirements. Further details for each component will be fleshed out during the implementation phase.

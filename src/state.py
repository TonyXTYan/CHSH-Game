class AppState:
    def __init__(self):
        self.active_teams = {}  # {team_name: {'creator_sid': sid, 'participant2_sid': None, 'team_id': db_team_id, 'current_round_number': 0, 'combo_tracker': {}, 'current_db_round_id': None, 'p1_answered_current_round': False, 'p2_answered_current_round': False}}
        self.participant_to_team = {}  # {sid: team_name}
        self.dashboard_clients = set() # Stores SIDs of connected dashboard clients
        self.game_started = False # Track if game has started
        # Store previous session mappings for reconnection
        self.previous_sessions = {} # {previous_sid: current_sid}
        # Store team ID to team name mapping for faster lookups
        self.team_id_to_name = {} # {team_id: team_name}

    def reset(self):
        self.active_teams.clear()
        self.participant_to_team.clear()
        self.dashboard_clients.clear()
        self.previous_sessions.clear()
        self.team_id_to_name.clear()
        self.game_started = False

# Create singleton instance for state
state = AppState()
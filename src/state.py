class AppState:
    def __init__(self):
        self.active_teams = {}  # {team_name: {'players': [], 'team_id': db_team_id, 'current_round_number': 0, 'combo_tracker': {}, 'current_db_round_id': None, 'answered_current_round': {}}}
        self.player_to_team = {}  # {sid: team_name}
        self.connected_players = set()  # All connected player SIDs
        self.dashboard_clients = set() # Stores SIDs of connected dashboard clients
        self.game_started = False # Track if game has started
        self.game_paused = False # Track if game is paused
        self.answer_stream_enabled = False # Track if answer streaming is enabled
        # Store previous session mappings for reconnection
        self.previous_sessions = {} # {previous_sid: current_sid}
        # Store team ID to team name mapping for faster lookups
        self.team_id_to_name = {} # {team_id: team_name}
        # Store recently disconnected player SIDs and their team position
        self.recently_disconnected_sids = {} # {previous_sid: {'team_id': team_id, 'original_slot': 0 or 1, 'timestamp': datetime}}

    def reset(self):
        self.active_teams.clear()
        self.player_to_team.clear()
        self.connected_players.clear()
        self.dashboard_clients.clear()
        self.previous_sessions.clear()
        self.team_id_to_name.clear()
        self.recently_disconnected_sids.clear()
        self.game_started = False
        self.game_paused = False
        self.answer_stream_enabled = False

# Create singleton instance for state
state = AppState()

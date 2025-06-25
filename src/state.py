class AppState:
    def __init__(self):
        self.active_teams = {}  # {team_name: {'players': [], 'team_id': db_team_id, 'current_round_number': 0, 'combo_tracker': {}, 'current_db_round_id': None, 'answered_current_round': {}}}
        self.player_to_team = {}  # {sid: team_name}
        self.connected_players = set()  # All connected player SIDs
        self.dashboard_clients = set() # Stores SIDs of connected dashboard clients
        self.game_started = False # Track if game has started
        self.game_paused = False # Track if game is paused
        self.answer_stream_enabled = False # Track if answer streaming is enabled
        # Store team ID to team name mapping for faster lookups
        self.team_id_to_name = {} # {team_id: team_name}
        # Track disconnected players for reconnection - maps team_name to disconnected player info
        self.disconnected_players = {}  # {team_name: {'player_session_id': old_sid, 'player_slot': 1|2, 'disconnect_time': timestamp}}

    def reset(self):
        self.active_teams.clear()
        self.player_to_team.clear()
        self.connected_players.clear()
        self.dashboard_clients.clear()
        self.team_id_to_name.clear()
        self.disconnected_players.clear()
        self.game_started = False
        self.game_paused = False
        self.answer_stream_enabled = False

# Create singleton instance for state
state = AppState()

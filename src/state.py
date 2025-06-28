class AppState:
    def __init__(self):
        self.active_teams = {}  # {team_name: {'players': [], 'team_id': db_team_id, 'current_round_number': 0, 'combo_tracker': {}, 'current_db_round_id': None, 'answered_current_round': {}, 'player_slots': {sid: slot_number}}}
        self.player_to_team = {}  # {sid: team_name}
        self.connected_players = set()  # All connected player SIDs
        self.dashboard_clients = set() # Stores SIDs of connected dashboard clients
        self.game_started = False # Track if game has started
        self.game_paused = False # Track if game is paused
        self.answer_stream_enabled = False # Track if answer streaming is enabled
        self.game_mode = 'new'  # Track current game mode: 'classic' or 'new'
        self.game_theme = 'food'  # Track current game theme: 'classic', 'food', etc.
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
        self.game_mode = 'new'  # Reset game mode to new
        self.game_theme = 'food'  # Reset game theme to food

    def get_player_slot(self, team_name, sid):
        """Get the database player slot (1 or 2) for a session ID in a team"""
        team_info = self.active_teams.get(team_name)
        if not team_info:
            return None
        return team_info.get('player_slots', {}).get(sid)
    
    def set_player_slot(self, team_name, sid, slot):
        """Set the database player slot for a session ID in a team"""
        team_info = self.active_teams.get(team_name)
        if team_info:
            if 'player_slots' not in team_info:
                team_info['player_slots'] = {}
            team_info['player_slots'][sid] = slot

# Create singleton instance for state
state = AppState()

import threading

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
        # Add lock for thread safety
        self._lock = threading.RLock()

    def reset(self):
        with self._lock:
            self.active_teams.clear()
            self.player_to_team.clear()
            self.connected_players.clear()
            self.dashboard_clients.clear()
            self.team_id_to_name.clear()
            self.game_started = False
            self.game_paused = False
            self.answer_stream_enabled = False
    
    # Thread-safe methods for state access and modification
    def add_player_to_team(self, sid, team_name):
        with self._lock:
            if team_name in self.active_teams and sid not in self.active_teams[team_name]['players']:
                self.active_teams[team_name]['players'].append(sid)
                self.player_to_team[sid] = team_name
                return True
            return False
    
    def remove_player_from_team(self, sid):
        with self._lock:
            if sid in self.player_to_team:
                team_name = self.player_to_team[sid]
                if team_name in self.active_teams and sid in self.active_teams[team_name]['players']:
                    self.active_teams[team_name]['players'].remove(sid)
                    del self.player_to_team[sid]
                    return team_name, len(self.active_teams[team_name]['players'])
            return None, 0
    
    def add_connected_player(self, sid):
        with self._lock:
            self.connected_players.add(sid)
    
    def remove_connected_player(self, sid):
        with self._lock:
            if sid in self.connected_players:
                self.connected_players.remove(sid)
    
    def add_dashboard_client(self, sid):
        with self._lock:
            self.dashboard_clients.add(sid)
    
    def remove_dashboard_client(self, sid):
        with self._lock:
            if sid in self.dashboard_clients:
                self.dashboard_clients.remove(sid)
    
    def get_team_info(self, team_name):
        with self._lock:
            return self.active_teams.get(team_name, None)
    
    def get_player_team(self, sid):
        with self._lock:
            return self.player_to_team.get(sid, None)
    
    def create_team(self, team_name, team_id):
        with self._lock:
            if team_name not in self.active_teams:
                self.active_teams[team_name] = {
                    'players': [],
                    'team_id': team_id,
                    'current_round_number': 0,
                    'combo_tracker': {},
                    'answered_current_round': {},
                    'status': 'waiting_pair'
                }
                self.team_id_to_name[team_id] = team_name
                return True
            return False
    
    def update_team_round(self, team_name, round_id):
        with self._lock:
            if team_name in self.active_teams:
                team_info = self.active_teams[team_name]
                team_info['current_db_round_id'] = round_id
                team_info['answered_current_round'] = {}
                return True
            return False
    
    def mark_player_answered(self, team_name, sid):
        with self._lock:
            if team_name in self.active_teams:
                team_info = self.active_teams[team_name]
                team_info['answered_current_round'][sid] = True
                return len(team_info['answered_current_round'])
            return 0
    
    def is_game_paused(self):
        with self._lock:
            return self.game_paused
    
    def set_game_paused(self, paused):
        with self._lock:
            self.game_paused = paused
    
    def is_game_started(self):
        with self._lock:
            return self.game_started
    
    def set_game_started(self, started):
        with self._lock:
            self.game_started = started
    
    def remove_team(self, team_name):
        with self._lock:
            if team_name in self.active_teams:
                team_id = self.active_teams[team_name]['team_id']
                del self.active_teams[team_name]
                if team_id in self.team_id_to_name:
                    del self.team_id_to_name[team_id]
                return True
            return False

# Create singleton instance for state
state = AppState()

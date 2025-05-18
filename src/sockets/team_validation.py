"""
Helper module for team validation functions to ensure team state integrity.
"""
from src.config import db
from src.state import state
from src.models.quiz_models import Teams
from src.sockets.game import validate_team_sessions, sync_team_state

def check_for_duplicate_player_assignments():
    """
    Check if the same player is assigned to multiple teams and fix this issue.
    Returns the number of fixed player assignments.
    """
    try:
        # Build a map of players to teams
        player_team_map = {}
        fixed_count = 0
        
        # First collect all player assignments
        for team_name, team_info in state.active_teams.items():
            for player in team_info['players']:
                if player is None:
                    continue
                    
                if player in player_team_map:
                    # Player is in multiple teams!
                    old_team = player_team_map[player]
                    print(f"WARNING: Player {player} is assigned to both {old_team} and {team_name}")
                    
                    # Keep the assignment that matches player_to_team
                    correct_team = state.player_to_team.get(player)
                    
                    if correct_team == team_name:
                        print(f"Removing player {player} from {old_team} (keeping in {team_name})")
                        old_team_info = state.active_teams[old_team]
                        if player in old_team_info['players']:
                            old_team_info['players'].remove(player)
                            fixed_count += 1
                            
                            # Also update the database
                            db_team = Teams.query.get(old_team_info['team_id'])
                            if db_team and db_team.player1_session_id == player:
                                db_team.player1_session_id = None
                            if db_team and db_team.player2_session_id == player:
                                db_team.player2_session_id = None
                    elif correct_team == old_team or correct_team is None:
                        print(f"Removing player {player} from {team_name} (keeping in {old_team})")
                        team_info['players'].remove(player)
                        fixed_count += 1
                        
                        # Also update the database
                        db_team = Teams.query.get(team_info['team_id'])
                        if db_team and db_team.player1_session_id == player:
                            db_team.player1_session_id = None
                        if db_team and db_team.player2_session_id == player:
                            db_team.player2_session_id = None
                else:
                    # First time seeing this player
                    player_team_map[player] = team_name
        
        if fixed_count > 0:
            db.session.commit()
            
        return fixed_count
    except Exception as e:
        print(f"Error in check_for_duplicate_player_assignments: {str(e)}")
        import traceback
        traceback.print_exc()
        return 0

def validate_all_teams():
    """
    Perform validation on all active teams to fix any inconsistencies.
    This is useful for periodic or startup validation.
    """
    try:
        # First check for players assigned to multiple teams
        fixed_count = check_for_duplicate_player_assignments()
        if fixed_count > 0:
            print(f"Fixed {fixed_count} duplicate player assignments")
        
        # Get a list of all active team names
        team_names = list(state.active_teams.keys())
        
        for team_name in team_names:
            # Validate each team
            print(f"Validating team: {team_name}")
            
            # Skip if team no longer exists (might have been deleted during iteration)
            if team_name not in state.active_teams:
                continue
                
            # Run our validation checks
            validate_result = validate_team_sessions(team_name)
            
            # If validation failed, the team might have been deleted
            if team_name not in state.active_teams:
                continue
                
            # Sync the team state
            sync_team_state(team_name)
            
        # Check for teams in database that are active but not in memory
        with db.session.no_autoflush:
            db_teams = Teams.query.filter_by(is_active=True).all()
            for db_team in db_teams:
                if db_team.team_name not in state.active_teams:
                    # Team exists in DB but not in memory
                    print(f"DB team {db_team.team_name} not found in memory, fixing")
                    
                    # Check if any players are still connected
                    active_players = []
                    if db_team.player1_session_id and db_team.player1_session_id in state.connected_players:
                        active_players.append(db_team.player1_session_id)
                    if db_team.player2_session_id and db_team.player2_session_id in state.connected_players:
                        active_players.append(db_team.player2_session_id)
                    
                    if not active_players:
                        # No players connected, mark team as inactive
                        print(f"No connected players for {db_team.team_name}, marking inactive")
                        db_team.is_active = False
                        db_team.player1_session_id = None
                        db_team.player2_session_id = None
                    else:
                        # Has connected players, recreate in memory
                        print(f"Recreating {db_team.team_name} in memory with {active_players}")
                        state.active_teams[db_team.team_name] = {
                            'players': active_players,
                            'team_id': db_team.team_id,
                            'current_round_number': 0,
                            'combo_tracker': {},
                            'answered_current_round': {},
                            'status': 'waiting_pair' if len(active_players) < 2 else 'paired'
                        }
                        state.team_id_to_name[db_team.team_id] = db_team.team_name
                        
                        # Update player mappings
                        for player in active_players:
                            state.player_to_team[player] = db_team.team_name
            
            db.session.commit()
                
        return True
    except Exception as e:
        print(f"Error in validate_all_teams: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

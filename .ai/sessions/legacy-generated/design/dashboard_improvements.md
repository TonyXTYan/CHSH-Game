# Dashboard Improvements Plan

## 1. Team Display Changes

### Backend Changes
1. Create new function `get_all_teams()` in dashboard.py:
   ```python
   def get_all_teams():
       try:
           # Query all teams from database
           all_teams = Teams.query.all()
           teams_list = []
           
           for team in all_teams:
               # Get active team info from state if available
               team_info = state.active_teams.get(team.team_name)
               
               # Compute stats regardless of active status
               hash1, hash2 = compute_team_hashes(team.team_id)
               corr_matrix, item_values, same_item_balance_avg, same_item_balance = compute_correlation_matrix(team.team_id)
               
               team_data = {
                   'team_name': team.team_name,
                   'team_id': team.team_id,
                   'is_active': team.is_active,
                   'player1_sid': team_info['players'][0] if team_info and len(team_info['players']) > 0 else None,
                   'player2_sid': team_info['players'][1] if team_info and len(team_info['players']) > 1 else None,
                   'current_round_number': team_info.get('current_round_number', 0) if team_info else 0,
                   'history_hash1': hash1,
                   'history_hash2': hash2,
                   'min_stats_sig': False,  # Default for inactive teams
                   'correlation_matrix': corr_matrix,
                   'correlation_labels': item_values,
                   'correlation_stats': compute_correlation_stats(team.team_id),
                   'last_active': team.created_at.isoformat() if team.created_at else None  # NEW: Show when team was created/last active
               }
               teams_list.append(team_data)
               
           return teams_list
       except Exception as e:
           print(f"Error getting all teams: {str(e)}")
           return []
   ```

2. Update dashboard update functions to use new method:
   - Modify `emit_dashboard_team_update()`
   - Modify `emit_dashboard_full_update()`
   - Add rate limiting for updates to prevent excessive database queries

### Frontend Changes
1. Update dashboard.html table header:
   ```html
   <h2>Teams</h2>
   <div class="team-filters">
       <label>
           <input type="checkbox" id="show-inactive" checked>
           Show Inactive Teams
       </label>
       <div class="filter-options">
           <select id="sort-teams">
               <option value="status">Sort by Status</option>
               <option value="name">Sort by Name</option>
               <option value="date">Sort by Last Active</option>
           </select>
       </div>
   </div>
   ```

2. Add CSS styles for teams:
   ```css
   .team-row.inactive {
       opacity: 0.7;
       background-color: #f5f5f5;
   }
   
   .team-row.inactive:hover {
       opacity: 1;
       transition: opacity 0.2s;
   }
   
   .team-status {
       display: inline-block;
       width: 8px;
       height: 8px;
       border-radius: 50%;
       margin-right: 5px;
   }
   
   .team-status.active {
       background-color: #4CAF50;
   }
   
   .team-status.inactive {
       background-color: #9E9E9E;
   }
   ```

3. Update dashboard.js to handle teams:
   ```javascript
   function updateTeamsTable(teams) {
       const showInactive = document.getElementById('show-inactive').checked;
       const sortBy = document.getElementById('sort-teams').value;
       
       // Filter teams
       let filteredTeams = teams;
       if (!showInactive) {
           filteredTeams = teams.filter(team => team.is_active);
       }
       
       // Sort teams
       filteredTeams.sort((a, b) => {
           if (sortBy === 'status') {
               if (a.is_active === b.is_active) return 0;
               return a.is_active ? -1 : 1;
           } else if (sortBy === 'date') {
               return new Date(b.last_active) - new Date(a.last_active);
           }
           return a.team_name.localeCompare(b.team_name);
       });
       
       // Update table
       // ... (existing table update logic)
   }
   ```

## 2. Reset Game Stats Enhancement

### Backend Changes
1. Modify `on_restart_game()`:
   ```python
   def on_restart_game():
       try:
           # Verify dashboard client
           if request.sid not in state.dashboard_clients:
               emit('error', {'message': 'Unauthorized'}); return
               
           # Update game state
           state.game_started = False
           
           # Begin transaction
           db.session.begin_nested()
           
           try:
               # Clear game data
               PairQuestionRounds.query.delete()
               Answers.query.delete()
               
               # Get timestamp for tracking when teams became inactive
               inactive_timestamp = datetime.utcnow()
               
               # Mark non-active teams as inactive
               teams_to_remove = []
               for team_name, team_info in state.active_teams.items():
                   if not team_info['players']:
                       db_team = Teams.query.get(team_info['team_id'])
                       if db_team:
                           existing_inactive = Teams.query.filter_by(
                               team_name=team_name, 
                               is_active=False
                           ).first()
                           
                           if existing_inactive:
                               db_team.team_name = f"{team_name}_{db_team.team_id}"
                           db_team.is_active = False
                           db_team.last_active = inactive_timestamp  # NEW: Track when team became inactive
                           
                           teams_to_remove.append((team_name, team_info['team_id']))
               
               # Update state outside the loop to prevent dict modification during iteration
               for team_name, team_id in teams_to_remove:
                   del state.active_teams[team_name]
                   del state.team_id_to_name[team_id]
               
               db.session.commit()
               
           except Exception as db_error:
               db.session.rollback()
               raise db_error
               
           # Reset remaining active team states
           for team_info in state.active_teams.values():
               team_info['current_round_number'] = 0
               team_info['current_db_round_id'] = None
               team_info['answered_current_round'].clear()  # Use clear() instead of reassignment
               team_info['combo_tracker'].clear()
           
           # Notify clients
           socketio.emit('game_state_changed', {'game_started': False})
           emit_dashboard_full_update()
           
           for dash_sid in state.dashboard_clients:
               socketio.emit('game_reset_complete', room=dash_sid)
               
       except Exception as e:
           print(f"Error in on_restart_game: {str(e)}")
           emit('error', {'message': f'Error restarting game: {str(e)}'})
   ```

### Frontend Changes
1. Update reset confirmation dialog:
   ```javascript
   function handleResetGame() {
       if (!confirmingStop) {
           startBtn.className = "confirm-reset";
           const inactiveCount = Array.from(document.querySelectorAll('.team-row:not(.inactive)'))
               .filter(row => !row.querySelector('.player-count') || 
                       row.querySelector('.player-count').textContent === '0').length;
           
           startBtn.textContent = `Click again to reset game stats and remove ${inactiveCount} inactive team${inactiveCount !== 1 ? 's' : ''}`;
           confirmingStop = true;
           setTimeout(() => {
               if (confirmingStop) {
                   cleanupResetConfirmation(startBtn);
               }
           }, 3000);
       } else {
           socket.emit("restart_game");
           startBtn.disabled = true;
           startBtn.textContent = "Resetting...";
       }
   }
   ```

## 3. Security and Error Handling
- Add validation for team state changes
- Implement proper error handling for state transitions
- Add logging for team state changes
- Handle edge cases in team state management
- Add database constraints to prevent invalid states
- Implement rate limiting for dashboard updates
- Add retry logic for failed state transitions
- Validate team names and IDs in all operations

## 4. Testing Strategy
1. Unit Tests:
   - Test team state transitions
   - Test reset functionality
   - Test data consistency between memory and database
   - Test edge cases in team status changes
   - Test sorting and filtering logic
   - Test concurrent operations

2. Integration Tests:
   - Test dashboard updates with both active and inactive teams
   - Test team state synchronization
   - Test reset workflow
   - Test browser state preservation
   - Test reconnection scenarios
   - Test large dataset handling

3. Performance Tests:
   - Test dashboard performance with many teams
   - Test state transition latency
   - Test memory usage under load

## 5. Performance Considerations
- Optimize database queries for team status checks
- Implement pagination for large numbers of teams
   ```javascript
   const TEAMS_PER_PAGE = 50;
   let currentPage = 1;
   
   function updateTeamsTable(teams, page = 1) {
       const start = (page - 1) * TEAMS_PER_PAGE;
       const paginatedTeams = teams.slice(start, start + TEAMS_PER_PAGE);
       // ... update table with paginated teams
   }
   ```
- Cache team statistics calculations
- Handle concurrent team state updates
- Use database indices for team queries
- Implement WebSocket message batching
- Use debouncing for UI updates

## 6. Data Migration
- Add script to handle existing teams
- Preserve team history during migration
- Add rollback capability
- Handle existing active/inactive team conflicts

## 7. Monitoring and Maintenance
- Add metrics for team state changes
- Monitor database performance
- Track memory usage patterns
- Set up alerts for state inconsistencies
- Implement automated cleanup of old inactive teams

## Implementation Order
1. Database schema updates and migration
2. Backend team query changes
3. Frontend team display updates
4. Reset functionality enhancement
5. Testing and validation
6. Performance optimization
7. Monitoring implementation

## Rollback Plan
1. Keep backup of team states
2. Implement version tracking for team status changes
3. Add ability to restore previous team states
4. Create emergency reset functionality
# Team Joining Improvements

## Overview
Add functionality to let players join both active and inactive teams, with separate sections for each type.

## UI Changes

### 1. Update index.html
```html
<div class="join-sections">
    <!-- Active Teams Section -->
    <div class="team-section active-teams">
        <h3>Join Existing Team</h3>
        <div id="available-teams-list">
            <!-- Active teams populated here -->
        </div>
    </div>

    <!-- Inactive Teams Section -->
    <div class="team-section inactive-teams">
        <h3>Reactivate Previous Team</h3>
        <div id="inactive-teams-list">
            <!-- Inactive teams populated here -->
        </div>
    </div>
</div>
```

### 2. Add CSS Styling
```css
.team-section {
    margin-bottom: 2rem;
    padding: 1rem;
    border-radius: 8px;
    background: #f5f5f5;
}

.team-section h3 {
    margin-top: 0;
    color: #333;
}

.team-list {
    display: grid;
    gap: 0.5rem;
}

.team-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem;
    background: white;
    border-radius: 4px;
    border: 1px solid #ddd;
}

.team-item.inactive {
    border-style: dashed;
}
```

## Backend Changes

### 1. Update Team Management API
- Modify `/api/teams` endpoint to return both active and inactive teams
- Add endpoint to reactivate an inactive team
- Update team joining logic to handle inactive teams

### 2. Socket Events
```python
@socketio.on('get_available_teams')
def get_available_teams():
    # Get active teams
    active_teams = Teams.query.filter_by(is_active=True).all()
    # Get inactive teams
    inactive_teams = Teams.query.filter_by(is_active=False).all()
    
    return {
        'active_teams': [serialize_team(t) for t in active_teams],
        'inactive_teams': [serialize_team(t) for t in inactive_teams]
    }

@socketio.on('reactivate_team')
def reactivate_team(data):
    team_name = data.get('team_name')
    # Find and reactivate the team
    team = Teams.query.filter_by(team_name=team_name, is_active=False).first()
    if team:
        team.is_active = True
        team.player1_session_id = request.sid
        db.session.commit()
        return {'success': True}
    return {'success': False, 'message': 'Team not found'}
```

### 3. Frontend JavaScript
```javascript
// Update team listings
function updateTeamLists(data) {
    const activeList = document.getElementById('available-teams-list');
    const inactiveList = document.getElementById('inactive-teams-list');
    
    // Update active teams
    activeList.innerHTML = data.active_teams.map(team => `
        <div class="team-item">
            <span>${team.name}</span>
            <button onclick="joinTeam('${team.name}')">Join Team</button>
        </div>
    `).join('');
    
    // Update inactive teams
    inactiveList.innerHTML = data.inactive_teams.map(team => `
        <div class="team-item inactive">
            <span>${team.name}</span>
            <button onclick="reactivateTeam('${team.name}')">Reactivate & Join</button>
        </div>
    `).join('');
}

// Handle team reactivation
function reactivateTeam(teamName) {
    socket.emit('reactivate_team', { team_name: teamName }, (response) => {
        if (response.success) {
            showMessage('Team reactivated successfully!');
            // Continue with normal team joining flow
            joinTeam(teamName);
        } else {
            showError(response.message || 'Failed to reactivate team');
        }
    });
}
```

## Implementation Steps

1. Backend Changes:
   - Update team management socket handlers
   - Add team reactivation functionality
   - Modify team serialization

2. Frontend Updates:
   - Modify index.html to add sections
   - Add new CSS styles
   - Update JavaScript handlers

3. Testing:
   - Test joining active teams
   - Test reactivating inactive teams
   - Verify proper error handling
   - Check UI responsiveness

## Security Considerations
- Validate team existence before reactivation
- Ensure proper session handling
- Prevent duplicate team names
- Handle concurrent reactivation attempts

## Error Handling
- Display clear error messages
- Handle network issues
- Manage concurrent modifications
- Provide feedback for all actions

This will require switching to Code mode to implement these changes.
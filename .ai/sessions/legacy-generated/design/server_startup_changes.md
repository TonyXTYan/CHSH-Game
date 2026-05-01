# Server Startup Changes

## Current Behavior
Currently, on server startup:
1. Marks all active teams as inactive
2. Preserves inactive teams in the database
3. Renames teams with conflicting names

## Required Changes
Modify the server startup process to:
1. Delete all inactive teams instead of preserving them
2. Delete all game-related data (answers, rounds) first
3. Mark any remaining active teams as inactive
4. Maintain proper database transaction handling

## Implementation Plan

### 1. Update main.py Initialization
```python
with app.app_context():
    db.create_all()
    try:
        # Begin transaction
        db.session.begin_nested()
        
        # Delete all game data first
        Answers.query.delete()
        PairQuestionRounds.query.delete()
        
        # Delete all inactive teams
        Teams.query.filter_by(is_active=False).delete()
        
        # Mark remaining teams as inactive
        Teams.query.filter_by(is_active=True).update({Teams.is_active: False})
        
        db.session.commit()
        
        # Notify any connected clients
        socketio.emit('game_reset_complete')
        
    except Exception as e:
        print(f"Error resetting database: {str(e)}")
        db.session.rollback()
        
    # Clear memory state
    state.reset()
```

### 2. Update wsgi.py Handling
No changes needed to wsgi.py as it already:
- Properly monkeypatches eventlet
- Sets up signal handlers for gunicorn
- Pushes app context

### Testing Steps
1. Start server with inactive teams in database
2. Verify inactive teams are removed
3. Verify active teams are marked inactive
4. Check database integrity
5. Verify socket notifications work

### Expected Results
- All inactive teams removed on startup
- Clean database state
- Proper error handling
- No data inconsistencies

This will require switching to Code mode to implement the changes.
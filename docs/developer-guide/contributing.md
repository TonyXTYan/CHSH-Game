# Contributing Guidelines

Welcome to the CHSH Game project! We appreciate your interest in contributing. This guide will help you get started and ensure smooth collaboration.

## Getting Started

### Prerequisites
- Read the [Development Setup](./setup.md) guide
- Understand the [Architecture Overview](./architecture.md)
- Familiarize yourself with the [API Reference](./api-reference.md)

### First Contribution
1. **Find an issue**: Look for issues labeled `good first issue` or `help wanted`
2. **Discuss first**: Comment on the issue to discuss your approach
3. **Fork and clone**: Create your own fork of the repository
4. **Create branch**: Use descriptive branch names (e.g., `feature/add-team-statistics`)
5. **Make changes**: Follow our coding standards and guidelines
6. **Test thoroughly**: Ensure all tests pass and add new tests if needed
7. **Submit PR**: Create a pull request with a clear description

## Development Workflow

### Branch Naming Convention
```
feature/descriptive-feature-name
bugfix/descriptive-bug-description
hotfix/critical-issue-description
docs/documentation-improvement
refactor/component-name-refactor
```

### Commit Message Format
```
type(scope): brief description

Optional longer description explaining the change.

Fixes #issue-number
```

**Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

**Examples**:
```
feat(dashboard): add real-time team statistics display

Add live updating statistics for team performance including
CHSH values, correlation matrices, and uncertainty calculations.

Fixes #123
```

```
fix(socket): handle player disconnection gracefully

Prevent team state corruption when players disconnect during
active game rounds.

Fixes #456
```

### Pull Request Process

1. **Update documentation** if you changed APIs or added features
2. **Add/update tests** for any new functionality
3. **Ensure CI passes** all checks including tests and linting
4. **Request review** from at least one maintainer
5. **Address feedback** promptly and professionally
6. **Squash commits** if requested before merging

### Pull Request Template

```markdown
## Description
Brief description of the changes.

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Testing
- [ ] Added tests for new functionality
- [ ] All existing tests pass
- [ ] Tested manually with multiple players/teams
- [ ] Tested on different browsers

## Checklist
- [ ] Code follows the project style guidelines
- [ ] Self-review of my own code completed
- [ ] Documentation updated (if applicable)
- [ ] No new warnings introduced
```

## Code Quality Standards

### Python Backend

#### Code Style
- **PEP 8 compliance**: Use `black` formatter and `flake8` linter
- **Type hints**: Required for all function parameters and return values
- **Docstrings**: Google-style docstrings for all public functions and classes
- **Import organization**: Use `isort` for consistent import ordering

#### Example:
```python
from typing import Dict, List, Optional
from flask_socketio import emit

def create_team(team_name: str, player_sid: str) -> Dict[str, Any]:
    """Create a new team with the specified name.
    
    Args:
        team_name: The name for the new team
        player_sid: Session ID of the player creating the team
        
    Returns:
        Dictionary containing team information and status
        
    Raises:
        ValueError: If team name is invalid or already exists
    """
    # Implementation here
    pass
```

#### Error Handling
```python
try:
    # Database operations
    result = db.session.execute(query)
    db.session.commit()
except SQLAlchemyError as e:
    logger.error(f"Database error in create_team: {str(e)}", exc_info=True)
    db.session.rollback()
    raise DatabaseError("Failed to create team") from e
except Exception as e:
    logger.error(f"Unexpected error in create_team: {str(e)}", exc_info=True)
    raise
```

#### Logging
```python
import logging
logger = logging.getLogger(__name__)

# Use structured logging
logger.info("Team created", extra={
    'team_id': team.team_id,
    'team_name': team.team_name,
    'player_count': len(team.players)
})
```

### JavaScript Frontend

#### Code Style
- **ESLint compliance**: Follow standard JavaScript style
- **Consistent naming**: Use camelCase for variables and functions
- **Modern JavaScript**: Use ES6+ features appropriately
- **Documentation**: JSDoc comments for complex functions

#### Example:
```javascript
/**
 * Handle new question received from server
 * @param {Object} data - Question data from server
 * @param {number} data.round_id - Round identifier
 * @param {string} data.item - Question type (A, B, X, Y)
 */
function handleNewQuestion(data) {
    if (!data.round_id || !data.item) {
        console.error('Invalid question data received:', data);
        return;
    }
    
    try {
        updateQuestionDisplay(data.item);
        currentRoundId = data.round_id;
        enableAnswerButtons();
    } catch (error) {
        console.error('Error handling new question:', error);
        showErrorMessage('Failed to display question');
    }
}
```

#### Error Handling
```javascript
// Graceful error handling with user feedback
function submitAnswer(answer) {
    try {
        socket.emit('submit_answer', {
            round_id: currentRoundId,
            answer: answer
        });
        
        disableAnswerButtons();
        showWaitingMessage();
    } catch (error) {
        console.error('Error submitting answer:', error);
        showErrorMessage('Failed to submit answer. Please try again.');
        enableAnswerButtons();
    }
}

// Socket error handling
socket.on('error', (error) => {
    console.error('Socket error:', error);
    showErrorMessage(error.message || 'Connection error occurred');
});
```

### Database Guidelines

#### Migrations
- All schema changes must use SQLAlchemy migrations
- Include both upgrade and downgrade methods
- Test migrations on sample data

#### Indexing
```python
# Add indexes for frequently queried fields
class Answers(db.Model):
    __table_args__ = (
        db.Index('idx_answers_team_timestamp', 'team_id', 'timestamp'),
        db.Index('idx_answers_team_item', 'team_id', 'assigned_item'),
    )
```

#### Transactions
```python
try:
    with db.session.begin():
        # All related operations in one transaction
        team = Teams(team_name=team_name)
        db.session.add(team)
        db.session.flush()  # Get team_id
        
        round_record = PairQuestionRounds(team_id=team.team_id)
        db.session.add(round_record)
except Exception:
    # Automatic rollback on exception
    raise
```

## Testing Guidelines

### Test Coverage
- **Minimum 80% coverage** for new code
- **100% coverage** for critical game logic
- Test both happy path and error conditions

### Unit Tests
```python
import pytest
from unittest.mock import patch, MagicMock

def test_create_team_success(app_context, db_session):
    """Test successful team creation."""
    team_name = "Test Team"
    player_sid = "test_sid_123"
    
    result = create_team(team_name, player_sid)
    
    assert result['success'] is True
    assert result['team']['team_name'] == team_name
    assert len(result['team']['players']) == 1

def test_create_team_duplicate_name(app_context, db_session):
    """Test team creation with duplicate name fails."""
    team_name = "Duplicate Team"
    
    # Create first team
    create_team(team_name, "sid1")
    
    # Attempt to create duplicate
    with pytest.raises(ValueError, match="Team name already exists"):
        create_team(team_name, "sid2")
```

### Integration Tests
```python
def test_full_game_flow(test_client, socketio_client):
    """Test complete game flow from team creation to answer submission."""
    # Create teams
    client1 = socketio_client()
    client2 = socketio_client()
    
    # Player 1 creates team
    client1.emit('create_team', {'team_name': 'Test Team'})
    response = client1.get_received()
    assert response[0]['name'] == 'team_created'
    
    # Player 2 joins team
    team_id = response[0]['args'][0]['team']['team_id']
    client2.emit('join_team', {'team_id': team_id})
    
    # Start game and verify flow
    # ... rest of test
```

### Frontend Tests
Use Jest or similar for JavaScript testing:
```javascript
describe('Game Logic', () => {
    test('should handle new question correctly', () => {
        const mockData = {
            round_id: 123,
            item: 'A'
        };
        
        handleNewQuestion(mockData);
        
        expect(document.getElementById('question-item')).toHaveTextContent('A');
        expect(document.getElementById('true-button')).not.toBeDisabled();
    });
});
```

## Security Guidelines

### Input Validation
```python
def validate_team_name(team_name: str) -> str:
    """Validate and sanitize team name."""
    if not team_name or not isinstance(team_name, str):
        raise ValueError("Team name is required")
    
    # Sanitize
    clean_name = team_name.strip()
    
    # Validate length
    if len(clean_name) < 1 or len(clean_name) > 100:
        raise ValueError("Team name must be 1-100 characters")
    
    # Validate characters (allow alphanumeric, spaces, basic punctuation)
    if not re.match(r'^[a-zA-Z0-9\s\-_\.!?]+$', clean_name):
        raise ValueError("Team name contains invalid characters")
    
    return clean_name
```

### SQL Injection Prevention
```python
# Good: Using SQLAlchemy ORM
teams = Teams.query.filter(Teams.team_name == user_input).all()

# Good: Using parameterized queries
result = db.session.execute(
    text("SELECT * FROM teams WHERE team_name = :name"),
    {"name": user_input}
)

# Bad: String concatenation
# query = f"SELECT * FROM teams WHERE team_name = '{user_input}'"
```

### WebSocket Security
```python
@socketio.on('submit_answer')
def on_submit_answer(data):
    # Validate session
    if request.sid not in state.player_to_team:
        emit('error', {'message': 'Invalid session'})
        return
    
    # Validate data structure
    if not isinstance(data, dict) or 'answer' not in data:
        emit('error', {'message': 'Invalid data format'})
        return
    
    # Validate business logic
    if not state.game_running:
        emit('error', {'message': 'Game not active'})
        return
```

## Documentation Guidelines

### Code Documentation
- **README updates**: Update if you change setup/usage instructions
- **API changes**: Update API reference for new endpoints/events
- **Architecture changes**: Update architecture documentation

### Inline Documentation
```python
def calculate_chsh_value(correlation_matrix: np.ndarray) -> float:
    """Calculate CHSH value from correlation matrix.
    
    The CHSH value is calculated using the formula:
    S = |C(A,X) + C(A,Y) + C(B,X) - C(B,Y)|
    
    Where C(i,j) represents the correlation between measurements
    i and j. Values > 2 indicate violation of classical bounds.
    
    Args:
        correlation_matrix: 4x4 numpy array with correlations
                          between measurement pairs
    
    Returns:
        CHSH value as float. Classical limit is 2.0,
        quantum maximum is 2√2 ≈ 2.828
    
    Raises:
        ValueError: If matrix is not 4x4 or contains invalid values
    """
```

## Performance Guidelines

### Database Performance
- Use database indexes for frequently queried fields
- Batch database operations when possible
- Monitor query performance in production

### Frontend Performance
- Minimize DOM manipulation
- Debounce user input events
- Use efficient event handling

### Memory Management
- Clean up event listeners on component destruction
- Monitor memory usage in long-running games
- Implement proper cache invalidation

## Issue Guidelines

### Bug Reports
Include:
- **Steps to reproduce**
- **Expected vs actual behavior**
- **Browser/environment information**
- **Console errors/logs**
- **Screenshots if applicable**

### Feature Requests
Include:
- **Use case description**
- **Proposed solution**
- **Alternative solutions considered**
- **Impact on existing functionality**

## Release Process

### Version Numbering
Follow Semantic Versioning (SemVer):
- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Checklist
- [ ] All tests pass
- [ ] Documentation updated
- [ ] Security scan clean
- [ ] Performance tests pass
- [ ] Migration scripts tested
- [ ] Rollback plan prepared
- [ ] Release notes written

## Community Guidelines

### Communication
- Be respectful and professional
- Ask questions if unclear about requirements
- Provide constructive feedback in reviews
- Help newcomers get started

### Code Reviews
- Focus on code quality and correctness
- Explain reasoning behind suggestions
- Acknowledge good work and improvements
- Test the changes locally when possible

---

Thank you for contributing to the CHSH Game project! Your contributions help make quantum physics education more accessible and engaging.
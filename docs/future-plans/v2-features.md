# Version 2 Features

This document outlines the major features planned for CHSH Game version 2.0, focusing on enhanced gameplay modes, educational improvements, and user experience enhancements.

## Overview

Version 2.0 will introduce significant gameplay innovations while maintaining backward compatibility with the current system. The primary focus is on making quantum physics concepts more accessible to different learning styles and educational contexts.

## Core New Features

### 1. Role-Based Game Mode

Based on analysis from `.ai-prompts/v2-chsh-game.md`, implement a specialized game mode where players have distinct roles:

#### Player Role Separation
- **Player A**: Only sees questions A and B
- **Player B**: Only sees questions X and Y
- **Maintains original team structure** with exactly 2 players per team
- **Preserves player identity** even if one teammate disconnects

#### Implementation Strategy
```python
# Enhanced player role tracking
class TeamMember:
    def __init__(self, session_id, role):
        self.session_id = session_id
        self.role = role  # 'A' or 'B'
        self.original_role = role  # Preserved on reconnection
        
class GameMode(Enum):
    CLASSIC = "classic"  # Current implementation
    ROLE_BASED = "role_based"  # New v2 mode
    
# Role-based question assignment
def assign_questions_role_based(team_id, round_number):
    team = get_team(team_id)
    
    if team.game_mode == GameMode.ROLE_BASED:
        player_a = team.get_player_by_role('A')
        player_b = team.get_player_by_role('B')
        
        # Player A only gets A/B questions
        question_a = random.choice(['A', 'B'])
        # Player B only gets X/Y questions  
        question_b = random.choice(['X', 'Y'])
        
        return {
            player_a.session_id: question_a,
            player_b.session_id: question_b
        }
```

#### Strategic Implications
- **Player A Strategy**: Focus on optimizing A vs B responses
- **Player B Strategy**: Focus on optimizing X vs Y responses
- **Team Coordination**: Requires pre-game strategy discussion
- **Educational Value**: Clearer role separation aids understanding

### 2. Enhanced Metrics System

Replace complex quantum metrics with intuitive success rate calculations:

#### Success Rate Calculation
```python
def calculate_success_rate(team_answers):
    """
    Calculate team success rate based on optimal CHSH strategy:
    - (B,Y) combination: players should respond differently (+1 if different, -1 if same)
    - All other combinations: players should respond the same (+1 if same, -1 if different)
    """
    total_score = 0
    total_rounds = 0
    
    for round_data in team_answers:
        player1_item = round_data['player1_item']
        player2_item = round_data['player2_item'] 
        player1_answer = round_data['player1_answer']
        player2_answer = round_data['player2_answer']
        
        if (player1_item == 'B' and player2_item == 'Y') or \
           (player1_item == 'Y' and player2_item == 'B'):
            # Should answer differently
            score = 1 if player1_answer != player2_answer else -1
        else:
            # Should answer the same
            score = 1 if player1_answer == player2_answer else -1
            
        total_score += score
        total_rounds += 1
    
    return (total_score / total_rounds) if total_rounds > 0 else 0
```

#### Metric Visibility Controls
```python
class MetricsDisplay:
    def __init__(self, game_mode, user_level):
        self.game_mode = game_mode
        self.user_level = user_level
        
    def get_visible_metrics(self):
        if self.user_level == 'beginner':
            return ['success_rate', 'total_rounds', 'team_coordination']
        elif self.user_level == 'intermediate':
            return ['success_rate', 'balanced_trace', 'correlation_strength']
        else:  # advanced
            return ['success_rate', 'chsh_value', 'trace_avg', 'balance', 'correlation_matrix']
```

### 3. Adaptive Game Modes

#### Game Mode Selection
```python
class GameConfiguration:
    def __init__(self):
        self.mode = GameMode.CLASSIC
        self.difficulty = DifficultyLevel.BEGINNER
        self.metrics_visibility = MetricsVisibility.SIMPLE
        self.tutorial_enabled = True
        
    @classmethod
    def for_classroom(cls, grade_level):
        config = cls()
        if grade_level <= 8:
            config.difficulty = DifficultyLevel.BEGINNER
            config.metrics_visibility = MetricsVisibility.SIMPLE
        elif grade_level <= 12:
            config.difficulty = DifficultyLevel.INTERMEDIATE
            config.metrics_visibility = MetricsVisibility.MODERATE
        else:
            config.difficulty = DifficultyLevel.ADVANCED
            config.metrics_visibility = MetricsVisibility.FULL
        return config
```

#### Dashboard Mode Toggle
```javascript
// Dashboard game mode controls
function toggleGameMode() {
    const currentMode = getCurrentGameMode();
    const newMode = currentMode === 'classic' ? 'role_based' : 'classic';
    
    socket.emit('change_game_mode', {
        mode: newMode,
        preserve_teams: true  // Don't reset existing teams
    });
    
    updateModeDisplay(newMode);
    updateMetricsDisplay(newMode);
}

function updateMetricsDisplay(mode) {
    const complexMetrics = document.querySelectorAll('.complex-metric');
    const simpleMetrics = document.querySelectorAll('.simple-metric');
    
    if (mode === 'role_based') {
        complexMetrics.forEach(el => el.style.display = 'none');
        simpleMetrics.forEach(el => el.style.display = 'block');
    } else {
        complexMetrics.forEach(el => el.style.display = 'block');
        simpleMetrics.forEach(el => el.style.display = 'block');
    }
}
```

## Educational Enhancements

### 1. Tutorial System

#### Interactive Tutorial Flow
```javascript
class TutorialSystem {
    constructor() {
        this.steps = [
            {
                title: "Welcome to Quantum Game",
                content: "Learn Bell's inequality through interactive gameplay",
                action: "highlight_overview"
            },
            {
                title: "Team Formation",
                content: "Create or join a team of exactly 2 players",
                action: "highlight_team_creation"
            },
            {
                title: "Strategy Discussion",
                content: "Plan your strategy before the game starts",
                action: "show_strategy_tips"
            },
            {
                title: "Question Types",
                content: "You'll receive A, B, X, or Y questions",
                action: "demonstrate_questions"
            },
            {
                title: "Response Strategy",
                content: "Answer True/False based on your team strategy",
                action: "show_optimal_strategy"
            }
        ];
    }
    
    start() {
        this.currentStep = 0;
        this.showStep(this.currentStep);
    }
    
    showStep(stepIndex) {
        const step = this.steps[stepIndex];
        this.displayTutorialModal(step);
        this.executeStepAction(step.action);
    }
}
```

#### Strategy Explanation System
```python
class StrategyExplainer:
    @staticmethod
    def get_strategy_explanation(difficulty_level):
        if difficulty_level == 'beginner':
            return {
                'title': "Simple Strategy",
                'rules': [
                    "When you both get the same question: give the same answer",
                    "When one gets B and other gets Y: give different answers", 
                    "For all other combinations: give the same answer"
                ],
                'why': "This strategy maximizes your team's success rate!"
            }
        elif difficulty_level == 'intermediate':
            return {
                'title': "CHSH Optimal Strategy", 
                'rules': [
                    "Agree on answers for each question type beforehand",
                    "B-Y combination is special - answer differently",
                    "Track your correlation patterns"
                ],
                'why': "This demonstrates quantum entanglement behavior"
            }
        else:
            return {
                'title': "Bell Inequality Violation",
                'rules': [
                    "Implement quantum-inspired correlations",
                    "Maximize CHSH value above classical limit (2.0)",
                    "Understand the quantum advantage"
                ],
                'why': "Explore the foundations of quantum mechanics"
            }
```

### 2. Progress Tracking

#### Student Progress System
```python
class StudentProgress:
    def __init__(self, student_id):
        self.student_id = student_id
        self.completed_tutorials = set()
        self.games_played = 0
        self.best_success_rate = 0.0
        self.strategies_tried = set()
        self.achievements = set()
        
    def record_game_completion(self, game_result):
        self.games_played += 1
        self.best_success_rate = max(self.best_success_rate, game_result.success_rate)
        self.strategies_tried.add(game_result.strategy_type)
        
        # Check for achievements
        self._check_achievements(game_result)
        
    def _check_achievements(self, game_result):
        if game_result.success_rate > 0.8:
            self.achievements.add('quantum_master')
        if self.games_played >= 10:
            self.achievements.add('persistent_learner')
        if len(self.strategies_tried) >= 3:
            self.achievements.add('strategy_explorer')
```

#### Learning Analytics
```python
class LearningAnalytics:
    @staticmethod
    def analyze_student_performance(student_id):
        progress = StudentProgress.load(student_id)
        games = GameHistory.get_for_student(student_id)
        
        return {
            'proficiency_level': AnalyticsEngine.calculate_proficiency(games),
            'learning_trajectory': AnalyticsEngine.track_improvement(games),
            'recommended_next_steps': AnalyticsEngine.suggest_activities(progress),
            'concept_mastery': AnalyticsEngine.assess_understanding(games)
        }
```

### 3. Classroom Integration

#### Teacher Dashboard
```python
class TeacherDashboard:
    def __init__(self, teacher_id):
        self.teacher_id = teacher_id
        self.classes = []
        
    def get_class_overview(self, class_id):
        students = self.get_students_in_class(class_id)
        return {
            'total_students': len(students),
            'active_students': self.count_active_students(students),
            'average_success_rate': self.calculate_class_average(students),
            'struggling_students': self.identify_struggling_students(students),
            'top_performers': self.identify_top_performers(students)
        }
        
    def generate_lesson_plan(self, topic, grade_level):
        return LessonPlanGenerator.create_plan(
            topic=topic,
            grade_level=grade_level,
            game_activities=self.get_recommended_activities(grade_level)
        )
```

## User Experience Improvements

### 1. Enhanced UI/UX

#### Responsive Design
```css
/* Mobile-first responsive design */
.game-container {
    display: grid;
    grid-template-columns: 1fr;
    gap: 1rem;
    padding: 1rem;
}

@media (min-width: 768px) {
    .game-container {
        grid-template-columns: 2fr 1fr;
        padding: 2rem;
    }
}

@media (min-width: 1024px) {
    .game-container {
        grid-template-columns: 3fr 2fr;
        max-width: 1200px;
        margin: 0 auto;
    }
}
```

#### Accessibility Improvements
```javascript
class AccessibilityManager {
    constructor() {
        this.highContrast = false;
        this.largeText = false;
        this.screenReader = false;
    }
    
    enableHighContrast() {
        document.body.classList.add('high-contrast');
        this.highContrast = true;
    }
    
    enableScreenReaderMode() {
        // Add ARIA labels and descriptions
        this.addAriaLabels();
        this.announceGameEvents();
        this.screenReader = true;
    }
    
    announceGameEvents() {
        socket.on('new_question', (data) => {
            this.announce(`New question: ${data.item}. Choose True or False.`);
        });
        
        socket.on('round_complete', () => {
            this.announce('Round complete. Waiting for next question.');
        });
    }
}
```

### 2. Performance Optimizations

#### Frontend Optimizations
```javascript
// Implement virtual scrolling for large datasets
class VirtualScroller {
    constructor(container, itemHeight, totalItems) {
        this.container = container;
        this.itemHeight = itemHeight;
        this.totalItems = totalItems;
        this.visibleStart = 0;
        this.visibleEnd = 0;
        
        this.init();
    }
    
    init() {
        this.container.addEventListener('scroll', 
            this.throttle(this.handleScroll.bind(this), 16));
        this.updateVisibleItems();
    }
    
    handleScroll() {
        this.updateVisibleItems();
        this.renderVisibleItems();
    }
}

// Implement request debouncing
class RequestManager {
    constructor(delay = 300) {
        this.delay = delay;
        this.timeouts = new Map();
    }
    
    debounce(key, callback) {
        if (this.timeouts.has(key)) {
            clearTimeout(this.timeouts.get(key));
        }
        
        const timeout = setTimeout(() => {
            callback();
            this.timeouts.delete(key);
        }, this.delay);
        
        this.timeouts.set(key, timeout);
    }
}
```

## Technical Implementation

### 1. Backward Compatibility

```python
class GameModeManager:
    @staticmethod
    def migrate_existing_teams():
        """Migrate existing teams to support new game modes"""
        existing_teams = Teams.query.filter_by(is_active=True).all()
        
        for team in existing_teams:
            if not hasattr(team, 'game_mode'):
                team.game_mode = GameMode.CLASSIC
                team.metrics_visibility = MetricsVisibility.FULL
                
        db.session.commit()
        
    @staticmethod
    def ensure_backward_compatibility(team_id):
        """Ensure existing functionality works for all teams"""
        team = Teams.query.get(team_id)
        
        if team.game_mode == GameMode.CLASSIC:
            # Use original question assignment logic
            return assign_questions_classic(team_id)
        else:
            # Use new role-based logic
            return assign_questions_role_based(team_id)
```

### 2. Feature Flags

```python
class FeatureFlags:
    def __init__(self):
        self.flags = {
            'role_based_mode': os.getenv('ENABLE_ROLE_BASED_MODE', 'false').lower() == 'true',
            'tutorial_system': os.getenv('ENABLE_TUTORIAL', 'true').lower() == 'true',
            'progress_tracking': os.getenv('ENABLE_PROGRESS_TRACKING', 'false').lower() == 'true',
            'teacher_dashboard': os.getenv('ENABLE_TEACHER_DASHBOARD', 'false').lower() == 'true'
        }
    
    def is_enabled(self, flag_name):
        return self.flags.get(flag_name, False)
    
    def enable_for_user(self, user_id, flag_name):
        # Per-user feature flag logic
        user_flags = UserFeatureFlags.query.filter_by(user_id=user_id).first()
        if user_flags:
            user_flags.flags[flag_name] = True
        else:
            user_flags = UserFeatureFlags(user_id=user_id, flags={flag_name: True})
        db.session.add(user_flags)
        db.session.commit()
```

### 3. Database Schema Changes

```python
# New database models for v2 features
class GameSession(db.Model):
    __tablename__ = 'game_sessions'
    session_id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'))
    game_mode = db.Column(db.Enum(GameMode), default=GameMode.CLASSIC)
    difficulty_level = db.Column(db.Enum(DifficultyLevel), default=DifficultyLevel.BEGINNER)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
class StudentProgress(db.Model):
    __tablename__ = 'student_progress'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    game_session_id = db.Column(db.Integer, db.ForeignKey('game_sessions.session_id'))
    success_rate = db.Column(db.Float)
    rounds_completed = db.Column(db.Integer)
    strategy_used = db.Column(db.String(50))
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)

# Enhanced Teams model
class Teams(db.Model):
    # ... existing fields ...
    game_mode = db.Column(db.Enum(GameMode), default=GameMode.CLASSIC)
    player_a_role = db.Column(db.String(50))  # 'A' or 'B'
    player_b_role = db.Column(db.String(50))  # 'A' or 'B'
    metrics_visibility = db.Column(db.Enum(MetricsVisibility), default=MetricsVisibility.FULL)
```

## Testing Strategy

### 1. Backward Compatibility Testing
```python
class BackwardCompatibilityTests(unittest.TestCase):
    def test_classic_mode_still_works(self):
        """Ensure existing functionality is preserved"""
        team = self.create_classic_team()
        game_session = GameSession(team=team, mode=GameMode.CLASSIC)
        
        # Should work exactly as before
        questions = assign_questions(team.team_id)
        self.assertIn(questions[0], ['A', 'B', 'X', 'Y'])
        self.assertIn(questions[1], ['A', 'B', 'X', 'Y'])
        
    def test_existing_teams_migrate_correctly(self):
        """Test migration of existing teams"""
        # Create team without new fields
        old_team = self.create_legacy_team()
        
        # Run migration
        GameModeManager.migrate_existing_teams()
        
        # Verify defaults applied
        updated_team = Teams.query.get(old_team.team_id)
        self.assertEqual(updated_team.game_mode, GameMode.CLASSIC)
```

### 2. New Feature Testing
```python
class RoleBasedModeTests(unittest.TestCase):
    def test_role_assignment(self):
        """Test role-based question assignment"""
        team = self.create_role_based_team()
        questions = assign_questions_role_based(team.team_id)
        
        # Player A should only get A/B questions
        player_a_question = questions[team.player_a_session_id]
        self.assertIn(player_a_question, ['A', 'B'])
        
        # Player B should only get X/Y questions  
        player_b_question = questions[team.player_b_session_id]
        self.assertIn(player_b_question, ['X', 'Y'])
```

## Release Plan

### Phase 1: Core Features (Month 1-2)
- [ ] Implement role-based game mode
- [ ] Add success rate metrics
- [ ] Create mode toggle in dashboard
- [ ] Ensure backward compatibility
- [ ] Basic testing and bug fixes

### Phase 2: Educational Features (Month 3-4)
- [ ] Develop tutorial system
- [ ] Implement progress tracking
- [ ] Create strategy explanation system
- [ ] Add difficulty level controls
- [ ] User testing with educators

### Phase 3: UX Improvements (Month 5-6)
- [ ] Responsive design improvements
- [ ] Accessibility enhancements
- [ ] Performance optimizations
- [ ] Mobile app considerations
- [ ] Final testing and deployment

---

Version 2.0 will significantly enhance the educational value and accessibility of the CHSH Game while maintaining the robust foundation of the current system.
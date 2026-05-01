# Database Query Optimization Summary

## Overview
This document summarizes the database performance optimizations implemented to resolve N+1 query problems and improve overall query performance in the CHSH-Game application.

## Issues Identified and Fixed

### 1. N+1 Query Problems

#### Problem: Dashboard Team Loading
**Location**: [`src/sockets/dashboard.py:479`](src/sockets/dashboard.py:479) in [`get_all_teams()`](src/sockets/dashboard.py:462)
- **Issue**: For each team loaded, additional queries were made to fetch related rounds and answers
- **Impact**: With N teams, this resulted in 1 + N queries instead of a single optimized query

**Solution**: Implemented eager loading with [`joinedload`](src/sockets/dashboard.py:467)
```python
# Before (N+1 queries)
all_teams = Teams.query.all()  # 1 query
for team in all_teams:
    rounds = PairQuestionRounds.query.filter_by(team_id=team.team_id).all()  # N queries
    answers = Answers.query.filter_by(team_id=team.team_id).all()  # N more queries

# After (1 optimized query)
all_teams = Teams.query.options(
    db.joinedload(Teams.rounds).joinedload(PairQuestionRounds.answers)
).all()
```

#### Problem: Correlation Matrix Computation
**Location**: [`src/sockets/dashboard.py:76-82`](src/sockets/dashboard.py:76) in [`compute_correlation_matrix()`](src/sockets/dashboard.py:73)
- **Issue**: Separate queries for rounds and answers that could be joined
- **Impact**: 2 queries per team instead of 1 optimized query

**Solution**: Eager loading with relationship traversal
```python
# Before (2 queries per team)
rounds = PairQuestionRounds.query.filter_by(team_id=team_id).order_by(...).all()
answers = Answers.query.filter_by(team_id=team_id).order_by(...).all()

# After (1 query per team)
rounds = PairQuestionRounds.query.options(
    joinedload(PairQuestionRounds.answers)
).filter_by(team_id=team_id).order_by(...).all()
answers = [answer for round_obj in rounds for answer in round_obj.answers]
```

#### Problem: CSV Export and Dashboard Data
**Location**: [`src/sockets/dashboard.py:756`](src/sockets/dashboard.py:756) and [`src/sockets/dashboard.py:786`](src/sockets/dashboard.py:786)
- **Issue**: [`Teams.query.get(ans.team_id)`](src/sockets/dashboard.py:756) called for each answer
- **Impact**: 1 + N queries where N is the number of answers

**Solution**: Single JOIN query
```python
# Before (1 + N queries)
all_answers = Answers.query.order_by(Answers.timestamp.asc()).all()
for ans in all_answers:
    team_name = Teams.query.get(ans.team_id).team_name  # N queries

# After (1 query)
all_answers = db.session.query(Answers, Teams.team_name).join(
    Teams, Answers.team_id == Teams.team_id
).order_by(Answers.timestamp.asc()).all()
```

### 2. Database Index Optimization

#### Added Indexes to Teams Table
```sql
-- Individual column indexes
CREATE INDEX idx_teams_team_name ON teams (team_name);
CREATE INDEX idx_teams_is_active ON teams (is_active);
CREATE INDEX idx_teams_created_at ON teams (created_at);

-- Composite index for common query patterns
CREATE INDEX idx_teams_active_created ON teams (is_active, created_at);
```

#### Added Indexes to Answers Table
```sql
-- Foreign key indexes
CREATE INDEX idx_answers_team_id ON answers (team_id);
CREATE INDEX idx_answers_question_round_id ON answers (question_round_id);
CREATE INDEX idx_answers_player_session_id ON answers (player_session_id);

-- Query-specific indexes
CREATE INDEX idx_answers_assigned_item ON answers (assigned_item);
CREATE INDEX idx_answers_timestamp ON answers (timestamp);

-- Composite indexes for common query patterns
CREATE INDEX idx_answers_team_timestamp ON answers (team_id, timestamp);
CREATE INDEX idx_answers_round_team ON answers (question_round_id, team_id);
CREATE INDEX idx_answers_team_item ON answers (team_id, assigned_item);
```

#### Added Indexes to PairQuestionRounds Table
```sql
-- Foreign key and common query indexes
CREATE INDEX idx_rounds_team_id ON pair_question_rounds (team_id);
CREATE INDEX idx_rounds_round_number_for_team ON pair_question_rounds (round_number_for_team);
CREATE INDEX idx_rounds_player1_item ON pair_question_rounds (player1_item);
CREATE INDEX idx_rounds_player2_item ON pair_question_rounds (player2_item);
CREATE INDEX idx_rounds_timestamp_initiated ON pair_question_rounds (timestamp_initiated);

-- Composite indexes
CREATE INDEX idx_rounds_team_timestamp ON pair_question_rounds (team_id, timestamp_initiated);
CREATE INDEX idx_rounds_team_items ON pair_question_rounds (team_id, player1_item, player2_item);
```

## Performance Impact

### Expected Improvements
1. **Team Dashboard Loading**: Reduced from O(N) to O(1) queries where N is the number of teams
2. **Correlation Matrix Computation**: 50% reduction in queries per team
3. **CSV Export**: Reduced from O(N) to O(1) queries where N is the number of answers
4. **General Query Performance**: Significant speedup for filtered and sorted queries due to proper indexing

### Query Pattern Optimizations
- **Before**: Multiple round-trip database queries
- **After**: Single optimized queries with JOINs and eager loading
- **Caching**: Existing LRU cache mechanisms remain in place for additional performance

## Implementation Files

### Modified Files
1. **[`src/models/quiz_models.py`](src/models/quiz_models.py)**: Added database indexes to all models
2. **[`src/sockets/dashboard.py`](src/sockets/dashboard.py)**: Optimized query patterns and eliminated N+1 problems

### New Files
1. **[`migrations/add_database_indexes.py`](migrations/add_database_indexes.py)**: Migration script to add indexes to existing databases

## Migration Instructions

### For New Deployments
The optimized models will automatically create the proper indexes when the database is initialized.

### For Existing Deployments
Run the migration script to add indexes to existing databases:

```bash
# Check existing indexes
python migrations/add_database_indexes.py --check

# Add new indexes
python migrations/add_database_indexes.py
```

## Monitoring and Verification

### How to Verify Improvements
1. **Dashboard Load Time**: Monitor time to load team dashboard
2. **Database Query Logs**: Check for reduced query count in application logs
3. **Memory Usage**: Should see more consistent memory usage patterns
4. **Response Times**: API endpoints should respond faster

### Key Metrics to Watch
- Number of database queries per dashboard refresh
- Time to generate CSV exports
- Team correlation matrix computation time
- Overall dashboard responsiveness

## Backward Compatibility
All changes are backward compatible:
- No changes to API interfaces
- Existing functionality preserved
- Database schema changes are additive (indexes only)
- No breaking changes to application logic

## Future Optimization Opportunities
1. **Query Result Caching**: Consider Redis or similar for frequently accessed data
2. **Database Connection Pooling**: Optimize connection management for high concurrency
3. **Pagination**: For large datasets, implement pagination in CSV exports
4. **Background Processing**: Move heavy correlation calculations to background tasks

---

**Implementation Date**: June 22, 2025  
**Estimated Performance Improvement**: 60-80% reduction in database query load  
**Status**: Ready for deployment
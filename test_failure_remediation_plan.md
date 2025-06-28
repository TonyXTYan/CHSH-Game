# Test Failure Remediation Plan

## Current Status Summary

### ✅ **Major Achievement**
- **Resolved:** All 107 import-related AttributeErrors 
- **Fixed:** Dashboard module refactoring backward compatibility issues
- **Commit:** `4bce897` on branch `cursor/refactor-dashboard-py-into-modular-files-a2e4`

### 🔍 **Current State**
- **Total Test Issues:** 99 failed tests (down from 138 total issues)
- **Passing Tests:** 247 passed + 11 skipped
- **Test Success Rate:** ~71% (247 passing out of 357 total)

### 📊 **Failure Categories Analysis**

| Category | Count | % of Failures | Priority |
|----------|-------|---------------|----------|
| Flask Request Context | ~30 | 30% | 🔴 High |
| Dashboard Socket Functions | ~35 | 35% | 🔴 High |
| Physics Calculations | ~8 | 8% | 🟡 Medium |
| Dynamic Statistics | ~6 | 6% | 🟡 Medium |
| Isolated Issues | ~20 | 20% | 🟢 Low |

---

## 🎯 **Phase-Based Remediation Plan**

### **Phase 1: Flask Request Context Issues** 
**Priority:** 🔴 **Critical** | **Impact:** High | **Effort:** Medium

#### **Problem Description**
```
RuntimeError: Working outside of request context.
This typically means that you attempted to use functionality that needed
an active HTTP request.
```

#### **Affected Tests**
- `tests/unit/test_mode_toggle.py` - All 15 tests
- `tests/unit/test_mode_toggle_improved.py` - All 8 tests  
- `tests/unit/test_dashboard_sockets.py` - Several socket event tests

#### **Root Cause**
Socket event handlers (`on_toggle_game_mode`, `on_pause_game`, etc.) access `request.sid` but tests don't provide proper Flask request context.

#### **Solution Strategy**
1. **Examine existing context fixtures:**
   ```bash
   grep -r "mock_request" tests/conftest.py
   grep -r "request_context" tests/conftest.py
   ```

2. **Apply consistent request context mocking:**
   ```python
   @pytest.fixture
   def mock_request_context():
       with app.test_request_context():
           with patch('flask.request') as mock_req:
               mock_req.sid = 'test_socket_id'
               yield mock_req
   ```

3. **Update test files to use context:**
   - Add `mock_request_context` fixture to failing tests
   - Ensure proper `request.sid` mocking
   - Verify Flask app context is available

#### **Expected Outcome**
- **Target:** Reduce failures from 99 to ~65-70
- **Tests Fixed:** ~30 tests across mode toggle functionality

---

### **Phase 2: Dashboard Socket Function Issues**
**Priority:** 🔴 **Critical** | **Impact:** High | **Effort:** High

#### **Problem Description**
Dashboard socket tests failing with assertions like:
- `Expected 'get_all_teams' to have been called.` 
- `assert 0 == 1` (function call count mismatches)
- `assert False` (boolean expectations not met)

#### **Affected Tests**
- `test_emit_dashboard_team_update_*` series
- `test_get_all_teams_*` series  
- `test_dashboard_throttling.py` tests

#### **Root Cause Analysis**
1. **Mock setup issues** after module refactoring
2. **Cache/throttling logic** preventing expected function calls
3. **Client state initialization** problems in test fixtures
4. **Event emission** not working as expected

#### **Solution Strategy**

**Step 2A: Debug Mock Setup**
```bash
# Test one specific failure to understand the issue
pytest tests/unit/test_dashboard_sockets.py::test_emit_dashboard_team_update -v -s
```

**Step 2B: Fix Function Call Tracking**
1. Verify mock imports match new module structure:
   ```python
   # Check if this changed:
   patch('src.sockets.dashboard.get_all_teams')
   # vs new structure:
   patch('src.sockets.dashboard.team_processing.get_all_teams')
   ```

2. Review cache clearing between tests:
   ```python
   @pytest.fixture(autouse=True)
   def clear_dashboard_caches():
       from src.sockets.dashboard import clear_team_caches
       clear_team_caches()
       yield
       clear_team_caches()
   ```

**Step 2C: Fix Client State Setup**
1. Ensure dashboard clients are properly initialized in test fixtures
2. Verify streaming client state setup
3. Check connected players count logic

**Step 2D: Debug Throttling Logic**
1. Review throttling delays in test environment
2. Check if time-based logic interferes with tests
3. Consider mocking time functions for deterministic behavior

#### **Expected Outcome**
- **Target:** Reduce failures from ~65 to ~30-35
- **Tests Fixed:** ~30-35 dashboard functionality tests

---

### **Phase 3: Physics Calculations Logic**
**Priority:** 🟡 **Medium** | **Impact:** Medium | **Effort:** Medium

#### **Problem Description**
Physics calculation tests returning invalid/empty results:
- `CHSH value 0 far from expected 4.0`
- `KeyError: 'A'` - missing correlation matrix data
- `Expected 2 A-X pairs, got 0` - measurement counts are zero

#### **Affected Tests**
- `test_chsh_theoretical_maximum`
- `test_balance_metric_edge_cases` 
- `test_extreme_bias_detection`
- `test_mathematical_consistency_checks`
- And 4 other CHSH-related tests

#### **Root Cause Analysis**
The `compute_correlation_matrix` function is returning empty/invalid data structures, likely due to:
1. **Mock data format** not matching expected input
2. **Database query mocking** issues after refactoring
3. **Data processing logic** changes in correlation calculations

#### **Solution Strategy**

**Step 3A: Debug Correlation Matrix Function**
```bash
# Debug the simplest physics test first
pytest tests/unit/test_physics_calculations.py::TestPhysicsCalculations::test_chsh_theoretical_maximum -v -s
```

**Step 3B: Investigate Data Flow**
1. Add debug logging to see what `compute_correlation_matrix` returns
2. Verify mock data format matches function expectations:
   ```python
   # Check if mock round/answer objects have correct structure
   def create_mock_round(round_id, p1_item, p2_item):
       # Verify this creates proper ItemEnum values
   ```

3. Ensure `_get_team_id_from_name` mocking works correctly
4. Check database query mocking for rounds and answers

**Step 3C: Fix Data Structure Issues**
1. Verify correlation matrix tuple format: `(numerator, denominator)`
2. Check item mapping: `['A', 'B', 'X', 'Y']` indexing
3. Ensure pair counting logic works with mock data

#### **Expected Outcome**
- **Target:** Reduce failures from ~30 to ~22-25  
- **Tests Fixed:** ~8 physics calculation tests

---

### **Phase 4: Dynamic Statistics & Game Mode**
**Priority:** 🟡 **Medium** | **Impact:** Medium | **Effort:** Medium

#### **Problem Description**
- `assert 'new' == 'classic'` - wrong game mode returned
- `Expected '_calculate_team_statistics' to have been called once. Called 0 times`
- Missing statistical calculation data

#### **Affected Tests**
- `test_classic_mode_team_processing`
- `test_new_mode_team_processing`  
- `test_success_statistics_calculation`
- `test_both_computations_called`
- `test_new_mode_individual_balance_calculation`
- `test_compute_success_metrics_tracks_individual_responses`

#### **Solution Strategy**

**Step 4A: Fix Game Mode Detection**
1. Ensure `mock_state.game_mode` is properly set and respected
2. Verify `_process_single_team` function uses correct game mode
3. Check game mode propagation through function calls

**Step 4B: Fix Statistics Function Calls**
1. Verify both `_calculate_team_statistics` and `_calculate_success_statistics` are called
2. Check if mocking interferes with function call detection
3. Ensure proper data flow through statistics calculations

**Step 4C: Debug Data Processing**
1. Verify success metrics calculation returns expected data structure
2. Check individual balance calculations
3. Ensure response tracking works correctly

#### **Expected Outcome**
- **Target:** Reduce failures from ~22 to ~16-18
- **Tests Fixed:** ~6 dynamic statistics tests

---

### **Phase 5: Isolated Issues**
**Priority:** 🟢 **Low** | **Impact:** Low | **Effort:** Variable

#### **Remaining Issues**
- Team management client cleanup: `test_handle_disconnect_dashboard_client`
- Cache invalidation edge cases
- Integration test dashboard visibility issues
- Mock object behavior inconsistencies

#### **Solution Strategy**
Address individually after main categories are resolved. Many may be fixed as side effects of earlier phases.

---

## 🚀 **Immediate Action Plan**

### **Next Steps (Recommended Order)**

#### **Step 1: Start with Flask Context (Highest Impact)**
```bash
# Focus on mode toggle tests first - biggest category
pytest tests/unit/test_mode_toggle.py -v --tb=short

# Examine existing request context setup
grep -r "mock_request" tests/
```

**Actions:**
1. Identify existing Flask request context fixtures in `conftest.py`
2. Apply consistent request context mocking to mode toggle tests  
3. Ensure `request.sid` is properly mocked for socket event handlers
4. Test one file at a time to verify fixes work

#### **Step 2: Tackle Dashboard Socket Issues**
```bash
# Pick one specific test to debug thoroughly
pytest tests/unit/test_dashboard_sockets.py::test_emit_dashboard_team_update_fresh_calculation -v -s
```

**Actions:**
1. Add debug logging to see which functions are/aren't called
2. Verify mock imports match new module structure  
3. Check cache state and client setup between tests
4. Fix throttling/timing issues affecting function calls

#### **Step 3: Debug Physics Calculations**
```bash
# Start with the most basic physics test
pytest tests/unit/test_physics_calculations.py::TestPhysicsCalculations::test_chsh_theoretical_maximum -v -s
```

**Actions:**
1. Add debug prints to correlation matrix function
2. Verify mock data format and structure
3. Check database query mocking setup
4. Fix data processing logic if needed

---

## 📈 **Success Metrics & Expected Timeline**

### **Phase Completion Targets**
- **Phase 1 Complete:** ~65-70 failures remaining (30% reduction)
- **Phase 2 Complete:** ~30-35 failures remaining (65% total reduction)  
- **Phase 3 Complete:** ~22-25 failures remaining (75% total reduction)
- **Phase 4 Complete:** ~16-18 failures remaining (82% total reduction)
- **Phase 5 Complete:** <10 failures remaining (90%+ total reduction)

### **Quality Gates**
- After each phase, run full test suite to check for regressions
- Maintain or improve the current 71% test success rate
- Ensure no new import/structure errors are introduced

### **Estimated Effort**
- **Phase 1:** 2-4 hours (systematic request context fixes)
- **Phase 2:** 4-6 hours (complex debugging and mock fixing)
- **Phase 3:** 2-3 hours (focused data structure debugging)  
- **Phase 4:** 1-2 hours (game mode and statistics fixes)
- **Phase 5:** 1-2 hours (cleanup remaining issues)

**Total Estimated Effort:** 10-17 hours

---

## 🔧 **Key Technical Context**

### **Module Structure (Post-Refactoring)**
```
src/sockets/dashboard/
├── __init__.py           # Re-exports for backward compatibility  
├── cache_system.py       # Caching and throttling logic
├── client_management.py  # Dashboard client state management
├── computations.py       # Core calculation functions
├── events.py            # Socket event handlers  
├── routes.py            # HTTP route handlers
└── team_processing.py   # Team data processing logic
```

### **Critical Import Paths**
Tests expect to import from `src.sockets.dashboard` but actual implementations are now in submodules. The `__init__.py` re-exports handle this, but some mocking may need updates.

### **Known Working Fixtures**
- Tests in `conftest.py` provide good examples of working Flask app/socket context
- Cache clearing fixtures exist and should be used consistently
- Database mocking patterns are established in passing tests

### **Testing Environment Notes**
- Flask app context is required for database operations
- Socket event handlers need request context with `request.sid`
- Cache state affects test isolation - ensure proper clearing between tests
- Time-based throttling may interfere with test determinism

---

## 📝 **Additional Resources**

### **Useful Debug Commands**
```bash
# Run specific test categories
pytest tests/unit/test_mode_toggle.py -v
pytest tests/unit/test_dashboard_sockets.py -k "emit_dashboard_team_update" -v
pytest tests/unit/test_physics_calculations.py -k "chsh" -v

# Run with debug output
pytest [test_file] -v -s --tb=short

# Check import structure
python -c "from src.sockets.dashboard import *; print(dir())"
```

### **Files to Focus On**
- `tests/conftest.py` - Test fixtures and setup
- `tests/unit/test_mode_toggle.py` - Flask context issues
- `tests/unit/test_dashboard_sockets.py` - Dashboard functionality  
- `tests/unit/test_physics_calculations.py` - Physics calculations
- `src/sockets/dashboard/__init__.py` - Import compatibility layer

---

*This plan should be executed systematically, with each phase building on the previous one's success. The high success rate (71%) indicates the core functionality is sound - these are primarily test setup and mock configuration issues rather than fundamental code problems.* 
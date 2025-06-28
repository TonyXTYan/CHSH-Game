# Test Failure Remediation Plan

## Current Status Summary

### ✅ **Major Achievement**
- **Resolved:** All 107 import-related AttributeErrors 
- **Fixed:** Dashboard module refactoring backward compatibility issues
- **Commit:** `4bce897` on branch `cursor/refactor-dashboard-py-into-modular-files-a2e4`

### 🎉 **Recent Progress Update**
- **Phase 1 COMPLETE:** All Flask request context issues resolved (23 tests fixed)
- **Phase 2 IN PROGRESS:** Dashboard socket issues being systematically addressed
- **Mock Path Pattern Identified:** `src.sockets.dashboard.*` → `src.sockets.dashboard.events.*`

### 🔍 **Updated Current State**
- **Total Test Issues:** 67 failed tests (down from 99, was 138 originally)
- **Passing Tests:** 279 passed + 11 skipped (up from 247)
- **Test Success Rate:** ~78% (279 passing out of 357 total, up from 71%)
- **Tests Fixed in Latest Round:** 32 tests resolved

### 📊 **Updated Failure Categories Analysis**

| Category | Original Count | Current Count | Status | Priority |
|----------|---------------|---------------|---------|----------|
| Flask Request Context | ~30 | 0 | ✅ **COMPLETE** | 🎉 Done |
| Dashboard Socket Functions | ~35 | ~30 | 🔄 **IN PROGRESS** | 🔴 High |
| Physics Calculations | ~8 | ~8 | ⏳ Pending | 🟡 Medium |
| Dynamic Statistics | ~6 | ~6 | ⏳ Pending | 🟡 Medium |
| Integration/Isolated Issues | ~20 | ~23 | ⏳ Pending | 🟢 Low |

---

## 🎯 **Updated Phase-Based Remediation Plan**

### ✅ **Phase 1: Flask Request Context Issues - COMPLETE** 
**Status:** 🎉 **COMPLETED** | **Achievement:** 23/23 tests fixed (100% success rate)

#### **What Was Fixed**
- All `tests/unit/test_mode_toggle.py` tests (15 tests)
- All `tests/unit/test_mode_toggle_improved.py` tests (8 tests)
- Socket event tests with request context issues

#### **Successful Solution Pattern**
```python
# Applied consistent mock_request_context fixture
@pytest.fixture  
def mock_request_context():
    with patch('flask.request') as mock_req:
        mock_req.sid = 'test_socket_id'
        yield mock_req
```

#### **Key Discovery: Mock Path Updates**
**Critical Pattern Identified:** Mock imports needed updating after module refactoring:
```python
# OLD (broken after refactoring):
patch('src.sockets.dashboard.on_toggle_game_mode')

# NEW (working pattern):
patch('src.sockets.dashboard.events.on_toggle_game_mode')
```

#### **Impact Achieved**
- **Target:** Reduce failures from 99 to ~65-70 ✅
- **Actual:** Reduced failures from 99 to 67 (32 tests fixed total)
- **Success Rate:** Improved from 71% to 78% (+7 percentage points)

---

### 🔄 **Phase 2: Dashboard Socket Function Issues - IN PROGRESS**
**Priority:** 🔴 **Critical** | **Impact:** High | **Status:** 1/~30 tests fixed

#### **Progress Update**
- ✅ **Pattern Established:** Successfully updated mock paths in `test_dashboard_sockets.py`
- ✅ **First Test Fixed:** `test_emit_dashboard_team_update` working
- 🔄 **Systematic Approach:** Mock import paths being updated across entire file

#### **Established Working Pattern**
```python
# OLD mock paths (causing failures):
patch('src.sockets.dashboard.get_all_teams')
patch('src.sockets.dashboard.emit_dashboard_team_update') 
patch('src.sockets.dashboard.clear_team_caches')

# NEW working paths (after refactoring):
patch('src.sockets.dashboard.team_processing.get_all_teams')
patch('src.sockets.dashboard.events.emit_dashboard_team_update')
patch('src.sockets.dashboard.cache_system.clear_team_caches')
```

#### **Remaining Dashboard Socket Issues**
Based on latest test results, still failing:
- `test_pause_game_*` - Event handler mocking
- `test_compute_correlation_matrix_*` - Computation function paths  
- `test_on_keep_alive` - Client management paths
- `test_handle_dashboard_disconnect` - Client cleanup paths
- `test_get_all_teams*` - Team processing paths
- `test_emit_dashboard_*` series - Event emission paths
- `test_dashboard_throttling.py` tests - Cache and throttling paths

#### **Next Steps for Phase 2**
1. **Systematically update all mock imports** in `test_dashboard_sockets.py`:
   ```bash
   # Apply the established pattern to remaining ~29 tests
   sed -i "s/src\.sockets\.dashboard\.get_all_teams/src.sockets.dashboard.team_processing.get_all_teams/g" tests/unit/test_dashboard_sockets.py
   ```

2. **Update dashboard throttling test paths** in `test_dashboard_throttling.py`
3. **Fix client state setup** issues revealed by working tests
4. **Address cache/throttling logic** with proper mock paths

#### **Expected Outcome (Updated)**
- **Target:** Reduce failures from 67 to ~35-40 
- **Tests to Fix:** ~27-30 dashboard functionality tests
- **Timeline:** Should accelerate now that pattern is established

---

### **Phase 3: Physics Calculations Logic**
**Priority:** 🟡 **Medium** | **Impact:** Medium | **Effort:** Medium | **Status:** Unchanged

#### **Current Failures (Still Present)**
From latest test results:
- `CHSH value 0 far from expected 4.0`
- `KeyError: 'A'` - missing correlation matrix data  
- `Expected 2 A-X pairs, got 0` - measurement counts are zero
- `test_chsh_*` series still failing

#### **Updated Solution Strategy**
Apply the same mock path pattern to physics tests:
```python
# Check if these need updating:
patch('src.sockets.dashboard.compute_correlation_matrix')
# To:
patch('src.sockets.dashboard.computations.compute_correlation_matrix')
```

#### **Expected Outcome**
- **Target:** Reduce failures from ~35 to ~27-30
- **Tests to Fix:** ~8 physics calculation tests

---

### **Phase 4: Dynamic Statistics & Game Mode** 
**Priority:** 🟡 **Medium** | **Impact:** Medium | **Status:** Unchanged

#### **Current Failures (Still Present)**
- `assert 'new' == 'classic'` - wrong game mode returned
- `Expected '_calculate_team_statistics' to have been called once. Called 0 times`
- Missing statistical calculation data

#### **Updated Solution Strategy**
Apply mock path updates:
```python
# Likely need to update:
patch('src.sockets.dashboard._calculate_team_statistics')
patch('src.sockets.dashboard._calculate_success_statistics')
# To:
patch('src.sockets.dashboard.computations._calculate_team_statistics') 
patch('src.sockets.dashboard.computations._calculate_success_statistics')
```

#### **Expected Outcome**
- **Target:** Reduce failures from ~27 to ~21-24
- **Tests to Fix:** ~6 dynamic statistics tests

---

### **Phase 5: Isolated Issues**
**Priority:** 🟢 **Low** | **Impact:** Low | **Status:** Some new issues identified

#### **Remaining Issues**
From latest results:
- Integration test: `test_player_tries_to_join_full_team` 
- Team management: `test_handle_disconnect_dashboard_client`
- Cache edge cases and mock object inconsistencies

#### **Expected Outcome**
- **Target:** <10 failures remaining
- **Tests to Fix:** ~15-20 remaining isolated issues

---

## 🚀 **Updated Immediate Action Plan**

### **Step 1: Complete Phase 2 - Dashboard Socket Issues (PRIORITY)**
```bash
# Apply established pattern to remaining dashboard tests
pytest tests/unit/test_dashboard_sockets.py -v --tb=short
pytest tests/unit/test_dashboard_throttling.py -v --tb=short
```

**Actions:**
1. **Systematically update all mock imports** using the established pattern
2. **Apply to dashboard throttling tests** 
3. **Verify each submodule path:**
   - `events.*` - Socket event handlers
   - `team_processing.*` - Team data functions  
   - `computations.*` - Calculation functions
   - `cache_system.*` - Cache and throttling
   - `client_management.*` - Client state management

### **Step 2: Apply Pattern to Physics & Statistics Tests**
```bash
# Update mock paths in remaining test files
pytest tests/unit/test_physics_calculations.py -k "chsh" -v
pytest tests/unit/test_dynamic_statistics.py -v
```

**Actions:**
1. **Update computation function paths** in physics tests
2. **Update statistics function paths** in dynamic statistics tests
3. **Verify game mode handling** with correct imports

### **Step 3: Clean Up Remaining Issues**
```bash
# Address final isolated failures
pytest tests/unit/test_team_management.py::test_handle_disconnect_dashboard_client -v
pytest tests/integration/test_player_interaction.py::TestPlayerInteraction::test_player_tries_to_join_full_team -v
```

---

## 📈 **Updated Success Metrics & Timeline**

### **Achievement Summary**
- ✅ **Resolved:** 138 → 67 total failures (51% reduction achieved)
- ✅ **Success Rate:** 69% → 78% (+9 percentage points)
- ✅ **Pattern Established:** Systematic mock path update approach proven

### **Revised Phase Completion Targets**
- ✅ **Phase 1 Complete:** 99 → 67 failures (32 tests fixed) 
- 🔄 **Phase 2 Target:** 67 → 35-40 failures (~27-30 tests to fix)
- ⏳ **Phase 3 Target:** 35-40 → 27-30 failures (~8 tests to fix)
- ⏳ **Phase 4 Target:** 27-30 → 21-24 failures (~6 tests to fix) 
- ⏳ **Phase 5 Target:** <10 failures remaining (~15-20 tests to fix)

### **Revised Timeline (Accelerated)**
- **Phase 2:** 2-3 hours (pattern established, systematic application)
- **Phase 3:** 1-2 hours (apply same pattern)
- **Phase 4:** 1 hour (apply same pattern)  
- **Phase 5:** 1-2 hours (cleanup remaining issues)

**Total Remaining Effort:** 5-8 hours (reduced from 10-17 hours)

---

## 🔧 **Key Technical Context - UPDATED**

### **Critical Discovery: Mock Path Mapping**
The dashboard module refactoring requires updating ALL test mock imports:

```python
# BEFORE (src.sockets.dashboard.*)
src.sockets.dashboard.on_toggle_game_mode         → src.sockets.dashboard.events.on_toggle_game_mode
src.sockets.dashboard.emit_dashboard_team_update  → src.sockets.dashboard.events.emit_dashboard_team_update  
src.sockets.dashboard.get_all_teams              → src.sockets.dashboard.team_processing.get_all_teams
src.sockets.dashboard.compute_correlation_matrix → src.sockets.dashboard.computations.compute_correlation_matrix
src.sockets.dashboard.clear_team_caches         → src.sockets.dashboard.cache_system.clear_team_caches
src.sockets.dashboard._calculate_team_statistics → src.sockets.dashboard.computations._calculate_team_statistics
```

### **Proven Systematic Approach**
1. **Identify failing test category**
2. **Map old mock paths to new submodule paths**  
3. **Update imports systematically** 
4. **Verify with targeted test runs**
5. **Move to next category**

### **Module Structure Reference**
```
src/sockets/dashboard/
├── events.py            # Socket event handlers (on_*, emit_*)
├── team_processing.py   # Team data functions (get_all_teams, _process_*)  
├── computations.py      # Calculation functions (compute_*, _calculate_*)
├── cache_system.py      # Cache/throttling (clear_*, _cache, throttling)
├── client_management.py # Client state (dashboard_*, handle_disconnect)
└── routes.py           # HTTP routes (less commonly mocked)
```

---

## 📝 **Updated Resources for Next AI**

### **Immediate Commands to Continue**
```bash
# Continue Phase 2 - Dashboard Socket fixes
grep -r "patch('src\.sockets\.dashboard\." tests/unit/test_dashboard_sockets.py
grep -r "patch('src\.sockets\.dashboard\." tests/unit/test_dashboard_throttling.py

# Apply systematic updates
sed -i "s/src\.sockets\.dashboard\.get_all_teams/src.sockets.dashboard.team_processing.get_all_teams/g" tests/unit/test_dashboard_sockets.py

# Verify progress  
pytest tests/unit/test_dashboard_sockets.py -v --tb=no -q
```

### **Success Pattern to Replicate**
The successful approach proven in Phase 1:
1. ✅ **Identify the test category** (Flask context, dashboard sockets, etc.)
2. ✅ **Find the pattern** (mock import paths need updating)
3. ✅ **Apply systematically** (update all instances of the pattern)
4. ✅ **Verify success** (run targeted tests to confirm fixes)
5. ✅ **Move to next category** (repeat the process)

---

*With Phase 1 complete and the systematic approach proven, the remaining phases should progress much faster. The pattern of updating mock import paths from `src.sockets.dashboard.*` to the appropriate submodule paths is the key to resolving the majority of remaining failures.* 
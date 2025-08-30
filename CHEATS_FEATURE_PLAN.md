## Cheats Feature Implementation Plan

### Phased Implementation (4 Steps)

Step 1 — Foundations, Flags, and Safety Nets
- Scope:
  - Implement robust `cheat_type` parser; store `cheat_type` only in `state.active_teams` (no DB schema change).
  - Add server kill switch and moderation guardrails: `state.cheats_banned` (default False); optionally read env `CHEATS_DISABLED=true` at boot to force-ban as a safety default in prod.
  - Ensure non-cheat teams are 100% unaffected: no new events, validations unchanged, and no client UI changes unless `cheat_type != 'none'`.
  - Logging scaffolding for cheat detection, emissions, and auto-fill decisions.
- Testing:
  - Unit: `parse_cheat_type` (case-insensitive, suffixes, malformed inputs).
  - Isolation: assert non-cheat teams never receive `cheat:*` events and follow existing rules.
- Definition of Done:
  - Parser is battle-tested; kill switch respected everywhere cheats would activate; logs in place; no behavior change for honest teams.

Step 2 — Detection Surfacing and Dashboard Moderation
- Scope:
  - Expose `cheat` and `cheat_type` in `get_all_teams()`; render 🤡 and a compact tag `[com|hint|tony|kevin]` in the dashboard.
  - Wire the dashboard “Ban Cheats” toggle to set `state.cheats_banned`, kick active cheating teams, and block future `cheat-*` joins/reactivations.
  - Emit `cheats_ban_changed` to dashboards and trigger a full refresh.
- Testing:
  - Integration: dashboard shows 🤡 and tag; toggling ban kicks cheaters and blocks new joins; honest teams unaffected.
- Definition of Done:
  - Dashboard moderation works end-to-end; no regressions in dashboard metrics or team lifecycle for honest teams.

Step 3 — Communication and Hints (cheat-com, cheat-hint)
- Scope:
  - `cheat-com`: on submit, emit `cheat:partner_choice` to the teammate.
  - `cheat-hint`: emit at most twice per round (round start; after first answer) with recommended button + rainbow glow + parity reason; cache round parity to avoid recompute.
  - AQM Joe v1: disable hints (acts like com only) to avoid leaking mode-specific logic.
- Testing:
  - Integration: partner choice on submit; hint at round start and after first answer; AQM Joe mode → no hints.
  - Isolation: non-cheat teams continue to receive no `cheat:*` events.
- Definition of Done:
  - Correct, rate-limited emissions; no cross-team leakage; UI glow shows/hides reliably; AQM Joe policy respected.

Step 4 — Single-player Autocomplete (cheat-tony, cheat-kevin) with Transactions
- Scope:
  - Relax `on_submit_answer` and `start_new_round_for_pair` only for `cheat-tony`/`cheat-kevin` when exactly one player is connected.
  - Auto-fill partner answer transactionally (win for tony, lose for kevin) if single-player at submit time; do not auto-fill if the second player is present or joins before commit.
  - Client: keep answer buttons enabled for incomplete tony/kevin teams.
- Testing:
  - Integration: single-player submit auto-completes and advances round; avoid double-insert under concurrent second submit; buttons remain enabled when `waiting_pair`.
  - Isolation: DB writes remain bounded (one round row, max two answers); non-cheat teams unchanged.
- Definition of Done:
  - Stable single-player flow with correct transactional semantics and clean rollback on conflict; telemetry confirms no duplicate inserts.

### Overview
- Enable optional cheat behaviors when a team name starts with a cheat prefix (case-insensitive).
- Allowed prefixes (case-insensitive):
  - `cheat-com*`: immediately show partner’s submitted choice in the other player’s UI.
  - `cheat-hint*`: includes `cheat-com` plus show the winning hint with reasoning and rainbow glow on the recommended button.
  - `cheat-tony*`: single-player team auto-wins consistent with player’s own choice.
  - `cheat-kevin*`: single-player team auto-loses consistent with player’s own choice.
- Admin dashboard gets a “Ban cheats” toggle that kicks current cheating teams and blocks new `cheat-*` teams. Dashboard marks cheat-enabled teams with 🤡.

Non-goals: change scoring/metrics; persist cheat history beyond current session.

---

### Integration Points with Existing Code

- Team lifecycle: `src/sockets/team_management.py`
  - Hook cheat detection in `on_create_team` and `on_join_team` using the team name; store cheat flags into in-memory team state.
  - Enforce ban in `on_create_team`, `on_join_team`, and `on_reactivate_team`.

- Round generation & answers: `src/game_logic.py`, `src/sockets/game.py`
  - At `start_new_round_for_pair(team_name)`: if team has hint cheat, emit per-player hints right after `new_question`.
  - At `on_submit_answer`: for `cheat-com` and `cheat-hint`, emit partner’s choice to teammate; for `cheat-tony`/`cheat-kevin` handle auto-fill of partner answer when team has one active player.
  - Single-player relaxations for `cheat-tony`/`cheat-kevin`:
    - `on_submit_answer`: relax the current checks that require two connected players and `status == 'active'`; allow submission when `len(players) == 1` and `status == 'waiting_pair'` for these cheat types.
    - `start_new_round_for_pair`: if `cheat_type in {"tony","kevin"}` and exactly one player is connected, still create the DB round and emit `new_question` only to the connected player; store `current_db_round_id` so subsequent auto-fill can complete the round. If the second player later joins mid-round, stop auto-fill for that round and proceed with standard two-player logic.

- Dashboard: `src/sockets/dashboard.py`, `src/static/dashboard.js`, `src/static/dashboard.html`
  - Add server-side flag in state and an event to toggle ban.
  - Mark teams with 🤡 in dashboard teams table when cheating.
  - Add advanced controls toggle to ban/unban cheats.

- Player UI: `src/static/socket-handlers.js`, `src/static/app.js`, `src/static/styles.css`
  - Add handlers for new events (partner choice and hints) and apply `.status-message` updates and rainbow glow class.

---

### State and Data Model

- File: `src/state.py`
  - Add `cheats_banned: bool` (default False) to global state; optionally seed from env `CHEATS_DISABLED=true` during app init.
  - Extend `state.active_teams[team_name]` structure with:
    - `cheat_type: Literal["none","com","hint","tony","kevin"]` (store only this; derive `is_cheater` as `cheat_type != "none"` wherever needed)
    - `cached_round_parity: Optional[Literal["same","different"]]` (cache per round to avoid recompute; clear on new round)

Parsing helper (to be added in `team_management.py` or a small util near it, robust and defensive):
```python
import re

CHEAT_RE = re.compile(r'^cheat-(com|hint|tony|kevin)(?:$|[-_\s].*)', re.IGNORECASE)

def parse_cheat_type(team_name: str) -> str:
    try:
        name = (team_name or "").strip()
        m = CHEAT_RE.match(name)
        if not m:
            return "none"
        return m.group(1).lower()
    except Exception:
        # Never throw from parsing; default to no-cheat on any error
        return "none"
```

Ban enforcement:
- If `state.cheats_banned` is True and team name matches `^cheat-`, reject/emit error; if an existing team is detected cheating when the toggle flips on, mark it inactive and disconnect players (emit `team_disbanded`).

---

### Parity and Recommendation Helpers

- File: `src/game_logic.py` (new helpers near existing logic):
  - `get_required_parity(p1_item: ItemEnum, p2_item: ItemEnum) -> Literal["same","different"]`
    - Rule: BY (and YB) requires different; others require same. This matches existing optimal strategy displayed in UI and tests.
  - `recommend_answers(parity, known_left: Optional[bool], known_right: Optional[bool]) -> Tuple[bool,bool]`
    - If both unknown: choose seed = random bool; return (seed, seed) for same else (seed, not seed).
    - If one known: compute the other accordingly.

These helpers ensure hints and auto-fill compute consistently with scoring and with both Classic/Simplified item generation.

---

### AQM Joe Mode Hint Policy

- For v1, disable `cheat-hint` recommendations in AQM Joe mode to avoid leaking AQM Joe–specific mapping complexities. Behavior: `cheat-hint` acts like `cheat-com` in AQM Joe mode (partner-choice only; no hints emitted).
- Optional future extension (not in v1 scope): implement AQM Joe–specific recommendations using the existing `evaluateAqmJoeResult` policy in `app.js` to derive a consistent recommendation engine on the server.

Tests should assert that in AQM Joe mode, `cheat-hint` teams receive `cheat:partner_choice` but no `cheat:hint` events.

---

### Socket Events and Flows

Existing events: `new_question`, `answer_confirmed`, `round_complete`.

New server→client events (players):
- `cheat:partner_choice` → `{ partnerChoice: boolean, at: isoString }`
- `cheat:hint` → `{ recommended: boolean, parity: "same"|"different", reason: string, at: isoString }`

New dashboard events (dashboard clients):
- `cheats_ban_changed` → `{ banned: boolean, kicked_teams: int, kicked_players: int }`

New dashboard→server events:
- `dashboard:toggle_cheats_ban` → `{ banned: boolean }`

Server changes:
- `team_management.py`
  - On create/reactivate/join: compute `cheat_type`, store in `state.active_teams[team_name]`.
  - If banned and name matches `^cheat-`: emit `error` and do not create/join.

- `game_logic.py`
  - After emitting `new_question` to both players, if `cheat_type in {"hint"}`: compute and emit `cheat:hint` to both players.

- `sockets/game.py:on_submit_answer`
  - After DB commit and before round completion:
    - For `com`/`hint`: identify partner SID via team db slots and emit `cheat:partner_choice` to the teammate with the submitted boolean.
    - For `tony`/`kevin`: if only one player currently in team (`len(team_info['players'])==1`) and only one answer exists for this round, auto-insert partner `Answers` row with the value required to win (`tony`) or to lose (`kevin`) given parity and known answer; mark answered and continue normal completion flow. If the second player is connected at submission time, do not auto-fill and fall back to standard logic.

Client changes:
- `src/static/socket-handlers.js`
  - Add listeners for `cheat:partner_choice` and `cheat:hint`.
  - Display partner choice via `.status-message` immediately.
  - For hints, add/remove `rainbow-glow` class to the recommended button until user answers or next round.
- `src/static/app.js`
  - Reset glow/hint state at `onNewQuestion` and when `onAnswerConfirmed` fires.
  - Keep answer buttons enabled for `cheat-tony`/`cheat-kevin` teams even when the team is incomplete (`waiting_pair`). Implementation: include `cheat_type` in player-facing events (`team_created`, `team_joined`, `team_status_update`), track it in client state, and in `updateGameState()` bypass the incomplete-team disable branch when `cheat_type in {"tony","kevin"}`.
- `src/static/styles.css`
  - Add `.rainbow-glow` animation class (simple keyframes, no layout changes).

Dashboard:
- `src/static/dashboard.html`
  - In Advanced Controls, add a toggle/button (e.g., “Ban Cheats”).
- `src/static/dashboard.js`
  - Emit `dashboard:toggle_cheats_ban` with the desired state.
  - Listen for `cheats_ban_changed` to update UI state (no heavy UI change needed initially).
  - In teams table render, show 🤡 next to `team_name` when `team_data.cheat` is true.
- `src/sockets/dashboard.py`
  - Add new handler for `dashboard:toggle_cheats_ban` that sets `state.cheats_banned`, kicks existing cheating teams (disconnect players, mark inactive), sends `cheats_ban_changed`, and triggers `emit_dashboard_full_update()`.
  - Ensure `get_all_teams()` includes both `cheat: bool` and `cheat_type: "none"|"com"|"hint"|"tony"|"kevin"` for each team (derived from team name/state). Avoid DB schema changes. The dashboard row renderer uses `cheat_type` to display 🤡 and a compact type tag (e.g., `[com]`, `[hint]`).

---

### Edge Cases
- If both players answer nearly simultaneously, partner-choice signals may arrive late; UI simply shows final submitted partner choice.
- `cheat-hint` after one player answered: recompute hint for the remaining player only and emit one more hint.
- If a second player joins a `tony/kevin` team mid-round, stop auto-fill for that round (team no longer single-player).
- Ensure hints and partner-choice are room-scoped to the correct team and SID.
 
Single-player safeguards:
- For `tony/kevin` teams, allow single-player submission and auto-completion only when exactly one player is connected for that team. If both are connected at the time of submission, do not auto-fill.

Database consistency:
- Always write exactly one `PairQuestionRounds` row per round and at most two `Answers` rows per round.
- For auto-fill, wrap partner insert + state updates in a transaction; on failure, rollback and emit `error` to the submitting client, leaving the round open.
- Do not double-insert an auto-filled `Answers` if the second player submitted concurrently; enforce uniqueness in logic by checking existing `Answers` for that `question_round_id` and `player_session_id`.

---

### Testing Plan (pytest)

Unit tests (new):
- `tests/unit/test_cheats_utils.py`
  - `parse_cheat_type` various cases (case-insensitive, suffixes).
  - `get_required_parity` correctness for pairs (BY/YB → different, else same).
  - `recommend_answers` correctness for both-unknown and single-known.

Integration tests (extend existing patterns):
- Add to `tests/integration/test_player_interaction.py` or a new `test_cheats_integration.py`:
  1) cheat-com: two players team with name `cheat-com-foo`; create+join; start round manually; submit answer from P1; assert P2 received `cheat:partner_choice` with correct boolean.
  2) cheat-hint: team `cheat-hint-foo`; after `start_new_round_for_pair`, assert both players received `cheat:hint`; after P1 submits, assert P2 receives updated hint consistent with parity and P1’s answer.
  3) cheat-tony single-player: team `cheat-tony-foo`; only one client; create team, set game_started, create a DB round with items; submit P1 answer; assert an auto-generated partner `Answers` row exists with value that makes the round win (respecting parity) and `round_complete` is emitted.
  4) cheat-kevin single-player: similar to tony, but assert partner answer forces a loss.
  5) ban toggle: create `cheat-com-bar` active; from dashboard test client emit `dashboard:toggle_cheats_ban` → True; assert the cheating team becomes inactive (dashboard shows inactive or team room receives `team_disbanded`), and a subsequent attempt to create `cheat-*` is rejected with `error`.
  6) AQM Joe policy: in AQM Joe mode, `cheat-hint` teams do not receive `cheat:hint` events (only partner-choice if applicable).
  7) Non-cheat isolation: team without `cheat-` prefix receives no new cheat events, standard disablement when incomplete, and standard server validations.

Dashboard rendering tests:
- Extend `get_all_teams()` path expectations by asserting `team_data` includes `cheat` bool; in `tests/integration/test_server_functionality.py`, after enabling teams streaming, check that a cheating team shows 🤡 next to name via `dashboard.js` render (can assert presence in processed row text or a small DOM string check via HTML snippet).
 - Extend `get_all_teams()` path expectations by asserting `team_data` includes `cheat: bool` and `cheat_type: str`; in `tests/integration/test_server_functionality.py`, after enabling teams streaming, check that a cheating team shows 🤡 and a compact type tag (e.g., `[com]`) next to the name via `dashboard.js` render (can assert presence in processed row text or a small DOM string check via HTML snippet).

Notes:
- Follow existing integration test patterns that use `SocketIOTestClient`, `eventlet.sleep`, and DB setup helpers.
- Use existing helpers in tests to insert `PairQuestionRounds` and set `team_info['current_db_round_id']` as shown in current integration tests.

---

### Logging & Metrics
- Log cheat detection on join/create with team name and `cheat_type`.
- Log `cheat:hint` emissions and partner-choice emissions with team name, round, and item pair.
- Log auto-fill events for `tony/kevin` with computed parity and values.
 - Performance guardrails: count hints emitted per second and short-circuit if server is under load (optional future).

Performance considerations:
- Hint compute is O(1); minimize work by:
  - Emitting at most twice per round per team (round start; after first answer).
  - Caching parity in `team_info` to avoid recompute.
  - Skipping hints entirely in AQM Joe v1.

---

### Rollout & Backward Compatibility
- Default: cheats not banned; behavior only for teams prefixed with `cheat-`.
- Kill switch: set env `CHEATS_DISABLED=true` to force-ban at startup; dashboard toggle remains functional but stays enforced.
- No DB schema changes required.
- Client code remains compatible for non-cheat teams; new events ignored by non-cheat teams.
- Player-side cheat UX is gated behind `cheat_type` values included in existing team events; non-cheat teams see unchanged behavior.
- Non-cheat verification: add tests that normal teams never receive `cheat:*` events and no relaxations apply.
- Rollback plan: enable dashboard ban or set env `CHEATS_DISABLED=true` and restart; no migrations or client updates required.
---

### Open Questions
- Should `tony/kevin` strictly require single-player at time of answer, or always override second player? Proposed: strictly single-player only.
- Hint randomness seeding for balance: acceptable to use `random` per round as today.
- For `cheat-com`, stream multiple changes if UI ever supports editing prior to finalization? Proposed: only on first submit event (current UI submits once).

---

### Minimal CSS Addition
```css
.rainbow-glow { animation: rainbow-glow 1.2s linear infinite; box-shadow: 0 0 12px 4px currentColor; border: 2px solid transparent; border-radius: 12px; }
@keyframes rainbow-glow { 0% { color: #ff0040; } 20% { color: #ff8000; } 40% { color: #ffff00; } 60% { color: #00ff00; } 80% { color: #00a0ff; } 100% { color: #ff00ff; } }
```

---

### Acceptance Criteria
- Step 1 (Foundations): parser correct on edge cases; `cheats_banned` respected across create/join/reactivate and gameplay hooks; non-cheat teams see no behavior/UI changes; logs visible for detection and emissions.
- Step 2 (Dashboard): dashboard renders 🤡 and `[type]`; toggling ban kicks active cheaters and blocks future `cheat-*`; dashboard state syncs via `cheats_ban_changed`.
- Step 3 (Com/Hint): com emits `cheat:partner_choice` on submit; hint emits at round start and after first answer only; UI glow toggles correctly; AQM Joe mode disables hints.
- Step 4 (Single-player): tony wins/kevin loses via transactional auto-fill when exactly one player connected; no duplicate answers; buttons enabled while `waiting_pair`.
- Global: All new unit/integration tests pass; no regressions in existing tests; no DB schema changes.


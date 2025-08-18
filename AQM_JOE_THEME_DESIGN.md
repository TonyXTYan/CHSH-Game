### AQM Joe Theme — Concise Design

**Goal**: Add a new theme, AQM Joe, with color/food semantics and scoring that reflects the constraints:
- If one answers “green” then the other always answers “peas”, if the food question is asked.
- When both are asked the colour question, sometimes both answer “green”.
- If both are asked the food question they never both answer “peas”.

---

### Theme set and naming

Third theme to add. Use the same keys across frontend and server:
- `classic` → Classic (default physics labels)
- `food` → Food Ingredients (current default)
- `aqmjoe` → AQM Joe

### Mode set and naming

Three modes across frontend and server:
- `classic` → Classic (correlation/CHSH scoring; any of A/B/X/Y to either player)
- `simplified` → Simplified (renamed from `new`; P1=A/B, P2=X/Y; success-rate path with existing rules)
- `aqmjoe` → AQM Joe mode (any of A/B/X/Y to either player; AQM Joe success policy for success-rate)

---

### UX and mapping

- **Theme key**: `aqmjoe`
- **Questions (items) → display**
  - `A`: “Favourite Color?”
  - `B`: “Favourite Color?”
  - `X`: “Favourite Food?”
  - `Y`: “Favourite Food?”
- **Answers per item (boolean → label)**
  - Color (`A`/`B`): `True → "Green"`, `False → "Red"`
  - Food (`X`/`Y`): `True → "Peas"`, `False → "Carrots"`
- **Modes**
  - Classic mode: Both players can receive any of `A/B/X/Y`; classic correlation/CHSH scoring applies. The AQM Joe theme only changes labels and copy.
  - Simplified mode (renamed from New): Player 1 gets `A/B` (color); Player 2 gets `X/Y` (food). Existing simplified-mode success rules remain unchanged (used for the success-rate path).
  - AQM Joe mode: Both players can receive any of `A/B/X/Y` (classic-style assignment), and the AQM Joe success policy (below) drives the success-rate scoreboard so Color–Color and Food–Food rounds are included.

#### Theme–Mode linking rules

- When theme is set to `aqmjoe`, force mode to `aqmjoe`.
- When mode is set to `aqmjoe`, force theme to `aqmjoe`.
- When switching away from AQM Joe:
  - If the user changes mode from `aqmjoe` to something else → theme auto-switches to `food`.
  - If the user changes theme from `aqmjoe` to something else → mode auto-switches to `simplified`.
- Implement linking atomically on the server to avoid UI ping‑pong. Provide a single action (e.g. `set_theme_and_mode`) that applies both values and emits one `game_state` update containing both.

Frontend:
- Add `aqmjoe` to `src/static/themes.js` (items, hints, colors, rules text).
- Add `getAnswerLabels(item)` to `ThemeManager` and use it in `src/static/app.js` to set per-round button labels.
- Add `evaluateAqmJoeResult(...)` and handle `theme==='aqmjoe'` in `generateLastRoundMessage`.
- In `src/static/dashboard.js`, add dropdown option and description for AQM Joe; update the mode control to include a third option “AQM Joe” and rename “New” → “Simplified”.

---

### Scoring (server: AQM Joe mode)

We keep existing metrics and introduce a success policy used in the new “AQM Joe mode” (success-rate dashboard path). The policy must satisfy the three rules while remaining simple and deterministic.

Definitions:
- Let `label(item, answerBool)` map booleans to labels using the table above.
- Items: `Color = {A, B}`; `Food = {X, Y}`.

Policy (per round):
- Food–Food: success if NOT (both “Peas”).
- Mixed Color–Food: if Color is “Green”, Food must be “Peas” to succeed. (Optional symmetry: Red↔Carrots succeeds.)
- Color–Color: neutral for success rate (no extra constraint).

Implementation:
- In `src/game_logic.py`, support `state.game_mode=='aqmjoe'` with classic-style assignment (both players can receive any of `A/B/X/Y`).
- In `src/sockets/dashboard.py`, add `_is_aqmjoe_success(...)` and, when `state.game_mode=='aqmjoe'`, use it inside `compute_success_metrics` and `_compute_success_metrics_optimized`.
- Keep classic-mode correlation unchanged; existing Simplified mode success rules unchanged. AQM Joe success policy applies only when `game_mode=='aqmjoe'`.

Pseudocode:

```python
def _aqmjoe_label(item, ans):
    if item in ('A', 'B'):
        return 'Green' if ans else 'Red'
    else:  # 'X', 'Y'
        return 'Peas' if ans else 'Carrots'

def _is_aqmjoe_success(p1_item, p2_item, p1_bool, p2_bool):
    l1 = _aqmjoe_label(p1_item, p1_bool)
    l2 = _aqmjoe_label(p2_item, p2_bool)

    p1_is_color = p1_item in ('A', 'B')
    p2_is_color = p2_item in ('A', 'B')
    p1_is_food = not p1_is_color
    p2_is_food = not p2_is_color

    # Rule 3: never both Peas when both food
    if p1_is_food and p2_is_food:
        return not (l1 == 'Peas' and l2 == 'Peas')

    # Rule 1: Green → Peas on mixed pairs
    if p1_is_color and p2_is_food:
        if l1 == 'Green':
            return l2 == 'Peas'
        # Optional symmetry
        return l2 == 'Carrots'
    if p2_is_color and p1_is_food:
        if l2 == 'Green':
            return l1 == 'Peas'
        # Optional symmetry
        return l1 == 'Carrots'

    # Both color: no hard constraint for success metric
    return True
```

Dashboard display:
- AQM Joe mode: success rate becomes the primary scoreboard metric, fed by the AQM Joe policy (includes Color–Color and Food–Food pairs).
- Simplified mode: success rate remains the primary metric using existing simplified-mode rules (mixed Color–Food only).
- Classic mode: show existing trace/balance/CHSH. The theme’s narrative appears in the rules pane only.

---

### Code changes

- Backend (`src/game_logic.py`): add `aqmjoe` game mode using classic-style assignment (`A/B/X/Y` for both players). Rename `new` → `simplified` in mode checks (keep `new` as an accepted alias for backwards compatibility).
- Backend (`src/state.py`): default `game_mode` becomes `simplified` (was `new`). Accept persisted `new` by mapping to `simplified` at load/reset.
- Backend (`src/sockets/dashboard.py`): add `_is_aqmjoe_success`; when `state.game_mode=='aqmjoe'`, use AQM Joe success logic inside `compute_success_metrics` and the optimized variant. Rename emitted/accepted mode string `new` → `simplified` (keep alias).
- Backend (linking): add an atomic action (e.g. `set_theme_and_mode`) that validates and applies linked changes server-side, preventing event ping‑pong.
- Frontend (`src/static/themes.js`): add/keep AQM Joe theme; expose `getAnswerLabels(item)`; no change.
- Frontend (`src/static/app.js`): use per-item labels; add/keep `evaluateAqmJoeResult`; handle `aqmjoe` in last-round message.
- Frontend (`src/static/dashboard.js`): add third mode option “AQM Joe”; rename all UI references from “New” → “Simplified”; treat `aqmjoe` mode like simplified for headers/metrics (success-rate scoreboard). Implement theme–mode linking in handlers to call the atomic server action.

No database or API schema changes.

---

### Tests

- Unit: `_is_aqmjoe_success` for mixed, food–food, color–color.
- Integration:
  - Assignment in `game_mode='aqmjoe'` includes Color–Color and Food–Food rounds.
  - Success rate and matrix reflect the AQM Joe policy when `game_mode='aqmjoe'` (theme may be `aqmjoe`).
  - Theme–mode linking: changing theme to `aqmjoe` forces mode to `aqmjoe`; changing mode to `aqmjoe` forces theme to `aqmjoe`; switching away applies the defaults (mode→`simplified`, theme→`food`).
  - Mode rename coverage: all tests updated from `new` → `simplified`. Add alias tests: server accepts `new` and normalizes to `simplified` (for backwards compatibility and older clients).

---

### Player-facing copy

- Mixed Color–Food: partner “Green” → answer “Peas”.
- Both Color: both can be “Green” sometimes.
- Both Food: never both “Peas”.

This messaging will be placed in `themes.js` for the rules/conditions panes.

---

### Rollout / compatibility

- Backward compatible; defaults remain `food` theme and `simplified` mode (renamed from `new`).
- Theme/mode switches mid-game are respected from that round onward.
- Ensure references use theme keys: `classic`, `food`, `aqmjoe`; and mode keys: `classic`, `simplified`, `aqmjoe`.
- Keep `new` as an accepted alias for `simplified` in API payloads/events for a transitional period; deprecate in UI.
- Dashboard: theme dropdown lists all three themes; mode control supports three modes (toggle cycle or dropdown). Linked updates applied atomically from server.



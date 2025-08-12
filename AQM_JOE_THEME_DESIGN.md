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
  - New mode (unchanged assignment): Player 1 gets `A/B` (color); Player 2 gets `X/Y` (food).
  - Classic mode: Both players can receive any of `A/B/X/Y` as usual.

Frontend:
- Add `aqmjoe` to `src/static/themes.js` (items, hints, colors, rules text).
- Add `getAnswerLabels(item)` to `ThemeManager` and use it in `src/static/app.js` to set per-round button labels.
- Add `evaluateAqmJoeResult(...)` and handle `theme==='aqmjoe'` in `generateLastRoundMessage`.
- In `src/static/dashboard.js`, add dropdown option and description for AQM Joe.

---

### Scoring (server, new mode only)

We keep existing metrics and introduce a theme-aware success policy used in “New mode” (success-rate dashboard path). The policy must satisfy the three rules while remaining simple and deterministic.

Definitions:
- Let `label(item, answerBool)` map booleans to labels using the table above.
- Items: `Color = {A, B}`; `Food = {X, Y}`.

Policy (per round):
- Food–Food: success if NOT (both “Peas”).
- Mixed Color–Food: if Color is “Green”, Food must be “Peas” to succeed. (Optional symmetry: Red↔Carrots succeeds.)
- Color–Color: neutral for success rate (no extra constraint).

Implementation:
- In `src/sockets/dashboard.py`, add `_is_aqmjoe_success(...)` and, when `state.game_theme=='aqmjoe'`, use it inside `compute_success_metrics` and `_compute_success_metrics_optimized`.
- Keep classic-mode correlation unchanged; AQM Joe affects only new-mode success.

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
- New mode: success rate becomes the primary scoreboard metric (already used). When theme=`aqmjoe`, the above policy feeds “successful_rounds”.
- Classic mode: show existing trace/balance/CHSH. The theme’s narrative appears in the rules pane only.

---

### Code changes

- Backend (`src/sockets/dashboard.py`): include `aqmjoe` in supported themes; add `_is_aqmjoe_success`; branch success logic by theme.
- Frontend (`src/static/themes.js`): add theme; expose `getAnswerLabels(item)`.
- Frontend (`src/static/app.js`): use per-item labels; add `evaluateAqmJoeResult`; handle `aqmjoe` in last-round message.
- Frontend (`src/static/dashboard.js`): add dropdown option + description.

No database or API schema changes.

---

### Tests

- Unit: `_is_aqmjoe_success` for mixed, food–food, color–color.
- Integration: success rate and matrix reflect policy when theme=`aqmjoe`, mode=`new`.

---

### Player-facing copy

- Mixed Color–Food: partner “Green” → answer “Peas”.
- Both Color: both can be “Green” sometimes.
- Both Food: never both “Peas”.

This messaging will be placed in `themes.js` for the rules/conditions panes.

---

### Rollout / compatibility

- Backward compatible; default remains `food`.
- Theme switches mid-game are respected from that round onward.
- Ensure all references use `classic`, `food`, `aqmjoe`; dashboard dropdown lists all three.



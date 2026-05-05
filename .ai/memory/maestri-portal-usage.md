# Maestri Portal Usage — CHSH Game Testing

## Setup

Three portals are pre-configured on the Maestri canvas:
- `Game-Dashboard` → `http://localhost:8080/dashboard` (Host Dashboard, 1000×929)
- `Game-L` → `http://localhost:8080/` (Player 1, 500×929)
- `Game-R` → `http://localhost:8080/` (Player 2, 500×929)

Always verify with `maestri list` before starting. Server must be running (`gunicorn wsgi:app --worker-class eventlet --bind 0.0.0.0:8080`).

## Key CLI Commands

```bash
maestri list                              # verify portals/agents connected
maestri portal info "Game-Dashboard"      # get URL, title, viewport
maestri portal screenshot "Portal"        # capture PNG → read with Read tool
maestri portal snapshot "Portal"          # accessibility tree with refs (@e1, @e2...)
maestri portal click "Portal" @e1         # click by ref (preferred)
maestri portal click "Portal" "x,y"       # click by coordinates (fallback)
maestri portal fill "Portal" @e1 "text"   # clear input and set value
maestri portal evaluate "Portal" "js"     # JS fallback if click by ref fails
```

## Running a Full Game Test

Use stable `evaluate` + `getElementById` for all critical actions (immune to positional ref shifts):

```bash
# 1. Game-L creates a team
maestri portal evaluate "Game-L" "document.getElementById('teamNameInput').value = 'TeamName'; 'ok'"
maestri portal evaluate "Game-L" "document.getElementById('createTeamBtn').click(); 'ok'"

# 2. Game-R joins the team (join button appears after team list updates)
# Use data-team-name attribute — exact team name, no transform, collision-free
maestri portal evaluate "Game-R" "document.querySelector('.join-btn[data-team-name=\"TeamName\"]').click(); 'ok'"

# 3. Start game from dashboard
maestri portal evaluate "Game-Dashboard" "document.getElementById('start-game-btn').click(); 'ok'"

# 4. Each round — check ingredients, then answer
maestri portal screenshot "Game-L"        # see Player 1's ingredient
maestri portal screenshot "Game-R"        # see Player 2's ingredient
maestri portal evaluate "Game-L" "document.getElementById('trueBtn').click(); 'ok'" &
maestri portal evaluate "Game-R" "document.getElementById('falseBtn').click(); 'ok'" &
wait
# trueBtn = Choose/True, falseBtn = Skip/False (text varies by theme, IDs are stable)
```

If you do use `snapshot` for exploration, key interactive controls now have `aria-label` attributes, so refs are more human-readable (e.g. `@e3 [button] "Start game"`).

## CHSH Ingredient Mapping (Simplified Mode)

Player 1 (Game-L) gets A/B ingredients; Player 2 (Game-R) gets X/Y ingredients.

| Ingredient | Role |
|------------|------|
| Bread      | A (Player 1) |
| Dumplings  | B (Player 1) |
| Lettuce    | X (Player 2) |
| Chocolate  | Y (Player 2) |

**Winning rule:** same answer wins *except* Dumplings(B) + Chocolate(Y) where different answers win.

| P1 \ P2    | Lettuce(X) | Chocolate(Y) |
|------------|------------|--------------|
| Bread(A)   | same ✓     | same ✓       |
| Dumplings(B) | same ✓   | different ✓  |

## Gotchas

- `click` by ref (`@eN`) can fail if the DOM changed since `snapshot`; prefer `evaluate` + `getElementById` for reliability.
- Parallelise independent clicks with `cmd & cmd & wait` to simulate simultaneous answers.
- After clicking, `sleep 1` before the next screenshot to let the server respond.
- Dynamic join/reactivate buttons are targeted via `data-team-name` attribute (exact team name, no transform): `querySelector('.join-btn[data-team-name="My Team"]')`.
- Stats Sig shows an hourglass until enough rounds are played for significance.

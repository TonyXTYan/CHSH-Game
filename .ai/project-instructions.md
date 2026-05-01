# Project Instructions

This file provides stable repository-specific guidance to any AI assistant working in this repository.

## AI Workspace

- `AGENTS.md` is the canonical entrypoint for agent instructions in this repo.
- `.ai/project-instructions.md` holds stable, repo-specific coding and architecture facts.
- `.ai/user_profile.md` is a symlink to shared preferences in `ai-common`.
- Keep this file focused on durable project facts; avoid temporary debugging notes or session logs.

### .ai/ Folder Structure

```
.ai/
  memory/               # persistent memory (Claude Code reads/writes here)
  prompts/              # active reference docs and strategy files
  prompts/archived/     # completed or implemented prompt/planning docs
  sessions/             # per-session AI work output
  sessions/legacy-generated/  # pre-convention archive
  project-instructions.md
  user_profile.md       # symlink → ai-common/user_profile.md
```

New session folders go directly under `sessions/` using the format:
`YYYY-MM-DD-<ai-tool>-<session-title>/`

Example: `2026-05-01-claude-mode-refactor/`

## Project Overview

CHSH Game is a real-time multiplayer web app implementing the CHSH (Clauser-Horne-Shimony-Holt) Bell inequality game. Teams of two players answer A/B/X/Y questions via a web interface while a host dashboard tracks scores and CHSH statistics.

## Commands

```bash
# Setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run dev server
gunicorn wsgi:app --worker-class eventlet --bind 0.0.0.0:8080

# Tests
pytest --cov=src --cov-branch --cov-report=xml tests/
pytest tests/unit/
pytest tests/integration/
pytest tests/stress/

# Single test file
pytest tests/unit/test_game_logic.py -v

# Type checking
mypy src
pyright src

# Load test
python chsh_load_test.py
```

## Architecture

Backend stack: Flask + Flask-SocketIO + Eventlet + SQLAlchemy.

- `src/main.py`: app startup, DB setup, signal handling, socket imports
- `src/config.py`: Flask and SocketIO setup, environment configuration
- `src/state.py`: global in-memory game state (`state`)
- `src/game_logic.py`: question assignment, combo tracking, round management
- `src/sockets/team_management.py`: connect/disconnect, team join/create, reconnection
- `src/sockets/game.py`: answer submission and round completion
- `src/sockets/dashboard.py`: dashboard updates, selective cache invalidation, throttled broadcasting
- `src/routes/static.py`: static file routes and `GET /api/server/id`
- `src/static/`: player UI and host dashboard frontend assets

## Key Behaviour

- Supported modes: `simplified` (default), `classic`, `aqmjoe`.
- Legacy mode value `'new'` is normalized to `'simplified'`.
- In `simplified` mode, player 1 gets A/B items and player 2 gets X/Y items; other modes allow all combinations.
- Some dashboard functions are imported inside function bodies in `src/sockets/game.py` to avoid circular imports.
- CHSH calculations use the `uncertainties` package (`ufloat`) for error propagation.

## Data and State

Database entities:
- `Teams`
- `PairQuestionRounds`
- `Answers`

In-memory `active_teams` tracks player membership, rounds, combo counts, and per-round answer state for each team.

## Working Conventions

- Keep edits minimal and targeted; avoid broad refactors unless explicitly requested.
- Preserve existing socket event behaviour and state shape unless the task requires changing them.
- Add or update tests with behavioural changes.
- Run relevant pytest suites before finishing changes.

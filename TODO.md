# TODOs

## URGENT

- [ ] Disable teams stats streaming for multi dashboard clients

## Normal ish 

- [ ] test website on windows

- [ ] button clear all inactive teams
- [ ] compact rows
- [x] ± statistics
- [x] Bug, sometimes after reforming (reactivating) a team then inputs are disabled??
- [x] Optimise CHSH normalisation
- [x] Put a crown on winning team
- [ ] fly.io deploy via CI
- [x] /about.html
- [ ] optimise server side CPU / RAM utilisation
- [ ] more unit tests, increase coverage for now
- [?] bug in the two CHSH value calc, once should be lower by 1/sqrt(2) ??

## Harder TODOs
- [ ] details stats shouldn't stream, should be on request, it also needs auto update upon team stats change
- [ ] batch load dashboard, i.e. don't instant update
- [ ] perhaps use cookies to store game state?
- [ ] multiple simultaneous games
- [ ] multiple game instances on multiple server machines
- [ ] persistent storage of game state, re-downloadable, maybe use browser storage too?

## Delegate to Cursor Background Agent
- [ ] Improve README.md
- [ ] use proper logging
- [ ] load_test should also validate info in dashabord 
- [ ] add goal info to dashboard and participant's page
- [ ] refactor code to break circular imports



## Maybe problem but won't fix now
- [ ] In src/main.py, there's a database initialization block that could fail silently if there are database connection issues.


## Notes

Database N+1 Query Problems (HIGH PRIORITY)
Location: src/sockets/dashboard.py:751-802
Problem: The get_all_teams() function makes separate queries for each team's statistics, leading to N+1 query problems.
Impact: With many teams, this creates excessive database load and slow response times.


Heavy DOM Operations (MEDIUM PRIORITY)
Location: src/static/dashboard.js:739-899
Problem: The updateActiveTeams() function rebuilds the entire table on every update, causing layout thrashing and poor performance.
Impact: Slow UI updates, especially with many teams.


Database Indexing (MEDIUM PRIORITY)
Location: src/models/quiz_models.py
Problem: Missing indexes on frequently queried fields.



Server Configuration Optimization (MEDIUM PRIORITY)
Location: wsgi.py, src/config.py
Problem: No optimized server configuration for production loads.


Connection Pooling (MEDIUM PRIORITY)
Location: src/config.py
Problem: No database connection pooling configuration.


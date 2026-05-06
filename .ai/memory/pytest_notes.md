# Pytest Notes

## Port 8080 must be free before running pytest

The conftest starts its own gunicorn server on port 8080 for integration tests. If a stale process (dev server or previous test run) already holds the port, gunicorn exits immediately and all tests error out.

Before running pytest:
```bash
kill $(lsof -ti :8080) 2>/dev/null
```

Watch for zombie gunicorn master processes that survive Ctrl+C — they hold the port even after workers exit. Verify with `lsof -i :8080 | grep LISTEN`.

## Missing dev dependencies (load_test module)

The `load_test/` module and its tests require packages not in the core `requirements.txt`. These are now tracked in `requirements-dev.txt` (or via `-r load_test/load_test_requirements.txt`). If new `ModuleNotFoundError`s appear during collection, add the missing package to `requirements-dev.txt`.

## eventlet monkey patching and tests

`src/config.py` guards `eventlet.monkey_patch()` behind the `TESTING` env flag. The conftest sets `TESTING=1` at module level so it takes effect before any `src` imports during collection. Test files must **not** call `eventlet.monkey_patch()` at module level — doing so patches `subprocess` and `socket` in the pytest process, causing `requests`-based tests to hang and `subprocess.Popen` to break.

`SocketIOTestClient` tests use `async_mode='threading'` (set automatically when `TESTING=1`) — no eventlet hub needed. Use `time.sleep` instead of `eventlet.sleep` in test files.

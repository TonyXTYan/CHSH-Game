# Change Review — dev/v2.5.0.1 uncommitted changes

**Date:** 2026-05-19  
**Branch:** dev/v2.5.0.1  
**Files reviewed:** README.md, src/sockets/dashboard.py, src/static/app.js, src/static/dashboard.html, src/static/index.html, src/static/styles.css, src/static/themes.js  
**Test result:** 295 unit tests passed

---

## Issues found

### 1. Redundant double-call in `setAnswerButtonsEnabled` (app.js ~line 600)

When `!currentRound?.alreadyAnswered`, two `setWaitingMessage` calls fire:

```javascript
setWaitingMessage({
    text: "Waiting for next round...",
    visible: Boolean(currentRound?.alreadyAnswered)  // false → hides + sets text
});
if (!currentRound?.alreadyAnswered) {
    setWaitingMessage({ visible: false });  // re-hides + clears text to '' via default
}
```

Net effect: element hidden, text cleared. No user-visible impact (element is hidden either way), but the second call silently overwrites the text that was just set. Code smell from the `setWaitingMessage` refactor; not a bug.

### 2. `setWaitingMessage({ visible: false })` always clears content

`setWaitingMessage` always writes `waitingMessage.textContent = text` (default `''`) on every call, even "hide-only" calls. All current call sites re-set content before re-showing, so this is safe today. Worth noting for future callers who might expect hide to preserve existing content.

---

## Everything else checked out

| Area | Finding |
|---|---|
| `TypedDict` classes (`TeamMetricsCache`, `FullMetricsCache`) | Dict literals assigned to cache variables match the TypedDicts exactly |
| `Protocol[P, R]` + `typing_extensions.ParamSpec` | Fine at runtime on Python 3.11; purely static-checker hints |
| `score_uncertainty` fix (dashboard.py ~line 1065) | Correct — `if normalized_cumulative_score is not None:` was always `True` (helper always returns `float`, never `None`); removing it eliminates dead code without changing behaviour |
| `inGameRoleHint` DOM reference | Guarded by `if (!inGameRoleHint) return` — no crash if element absent |
| `partner-waiting` CSS spinner cleanup | Any `setWaitingMessage({ visible: false })` call removes the class via `classList.toggle('partner-waiting', false)` |
| Dashboard label "Connected Players" → "Connected Clients" | Correct — the count includes dashboard socket clients, not just players |
| Copy fixes ("No communicate" → "Do not communicate", etc.) | Straightforward, no logic impact |

---

## Summary

Safe to commit. The only actionable item is tidying the double-call in `setAnswerButtonsEnabled` if code clarity matters. No functional regressions.

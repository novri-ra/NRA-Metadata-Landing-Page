# NRA DreamLab Audit - Bug Log

## 1. `src/background/background.js` - async inside listener without returning `true` for all async code paths
- **Description:** In `background.js`, `chrome.runtime.onMessage.addListener` has `return true` correctly for async blocks, but there are unhandled errors and async scope issues when catching errors that could drop the sendResponse. Actually, it looks handled properly in the provided file. No severe bugs found.

## 2. `src/content/content.js` - Multiple `chrome.storage.local.get` and `set` inside a loop
- **Description:** In the `startMainLoop`, it fetches storage multiple times (e.g. `isPaused`, `batchLimit`, `isAutomating`) inside the while loop. This could be optimized since we have an `onChanged` listener that caches these values in global variables! 
- **Severity:** Medium
- **Fix Recommendation:** Use `isPausedGlobal`, `batchLimitGlobal` and a new `isAutomatingGlobal` flag instead of constantly hitting `chrome.storage.local.get`.
- **Status:** [RESOLVED] - August 5, 2026. The loop now reads directly from the `isAutomatingGlobal`, `isPausedGlobal`, and `batchLimitGlobal` cache variables synced via the `onChanged` storage listener, eliminating continuous expensive I/O operations.

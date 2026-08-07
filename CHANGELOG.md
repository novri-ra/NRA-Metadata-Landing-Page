# Changelog

## [1.1.32] - 2026-08-07

### Verified
- **Stable Release**: All fixes from v1.1.31 (stale DOM cooldown retrigger, tagGhostCooldowns XPath, getScreenCooldownMs strictness) verified 100% working in live user environment.
- **Run Button State**: Confirmed no longer stuck after cooldown recovery.

## [1.1.31] - 2026-08-07

### Fixed
- **Stale DOM Cooldown Retrigger**: Prevented repeated cooldown cycles caused by POST-FLIGHT CHECK reading leftover alert/banner text from the DOM after a cooldown just finished.
- **tagGhostCooldowns**: Simplified XPath to tag ALL elements containing cooldown text (including `role="alert"` and `role="status"`), not just those outside alert containers.
- **getScreenCooldownMs**: Replaced `display:none` hiding (which `textContent` ignores) with `textContent` clearing to fully suppress stale nodes. Switched body fallback from `textContent` to `innerText`. Added `aria-disabled` check on Generate button.

## [1.1.30] - 2026-08-06

### Fixed
- Enforce robust Ping recovery and un-lock Run button properly.
- Ensure granular step status passes `currentIndex` and `totalPrompts` correctly down the call stack.



## [1.1.27] - 2026-08-05
### Fixed
- **Consecutive Cooldown Tolerance**: Increased `MAX_CONSECUTIVE_COOLDOWN` threshold from 2 to 3. Moved the auto-pause guard to evaluate *after* the timer finishes, ensuring the bot will patiently wait for the cooldown to clear before dropping the session on sequential rate-limits.

## [1.1.26] - 2026-08-05
### Added
- **Consecutive Cooldown Guard**: Added an auto-pause safeguard that forces the bot to stop executing if multiple cooldowns are hit successively (`>= 2`) without successful generation. This protects against hard account limit loops.

## [1.1.25] - 2026-08-05
### Fixed
- **Post-Flight Cooldown Retrigger (Stale DOM)**: Prevented redundant cooldown triggers caused by Canva's UI slowly removing alert texts. Added a `justFinishedCooldown` bypass flag and dynamic Generate button validation inside the text scraper.

## [1.1.24] - 2026-08-05
### Fixed
- **Cooldown Loop Timer**: Solved a race condition where overlapping cooldown timers caused an infinite delay loop without resuming automation. Implemented an atomic `isCooldownActive` guard to enforce single-threaded cooldown execution.
- **UI State Start Button**: Fixed a bug where the 'Run' button remained disabled despite having a prompt and being connected to Canva. Added real-time text evaluation during initial load and keystroke events.

## [1.1.22] - 2026-08-05
### Fixed
- Optimalisasi I/O storage pada content script (`startMainLoop`) menggunakan caching variabel global.

### Performance
- Pengurangan konsumsi CPU dan I/O `chrome.storage.local` yang signifikan selama loop otomatisasi.
- Penghapusan polling state delay loop yang over-engineered.

### Documentation
- Pembaruan pelacakan bug dan resolusi di `BUG_LOG.md`.
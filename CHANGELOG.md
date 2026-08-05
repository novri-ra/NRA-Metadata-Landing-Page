# Changelog

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
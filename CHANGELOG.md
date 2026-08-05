# Changelog

## [1.1.22] - 2026-08-05
### Fixed
- Optimalisasi I/O storage pada content script (`startMainLoop`) menggunakan caching variabel global.

### Performance
- Pengurangan konsumsi CPU dan I/O `chrome.storage.local` yang signifikan selama loop otomatisasi.
- Penghapusan polling state delay loop yang over-engineered.

### Documentation
- Pembaruan pelacakan bug dan resolusi di `BUG_LOG.md`.
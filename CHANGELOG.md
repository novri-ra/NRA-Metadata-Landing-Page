# Changelog
All notable changes to the NRA DreamLab extension will be documented in this file.

## [1.1.14] - 2026-07-15
### Fixed
- Resolved storage key asynchrony for createSubfolder and downloadFolder targets across panel.js components.
- Eliminated redundant message listener registration for PROMPT_FAILED to ensure accurate visual updating of both Failed and Quarantined prompt containers.

## [1.1.13] - 2026-07-15
### Added
- Implemented sequential prompt state tracking (Sketching to Finalizing) in submitAndWaitForImages with an automated 3-second post-finalizing delay filter to avoid asset blur issues.
### Fixed
- Fixed double tab trigger bug on rocket icon button (openDreamLabBtn) by removing duplicate click event listener declarations inside panel.js.

## [1.1.12] - 2026-07-15
### Fixed
- Fixed SyntaxError in getScreenCooldownMs by reverting document.querySelectorAll to use pure CSS selectors instead of the XPath expression from CANVA_SELECTORS.ALERT_STATUS.

## [1.1.11] - 2026-07-15
### Fixed
- Applied secondary audit recommendations by substituting manual query selectors with CANVA_SELECTORS.ALERT_STATUS in content.js.
- Cleaned up source code by removing deprecated logToTerminal functions.
- Implemented global defensive .catch gates on emergency exception messaging streams.

## [1.1.9] - 2026-07-15
### Fixed
- Fixed image blur rendering bug by checking visual container opacity state in content.js.
- Fixed UI Settings slider freeze issue by localizing element scope variables inside panel.js.

## [1.1.8] - 2026-07-15
### Fixed
- Added 'https://media.canva.com/*' to manifest host_permissions to resolve HTTP 403 Access Denied download interception errors.

## [1.1.7] - 2026-07-15
### Added
- Implemented Adaptive Render Detection Loop in submitAndWaitForImages by actively polling for Canva's 'Refining', 'Generating', and progressbar states, eliminating the reliance on static timers.

## [1.1.6] - 2026-07-15
### Fixed
- Fixed dynamic URL match string verification to prevent infinite reload loops caused by complex Canva tracking parameters (adj query strings).

## [1.1.5] - 2026-07-13
### Added
- Auto-scroll reset to top (window.scrollTo) when typing a new prompt.
- Instant visual focus and centering on the textarea container before input simulation starts.

## [1.1.4] - 2026-07-13
### Fixed
- Fixed 'Cannot redeclare block-scoped variable' syntax error in panel.js.
- Restricted image downloads to only target containers matching the active prompt text.
- Synchronized downloadingPrompt state to local storage right before download triggers.
- Accelerated human typing speed simulation to 20ms delay per character.
- Implemented double-shielded Pre-Flight and Post-Flight cooldown gates.
- Integrated 3-5 seconds randomized smart render delay to wait for Canva generation.
- Corrected currentIndex tracking calculations to prevent skips in the panel status.
- Re-activated UI settings gear icon and close cross icon buttons via Centralized Defensive Event Listener.

## [1.1.0] - 2026-04-15
### Added
- Integrated Advanced Image Metadata Extractor and Sanitizer.
- Added capability to scrub AI-generated signatures and inject professional camera presets into image files.
- Added support for KernelSU environment performance modules optimization compatibility.

## [1.0.5] - 2026-03-22
### Added
- Automated school budget (LPJ) initial integration structure using Python (FastAPI), Gemini, and Groq APIs.
- Modular state management update using GetX concepts for handling response tokens.

## [1.0.0] - 2026-01-10
### Added
- Initial official release of NRA DreamLab Canva Automation Extension.
- Core automation loop featuring custom prompt injection, aspect ratio config, and automatic element selection.
- Basic human-like typing simulation delay.
- Session metrics logging including progress tracking and success rates.
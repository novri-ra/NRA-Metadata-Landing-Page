# Canva Auto Prompter

An elegant, robust Manifest V3 Google Chrome Side Panel extension designed to automate bulk prompt generation, dropdown configuration, and image downloading on **Canva Dream Lab** (`canva.com/dream-lab`).

---

## Project Overview

**Canva Auto Prompter** simplifies batch image creation inside Canva's Dream Lab. Developers and designers can paste a list of text prompts (one per line) and automatically:
1. Configure generations with custom **Aspect Ratios** and **Image Styles**.
2. Clear and inject prompts sequentially using React-compatible input simulation.
3. Poll and detect new high-resolution render completions without reloading the page.
4. Download only the newly generated batch of images (excluding older historical assets).
5. Shift completed prompts out of the active text area queue in real-time so that stopping the process leaves only unprocessed prompts.
6. Pause/cancel the batch at any point with a responsive, color-transitioning **Start/Stop** toggle button.

---

## Architecture

The extension is structured using standard Chrome Extension MV3 components:

```
├── manifest.json       # Configures permissions, host matches, and native Side Panel defaults
├── background.js       # Background service worker; launches the side panel on toolbar click
├── panel.html          # HTML view for the native Side Panel (dark-mode styling)
├── panel.js            # Handles side panel state, input retrieval, and communicates with content.js
└── content.js          # The automation engine; interacts directly with Canva's React portal DOM
```

### Component Interaction

1. **`background.js` (Service Worker)**: Registers the default panel behavior (`openPanelOnActionClick: true`), opening `panel.html` persistently next to the browser tab.
2. **`panel.html` & `panel.js` (Side Panel Control)**: Stores the prompt queue, updates remaining prompts, and captures styling values in `chrome.storage.local`. Upon click, it toggles `isRunning` and posts a message to trigger or cancel the content script. Intercepts `UPDATE_TEXTAREA` messages from the content script to dynamically delete completed prompts from the editor.
3. **`content.js` (Content Script)**: Injected directly on `canva.com/dream-lab`. Contains robust React text value overrides, custom XPath portals parsing routines, count-based polling loops, and immediate cancelation gates (`USER_STOPPED` exceptions) that prevent automation hang-ups. Destructively shifts processed prompts out of the queue on successful downloads or generation errors, keeping state synchronized.

---

## Features

- **Direct URL Matching**: Operates exclusively on the new Canva Dream Lab interface (`canva.com/dream-lab`).
- **Drop-Down Automation**: Automatically configures **Aspect Ratio** and **Image Style** by interacting with custom Canva React portals.
- **Dynamic Download Counts**: Select between **1, 2, 3, 4**, or **Random** download limits. Selecting *Random* shuffles download targets on each iteration.
- **Continuous Loop (No Page Reloads)**: Runs all prompts sequentially in a single execution context. Resolves the issue where old download buttons would trigger premature downloads.
- **FIFO Destructive Queue**: Prompts are sliced and deleted ("cut") from the textarea queue upon successful download (or failure), ensuring that stopping the process leaves only unprocessed prompts behind.
- **Start/Stop Toggle**: Converts the "Run" button to a red "Stop" button. Clicking Stop instantly halts DOM queries and resets storage.
- **Progress Reporting**: Real-time status bar updates and progress indicators (e.g. `12 prompts remaining`) synchronize between scripts.
- **AFK Mode Alerts**: Plays a pleasant, ascending 2-tone chime sound and triggers a native Chrome desktop notification when the prompt batch completes, notifying the user that all tasks are finished.

---

## Setup Instructions

To run the extension locally in developer mode:

1. **Clone or Download** this directory to your machine.
2. Open Google Chrome or Brave and navigate to `chrome://extensions/`.
3. Enable **Developer mode** using the toggle switch in the top right corner.
4. Click **Load unpacked** in the top left corner.
5. Select the `Canva Auto Prompter` project folder.
6. Open `https://www.canva.com/dream-lab` in a new tab.
7. Click the **Canva Auto Prompter** extension icon in your browser toolbar to open the Side Panel.

---

## Known Bugs & Troubleshooting (Audit Log)

### 1. Connection Failures
* **Symptom:** `"Could not establish connection. Receiving end does not exist."` shown in side panel.
* **Root Cause:** The Side Panel loaded and tried to send a message before `content.js` was injected, or navigation occurred to a non-matching domain.
* **Solution:** Navigate to `canva.com/dream-lab` and reload the page. The extension has catch-blocks that prompt you to refresh the Canva tab if connection fails.

### 2. Immediate Stop / Textarea Selector Failures
* **Symptom:** The extension immediately halts or reports `"Textarea not found"`.
* **Root Cause:** Canva's DOM wasn't fully loaded, or the React portal elements changed class/placeholder names, selecting a hidden textarea.
* **Solution:** Upgraded the element query to target `textarea[placeholder*="Describe"], textarea[class*="canva"]` and increased the search window to `15 seconds` (`15000ms`).

### 3. Race Conditions (Truncated Downloads)
* **Symptom:** Canva redirects or clears generation states before the browser has finished writing downloaded files to disk.
* **Root Cause:** Simulated clicks are instantaneous; Chrome needs a buffer window to establish file handles.
* **Solution:** Configured a mandatory `6000ms` (6 seconds) sleep block directly after simulated clicks to allow downloads to finish writing to disk.

### 4. Dropdown Option Menu Not Found
* **Symptom:** The script opens a dropdown but fails to select the option, warning `"Menu option not found"`.
* **Root Cause:** Canva renders options inside React portals dynamically. Standard selectors execute before the listbox renders.
* **Solution:** Added a `1200ms` synchronization pause post-trigger click, and implemented an XPath evaluation check targeting `role='option'` spans (`//*[contains(., '<text>') and (@role='option' or ancestor::*[@role='option'])]`) to support nested elements.

### 5. Policy Restrictions
* **Limitation:** Administrator policies blocking Canva AI or Dream Lab access will prevent the script from finding generation inputs. The script will halt and output an error status. Ensure you have an active subscription or valid account access.

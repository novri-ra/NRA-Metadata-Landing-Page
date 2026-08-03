# 🎮 NRA DreamLab

![Chrome Extension](https://img.shields.io/badge/Chrome-Extension-4285F4?logo=googlechrome&logoColor=white)
![Manifest V3](https://img.shields.io/badge/Manifest-V3-34A853)
![Version](https://img.shields.io/badge/version-1.1.21-6366f1)
![License](https://img.shields.io/badge/license-MIT-green)

> **Automate prompt input and batch-download AI-generated images on [Canva Dream Lab](https://www.canva.com/dream-lab).**

NRA DreamLab is a Chrome extension that automates the repetitive workflow of typing prompts, waiting for image generation, and downloading results on Canva's Dream Lab. It runs entirely client-side with zero external dependencies.

---

## 📋 Table of Contents

- [Features](#-features)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Project Structure](#-project-structure)
- [Architecture Overview](#-architecture-overview)
- [Permissions](#-permissions)
- [Configuration](#-configuration)
- [Changelog](#-changelog)
- [License](#-license)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Bulk Prompt Processing** | Paste multiple prompts (one per line) and process them sequentially. |
| **Style & Ratio Selection** | Auto-select image style and aspect ratio before each generation. |
| **Smart Download** | Automatically download generated images with clean, prompt-based filenames. |
| **Cooldown Detection** | Detects Canva rate limits (MM:SS, Xm Ys, Xs) and updates panel timer in real-time. |
| **Container Isolation** | Accurately tracks new Canva renders to avoid downloading outdated images. |
| **Pause / Resume** | Pause automation mid-session and resume without losing progress. |
| **Session Recovery** | Survives page reloads and browser restarts via persistent state. |
| **Prompt Iteration** | Use `{i}` placeholder to generate numbered prompt variants. |
| **Quarantine System** | Failed prompts are captured for retry without re-entering them. |
| **Retro Pixel UI** | Side panel with customizable themes, fonts, and real-time statistics. |

---

## 🔧 Prerequisites

- **Google Chrome** version 114 or newer (Manifest V3 + Side Panel API support).
- A [Canva](https://www.canva.com) account with access to Dream Lab.

---

## 🚀 Installation

1. **Clone or download** this repository:
   ```bash
   git clone https://github.com/your-username/Canva-Auto-Prompter.git
   ```

2. Open Chrome and navigate to:
   ```
   chrome://extensions
   ```

3. Enable **Developer mode** (toggle in the top-right corner).

4. Click **"Load unpacked"** and select the root folder of this project (the folder containing `manifest.json`).

5. The NRA DreamLab icon will appear in your toolbar. Click it to open the side panel.

6. Navigate to [https://www.canva.com/dream-lab](https://www.canva.com/dream-lab) and start automating!

---

## 📁 Project Structure

```
Canva-Auto-Prompter/
├── manifest.json                  # Extension manifest (MV3)
├── assets/
│   └── icon.png                   # Extension icon (16/48/128)
├── src/
│   ├── background/
│   │   └── background.js          # Service Worker (mutex, power, downloads)
│   ├── content/
│   │   ├── selectors.js           # Centralized DOM selectors (ARIA/XPath)
│   │   └── content.js             # Main automation logic (injection, generation, download)
│   ├── sidepanel/
│   │   ├── panel.html             # Side panel UI (retro pixel theme)
│   │   └── panel.js               # Panel logic (stats, settings, message handling)
│   └── utils/
│       ├── utils.js               # Input sanitization utility
│       └── rename.js              # Dev-only branding rename script (not loaded at runtime)
├── README.md
├── USER_GUIDE.md
├── CHANGELOG.md
└── LICENSE
```

---

## 🏗 Architecture Overview

NRA DreamLab follows Chrome's Manifest V3 architecture with three isolated execution contexts communicating via `chrome.runtime` message passing.

### Component Diagram

```
┌─────────────────────┐     chrome.runtime      ┌──────────────────────┐
│   Side Panel (UI)   │◄────── messages ────────►│   Background Worker  │
│   panel.js          │                          │   background.js      │
└────────┬────────────┘                          └──────────┬───────────┘
         │ chrome.tabs.sendMessage                          │
         ▼                                                  │
┌─────────────────────┐     chrome.runtime      ┌──────────┘
│   Content Script    │◄────── messages ────────┘
│   content.js        │
│   (canva.com only)  │
└─────────────────────┘
```

### Core Systems

#### 1. Multi-Tab Mutex & Power Management

The background service worker prevents multiple tabs from running automation simultaneously using a storage-based mutex (`activeAutomationTab`). It also manages system wake locks via `chrome.power` to prevent sleep during long sessions.

**Lifecycle:**
- `chrome.runtime.onStartup` / `onInstalled`: Clears stale mutex on browser restart or crash recovery.
- `chrome.tabs.onRemoved`: Releases mutex when the automation tab is closed.
- `chrome.tabs.onUpdated`: Releases mutex on navigation away from Canva.
- `chrome.runtime.onSuspend`: Emergency cleanup before service worker terminates.

#### 2. Unthrottled Web Worker Delay

Content scripts use a dedicated Web Worker for `delay()` timing, immune to Chrome's background tab throttling. A dual-layer fallback ensures reliability:

```
Primary:  Web Worker postMessage (accurate timing)
    ↓ failure
Fallback: Native setTimeout + Worker.terminate() + reinit
```

The worker is explicitly terminated on error to prevent zombie threads.

#### 3. DOM Observation with MutationObserver

Element detection uses a unified `waitForElement()` utility powered by `MutationObserver`:

- Supports both **CSS selectors** and **XPath** expressions.
- Validates visibility using `getBoundingClientRect()` instead of the less reliable `offsetParent`.
- Includes `USER_STOPPED` interrupt checks for clean shutdown.
- Single function replaces the previous dual-function approach for consistency.

#### 4. Batched UI Log Rendering

The side panel's console log uses a **queue + DocumentFragment + requestAnimationFrame** pipeline to prevent DOM thrashing during high-frequency log bursts:

```
Message received → logQueue.push(div) → schedule rAF → flushLogs()
                                                          ├── DocumentFragment batch insert
                                                          ├── Cap at 500 entries
                                                          └── Auto-scroll
```

#### 5. Centralized Selectors

All DOM selectors are defined in `selectors.js` using stable attributes (ARIA labels, roles, element types) rather than obfuscated class names, improving resilience against Canva UI updates.

---

## 🔐 Permissions

| Permission | Purpose |
|------------|---------|
| `activeTab` | Access the currently active Canva tab. |
| `scripting` | Inject content scripts into Dream Lab pages. |
| `storage` | Persist prompts, settings, session state, and statistics. |
| `sidePanel` | Render the control panel UI alongside the browser. |
| `notifications` | Alert the user when all prompts are processed. |
| `power` | Prevent system sleep during long automation sessions. |
| `downloads` | Trigger and rename image downloads. |

**Host permissions** are scoped exclusively to `*.canva.com`.

---

## ⚙ Configuration

All settings are accessible from the side panel's **Settings** modal:

| Setting | Default | Description |
|---------|---------|-------------|
| Typing Mode | `human` | `human` (20ms per char) or `instant` (native setter). |
| Batch Limit | `0` (unlimited) | Stop after N prompts per session. |
| Safety Delay | `0s` | Extra wait after image generation before downloading. |
| Save Delay | `6s` | Delay between download button clicks. |
| Sound Alert | On | Play a chime when all prompts are completed. |
| Create Subfolder | Off | Save downloads into a named subfolder. |
| Debug Mode | Off | Show verbose INFO logs in the console panel. |

---

## 📝 Changelog

See [CHANGELOG.md](CHANGELOG.md) for the full version history.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
  
---  
### ☕ Support & Portfolio  
  
- **Support & Donasi:** https://lynk.id/novri-ra/s/qmvpeeg4kl5j/checkout  
- **Aplikasi & Portofolio Lainnya:** https://lynk.id/novri-ra 

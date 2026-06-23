<div align="center">
  <h1>🤖 Canva Auto Prompter</h1>
  
  <p><strong>God-Tier Automation & Bulk Prompt Runner for Canva Dream Lab</strong></p>

  <p>
    <img alt="Chrome Extension" src="https://img.shields.io/badge/Chrome-Extension-4285F4?style=flat-square&logo=google-chrome&logoColor=white" />
    <img alt="Manifest V3" src="https://img.shields.io/badge/Manifest-V3-181717?style=flat-square" />
    <img alt="JavaScript" src="https://img.shields.io/badge/JavaScript-F7DF1E?style=flat-square&logo=javascript&logoColor=black" />
    <img alt="CDP Protocol" src="https://img.shields.io/badge/CDP-Protocol-4285F4?style=flat-square" />
  </p>
</div>

---

## 📖 Table of Contents
- [About the Project](#-about-the-project)
- [Key Features](#-key-features)
- [Installation](#-installation)
- [How to Use](#-how-to-use)
- [Project Structure](#-project-structure)
- [Roadmap](#-roadmap)
- [Disclaimer](#-disclaimer)

---

## 🚀 About the Project

**Canva Auto Prompter** is a powerful, hardware-level automation extension built exclusively for **Canva Dream Lab** (`canva.com/dream-lab`). It bypasses modern React virtual DOM restrictions by utilizing the **Chrome DevTools Protocol (CDP)** to simulate real, native user interactions.

Designed with an **"Ergonomic Midnight Arcade"** aesthetic, it features pure-CSS collapsible menus, utility shortcut icons, and a live scrollable terminal console directly inside a non-intrusive Chrome Side Panel.

---

## ✨ Key Features

- **CDP Hardware-Level Input:** Simulates true OS-level mouse and keyboard events to interact seamlessly with React-controlled elements.
- **Chrome Throttling Immunity:** Uses absolute timestamp tracking (`Date.now()`) in cooldown loops to prevent infinite waits when the browser tab becomes inactive.
- **Dynamic Rate Limit Handling:** Intelligently reads cooldown timers (e.g., *"Try again in 4:20"*), pauses operations, and displays a live visual countdown with automatic DOM tag recovery.
- **Auto-Clear & Retype Recovery:** Automatically recovers from cooldowns by clearing inputs and re-entering prompts natively.
- **Stale-DOM Immunity:** A built-in Parallel State Machine dynamically tracks Canva's React DOM to successfully capture and download images regardless of UI changes.
- **In-App Terminal Console:** Real-time, color-coded logging of operations right in your Side Panel for easy monitoring.
- **Utility Icons:** Quick-access buttons to open Dream Lab (🚀), clear prompts (🗑️), and clear terminal logs (🗑️).
- **Queue Management:** Destructive FIFO queue system—prompts are only removed once the image is successfully generated and downloaded.

---

## 🛠️ Installation

1. Download or clone this repository to your machine.
2. Open Google Chrome and navigate to `chrome://extensions/`.
3. Enable **Developer Mode** (toggle in the top-right corner).
4. Click **Load unpacked** and select the folder containing this project.

---

## 🎮 How to Use

1. Navigate to [Canva Dream Lab](https://www.canva.com/dream-lab).
2. Click the **Canva Auto Prompter** icon in your Chrome extension toolbar to open the Side Panel.
3. Paste your prompts into the text area (one prompt per line).
4. Configure your desired **Aspect Ratio**, **Image Style**, and **Download Count**.
5. Click **Run** to start the automation.

### Utility Icons
- **🚀 (Header):** Quick shortcut to open Canva Dream Lab in a new tab.
- **🗑️ (Prompt Text):** Clear all prompts from the textarea with confirmation.
- **🗑️ (Terminal Logs):** Instantly wipe all console output logs.

> [!WARNING]  
> **Debugger Banner:** Chrome will show a yellow banner: *"Canva Auto Prompter" started debugging this browser*. **DO NOT close it!** Closing this banner will detach the debugger and instantly stop the automation.

---

## 🏗️ Project Structure

```
Canva-Auto-Prompter/
├── manifest.json          # Chrome Extension configuration (Manifest V3)
├── background.js          # CDP Bridge & Debugger session manager
├── content.js             # DOM Sniper & automation state machine
├── panel.html             # Side Panel UI (Midnight Arcade theme)
├── panel.js               # UI event handlers & storage sync
├── icon.png               # Extension icon
└── README.md              # Documentation
```

### Architecture Overview
- **`background.js` (CDP Bridge):** Attaches `chrome.debugger` to translate frontend requests into protocol commands like `Input.dispatchMouseEvent` and `Input.insertText`.
- **`content.js` (DOM Sniper):** Runs directly on the Canva page to traverse the DOM, evaluate states, handle rate limits with absolute timestamp tracking, and manage cooldown recovery with DOM tag stamping.
- **`panel.html` / `panel.js` (UI Manager):** The Manifest V3 side panel that provides the retro-styled interface, queue management, utility icons, and terminal logs.

---

## 🔮 Roadmap

- [ ] **Multi-Account Session Rotation:** Automatically switch accounts when a rate limit exceeds a certain threshold.
- [ ] **Dynamic Network Hooking:** Intercept CDP network events (`Network.responseReceived`) to detect completed images directly from Canva's rendering servers.
- [ ] **Batch Export Organizer:** Automatically organize downloaded images into folders by prompt or generation date.

---

## ⚠️ Disclaimer

This software is developed strictly for **educational and research purposes**. Automating platforms like Canva can be a violation of their **Terms of Service**. The developer assumes absolutely **no liability** for any account bans, suspensions, resource limitations, or data loss resulting from the use of this tool. Use responsibly and at your own discretion.

---

<div align="center">
  <p><strong>© 2026 Novri Rizki Akbar. All rights reserved.</strong></p>
  <p>Support & Premium Products: <a href="https://lynk.id/novri-ra" target="_blank">lynk.id/novri-ra</a></p>
</div>
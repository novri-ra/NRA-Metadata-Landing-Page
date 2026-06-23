<div align="center">
  <h1>🤖 Canva Auto Prompter</h1>
  
  <p><strong>God-Tier Automation & Bulk Prompt Runner for Canva Dream Lab</strong></p>
  
  <img src="assets/screenshot.png" alt="Canva Auto Prompter UI" width="800" style="border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);"/>

  <p>
    <img alt="Chrome Extension" src="https://img.shields.io/badge/Chrome-Extension-4285F4?style=flat-square&logo=google-chrome&logoColor=white" />
    <img alt="Manifest V3" src="https://img.shields.io/badge/Manifest-V3-181717?style=flat-square" />
    <img alt="JavaScript" src="https://img.shields.io/badge/JavaScript-F7DF1E?style=flat-square&logo=javascript&logoColor=black" />
  </p>
</div>

---

## 📖 Table of Contents
- [About the Project](#-about-the-project)
- [Key Features](#-key-features)
- [Installation](#-installation)
- [How to Use](#-how-to-use)
- [How it Works](#-how-it-works)
- [Roadmap](#-roadmap)
- [Disclaimer](#-disclaimer)

---

## 🚀 About the Project

**Canva Auto Prompter** is a powerful, hardware-level automation extension built exclusively for **Canva Dream Lab** (`canva.com/dream-lab`). It bypasses modern React virtual DOM restrictions by utilizing the **Chrome DevTools Protocol (CDP)** to simulate real, native user interactions.

Designed with an **"Ergonomic Midnight Arcade"** aesthetic, it features pure-CSS collapsible menus and a live scrollable terminal console directly inside a non-intrusive Chrome Side Panel.

---

## ✨ Key Features

- **CDP Hardware-Level Input:** Simulates true OS-level mouse and keyboard events to interact seamlessly with React-controlled elements.
- **Dynamic Rate Limit Handling:** Intelligently reads cooldown timers (e.g., *"Try again in 4:20"*), pauses operations, and displays a live visual countdown.
- **Auto-Clear & Retype Recovery:** Automatically recovers from cooldowns by clearing inputs and re-entering prompts natively.
- **Stale-DOM Immunity:** A built-in Parallel State Machine dynamically tracks Canva's React DOM to successfully capture and download images regardless of UI changes.
- **In-App Terminal Console:** Real-time, color-coded logging of operations right in your Side Panel for easy monitoring.
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
5. Click **Run**.

> [!WARNING]  
> **Debugger Banner:** Chrome will show a yellow banner: *"Canva Auto Prompter" started debugging this browser*. **DO NOT close it!** Closing this banner will detach the debugger and instantly stop the automation.

---

## 🏗️ How it Works

The extension operates on a robust architecture:
- **`background.js` (CDP Bridge):** Attaches the `chrome.debugger` to translate frontend requests into protocol commands (like `Input.dispatchMouseEvent`).
- **`content.js` (DOM Sniper):** Runs directly on the Canva page to traverse the DOM, evaluate states, and handle rate limits.
- **`panel.html` / `panel.js` (UI Manager):** The Manifest V3 side panel that provides the interface, queue management, and terminal logs.

---

## 🔮 Roadmap

- [ ] **Multi-Account Session Rotation:** Automatically switch accounts when a rate limit exceeds a certain threshold.
- [ ] **Dynamic Network Hooking:** Intercept CDP network events (`Network.responseReceived`) to detect completed images directly from Canva's rendering servers.

---

## ⚠️ Disclaimer

This software is developed strictly for **educational and research purposes**. Automating platforms like Canva can be a violation of their **Terms of Service**. The developer assumes absolutely **no liability** for any account bans, suspensions, resource limitations, or data loss resulting from the use of this tool. Use responsibly and at your own discretion.
# 🤖 NRA DreamLab

<div align="center">

![NRA DreamLab](https://img.shields.io/badge/NRA-DreamLab-00C4CC?style=for-the-badge&logo=canva&logoColor=white)

**Automate bulk AI image generation & downloading on [Canva Dream Lab](https://www.canva.com/dream-lab)**

[![Chrome Extension](https://img.shields.io/badge/Chrome-Extension-4285F4?logo=google-chrome&logoColor=white)](https://www.google.com/chrome/)
[![Manifest V3](https://img.shields.io/badge/Manifest-V3-success)](https://developer.chrome.com/docs/extensions/mv3/)
[![JavaScript](https://img.shields.io/badge/JavaScript-ES6+-F7DF1E?logo=javascript&logoColor=black)](https://developer.mozilla.org/en-US/docs/Web/JavaScript)
[![License](https://img.shields.io/badge/License-Educational-orange)](LICENSE)

[Features](#-features) · [Installation](#-installation) · [Usage](#-usage) · [Release Notes](#-release-notes) · [Author](#-author)

</div>

---

## 💡 What Is This?

**NRA DreamLab** is a Chrome extension that automates prompt input and image downloading on [Canva Dream Lab](https://www.canva.com/dream-lab). Queue multiple prompts, configure style & aspect ratio, and let the bot handle generation, rate-limit cooldowns, and batch downloading — all hands-free.

> **Who is this for?** Content creators, designers, and marketers who need to generate large batches of AI images efficiently.

---

## ✨ Features

- **Bulk Prompt Queue** — Paste hundreds of prompts (one per line) or import from `.txt` files
- **Auto Style & Aspect Ratio** — Set per-session or randomize per prompt
- **Smart Download** — Polls DOM for newly rendered download buttons; no more stale-element bugs
- **Native DOM Click** — Uses real browser click events for maximum stability across Canva UI updates
- **Rate Limit Handling** — Auto-detects cooldown modals and waits before retrying
- **Configurable Delays** — Safety delay, save delay, and batch auto-stop limit
- **Session Analytics** — Live stats: prompts processed, images downloaded, success rate, ETA
- **Prompt Presets** — Save/load/delete named prompt sets via `chrome.storage`
- **Failed & Quarantine Queues** — Automatically rescues blocked prompts for retry
- **Retro Pixel UI** — CRT scanline side-panel with multiple themes (Retro, Hacker, Light)
- **Keyboard Shortcut** — `Ctrl+Shift+P` to pause/resume without opening the panel

---

## 📦 Installation

1. Download or clone this repository:
   ```bash
   git clone https://github.com/novri-ra/Canva-Auto-Prompter.git
   ```
2. Open Chrome and navigate to `chrome://extensions/`
3. Enable **Developer mode** (toggle in top-right)
4. Click **Load unpacked** and select the project folder (the one containing `manifest.json`)
5. Open [Canva Dream Lab](https://www.canva.com/dream-lab) — the extension side-panel will be available

---

## 🚀 Usage

1. Click the extension icon or open the side panel on `canva.com/dream-lab`
2. Paste your prompts (one per line) in the **Prompt Text** area
3. Configure **Aspect Ratio**, **Image Style**, and **Download Count** in Settings
4. Click **Run** — the bot will type each prompt, generate images, and download them automatically
5. Monitor progress in **Session Analytics** and **Terminal Logs**

---

## 📋 Release Notes

### v1.1.3 — NRA DreamLab Rebranding & Native DOM Click

- **Rebranding**: Renamed from "Canva Auto Prompter" to **NRA DreamLab**
- **Native DOM Click**: Migrated download trigger from CDP `Input.dispatchMouseEvent` to native `element.click()` for resolution-independent, stable downloading
- **Smart Wait (Polling)**: Replaced hardcoded `delay(2000)` with DOM polling that waits for new download buttons to appear (up to 10s timeout), eliminating race conditions
- **Dynamic Slicing**: Download button selection now captures only the N newest buttons instead of a static `.slice(-4)`, preventing stale-element downloads

### v1.1.2

- Initial public release with CDP-based clicking, bulk prompt queue, and retro UI

---

## 👤 Author

**Novri Rizki Akbar**

- GitHub: [@novri-ra](https://github.com/novri-ra)
- Support & Premium Products: [lynk.id/novri-ra](https://lynk.id/novri-ra)

---

## 📄 License

This project is for **educational purposes only**. See [LICENSE](LICENSE) for details.
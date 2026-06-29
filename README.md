# 🤖 Canva Auto Prompter

<div align="center">

![Canva Auto Prompter](https://img.shields.io/badge/Canva-Auto_Prompter-00C4CC?style=for-the-badge&logo=canva&logoColor=white)

**Automate bulk AI image generation on [Canva Dream Lab](https://www.canva.com/dream-lab)**

[![Chrome Extension](https://img.shields.io/badge/Chrome-Extension-4285F4?logo=google-chrome&logoColor=white)](https://www.google.com/chrome/)
[![Manifest V3](https://img.shields.io/badge/Manifest-V3-success)](https://developer.chrome.com/docs/extensions/mv3/)
[![JavaScript](https://img.shields.io/badge/JavaScript-ES6+-F7DF1E?logo=javascript&logoColor=black)](https://developer.mozilla.org/en-US/docs/Web/JavaScript)
[![License](https://img.shields.io/badge/License-Educational-orange)](LICENSE)

[Features](#-features) · [Installation](#-installation) · [Usage](#-usage) · [Troubleshooting](#-troubleshooting) · [Author](#-author)

</div>

---

## 💡 What Is This?

**Canva Auto Prompter** is a Chrome extension that lets you queue multiple prompts and automatically generates AI images on Canva Dream Lab — handling style selection, aspect ratios, rate limit cooldowns, and image downloading without any manual intervention.

> **Who is this for?** Content creators, designers, and marketers who need to generate large batches of AI images efficiently.

---

## ✨ Features

<table>
<tr>
<td width="50%">

### 🎯 Automation
- **Bulk Prompt Queue** — Process unlimited prompts sequentially
- **Smart Rate Limit Handling** — Auto-detects cooldowns with live countdown timer
- **Auto-Download** — Download 1–4 images per prompt (or random)
- **CDP-Powered Clicks** — Hardware-level input via Chrome DevTools Protocol
- **Auto-Recovery** — Graceful error handling, auto-retry, and page reload recovery
- **Pause / Resume / Stop** — Full control during automation

</td>
<td width="50%">

### 🎨 Customization
- **18 Image Styles** — Smart, Cinematic, 3D Render, Vector, Pop Art, etc.
- **7 Aspect Ratios** — 1:1, 16:9, 9:16, 4:3, 3:4, 3:2, 2:3
- **Random Mode** — Randomize style and/or ratio per prompt
- **3 UI Themes** — Retro Terminal, Matrix Hacker, Clean Light
- **Typing Modes** — Human-like animation or instant paste
- **Audio Alerts** — Sound notification on batch completion

</td>
</tr>
</table>

### 📊 Monitoring

| Feature | Description |
|---------|-------------|
| **Live Terminal** | Real-time color-coded logs (green = success, yellow = wait, red = error) |
| **Progress Tracking** | Queue count, current prompt, remaining prompts |
| **Batch Limits** | Auto-stop after N downloads |
| **Failed Prompts** | Tracks rejected prompts for review |
| **Session Summary** | End-of-batch report with total time, downloads, and cooldowns |

---

## 📋 Requirements

| Requirement | Details |
|------------|---------|
| **Browser** | Google Chrome (latest version) |
| **Account** | Active Canva account with Dream Lab access |
| **Settings** | Developer Mode enabled in `chrome://extensions/` |

---

## 📥 Installation

### Step 1 — Get the Code

**Option A: Clone** (recommended)
```bash
git clone https://github.com/novri-ra/Canva-Auto-Prompter.git
```

**Option B: Download ZIP**
Click the green **Code** button on GitHub → **Download ZIP** → Extract

### Step 2 — Load in Chrome

1. Open `chrome://extensions/`
2. Toggle **Developer Mode** ON (top-right)
3. Click **Load unpacked**
4. Select the `Canva-Auto-Prompter` folder
5. ✅ Done! The extension icon appears in your toolbar

---

## 🎯 Usage

| Step | Action |
|:----:|--------|
| **1** | Navigate to [canva.com/dream-lab](https://www.canva.com/dream-lab) or click 🚀 in the panel |
| **2** | Click the extension icon to open the side panel |
| **3** | Paste your prompts *(one per line)* in the text area |
| **4** | Select **Image Style**, **Aspect Ratio**, and **Download Count** |
| **5** | Click **▶ Run** — automation begins! |

### Example Prompts

```
A serene mountain landscape at golden hour, cinematic lighting
Futuristic cyberpunk city with neon reflections in rain puddles
Minimalist abstract geometric pattern in blue and gold
Cute robot reading a book in a cozy library, 3D render
```

### ⚠️ Debugger Banner

When automation starts, Chrome shows:

> **"Canva Auto Prompter" started debugging this browser**

**Do not close this banner!** It's required for the automation to work. Closing it terminates the session immediately.

---

## ⚙️ Settings

Click the ⚙️ icon in the panel to configure:

| Setting | Options | Default |
|---------|---------|---------|
| **Color Theme** | Retro Terminal / Matrix Hacker / Clean Light | Retro Terminal |
| **Font Style** | Pixel / Monospace / System Default | Pixel |
| **Typing Mode** | Human Typing / Instant Paste | Human Typing |
| **Batch Limit** | 0 (unlimited) – 999 | 0 |
| **Safety Delay** | 0s – 10s extra between operations | 0s |
| **Audio Alerts** | On / Off | On |

### Supported Styles

| | | | |
|---|---|---|---|
| Smart | Cinematic Concept | Creative | Bokeh |
| Macro | Illustration | 3D Render | Cinematic |
| Fashion | Minimalist | Moody | Portrait |
| Sketch - Color | Stock Photo | Ray Traced | Vibrant |
| Pop Art | Vector | | |

---

## 🔧 Troubleshooting

<details>
<summary><b>❌ Automation stops immediately after clicking Run</b></summary>

- Ensure you're on `canva.com/dream-lab` (not other Canva pages)
- Check if the debugger banner appeared — if not, refresh and retry
- Verify Developer Mode is enabled in `chrome://extensions/`
</details>

<details>
<summary><b>⏳ Status shows "Rate Limited — Waiting..."</b></summary>

- This is **normal** — Canva enforces cooldown periods between generations
- The extension auto-resumes when the cooldown ends (live countdown shown)
- Don't close the browser tab during cooldown
</details>

<details>
<summary><b>🚫 Prompt marked as "Content Policy Violation"</b></summary>

- Canva rejected the prompt due to content guidelines
- Check the "Failed Prompts" section in the panel
- The extension auto-skips and continues with remaining prompts
</details>

<details>
<summary><b>📥 Images not downloading</b></summary>

- Check Chrome download settings (`Ctrl+J`)
- Try increasing **Safety Delay** in settings
- Verify your Downloads folder has available space
</details>

<details>
<summary><b>🔄 Panel is blank or unresponsive</b></summary>

- Close and reopen the side panel
- Reload the extension in `chrome://extensions/`
- Clear browser cache and restart Chrome
</details>

---

## 🏗️ Architecture

Built on **Chrome Manifest V3** with three core components:

```
┌─────────────────┐
│  panel.html/js  │  ← UI: Queue management, settings, live terminal
└────────┬────────┘
         │ chrome.runtime messages
┌────────▼────────┐
│  background.js  │  ← Service Worker: CDP connection, debugger attach/detach
└────────┬────────┘
         │ CDP protocol
┌────────▼────────┐
│   content.js    │  ← DOM Engine: State machine, rate limit parser, automation loop
└─────────────────┘
```

**Key technologies:**
- **Chrome DevTools Protocol (CDP)** — Simulates real hardware mouse/keyboard events that bypass React's synthetic event system
- **XPath Selectors** — Robust querying for Canva's dynamic React DOM
- **Web Worker Timers** — Immune to Chrome's background tab throttling
- **Chrome Storage API** — Persistent queue and configuration state

---

## ⚠️ Important Notes

| Topic | Details |
|-------|---------|
| **Rate Limits** | Canva enforces per-request cooldowns (2–5 min) and monthly AI limits based on your plan. The extension handles these automatically. |
| **Content Policy** | Prompts violating Canva's guidelines are auto-skipped. Failed prompts are logged for review. |
| **Active Tab** | The extension requires an active Chrome window — it can't run reliably in background tabs. |
| **Scope** | Only works on `canva.com/dream-lab`. |

---

## 📄 Disclaimer

> **⚠️ Educational & Research Purpose Only**
>
> This software demonstrates Chrome extension development and browser automation techniques.
>
> **Using this tool may violate Canva's [Terms of Service](https://www.canva.com/policies/terms-of-use/).** The developer assumes **no liability** for account suspensions, data loss, or any other consequences of use.
>
> **Use responsibly and at your own risk.**

---

## 👨‍💻 Author

<div align="center">

**Novri Rizki Akbar**

[![Portfolio](https://img.shields.io/badge/Portfolio-lynk.id/novri--ra-blue?style=for-the-badge)](https://lynk.id/novri-ra)
[![GitHub](https://img.shields.io/badge/GitHub-novri--ra-black?style=for-the-badge&logo=github)](https://github.com/novri-ra)

</div>

---

<div align="center">

**⭐ If this project helps you, consider starring it on GitHub!**

Made with ❤️ for the automation community

**[⬆ Back to Top](#-canva-auto-prompter)**

</div>
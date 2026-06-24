# 🤖 Canva Auto Prompter

<div align="center">

![Canva Auto Prompter Banner](https://img.shields.io/badge/Canva-Auto_Prompter-00C4CC?style=for-the-badge&logo=canva&logoColor=white)

**Automate bulk AI image generation on Canva Dream Lab with intelligent rate limiting and CDP-powered automation**

[![Chrome Extension](https://img.shields.io/badge/Chrome-Extension-4285F4?logo=google-chrome&logoColor=white)](https://www.google.com/chrome/)
[![Manifest V3](https://img.shields.io/badge/Manifest-V3-success)](https://developer.chrome.com/docs/extensions/mv3/)
[![JavaScript](https://img.shields.io/badge/JavaScript-ES6+-F7DF1E?logo=javascript&logoColor=black)](https://developer.mozilla.org/en-US/docs/Web/JavaScript)
[![License](https://img.shields.io/badge/License-Educational-orange)](LICENSE)

[Features](#-features) • [Installation](#-installation) • [Usage](#-usage) • [Troubleshooting](#-troubleshooting) • [Author](#-author)

</div>

---

## 📑 Table of Contents

- [Overview](#overview)
- [Features](#-features)
- [Requirements](#-requirements)
- [Installation](#-installation)
- [Usage](#-usage)
- [Configuration](#-configuration)
- [Troubleshooting](#-troubleshooting)
- [Technical Details](#-technical-details)
- [Roadmap](#-roadmap)
- [Disclaimer](#-disclaimer)
- [Author](#-author)

---

## Overview

**Canva Auto Prompter** is a Chrome extension that automates bulk AI image generation on Canva Dream Lab. Instead of manually entering prompts one by one, this tool allows you to queue multiple prompts and let the automation handle the entire process—including rate limit detection, style selection, and automatic downloading.

Perfect for content creators, designers, and marketers who need to generate multiple AI images efficiently.

---

## ✨ Features

<table>
<tr>
<td width="50%">

### 🎯 Automation
- **Bulk Processing** - Queue unlimited prompts
- **Smart Rate Limiting** - Auto-detects cooldowns with live countdown
- **Error Recovery** - Handles failures gracefully
- **Auto-Download** - Save 1-4 images per prompt
- **CDP-Powered** - Undetectable hardware-level clicks

</td>
<td width="50%">

### 🎨 Customization
- **20 Image Styles** - Smart, Cinematic, 3D, Illustration, etc.
- **6 Aspect Ratios** - 1:1, 16:9, 9:16, 3:4, 4:3, 2:1
- **3 Color Themes** - Retro, Matrix, Clean Light
- **Typing Modes** - Human-like or instant paste
- **Audio Alerts** - Optional sound notifications

</td>
</tr>
</table>

### 📊 Monitoring & Control

- **Live Terminal Logs** - Real-time color-coded status updates
- **Progress Tracking** - Current prompt, queue count, success/fail tallies
- **Batch Limits** - Auto-stop after N downloads
- **Failed Prompt List** - Track and retry rejected prompts

---

## 📋 Requirements

| Requirement | Details |
|------------|---------|
| **Browser** | Google Chrome (latest version) |
| **Account** | Active Canva account with Dream Lab access |
| **Permissions** | Developer Mode enabled in Chrome Extensions |

---

## 📥 Installation

### Method 1: Clone Repository (Recommended)

```bash
# Clone the repository
git clone https://github.com/novri-ra/Canva-Auto-Prompter.git

# Navigate to folder
cd Canva-Auto-Prompter
```

### Method 2: Download ZIP

1. Click the green **Code** button above
2. Select **Download ZIP**
3. Extract to your desired location

### Load Extension in Chrome

1. Open Chrome and navigate to `chrome://extensions/`
2. Toggle **Developer Mode** (top-right corner)
3. Click **Load unpacked**
4. Select the `Canva-Auto-Prompter` folder
5. ✅ Extension loaded! Look for the icon in your toolbar

---

## 🎯 Usage

### Quick Start Guide

<table>
<tr>
<td width="30" align="center">1️⃣</td>
<td>

**Open Canva Dream Lab**
- Navigate to [canva.com/dream-lab](https://www.canva.com/dream-lab)
- Or click the 🚀 button in the extension panel

</td>
</tr>
<tr>
<td width="30" align="center">2️⃣</td>
<td>

**Prepare Your Prompts**
- Click the extension icon to open the side panel
- Paste your prompts (one per line) in the text area
- Example:
  ```
  A serene mountain landscape at sunset
  Futuristic city with flying cars
  Abstract geometric pattern in blue and gold
  ```

</td>
</tr>
<tr>
<td width="30" align="center">3️⃣</td>
<td>

**Configure Settings**
- **Image Style**: Choose from 20 styles (e.g., Cinematic, 3D Render)
- **Aspect Ratio**: Select format (e.g., 1:1 for Instagram, 16:9 for YouTube)
- **Download Count**: Pick 1-4 images per prompt (or random)

</td>
</tr>
<tr>
<td width="30" align="center">4️⃣</td>
<td>

**Start Automation**
- Click the **▶ Run** button
- The debugger banner will appear: **"Canva Auto Prompter" started debugging this browser**
- ⚠️ **DO NOT close this banner!** It's required for automation

</td>
</tr>
<tr>
<td width="30" align="center">5️⃣</td>
<td>

**Monitor Progress**
- Watch the live terminal for real-time updates
- Status bar shows current operation
- Green = Success, Yellow = Waiting, Red = Error
- Images auto-download to your Downloads folder

</td>
</tr>
</table>

---

## ⚙️ Configuration

### Advanced Settings

Click the ⚙️ **Settings** icon in the panel to access:

| Setting | Options | Description |
|---------|---------|-------------|
| **Color Theme** | Retro Terminal / Matrix Hacker / Clean Light | Choose your preferred visual style |
| **Font Style** | Pixel / Monospace / System Default | Customize the terminal font |
| **Typing Mode** | Human Typing / Instant Paste | Realistic typing vs. fast paste |
| **Batch Limit** | 0 (unlimited) - 999 | Auto-stop after N downloads |
| **Safety Delay** | 0s - 10s | Extra delay between operations |
| **Audio Alerts** | On / Off | Sound notification on completion |

### Image Styles Available

```
Smart          Cinematic      3D Render      Anime
Illustration   Oil Painting   Charcoal       Watercolor
Sketch         Graffiti       Pop Art        Flat
Line Art       Pencil         Fantasy Art    Low Poly
Neon           Retro          Pixel Art      Origami
```

---

## 🔧 Troubleshooting

<details>
<summary><b>❌ Automation stops immediately after clicking Run</b></summary>

**Solution:**
- Check if the debugger banner appeared
- If it didn't, refresh the Canva page and try again
- Make sure you're on `canva.com/dream-lab` (not other Canva pages)
- Ensure Developer Mode is enabled in `chrome://extensions/`

</details>

<details>
<summary><b>⏸️ Extension shows "Rate Limited - Waiting..."</b></summary>

**Solution:**
- This is normal! Canva enforces cooldown periods
- The extension will automatically resume when the cooldown ends
- Live countdown is displayed in the status bar
- Don't close the browser or tab during cooldown

</details>

<details>
<summary><b>🚫 Prompts marked as "Content Policy Violation"</b></summary>

**Solution:**
- Canva rejected the prompt due to content guidelines
- Check the "Failed Prompts" section to see which ones failed
- Modify or remove problematic prompts
- The extension will automatically skip and continue with remaining prompts

</details>

<details>
<summary><b>📥 Images not downloading automatically</b></summary>

**Solution:**
- Check Chrome's download settings (Ctrl+J)
- Ensure Chrome has permission to download files
- Try increasing the "Safety Delay" in settings
- Check if your Downloads folder is full or has permission issues

</details>

<details>
<summary><b>🔄 Extension interface is blank or not responding</b></summary>

**Solution:**
- Close and reopen the side panel
- Reload the extension in `chrome://extensions/`
- Clear browser cache and restart Chrome
- Check browser console (F12) for error messages

</details>

---

## 🛠️ Technical Details

### Architecture

Built on **Chrome Manifest V3** with a three-component architecture:

```
┌─────────────────┐
│  panel.html/js  │ ← User Interface & Queue Management
└────────┬────────┘
         │
┌────────▼────────┐
│  background.js  │ ← Service Worker & CDP Connection Manager
└────────┬────────┘
         │
┌────────▼────────┐
│   content.js    │ ← DOM Automation Engine & State Machine
└─────────────────┘
```

### Key Technologies

- **Chrome DevTools Protocol (CDP)** - Hardware-level input simulation that bypasses React's synthetic event system
- **XPath Selectors** - Robust DOM querying for dynamic React elements
- **State Machine Pattern** - Sequential operation flow with automatic error recovery
- **Chrome Storage API** - Persistent configuration and queue management
- **MutationObserver** - Real-time DOM monitoring for rate limit detection

### Why CDP Instead of Click Events?

Traditional JavaScript click events don't work on Canva because:
1. React's synthetic event system blocks programmatic events
2. Event listeners check for trusted user interactions
3. Form inputs validate event origin

CDP simulates **actual hardware input** (mouse, keyboard) that browsers cannot distinguish from real user actions.

---

## ⚠️ Important Notes

### The Debugger Banner

When automation starts, Chrome displays a banner:

> **"Canva Auto Prompter" started debugging this browser**

**DO NOT CLOSE THIS BANNER!** It's required for CDP to function. Closing it stops automation immediately.

### Rate Limits

Canva enforces generation limits based on your subscription:
- **Free**: ~10-20 generations per day
- **Pro/Teams**: Higher limits, faster cooldowns
- **Cooldown**: Typically 2-5 minutes between batches

The extension handles these automatically with live countdown timers.

### Content Policy

Canva may reject prompts containing:
- Violent or graphic content
- Copyrighted characters or brands
- Political figures or sensitive topics
- Adult or inappropriate content

Failed prompts are logged for review and modification.

---

## 🔮 Roadmap

- [ ] Multi-account session rotation
- [ ] Network-based download detection (CDP Network events)
- [ ] Prompt templates with variables (e.g., `{{color}} car`)
- [ ] Export/import prompt lists (JSON, CSV)
- [ ] Batch analytics dashboard
- [ ] Custom style preset manager
- [ ] Scheduled automation (set time/date)
- [ ] Integration with other AI art platforms

---

## 📄 Disclaimer

> **⚠️ IMPORTANT: Educational Purpose Only**
>
> This software is developed strictly for **educational and research purposes** to demonstrate Chrome extension development and browser automation techniques.
>
> **Using this tool may violate Canva's [Terms of Service](https://www.canva.com/policies/terms-of-use/).** The developer assumes **NO LIABILITY** for:
> - Account suspensions or bans
> - Data loss or corruption
> - Violation of service limits
> - Any other consequences of use
>
> **Use responsibly and at your own risk.** Always respect platform policies and rate limits.

---

## 👨‍💻 Author

<div align="center">

**Novri Rizki Akbar**

[![Portfolio](https://img.shields.io/badge/Portfolio-lynk.id/novri--ra-blue?style=for-the-badge)](https://lynk.id/novri-ra)
[![GitHub](https://img.shields.io/badge/GitHub-novri--ra-black?style=for-the-badge&logo=github)](https://github.com/novri-ra)

*Building automation tools that save time and boost productivity*

For support, premium tools, or custom automation projects, visit my portfolio.

</div>

---

## 📜 License

This project is provided for **educational and research use only**. See the [Disclaimer](#-disclaimer) section for important information about usage and liability.

---

<div align="center">

### ⭐ Star This Repository

If this project helps you, consider giving it a star on GitHub!

**Made with ❤️ for the automation community**

---

**[⬆ Back to Top](#-canva-auto-prompter)**

</div>
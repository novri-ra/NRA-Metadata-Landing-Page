# 🤖 Canva Auto Prompter

<div align="center">

**Automate bulk AI image generation on Canva Dream Lab**

[![Chrome Extension](https://img.shields.io/badge/Chrome-Extension-blue?logo=google-chrome)](https://www.google.com/chrome/)
[![Manifest V3](https://img.shields.io/badge/Manifest-V3-green)](https://developer.chrome.com/docs/extensions/mv3/)
[![License](https://img.shields.io/badge/License-Educational-orange)](LICENSE)

</div>

---

## ✨ Features

- 🚀 **Bulk Automation** - Process multiple prompts in sequence without manual intervention
- 🎨 **20 Image Styles** - Support for all Canva Dream Lab styles (Smart, Cinematic, 3D Render, Illustration, etc.)
- 📐 **Multiple Aspect Ratios** - 1:1, 16:9, 9:16, 3:4, 4:3, 2:1
- ⏱️ **Smart Rate Limit Handling** - Automatically detects and waits out cooldown periods with live countdown
- 💾 **Auto-Download** - Download 1-4 images per prompt (or random selection)
- 🎯 **CDP-Powered Clicks** - Uses Chrome DevTools Protocol for undetectable, hardware-level input simulation
- 🌙 **Retro UI Theme** - Ergonomic midnight arcade interface with minimal eye strain
- 📊 **Live Console Logs** - Real-time operation monitoring with color-coded status updates
- 🔄 **Auto-Recovery** - Handles errors gracefully and resumes automation
- 🎵 **Audio Alerts** - Optional sound notifications on completion

---

## 📋 Requirements

- **Google Chrome** (latest version)
- **Canva Account** with Dream Lab access
- **Developer Mode** enabled in Chrome Extensions

---

## 📥 Installation

1. **Download the Extension**
   ```bash
   git clone https://github.com/novri-ra/Canva-Auto-Prompter.git
   cd Canva-Auto-Prompter
   ```

2. **Load in Chrome**
   - Open Chrome and navigate to `chrome://extensions/`
   - Enable **Developer Mode** (toggle in top-right corner)
   - Click **Load unpacked**
   - Select the `Canva-Auto-Prompter` folder

3. **Verify Installation**
   - You should see the Canva Auto Prompter icon in your extensions toolbar
   - Click it to open the side panel

---

## 🎯 Usage

### Quick Start

1. **Open Canva Dream Lab**
   - Navigate to [canva.com/dream-lab](https://www.canva.com/dream-lab)
   - Or click the 🚀 button in the extension panel

2. **Configure Settings**
   - Paste your prompts (one per line) in the text area
   - Select **Image Style** (e.g., Cinematic, 3D Render, Smart)
   - Choose **Aspect Ratio** (e.g., 1:1, 16:9)
   - Set **Download Count** (1-4 images per prompt)

3. **Start Automation**
   - Click the **Run** button
   - The debugger banner will appear - **DO NOT close it**
   - Watch the live terminal logs for progress updates

4. **Monitor Progress**
   - Real-time status updates in the terminal
   - Live countdown during rate limit cooldowns
   - Automatic image downloads to your Downloads folder

### Advanced Settings

Click the ⚙️ settings icon to access:
- **Color Theme** - Retro Terminal, Matrix Hacker, Clean Light Mode
- **Font Style** - Pixel, Monospace, or System Default
- **Typing Mode** - Human Typing (realistic) or Instant Paste (fast)
- **Batch Limit** - Auto-stop after N downloads
- **Safety Delay** - Extra delay between operations (0-10s)
- **Audio Alerts** - Enable/disable completion sounds

---

## ⚠️ Important Notes

### The Debugger Banner

When automation starts, Chrome displays a yellow banner:

> **"Canva Auto Prompter" started debugging this browser**

**⚠️ DO NOT close or dismiss this banner!** Closing it will stop the automation immediately. This banner is required for the Chrome DevTools Protocol to function.

### Rate Limits

Canva enforces generation limits:
- **Per-request cooldowns** - Typically 2-5 minutes between batches
- **Monthly AI limits** - Based on your Canva subscription plan

The extension automatically detects and handles these limits, displaying live countdowns in the status bar.

### Content Policy

Canva may reject prompts that violate their content policy. The extension will:
- Detect policy violations automatically
- Skip the blocked prompt
- Continue with remaining prompts
- Log failed prompts in the "Failed Prompts" section

---

## 🛠️ Technical Architecture

Built on **Chrome Manifest V3** with three core components:

- **`background.js`** - Service worker managing Chrome DevTools Protocol connections
- **`content.js`** - DOM automation engine with state machine and rate limit parser
- **`panel.html/js`** - Side panel UI with queue management and live terminal

### Key Technologies

- **Chrome DevTools Protocol (CDP)** - Hardware-level input simulation bypassing React event barriers
- **XPath Selectors** - Robust DOM querying for dynamic React elements
- **State Machine** - Sequential operation flow with error recovery
- **Storage API** - Persistent configuration and queue management

---

## 🐛 Known Limitations

- Only works on `canva.com/dream-lab`
- Requires active Chrome window (can't run in background tabs reliably)
- Subject to Canva's rate limits and terms of service
- Monthly AI generation limits apply based on your Canva plan

---

## 🔮 Roadmap

- [ ] Multi-account session rotation
- [ ] Network-based download detection (CDP Network events)
- [ ] Prompt templates and variables
- [ ] Export/import prompt lists
- [ ] Batch analytics and statistics
- [ ] Custom style presets

---

## 📄 Disclaimer

This software is developed strictly for **educational and research purposes**. 

⚠️ **Important:** Automating Canva may violate their [Terms of Service](https://www.canva.com/policies/terms-of-use/). Use at your own risk. The developer assumes **no liability** for:
- Account suspensions or bans
- Data loss or corruption
- Resource limit violations
- Any other consequences of use

**Use responsibly and respect Canva's policies.**

---

## 👨‍💻 Author

**Novri Rizki Akbar**

- 🔗 Portfolio: [lynk.id/novri-ra](https://lynk.id/novri-ra)
- 📧 Support: Available through portfolio link
- 💼 Premium Products: Check portfolio for advanced automation tools

---

## 📜 License

Educational and Research Use Only

---

<div align="center">

**⭐ If this project helps you, consider starring it on GitHub!**

Made with ❤️ for the automation community

</div>
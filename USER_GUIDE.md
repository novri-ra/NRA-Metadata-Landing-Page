# 📖 NRA DreamLab - User Guide

Welcome to the **NRA DreamLab** extension! This guide will walk you through how to use the extension to automate generating and downloading images on Canva's Dream Lab. 

---

## 🚀 Getting Started

### 1. Open Canva Dream Lab
First, navigate to the Canva Dream Lab page in Google Chrome:
👉 [https://www.canva.com/dream-lab](https://www.canva.com/dream-lab)

### 2. Open the Side Panel
Click the **NRA DreamLab icon** in your Chrome toolbar (the puzzle piece menu). This will open the control panel on the side of your screen. You will see a status light:
- 🟢 **Green (Canva Connected):** You are on the correct page and ready to go!
- 🔴 **Red (Error):** You need to open the Canva Dream Lab page, or refresh the tab.

---

## 🛠️ How to Run Automation

### Step 1: Enter Your Prompts
In the main text box, paste your image prompts. 
**Rule:** Put exactly **one prompt per line**. Blank lines are automatically skipped.

> 💡 **Pro Tip: Using the `{i}` Variable**
> If you want to generate the same prompt multiple times, add `{i}` anywhere in the text. For example: `A futuristic city in the rain {i}`. When you click Run, the extension will ask you how many iterations you want, and automatically create numbered variations for you!

### Step 2: Choose Your Settings
Use the dropdown menus below the text box to configure the output:
- **Aspect Ratio:** E.g., `16:9`, `1:1`, `9:16`. (Select "Random" to randomize).
- **Style:** E.g., `Cinematic`, `Minimalist`, `Anime`.
- **Download Count:** How many images to download per prompt (1 to 4).

### Step 3: Start Automation
Click the big **RUN** button. 
Sit back and watch! The extension will:
1. Type your prompt into the Canva input box.
2. Click the Generate button.
3. Wait until the images are fully rendered (sharp and clear).
4. Download the images directly to your computer.
5. Move on to the next prompt automatically.

---

## 📊 Understanding the Panel

### Status & Progress
- **Status Indicator:** Shows exactly what the bot is doing right now (e.g., "Typing prompt...", "Waiting for images...", "Cooldown: 02:45").
- **Progress:** Shows how many prompts are left in the queue.
- **Statistics Board:** Real-time metrics showing total processed prompts, total downloaded images, success rate, elapsed time, average speed, and Estimated Time of Arrival (ETA) for the remaining queue.

### Console Logs
The black terminal window at the bottom shows technical logs. Useful for monitoring the background process. You can export these logs or clear them using the tiny icons in the header.

---

## ⏸️ Pause & Resume

Need to stop the bot temporarily? 
Click the **⏸ PAUSE** button. The bot will finish its current task and then halt. 
Click **▶ RESUME** when you're ready to continue. 

If you click the **STOP** button (the big red button while running), the automation ends completely. However, your remaining prompts are saved. You can resume later and the bot will pick up right where it left off!

---

## 🛡️ Smart Error Handling (How the Bot Protects You)

NRA DreamLab is built with an advanced protection system so you can walk away from your computer safely:

### Server Overload & Cooldowns
Canva limits how fast you can generate images. If Canva shows a **"Try again in X minutes"** or **"Lots of people are using Dream Lab"** warning, the bot will instantly pause, read the exact remaining time on screen (whether it's format MM:SS, Xm Ys, or just Xs), and display a countdown timer. Once the cooldown clears, it resumes automatically.

### Monthly Limit Reached
If you hit your account's monthly AI generation limit, the bot detects the warning, stops immediately, and sends you a browser notification.

### "Preventative Memory Dump" (Auto-Reload)
Canva pages get slow and use a lot of RAM if left open for hundreds of generations. To prevent your browser from freezing, the bot performs a **Preventative Memory Dump**:
1. Every 50 prompts, the bot will automatically refresh the Canva tab.
2. It pauses itself briefly.
3. It reconnects, remembers exactly where it was, and resumes automatically!

### Quarantine System (Failed Prompts)
Sometimes Canva refuses a prompt (e.g., for safety violations, or random network errors). If a prompt fails completely, the bot skips it to keep the queue moving. 
- You will see the failed prompt appear in the **Quarantined Prompts** text box. 
- You can review them, edit out prohibited words, and click the ♻️ icon to send them back to the main queue!

---

## ⚙️ Advanced Settings (Settings Modal)

Click the **Gear Icon ⚙️** at the top of the panel to access Advanced Settings:

- **Download Folder Name:** Save all generated images into a specific subfolder (e.g., `MyProject/`).
- **Typing Mode:** Switch between "Human" (types fast character by character) and "Instant" (pastes instantly).
- **Safety Delay:** Add extra wait time (in seconds) after the image finishes rendering before downloading. Helpful for slow internet connections.
- **Save Delay:** Add extra delay between clicking the download buttons.
- **Play Sound Alert:** Rings a chime when the entire queue is finished.

---

## ❓ Troubleshooting

**The Start button is greyed out!**
Make sure you are on the `https://www.canva.com/dream-lab` page. If you are, just refresh the Canva tab.

**The bot stopped midway and the button says Error!**
Check the Console Logs for the exact error message. Usually, refreshing the Canva tab and clicking Run again solves most network or DOM issues.

**My computer went to sleep and the bot stopped!**
The extension has an active "KeepAwake" feature that asks your computer not to sleep while automating. Make sure your operating system isn't overriding Chrome's requests.

---
_Happy generating! 🎨_
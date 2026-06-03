# 🤖 Canva Auto Prompter

**_Manifest V3 Chrome Extension powered by Chrome DevTools Protocol (CDP)_**

---

## 🚀 1. Project Overview

**Canva Auto Prompter** is a God-Tier automation and bulk prompt runner engineered exclusively for **Canva Dream Lab** (`canva.com/dream-lab`). Built on the Google Chrome Manifest V3 standard, the extension wraps a robust background engine that connects directly to the Chrome DevTools Protocol (CDP) to execute hardware-level user inputs. This bypasses the virtualized synthetic event barriers common in modern React architectures.

Designed with an **"Ergonomic Midnight Arcade" 8-bit retro theme**, the panel uses slate-blue and green tones that minimize visual eye strain during long-running background sessions. The UI implements pure-CSS collapsible accordions (using the checkbox hack) to manage clutter and houses a custom, scrollable in-app terminal console displaying live, color-coded, verbose operation logs.

---

## 🏗️ 2. Architecture & Core Components

```
├── manifest.json       # Declarative permissions, debugger rules, and Side Panel configurations
├── background.js       # The CDP Bridge & Service Worker (debugger session runner)
├── panel.html          # Front-end Side Panel ( Midnight Arcade style UI )
├── panel.js            # Frontend State Sync, Queue Controller, and UI events
└── content.js          # DOM Sniper, Automation State Machine, & Console interceptor
```

### 🌉 `background.js` (The CDP Bridge)
Attaches `chrome.debugger` to the active tab to execute commands that regular content scripts cannot perform due to security sandboxes.
*   **Debugger Attachment:** Orchestrates `chrome.debugger.attach` and `detach` hooks.
*   **CDP Event Router:** Translates frontend action requests (`CDP_CLICK` and `CDP_TYPE`) into protocol commands:
    *   `Input.dispatchMouseEvent` (simulating coordinates-based press and release).
    *   `Input.dispatchKeyEvent` and `Input.insertText` (inserting high-speed keyboard input).

### 🎯 `content.js` (The DOM Sniper & State Machine)
Runs directly in the context of the Canva page. It is responsible for DOM traversal, state evaluation, error recovery, and rate limit parsing.
*   **DOM Sniper:** Dynamically queries custom elements, spans, and React portal inputs using robust fallback selectors and XPath expressions.
*   **State Machine:** Executes a strict sequential loop (Inject -> Verify -> Submit -> Cooldown Check -> Poll -> Download -> Shift Queue).
*   **Console Interceptor:** Overrides `console.log`, `console.warn`, and `console.error` to broadcast tab logs back to the side panel.

### 🎛️ `panel.html` & `panel.js` (UI & Queue Manager)
Powered by the Chrome Extensions Manifest V3 side panel API, providing a persistent, non-intrusive workspace interface.
*   **Queue Manager:** Manages the prompt queue in a FIFO (First-In, First-Out) destructive manner. Shifts prompts only after verified successful generation and download, preventing data loss in the event of failure.
*   **Visual Terminal logs:** Updates the customized scrollable terminal console with rich text formatting (green for info, yellow for warnings, and bold red for errors).

---

## ✨ 3. Key Features (The God-Tier Upgrades)

*   **CDP Hardware-Level Input:** Traditional DOM simulation (`element.click()`, `dispatchEvent`) fails on React-controlled elements because they do not trigger React's internal fiber state updates. By routing interactions through Chrome's native debugger API, Canva receives true OS-level mouse and keyboard events.
*   **Dynamic Rate Limit Handling:** When Canva displays a cooldown notification (e.g. *"Try again in 4:20"* or *"generate again in 0:45"*), `content.js` executes a RegEx scanner over the DOM. It extracts the minutes and seconds, converts it to milliseconds, adds a **5-second safety buffer**, and initiates a **live, visual countdown** ticking directly inside the Side Panel's Status bar.
*   **Auto-Clear & Retype Recovery:** After surviving a rate limit cooldown, the automation engine locates the input textarea, focuses it, clears it natively by dispatching input events, retypes the prompt using CDP typing commands, and verifies the content before triggering another submission.
*   **In-App Terminal Console:** Built-in console interceptor captures all console messages from the page, processes them with timestamps, prepends status tags (`[>]` for info, `[?]` for warnings, `[!]` for errors), and appends them to a formatted scrollable `div` terminal log.

---

## 🛡️ 4. Development Audit & Bug Log (The Journey)

### 🐛 Bug 1: Canva ignoring standard DOM input simulation
*   **Symptom:** Scripts using `textarea.value = text` followed by `dispatchEvent(new Event('input'))` failed. The text would appear visually but vanish the moment the "Submit" button was clicked, or the submit button would remain disabled.
*   **Root Cause:** Canva's inputs are tightly bound to React's state. React intercepts synthetic input events and ignores programmatic modifications that don't trigger the virtual DOM's fiber node setters.
*   **Solution:** Migrated the input logic to the Chrome DevTools Protocol (`CDP`). The script clicks the element to focus, clears the text area value natively, dispatches an input event to notify React, and uses the CDP debugger command `Input.insertText` to inject characters as if typed directly via a physical keyboard.

### 🐛 Bug 2: Account Rate Limits and Background Hangs
*   **Symptom:** Canva enforces strict generation rate limits. The automation loop would hit the warning toast and either freeze silently in the background or continuously click submit, resulting in blockages or false passes.
*   **Root Cause:** Submission was structured without catching active toast/modal messages returned by the Canva generation servers.
*   **Solution:** Built a dynamic RegEx parser inside the submission loop:
    ```javascript
    const timeMatch = warningText.match(/(\d+):(\d+)/);
    ```
    If matched, it calculates the exact wait time, converts the background sleep to a visual countdown loop that pushes updates to the side panel status text every second, and safely sleeps the thread.

### 🐛 Bug 3: `ReferenceError: currentPrompt is not defined`
*   **Symptom:** During rate-limit recovery loops, the script would crash or throw a `ReferenceError` when attempting to retype the prompt.
*   **Root Cause:** `currentPrompt` was declared within the inner try-catch scope of the main loop block. When the rate limit handler threw a recovery error or required a loop retry, the reference was lost.
*   **Solution:** Lifted the `currentPrompt` variable declaration to the outer scope of the `while (prompts.length > 0)` loop in `startMainLoop`, ensuring accessibility across the entire validation and retry lifecycle.

### 🐛 Bug 4: Visual Fatigue and UI Clutter
*   **Symptom:** The initial design used a flat red/brown color scheme that caused extreme visual fatigue, and long configuration options made the panel too tall, requiring constant scrolling.
*   **Root Cause:** Poor color choices and lack of collapsible controls.
*   **Solution:** Redesigned the UI with an "Ergonomic Midnight Arcade" palette (slate-blue background, muted borders, neon-green accents). Implemented pure-CSS "Checkbox Hack" accordions to collapse Settings, Terminal Logs, and Failed Prompts lists.
    ```css
    .toggle-cb:checked ~ .toggle-content { display: block; }
    .toggle-cb:not(:checked) ~ .toggle-content { display: none; }
    ```

---

## 🔮 5. Future Roadmap & Synchronizations

*   **🔄 Multi-Account Session Rotation:** Integration of a cookie/token storage array to automatically sign out and rotate sessions to a fresh account once a rate-limit cooldown exceeds 10 minutes.
*   **📡 Dynamic Network Hooking:** Replacing DOM polling for download button detection with CDP network event interception (`Network.responseReceived`), checking for completed high-res PNG/JPG canvas assets from Canva's rendering servers.

---

## 📥 6. Installation & Usage

### ⚙️ Installation
1.  Download or clone this repository to your local system.
2.  Open Google Chrome and navigate to `chrome://extensions/`.
3.  Enable **Developer Mode** using the switch in the top-right corner.
4.  Click **Load unpacked** in the top-left and select this project directory.

### 🕹️ Running Automation
1.  Navigate to `https://www.canva.com/dream-lab`.
2.  Click the **Canva Auto Prompter** icon in your extension toolbar to open the Side Panel.
3.  Paste your prompt list (one prompt per line) in the textarea.
4.  Set your desired **Aspect Ratio**, **Image Style**, and **Download Count**.
5.  Click **Run**.

> [!WARNING]  
> **The Debugger Banner:** Chrome will display a yellow banner stating: *"\"Canva Auto Prompter\" started debugging this browser"*. **DO NOT close or dismiss this banner.** Closing the banner detaches the debugger, instantly killing the automation process.

---

## ⚠️ 7. Disclaimer & Liability

This software is developed strictly for **educational and research purposes**. Automating platforms like Canva can be a violation of their **Terms of Service**. The developer assumes absolutely **no liability** for any account bans, suspensions, resource limitations, or data loss resulting from the use of this tool. Use responsibly and at your own discretion.

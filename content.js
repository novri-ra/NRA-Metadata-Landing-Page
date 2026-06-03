// ==========================================
// Console Interceptor for Side Panel UI
// ==========================================
const originalConsoleLog = console.log;
const originalConsoleWarn = console.warn;
const originalConsoleError = console.error;

function broadcastLog(level, ...args) {
  try {
    const msg = args.map(a => typeof a === 'object' ? JSON.stringify(a) : String(a)).join(' ');
    chrome.runtime.sendMessage({ action: "CONSOLE_LOG", level: level, message: msg }).catch(() => {});
  } catch (e) {
    // Fail silently if extension context is invalidated
  }
}

console.log = function(...args) { originalConsoleLog.apply(console, args); broadcastLog('INFO', ...args); };
console.warn = function(...args) { originalConsoleWarn.apply(console, args); broadcastLog('WARN', ...args); };
console.error = function(...args) { originalConsoleError.apply(console, args); broadcastLog('ERROR', ...args); };

// Canva Auto Prompter - Content Script targeting canva.com/dream-lab
// Operates exclusively on https://www.canva.com/dream-lab

// Global execution flag for the automation loop
let isRunning = false;

/**
 * Sends a status update message to the Side Panel/Popup.
 * @param {string} statusText 
 */
function sendStatusUpdate(statusText) {
  console.log(`[Canva Automation] Status update: ${statusText}`);
  chrome.runtime.sendMessage({ action: 'STATUS_UPDATE', status: statusText }, (response) => {
    // Ignore runtime error if Side Panel is not open to receive the message
    if (chrome.runtime.lastError) {
      // Diagnostic fail-silent
    }
  });
}

/**
 * delay(ms): Promise-based timeout.
 * @param {number} ms 
 * @returns {Promise<void>}
 */
function delay(ms) {
  console.log(`[Canva Automation] Waiting for ${ms}ms...`);
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Helper to check if automation has been stopped by the user.
 * @returns {Promise<boolean>}
 */
async function checkIfStopped() {
  return new Promise((resolve) => {
    chrome.storage.local.get(["isAutomating"], (res) => {
      resolve(res && res.isAutomating === false);
    });
  });
}

/**
 * Helper to dynamically wait for elements to exist in the DOM.
 * Loops every 300ms, throws error on timeout.
 * @param {string} selector 
 * @param {boolean} isXPath 
 * @param {number} maxWait 
 * @returns {Promise<HTMLElement>}
 */
function waitForElement(selector, isXPath = false, maxWait = 10000) {
  const checkInterval = 300;
  let elapsed = 0;

  return new Promise((resolve, reject) => {
    const interval = setInterval(() => {
      // Check if automation was stopped
      if (!isRunning) {
        clearInterval(interval);
        reject(new Error("USER_STOPPED"));
        return;
      }

      let element = null;
      if (isXPath) {
        element = document.evaluate(
          selector,
          document,
          null,
          XPathResult.FIRST_ORDERED_NODE_TYPE,
          null
        ).singleNodeValue;
      } else {
        element = document.querySelector(selector);
      }

      if (element) {
        clearInterval(interval);
        resolve(element);
      } else {
        elapsed += checkInterval;
        if (elapsed >= maxWait) {
          clearInterval(interval);
          reject(new Error(`Timeout waiting for element matching: ${selector}`));
        }
      }
    }, checkInterval);
  });
}

/**
 * Error Handling Router: updates state in storage and logs details to side panel.
 * @param {Error} err 
 */
function handleAutomationError(err) {
  if (err.message === "USER_STOPPED") {
    console.log("[Canva Automation] Process stopped manually.");
    chrome.storage.local.set({ isAutomating: false, step: 'IDLE' }, () => {
      sendStatusUpdate("Automation stopped by user.");
    });
    return;
  }

  console.error("[Canva Automation] Loop broken due to:", err);
  const errMsg = err.message || 'Unknown error occurred.';
  
  chrome.storage.local.set({ isAutomating: false, step: 'ERROR' }, () => {
    chrome.runtime.sendMessage({ status: "Error: " + errMsg });
  });
}

async function cdpClick(element) {
  element.scrollIntoView({ behavior: 'instant', block: 'center' });
  await delay(300);
  const rect = element.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) throw new Error("Element is hidden (0x0).");
  const x = Math.round(rect.left + rect.width / 2);
  const y = Math.round(rect.top + rect.height / 2);
  await new Promise(resolve => chrome.runtime.sendMessage({ action: "CDP_CLICK", x, y }, resolve));
}

async function cdpType(text) {
  await new Promise(resolve => chrome.runtime.sendMessage({ action: "CDP_TYPE", text }, resolve));
}

/**
 * Selects a value from a custom Canva dropdown element.
 * @param {string} labelText - The label identifying the dropdown (e.g., "Aspect ratio", "Style")
 * @param {string} optionText - The option text to select
 */
async function selectCanvaDropdown(labelText, optionText) {
  if (!optionText || optionText === 'None') {
    console.log(`[Canva Automation] Style set to None or empty. Skipping dropdown: ${labelText}`);
    return;
  }

  console.log(`[Canva Automation] Setting dropdown "${labelText}" to: "${optionText}"`);

  // Find label element to locate dropdown
  let labelElement = null;
  const elements = Array.from(document.querySelectorAll('label, span, button, p'));
  for (const el of elements) {
    if (el.textContent.trim().toLowerCase() === labelText.toLowerCase()) {
      labelElement = el;
      break;
    }
  }

  let dropdownTrigger = null;
  if (labelElement) {
    dropdownTrigger = labelElement.closest('button') ||
      labelElement.nextElementSibling?.querySelector('button') ||
      labelElement.nextElementSibling;
  }

  if (!dropdownTrigger) {
    dropdownTrigger = document.querySelector(`button[aria-label*="${labelText}" i]`) ||
      document.querySelector(`button[title*="${labelText}" i]`);
  }

  if (!dropdownTrigger) {
    throw new Error(`Gate Failed: Dropdown trigger for "${labelText}" not found.`);
  }

  // Open dropdown list
  await cdpClick(dropdownTrigger);
  
  // Wait 1200ms to ensure Canva's React Portal has fully rendered the listbox menu
  await delay(1200);

  // Evaluate XPath to find options handling nested HTML spans and role=option hierarchy
  const xpathPattern = "//*[contains(., '" + optionText + "') and (@role='option' or ancestor::*[@role='option'])]";
  let optionEl = null;
  try {
    optionEl = await waitForElement(xpathPattern, true, 4000);
  } catch (err) {
    console.log(`[Canva Automation] Primary option XPath lookup failed. Trying simpler contains(text()) fallback for: ${optionText}`);
    const fallbackXpath = "//*[contains(text(), '" + optionText + "')]";
    optionEl = await waitForElement(fallbackXpath, true, 2000);
  }

  if (optionEl) {
    console.log(`[Canva Automation] Found menu item option "${optionText}". Clicking to select...`);
    await cdpClick(optionEl);
    
    // Validation loop: ensure the menu has closed before proceeding
    let menuChecks = 0;
    while (document.body.contains(optionEl) && menuChecks < 10) {
      console.log("[Canva Automation] Waiting for dropdown menu to close...");
      await delay(300);
      menuChecks++;
    }
  } else {
    console.warn(`[Canva Automation] Menu option "${optionText}" not found in dropdown list.`);
    // Close dropdown to avoid blockages
    await cdpClick(dropdownTrigger);
    await delay(300);
  }
}

/**
 * Starts the main bulk automation loop, running sequentially without page reloads.
 */
async function startMainLoop() {
  console.log("[Canva Automation] Starting main automation loop...");
  sendStatusUpdate("Starting automation...");

  // Retrieve settings
  chrome.storage.local.get(["prompts", "aspectRatio", "imageStyle", "downloadCount"], async (result) => {
    try {
      // Pre-flight Check: Ensure loop is on the correct page
      if (!window.location.href.includes('dream-lab')) {
        throw new Error("URL_MISMATCH");
      }

      let prompts = result.prompts || [];
      const aspectRatio = result.aspectRatio;
      const imageStyle = result.imageStyle;
      const downloadCountSetting = result.downloadCount || "4";

      if (prompts.length === 0) {
        throw new Error("No prompts found in storage.");
      }

      // Mark status as active automation
      chrome.storage.local.set({ isAutomating: true });

      // Explicitly attach the debugger before starting the loop
      await new Promise(resolve => chrome.runtime.sendMessage({ action: "ATTACH_DEBUGGER" }, resolve));

      while (prompts.length > 0 && isRunning) {
        if (await checkIfStopped()) {
          console.log("[Canva Automation] Loop stopped by user request.");
          sendStatusUpdate("Automation stopped by user.");
          await new Promise(resolve => chrome.runtime.sendMessage({ action: "DETACH_DEBUGGER" }, resolve));
          return;
        }

        let currentPrompt = prompts[0];

        try {
          console.log(`[Canva Automation] Processing prompt: "${currentPrompt}"`);
          
          // Send current progress indicator back to Side Panel UI
          chrome.runtime.sendMessage({ progress: `${prompts.length} prompts remaining` });
          sendStatusUpdate("Configuring settings...");

          // Action 1 (Configure & Inject):
          // 1. Configure dropdown settings (Aspect Ratio and Image Style only)
          if (aspectRatio) {
            if (!isRunning) throw new Error("USER_STOPPED");
            sendStatusUpdate(`Setting Aspect Ratio: ${aspectRatio}`);
            await selectCanvaDropdown('Aspect ratio', aspectRatio);
          }
          if (imageStyle) {
            if (!isRunning) throw new Error("USER_STOPPED");
            sendStatusUpdate(`Setting Style: ${imageStyle}`);
            await selectCanvaDropdown('Style', imageStyle);
          }

          // 2. Find prompt input, clear it, inject text, and strictly verify
          if (!isRunning) throw new Error("USER_STOPPED");
          const textarea = await waitForElement('textarea[placeholder*="Describe"], textarea[class*="canva"]', false, 15000);
          sendStatusUpdate("Typing prompt...");
          
          // Focus the textarea, clear it natively, then type via CDP
          await cdpClick(textarea);
          await delay(200);
          textarea.value = '';
          textarea.dispatchEvent(new Event('input', { bubbles: true }));
          await cdpType(currentPrompt);
          await delay(500);

          if (!isRunning) throw new Error("USER_STOPPED");
          if (textarea.value !== currentPrompt) {
            console.warn("[Canva Automation] Value mismatch detected. Retrying cdpType...");
            await cdpClick(textarea);
            await delay(200);
            textarea.value = '';
            textarea.dispatchEvent(new Event('input', { bubbles: true }));
            await cdpType(currentPrompt);
            await delay(500);
          }
          if (textarea.value !== currentPrompt) {
            throw new Error("Action 1 Failed: Textarea value mismatch validation.");
          }

          // 3. Count the existing download buttons on the page BEFORE submitting
          let initialButtonCount = document.querySelectorAll('button[aria-label="Download Image"]').length;
          console.log(`[Canva Automation] Initial download button count: ${initialButtonCount}`);

          // 4. Submit prompt with Dynamic Rate Limit Handling
          let isRateLimited = true;
          while (isRateLimited) {
            if (!isRunning) throw new Error("USER_STOPPED");
            const submitBtn = await waitForElement('button[type="submit"]', false, 10000);
            console.log("[Canva Automation] Clicking submit button...");
            sendStatusUpdate("Generating images...");
            await cdpClick(submitBtn);

            // Wait to catch any immediate rate limit toast/text from Canva
            await delay(1500);

            // Look for the rate limit text anywhere on the screen
            const rateLimitWarning = document.evaluate(
              "//*[contains(text(), 'generate again in') or contains(text(), 'Try again in')]",
              document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null
            ).singleNodeValue;

            if (rateLimitWarning) {
              const warningText = rateLimitWarning.textContent;
              console.warn(`[Canva Automation] ⏳ Rate limit hit! Detected text: "${warningText}"`);

              // Extract mm:ss using regex (matches "0:52", "4:50", etc.)
              const timeMatch = warningText.match(/(\d+):(\d+)/);
              let waitTimeMs = 330000; // Default 5.5 minutes fallback just in case regex fails
              let logMsg = "default 5.5m fallback";

              if (timeMatch) {
                const minutes = parseInt(timeMatch[1], 10);
                const seconds = parseInt(timeMatch[2], 10);
                waitTimeMs = ((minutes * 60) + seconds) * 1000;
                logMsg = `${minutes}m ${seconds}s`;
              }

              // Add a 5000ms (5 seconds) safety buffer to ensure Canva's server clears the lock
              const finalWaitMs = waitTimeMs + 5000;
              const displayWaitSecs = Math.ceil(finalWaitMs / 1000);

              console.log(`[Canva Automation] Parsed dynamic wait time: ${logMsg}. Adding 5s buffer. Total sleep: ${displayWaitSecs} seconds.`);
              sendStatusUpdate(`Rate limit! Resting for ${displayWaitSecs} seconds...`);

              // Visual Countdown Loop
              const totalWaitSecs = Math.ceil(finalWaitMs / 1000);
              for (let i = totalWaitSecs; i > 0; i--) {
                  if (!isRunning) throw new Error("USER_STOPPED");
                  // Send countdown strictly to the Status text so the user can see it ticking
                  chrome.runtime.sendMessage({ action: "STATUS_UPDATE", status: `Limit cooldown: ${i}s remaining` });
                  await delay(1000);
              }
              
              // Dismiss 'Got it' toast
              const gotItBtn = document.evaluate("//button[.//span[text()='Got it']]", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
              if (gotItBtn) {
                  console.log("[Canva Automation] Dismissing 'Got it' toast before retrying.");
                  try { await cdpClick(gotItBtn); } catch (e) { /* ignore */ }
              }

              console.log("[Canva Automation] Dynamic cooldown complete. Clearing text field and retyping prompt...");
              sendStatusUpdate("Cooldown done. Retyping prompt...");

              // Retype prompt logic
              const retryTextarea = await waitForElement('textarea[placeholder*="Describe"], textarea[class*="canva"]', false, 5000);
              if (retryTextarea) {
                  await cdpClick(retryTextarea);
                  await delay(300);
                  retryTextarea.value = '';
                  retryTextarea.dispatchEvent(new Event('input', { bubbles: true }));
                  await delay(300);
                  await cdpType(currentPrompt); // Variable exists thanks to the previous scope fix
                  await delay(500);
              }

              console.log("[Canva Automation] Retyping complete. Initiating new submission loop...");
              if (!isRunning) throw new Error("USER_STOPPED");
            } else {
              // Success, no limit block detected
              isRateLimited = false;
            }
          }

          // Action 2 (Wait & Download):
          // 1. Polling loop checking every 1000ms until the button count strictly increases
          let currentBtnCount = initialButtonCount;
          let pollAttempts = 0;
          const maxPollAttempts = 90; // 90 seconds timeout for image generation
          
          while (currentBtnCount <= initialButtonCount) {
            if (!isRunning) throw new Error("USER_STOPPED");
            await delay(1000);
            currentBtnCount = document.querySelectorAll('button[aria-label="Download Image"]').length;
            pollAttempts++;
            console.log(`[Canva Automation] Polling for new download buttons (attempt ${pollAttempts}). Current count: ${currentBtnCount}, Initial count: ${initialButtonCount}`);
            if (pollAttempts > maxPollAttempts) {
              throw new Error("Action 2 Failed: Timeout waiting for new generated images.");
            }
          }

          // 2. CRITICAL VISUAL RENDER DELAY: 5000ms to allow Canva to fully paint the high-res image assets
          if (!isRunning) throw new Error("USER_STOPPED");
          console.log('[Canva Automation] New images detected! Awaiting 5s paint delay...');
          sendStatusUpdate("Assets detected. Loading high-res images...");
          await delay(5000);

          // 3. Query buttons again and slice the newest batch from the top
          if (!isRunning) throw new Error("USER_STOPPED");
          const allBtns = document.querySelectorAll('button[aria-label="Download Image"]');
          let newestButtons = Array.from(allBtns).slice(0, 4);
          let targetCount = 4;

          if (downloadCountSetting === "Random") {
            targetCount = Math.floor(Math.random() * 4) + 1;
            newestButtons.sort(() => Math.random() - 0.5);
            console.log(`[Canva Automation] Random mode chosen. Shuffled list and resolved target count: ${targetCount}`);
          } else {
            targetCount = parseInt(downloadCountSetting, 10);
            if (isNaN(targetCount) || targetCount < 1) {
              targetCount = 4;
            }
            console.log(`[Canva Automation] Target download count: ${targetCount}`);
          }

          const buttonsToDownload = newestButtons.slice(0, targetCount);

          // 4. Download click loop
          for (let i = 0; i < buttonsToDownload.length; i++) {
            if (!isRunning) throw new Error("USER_STOPPED");
            console.log(`[Canva Automation] Downloading image ${i + 1}/${buttonsToDownload.length}`);
            sendStatusUpdate(`Downloading image ${i + 1} of ${buttonsToDownload.length}...`);
            await cdpClick(buttonsToDownload[i]);
            await delay(1500);
          }

          // 5. Mandatory save delay
          if (!isRunning) throw new Error("USER_STOPPED");
          console.log('[Canva Automation] Waiting 6 seconds for download files to save to disk...');
          sendStatusUpdate("Saving downloaded images...");
          await delay(6000);

          // Destructive Queue Shift: Remove processed prompt and update storage/UI
          prompts.shift();
          await chrome.storage.local.set({ prompts: prompts });
          chrome.runtime.sendMessage({ action: "UPDATE_TEXTAREA", remainingPrompts: prompts });

        } catch (error) {
          if (error.message === "USER_STOPPED") {
            console.log("[Canva Automation] Process stopped manually.");
            chrome.storage.local.set({ isAutomating: false, step: "IDLE" }, () => {
              sendStatusUpdate("Automation stopped by user.");
            });
            await new Promise(resolve => chrome.runtime.sendMessage({ action: "DETACH_DEBUGGER" }, resolve));
            return; // Break the main loop and exit
          }
          console.warn("[Canva Automation] Prompt failed/skipped:", currentPrompt, error);
          
          // Send the failed prompt to the panel
          chrome.runtime.sendMessage({ action: "PROMPT_FAILED", failedPrompt: currentPrompt });

          // Remove the failed prompt from the queue
          prompts.shift();

          // Update chrome.storage.local with the new prompts array
          await chrome.storage.local.set({ prompts: prompts });

          // Send the "UPDATE_TEXTAREA" message to refresh the main input UI
          chrome.runtime.sendMessage({ action: "UPDATE_TEXTAREA", remainingPrompts: prompts });

          // Send a status update
          sendStatusUpdate("Prompt failed. Recovering and moving to next...");

          // Detach debugger cleanly before forcing reload
          await new Promise(resolve => chrome.runtime.sendMessage({ action: "DETACH_DEBUGGER" }, resolve));

          // CRITICAL RECOVERY: Force a page reload
          window.location.href = "https://www.canva.com/dream-lab";
        }
      }

      // Finished loop cleanly without cancellation
      if (isRunning && prompts.length === 0) {
        chrome.storage.local.set({ isAutomating: false, step: "IDLE" }, () => {
          console.log('[Canva Automation] Reset state to IDLE. Bulk automation complete.');
          sendStatusUpdate("Bulk generation complete!");
        });
      }
      await new Promise(resolve => chrome.runtime.sendMessage({ action: "DETACH_DEBUGGER" }, resolve));

    } catch (loopErr) {
      if (loopErr.message === "USER_STOPPED") {
        console.log("[Canva Automation] Loop caught USER_STOPPED outer signal.");
        chrome.storage.local.set({ isAutomating: false, step: "IDLE" }, () => {
          sendStatusUpdate("Automation stopped by user.");
        });
      } else {
        handleAutomationError(loopErr);
      }
      await new Promise(resolve => chrome.runtime.sendMessage({ action: "DETACH_DEBUGGER" }, resolve));
    }
  });
}

// ==========================================
// Initialization Block
// ==========================================

// 1. Listen for START_AUTOMATION and STOP_AUTOMATION messages from popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message) {
    if (message.action === "START_AUTOMATION") {
      console.log("[Canva Automation] START_AUTOMATION trigger received.");
      if (window.location.href.includes("dream-lab")) {
        isRunning = true;
        startMainLoop().catch(err => handleAutomationError(err));
        sendResponse({ success: true, status: "Automation started" });
      } else {
        sendResponse({
          success: false,
          error: "Extension is not currently on a canva.com/dream-lab page.",
        });
      }
    } else if (message.action === "STOP_AUTOMATION") {
      console.log("[Canva Automation] STOP_AUTOMATION trigger received.");
      isRunning = false;
      chrome.storage.local.set({ isAutomating: false, step: "IDLE" }, () => {
        sendStatusUpdate("Automation stopped by user.");
      });
      sendResponse({ success: true, status: "Automation stopped by user." });
    }
    return true; // async channel keep-alive
  }
});

// 2. Run state check on page load / refresh (resuming automation loop states)
(async () => {
  console.log(
    "[Canva Automation] Content script loaded. Checking automation state...",
  );
  if (!window.location.href.includes("dream-lab")) {
    console.log("[Canva Automation] Not on dream-lab page. Exiting initialization.");
    return;
  }
  try {
    chrome.storage.local.get(["isAutomating"], (result) => {
      console.log("[Canva Automation] Local state retrieved on load:", result);
      if (result && result.isAutomating === true) {
        isRunning = true;
        startMainLoop().catch(err => handleAutomationError(err));
      }
    });
  } catch (err) {
    handleAutomationError(err);
  }
})();

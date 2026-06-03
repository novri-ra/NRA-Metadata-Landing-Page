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

/**
 * simulateTyping(el, text): Sets value, dispatches 'input' and 'change' events.
 * Uses prototype setter override for React application compatibility.
 * @param {HTMLTextAreaElement|HTMLInputElement} el 
 * @param {string} text 
 */
function simulateTyping(el, text) {
  console.log(`[Canva Automation] Typing text: "${text}"`);
  el.value = text;

  const elementType =
    el instanceof HTMLTextAreaElement ? HTMLTextAreaElement : HTMLInputElement;
  const nativeSetter = Object.getOwnPropertyDescriptor(
    elementType.prototype,
    "value",
  )?.set;
  if (nativeSetter) {
    console.log(
      `[Canva Automation] React-specific setter found. Executing prototype write.`,
    );
    nativeSetter.call(el, text);
  }

  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.dispatchEvent(new Event("change", { bubbles: true }));
}

/**
 * simulateHumanClick(el): Dispatches 'mouseover', 'mousedown', 'mouseup', 'click'.
 * @param {HTMLElement} el
 */
function simulateHumanClick(el) {
  const opts = { bubbles: true, cancelable: true, view: window };
  el.dispatchEvent(new MouseEvent("mouseover", opts));
  el.dispatchEvent(new MouseEvent("mousedown", opts));
  el.dispatchEvent(new MouseEvent("mouseup", opts));
  el.dispatchEvent(new MouseEvent("click", opts));
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
  simulateHumanClick(dropdownTrigger);
  
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
    simulateHumanClick(optionEl);
    
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
    simulateHumanClick(dropdownTrigger);
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

      while (prompts.length > 0 && isRunning) {
        if (await checkIfStopped()) {
          console.log("[Canva Automation] Loop stopped by user request.");
          sendStatusUpdate("Automation stopped by user.");
          return;
        }

        try {
          const currentPrompt = prompts[0];
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
          textarea.value = ''; // Clear it first
          simulateTyping(textarea, currentPrompt);
          await delay(500);

          if (!isRunning) throw new Error("USER_STOPPED");
          if (textarea.value !== currentPrompt) {
            console.warn("[Canva Automation] Value mismatch detected. Retrying simulateTyping...");
            textarea.value = '';
            simulateTyping(textarea, currentPrompt);
          }
          if (textarea.value !== currentPrompt) {
            throw new Error("Action 1 Failed: Textarea value mismatch validation.");
          }

          // 3. Count the existing download buttons on the page BEFORE submitting
          let initialButtonCount = document.querySelectorAll('button[aria-label="Download Image"]').length;
          console.log(`[Canva Automation] Initial download button count: ${initialButtonCount}`);

          // 4. Submit prompt
          if (!isRunning) throw new Error("USER_STOPPED");
          const submitBtn = await waitForElement('button[type="submit"]', false, 10000);
          console.log("[Canva Automation] Clicking submit button...");
          sendStatusUpdate("Generating images...");
          simulateHumanClick(submitBtn);

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
            simulateHumanClick(buttonsToDownload[i]);
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

    } catch (loopErr) {
      if (loopErr.message === "USER_STOPPED") {
        console.log("[Canva Automation] Loop caught USER_STOPPED outer signal.");
        chrome.storage.local.set({ isAutomating: false, step: "IDLE" }, () => {
          sendStatusUpdate("Automation stopped by user.");
        });
      } else {
        handleAutomationError(loopErr);
      }
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

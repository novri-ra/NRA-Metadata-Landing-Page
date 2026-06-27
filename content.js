// ==========================================
// Console Interceptor for Side Panel UI
// ==========================================
const originalConsoleLog = console.log;
const originalConsoleWarn = console.warn;
const originalConsoleError = console.error;

function broadcastLog(level, ...args) {
  try {
    const msg = args
      .map((a) => (typeof a === "object" ? JSON.stringify(a) : String(a)))
      .join(" ");
    chrome.runtime
      .sendMessage({ action: "CONSOLE_LOG", level: level, message: msg })
      .catch((err) => {
        if (
          chrome.runtime?.lastError?.message !== "Extension context invalidated"
        ) {
          originalConsoleWarn("[Content] Log broadcast failed:", err);
        }
      });
  } catch (e) {
    // Fail silently if extension context is invalidated
  }
}

console.log = function (...args) {
  originalConsoleLog.apply(console, args);
  broadcastLog("INFO", ...args);
};
console.warn = function (...args) {
  originalConsoleWarn.apply(console, args);
  broadcastLog("WARN", ...args);
};
console.error = function (...args) {
  originalConsoleError.apply(console, args);
  broadcastLog("ERROR", ...args);
};

// Verbose Logs Helper Function
async function logToTerminal(message, isVerboseOnly = false) {
  // Check user settings
  const res = await chrome.storage.local.get(["verboseLogs"]);
  const isVerboseMode = res.verboseLogs !== false; // Default to true

  // If this is a detailed log and the user turned off verbose mode, skip it.
  if (isVerboseOnly && !isVerboseMode) return;

  const timestamp = new Date().toLocaleTimeString();
  const fullMessage = `[${timestamp}] ${message}`;

  console.log(fullMessage);
  chrome.runtime.sendMessage({ action: "LOG_MESSAGE", message: fullMessage });
}

// Canva Auto Prompter - Content Script targeting canva.com/dream-lab
// Operates exclusively on https://www.canva.com/dream-lab

let isPausedGlobal = false;
let batchLimitGlobal = 0;

// Set up a local cache listener to drastically reduce storage I/O
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "local") {
    if (changes.isPaused !== undefined) {
      isPausedGlobal = changes.isPaused.newValue === true;
    }
    if (changes.batchLimit !== undefined) {
      batchLimitGlobal = parseInt(changes.batchLimit.newValue, 10) || 0;
    }
  }
});

// Seed the variables immediately on script load
chrome.storage.local.get(["isPaused", "batchLimit"], (res) => {
  if (res.isPaused !== undefined) isPausedGlobal = res.isPaused === true;
  if (res.batchLimit !== undefined)
    batchLimitGlobal = parseInt(res.batchLimit, 10) || 0;
});

// Global execution flag for the automation loop
let isRunning = false;
// Mutex guard: prevents concurrent startMainLoop() invocations (KRITIS-2)
let isLoopActive = false;
// Session Statistics Telemetry
let prompts = [];
let sessionStats = {
  startTime: null,
  successCount: 0,
  downloadCount: 0,
  totalCooldowns: 0,
  totalPrompts: 0,
};

/**
 * Helper function to sanitize sessionStats and prevent NaN values.
 * @param {Object} stats
 * @returns {Object}
 */
function sanitizeStats(stats) {
  if (!stats)
    return {
      startTime: Date.now(),
      successCount: 0,
      downloadCount: 0,
      totalCooldowns: 0,
      totalPrompts: 0,
    };

  return {
    startTime: stats.startTime || Date.now(),
    successCount: isNaN(stats.successCount) ? 0 : Number(stats.successCount),
    downloadCount: isNaN(stats.downloadCount) ? 0 : Number(stats.downloadCount),
    totalCooldowns: isNaN(stats.totalCooldowns)
      ? 0
      : Number(stats.totalCooldowns),
    totalPrompts: isNaN(stats.totalPrompts) ? 0 : Number(stats.totalPrompts),
  };
}

/**
 * Sends a status update message to the Side Panel/Popup.
 * @param {string} statusText
 */
function sendStatusUpdate(statusText) {
  console.log(`[Canva Automation] Status update: ${statusText}`);
  chrome.runtime.sendMessage(
    { action: "STATUS_UPDATE", status: statusText },
    (response) => {
      if (chrome.runtime.lastError) return; // Fail silently but correctly
    },
  );
}

// --- UNTHROTTLED WEB WORKER DELAY (IMMUNE TO BACKGROUND THROTTLING) ---
const workerBlob = new Blob(
  [
    `self.onmessage = function(e) { setTimeout(() => postMessage(e.data.id), e.data.time); }`,
  ],
  { type: "application/javascript" },
);

const workerUrl = URL.createObjectURL(workerBlob);
const delayWorker = new Worker(workerUrl);
URL.revokeObjectURL(workerUrl); // CRITICAL FIX: Frees the memory immediately

/**
 * delay(ms): Promise-based timeout using a Web Worker thread.
 * Web Workers are immune to Chrome's background tab throttling,
 * which throttles standard setTimeout to 1 execution per minute.
 * @param {number} ms
 * @returns {Promise<void>}
 */
function delay(ms) {
  if (ms >= 1000) console.log(`[Canva Automation] Waiting for ${ms}ms...`);
  return new Promise((resolve) => {
    const id = Math.random().toString();
    const handler = (e) => {
      if (e.data === id) {
        delayWorker.removeEventListener("message", handler);
        resolve();
      }
    };
    delayWorker.addEventListener("message", handler);
    delayWorker.postMessage({ id: id, time: ms });
  });
}
/**
 * delayWithFallback(ms, fallbackMs): Aman terhadap worker termination.
 * Jika worker mati, fungsi tetap resolve setelah fallbackMs untuk mencegah loop macet.
 * @param {number} ms - Waktu delay utama (dalam milidetik)
 * @param {number} fallbackMs - Waktu maksimum tunggu sebelum fallback (default: ms + 2000)
 * @returns {Promise<void>}
 */
function delayWithFallback(ms, fallbackMs = ms + 2000) {
  return new Promise((resolve) => {
    let resolved = false;

    // Fallback timer menggunakan setTimeout sebagai safety net
    const fallbackTimer = setTimeout(() => {
      if (!resolved) {
        console.warn(
          `[Canva Automation] ⚠️ Delay fallback triggered after ${fallbackMs}ms (Worker mati atau lambat)`,
        );
        resolved = true;
        resolve();
      }
    }, fallbackMs);

    // Coba gunakan worker jika masih hidup
    try {
      const id = Math.random().toString();
      const handler = (e) => {
        if (e.data === id) {
          delayWorker.removeEventListener("message", handler);
          if (!resolved) {
            resolved = true;
            clearTimeout(fallbackTimer);
            resolve();
          }
        }
      };
      delayWorker.addEventListener("message", handler);
      delayWorker.postMessage({ id: id, time: ms });
    } catch (e) {
      // Worker sudah mati/terminate, resolve segera tanpa menunggu
      console.warn(
        "[Canva Automation] ⚠️ Worker tidak tersedia, menggunakan fallback instan.",
      );
      if (!resolved) {
        resolved = true;
        clearTimeout(fallbackTimer);
        resolve();
      }
    }
  });
}

/**
 * Formats raw seconds into an MM:SS string (e.g., 252 -> "4:12").
 * @param {number} totalSeconds
 * @returns {string}
 */
function formatTime(totalSeconds) {
  const m = Math.floor(totalSeconds / 60);
  const s = (totalSeconds % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

/**
 * Helper to check if automation has been stopped by the user.
 * @returns {Promise<boolean>}
 */
async function checkIfStopped() {
  const res = await chrome.storage.local.get(["isAutomating"]);
  return res && res.isAutomating === false;
}

/**
 * Helper to tag processed warnings so they are ignored in the future.
 * Applies data-bot-ignored attribute and visual feedback to ghost cooldown text.
 */
function tagGhostCooldowns() {
  const warnings = document.evaluate(
    "//*[not(@data-bot-ignored='true') and (contains(text(), 'Lots of people are using Dream Lab') or (not(ancestor-or-self::*" +
      CANVA_SELECTORS.ALERT_STATUS +
      ") and (contains(text(), 'generate again in') or contains(text(), 'Try again in'))))]",
    document,
    null,
    XPathResult.UNORDERED_NODE_SNAPSHOT_TYPE,
    null,
  );

  for (let i = 0; i < warnings.snapshotLength; i++) {
    const el = warnings.snapshotItem(i);
    el.setAttribute("data-bot-ignored", "true");
    el.style.opacity = "0.3";

    // Auto-click the Dismiss 'X' button if it exists nearby
    const dismissBtn = el
      .closest("div")
      ?.querySelector('button[aria-label="Dismiss"]');
    if (dismissBtn) dismissBtn.click();
  }
}

/**
 * Promisified utility to wait for a DOM element to exist, checking every 300ms.
 * Supports both CSS selectors and XPath.
 * @param {string} selector
 * @param {boolean} isXPath
 * @param {number} timeout
 * @returns {Promise<Element>}
 */
async function waitForElement(selector, isXPath = false, timeout = 10000) {
  return new Promise((resolve, reject) => {
    const checkInterval = 300;
    let elapsed = 0;

    const interval = setInterval(() => {
      // Check if automation was stopped externally
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
          null,
        ).singleNodeValue;
      } else {
        element = document.querySelector(selector);
      }

      if (element) {
        clearInterval(interval);
        resolve(element);
      } else {
        elapsed += checkInterval;
        if (elapsed >= timeout) {
          clearInterval(interval);
          reject(
            new Error(`Timeout waiting for element matching: ${selector}`),
          );
        }
      }
    }, checkInterval);
  });
}

function auditSelectors() {
  for (const [key, selector] of Object.entries(CANVA_SELECTORS)) {
    let element;
    if (selector.startsWith("//")) {
      // XPath selector
      const result = document.evaluate(
        selector,
        document,
        null,
        XPathResult.FIRST_ORDERED_NODE_TYPE,
        null,
      );
      element = result.singleNodeValue;
    } else {
      // CSS selector
      element = document.querySelector(selector); // Shorter timeout for quick check
    }
    if (!element) {
      console.error(`DIAGNOSTIC ERROR: Selector ${key} is NULL/NOT FOUND`);
    } else {
      console.log(`DIAGNOSTIC OK: Selector ${key} found`);
    }
  }
}

/**
 * Extracts the cooldown time remaining from a rate-limit warning element on the screen.
 * Updated radar to strictly ignore tagged ghosts.
 * @returns {number} Cooldown in milliseconds, or 0 if not found.
 */
function getScreenCooldownMs() {
  // Ensure we ignore elements tagged by tagGhostCooldowns
  let ignoredNodes = [];
  try {
    const nodes = document.querySelectorAll('[data-bot-ignored="true"]');
    if (nodes) ignoredNodes = Array.from(nodes);
  } catch (e) {}
  const originalStyles = [];
  ignoredNodes.forEach((node) => {
    originalStyles.push(node.style.display);
    node.style.display = "none";
  });

  const COOLDOWN_PATTERNS = {
    BUSY: /Lots of people are using/i,
    GENERATE: /generate again in/i,
    TRY: /Try again in/i,
  };

  const pageText = document.body.innerText;

  // Restore original display styles
  ignoredNodes.forEach((node, i) => {
    node.style.display = originalStyles[i];
  });

  for (const [key, pattern] of Object.entries(COOLDOWN_PATTERNS)) {
    const match = pageText.match(pattern);
    if (match) {
      if (key === "BUSY") {
        console.warn(
          "[Canva Automation] Server overload detected. Defaulting to 3 minutes cooldown.",
        );
        return 3 * 60 * 1000;
      } else if (key === "GENERATE" || key === "TRY") {
        const timeMatch = pageText.match(/(\d+):(\d+)/);
        if (timeMatch) {
          return (
            (parseInt(timeMatch[1], 10) * 60 + parseInt(timeMatch[2], 10)) *
            1000
          );
        }
      }
    }
  }

  return 0;
}

/**
 * Error Handling Router: updates state in storage and logs details to side panel.
 * @param {Error} err
 */
function handleAutomationError(err) {
  // KRITIS-3 FIX: Always reset both flags to prevent stuck state
  isRunning = false;
  isLoopActive = false;

  if (err.message === "USER_STOPPED") {
    console.log("[Canva Automation] Process stopped manually.");
    if (heartbeatInterval) {
      clearInterval(heartbeatInterval);
      heartbeatInterval = null;
    }
    chrome.storage.local.set({ isAutomating: false, step: "IDLE" }, () => {
      sendStatusUpdate("Automation stopped by user.");
    });
    return;
  }

  if (err.message === "MONTHLY_LIMIT_REACHED") {
    console.error(
      "[Canva Automation] Monthly AI limit reached. Stopping permanently.",
    );
    chrome.storage.local.set({ isAutomating: false, step: "ERROR" }, () => {
      sendStatusUpdate("🛑 Monthly Limit Reached. Stopped.");
      chrome.runtime.sendMessage({
        action: "SHOW_NOTIFICATION",
        title: "Canva Automation Halted",
        message:
          "You've hit your plan's monthly AI limit! Automation has been permanently stopped.",
      });
    });
    return;
  }

  console.error("[Canva Automation] Loop broken due to:", err);
  const errMsg = err.message || "Unknown error occurred.";

  // KRITIS-4 FIX: Include action key so panel.js processes the status correctly
  chrome.storage.local.set({ isAutomating: false, step: "ERROR" }, () => {
    chrome.runtime.sendMessage({
      action: "STATUS_UPDATE",
      status: "Error: " + errMsg,
    });
  });
}

async function safeCdpClick(element, context = "element") {
  try {
    await cdpClick(element);
  } catch (error) {
    console.error(`[Canva Automation] 🛑 Failed to click ${context}:`, error);
    chrome.runtime.sendMessage({ action: "EMERGENCY_CLEANUP" });
    throw new Error(`Click interaction failed for ${context}`); // Throw custom error instead of TypeError
  }
}

async function safeCdpTypeHuman(text, context = "input") {
  try {
    await cdpTypeHuman(text);
  } catch (error) {
    console.error(`[Canva Automation] 🛑 Failed to type in ${context}:`, error);
    chrome.runtime.sendMessage({ action: "EMERGENCY_CLEANUP" });
    throw new Error(`Type interaction failed for ${context}`); // Throw custom error instead of TypeError
  }
}
async function cdpClick(element) {
  element.scrollIntoView({ behavior: "instant", block: "center" });
  await delay(300);
  const rect = element.getBoundingClientRect();

  if (rect.width === 0 || rect.height === 0) {
    // LAYOUT TREE SUSPENDED (MINIMIZED/BACKGROUNDED TAB) -> Use native DOM events
    console.log(
      `[Canva Automation] Tab backgrounded. Using native DOM click fallback.`,
    );
    element.dispatchEvent(
      new MouseEvent("mousedown", {
        bubbles: true,
        cancelable: true,
        view: window,
      }),
    );
    element.dispatchEvent(
      new MouseEvent("mouseup", {
        bubbles: true,
        cancelable: true,
        view: window,
      }),
    );
    element.click();
    return;
  }

  // NORMAL ACTIVE TAB -> Use CDP Click
  const x = Math.round(rect.left + rect.width / 2);
  const y = Math.round(rect.top + rect.height / 2);

  // Timeout wrapper (10 detik maksimal)
  const response = await new Promise((resolve, reject) => {
    const timer = setTimeout(
      () =>
        reject(new Error("CDP_CLICK timeout: Background script unresponsive")),
      10000,
    );
    chrome.runtime.sendMessage({ action: "CDP_CLICK", x, y }, (res) => {
      clearTimeout(timer);
      resolve(res);
    });
  });

  if (response && !response.success) {
    console.warn(
      `[Canva Automation] ⚠️ CDP click failed, attempting native DOM click fallback.`,
    );
    element.dispatchEvent(
      new MouseEvent("mousedown", {
        bubbles: true,
        cancelable: true,
        view: window,
      }),
    );
    element.dispatchEvent(
      new MouseEvent("mouseup", {
        bubbles: true,
        cancelable: true,
        view: window,
      }),
    );
    element.click();
  }
}

async function cdpType(text) {
  // Timeout wrapper (10 detik maksimal)
  const response = await new Promise((resolve, reject) => {
    const timer = setTimeout(
      () =>
        reject(new Error("CDP_TYPE timeout: Background script unresponsive")),
      10000,
    );
    chrome.runtime.sendMessage({ action: "CDP_TYPE", text }, (res) => {
      clearTimeout(timer);
      resolve(res);
    });
  });
  if (response && !response.success)
    throw new Error(response.error || "Unknown CDP_TYPE error");
}

async function cdpTypeHuman(text) {
  console.log(`[Canva Automation] Typing prompt with human animation...`);
  for (let i = 0; i < text.length; i++) {
    const char = text[i];

    // Send single character
    const response = await new Promise((resolve) => {
      chrome.runtime.sendMessage({ action: "CDP_TYPE", text: char }, resolve);
    });

    // Strict error validation
    if (!response || response.success === false) {
      throw new Error(
        response?.error ||
          chrome.runtime.lastError?.message ||
          "CDP connection lost during typing",
      );
    }

    // Random delay between 15ms and 60ms to simulate human typing speed
    const typeDelay = Math.floor(Math.random() * 45) + 15;
    await delay(typeDelay);
  }
}

async function safeSelectCanvaConfiguration(typeLabel, optionText) {
  try {
    await selectCanvaConfiguration(typeLabel, optionText);
  } catch (error) {
    console.error(
      `[Canva Automation] 🛑 Failed to configure ${typeLabel} with ${optionText}:`,
      error,
    );
    chrome.runtime.sendMessage({ action: "EMERGENCY_CLEANUP" });
    throw new Error(`Configuration interaction failed for ${typeLabel}`);
  }
}

async function selectCanvaConfiguration(typeLabel, optionText) {
  if (
    !optionText ||
    optionText === "None" ||
    optionText === "" ||
    optionText === "Random"
  )
    return;

  const escapedOption = optionText.replace(/'/g, "\\'");

  // Helper to find the target option inside the popover grid
  const findTargetOption = () => {
    let xpath = `//div[@role='button' and @aria-label='${escapedOption}']`;
    let node = document.evaluate(
      xpath,
      document,
      null,
      XPathResult.FIRST_ORDERED_NODE_TYPE,
      null,
    ).singleNodeValue;
    if (!node) {
      xpath = `//*[(local-name()='button' or @role='button') and contains(normalize-space(), '${escapedOption}')]`;
      node = document.evaluate(
        xpath,
        document,
        null,
        XPathResult.FIRST_ORDERED_NODE_TYPE,
        null,
      ).singleNodeValue;
    }
    return node;
  };

  let targetButton = findTargetOption();
  let isTargetVisible =
    targetButton && targetButton.getBoundingClientRect().height > 0;

  // 1. OPEN THE MENU IF THE TARGET IS NOT VISIBLE
  if (!isTargetVisible) {
    console.log(
      `[Canva Automation] ${typeLabel} menu seems closed. Searching for trigger button...`,
    );

    // Exhaustive list to catch the trigger button no matter what its current text is
    const styleKeywords = [
      "Style",
      "None",
      "Smart",
      "Cinematic Concept",
      "Creative",
      "Bokeh",
      "Macro",
      "Illustration",
      "3D Render",
      "Cinematic",
      "Fashion",
      "Minimalist",
      "Moody",
      "Portrait",
      "Sketch - Color",
      "Stock Photo",
      "Ray Traced",
      "Vibrant",
      "Sketch - Black & White",
      "Pop Art",
      "Vector",
    ];
    const ratioKeywords = [
      "Ratio",
      "1:1",
      "16:9",
      "9:16",
      "4:3",
      "3:4",
      "3:2",
      "2:3",
    ];

    const keywordsToSearch =
      typeLabel === "Style" ? styleKeywords : ratioKeywords;
    let triggerBtn = null;

    // Search for exact match first
    for (const kw of keywordsToSearch) {
      const kwEsc = kw.replace(/'/g, "\\'");
      const xpath = `//*[(local-name()='button' or @role='button') and normalize-space(text())='${kwEsc}']`;
      const nodes = document.evaluate(
        xpath,
        document,
        null,
        XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,
        null,
      );
      for (let i = 0; i < nodes.snapshotLength; i++) {
        const n = nodes.snapshotItem(i);
        if (n.getBoundingClientRect().height > 0) {
          triggerBtn = n;
          break;
        }
      }
      if (triggerBtn) break;
    }

    // Fallback: search for partial match if exact match fails
    if (!triggerBtn) {
      for (const kw of keywordsToSearch) {
        const kwEsc = kw.replace(/'/g, "\\'");
        const xpath = `//*[(local-name()='button' or @role='button') and contains(normalize-space(), '${kwEsc}')]`;
        const nodes = document.evaluate(
          xpath,
          document,
          null,
          XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,
          null,
        );
        for (let i = 0; i < nodes.snapshotLength; i++) {
          const n = nodes.snapshotItem(i);
          if (n.getBoundingClientRect().height > 0) {
            triggerBtn = n;
            break;
          }
        }
        if (triggerBtn) break;
      }
    }

    // Click the trigger button if found
    if (triggerBtn) {
      triggerBtn.scrollIntoView({
        behavior: "smooth",
        block: "center",
        inline: "center",
      });
      await delay(500);

      const rect = triggerBtn.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) {
        // Background Tab Fallback
        triggerBtn.click();
      } else {
        const cx = Math.round(rect.left + rect.width / 2);
        const cy = Math.round(rect.top + rect.height / 2);
        await new Promise((r) =>
          chrome.runtime.sendMessage({ action: "CDP_CLICK", x: cx, y: cy }, r),
        );
      }

      await delay(1200); // Give the popover grid time to animate and open

      // Re-evaluate target button after menu opens
      targetButton = findTargetOption();
      isTargetVisible =
        targetButton && targetButton.getBoundingClientRect().height > 0;
    } else {
      console.warn(
        `[Canva Automation] ⚠️ Could not find the main trigger button to open the ${typeLabel} menu.`,
      );
    }
  }

  // 2. CHECK IF TARGET EXISTS IN DOM
  if (!targetButton) {
    console.warn(
      `[Canva Automation] ⚠️ Option '${optionText}' not found on screen. Proceeding with current settings.`,
    );
    return;
  }

  // 3. CHECK IF ALREADY ACTIVE (aria-pressed)
  if (targetButton.getAttribute("aria-pressed") === "true") {
    console.log(
      `[Canva Automation] ${typeLabel} '${optionText}' is already active. Skipping click.`,
    );
    return;
  }

  // 4. SCROLL AND CLICK TARGET OPTION
  console.log(`[Canva Automation] Selecting ${typeLabel}: '${optionText}'...`);
  targetButton.scrollIntoView({
    behavior: "smooth",
    block: "center",
    inline: "center",
  });
  await delay(700);

  const targetRect = targetButton.getBoundingClientRect();

  if (targetRect.width === 0 || targetRect.height === 0) {
    // Background Tab Fallback
    console.log(
      "[Canva Automation] Tab is in background. Using native DOM click for ",
      optionText,
    );
    targetButton.click();
  } else {
    // Active Tab CDP Click
    const clickX = Math.round(targetRect.left + targetRect.width / 2);
    const clickY = Math.round(targetRect.top + targetRect.height / 2);
    const response = await new Promise((resolve) => {
      chrome.runtime.sendMessage(
        { action: "CDP_CLICK", x: clickX, y: clickY },
        resolve,
      );
    });

    // Fallback if CDP fails
    if (!response || response.success === false) {
      console.warn(
        `[Canva Automation] � � CDP click failed, attempting native DOM click.`,
      );
      targetButton.click();
    }
  }

  await delay(1000); // Stabilize UI before proceeding
}
/**
 * Starts the main bulk automation loop, running sequentially without page reloads.
 */
async function startMainLoop() {
  console.log("[Canva Automation] Starting main automation loop...");
  sendStatusUpdate("Starting automation...");

  // Initialize Session Statistics
  sessionStats = {
    successCount: 0,
    downloadCount: 0,
    totalCooldowns: 0,
    startTime: Date.now(),
  };
  const storedStats = await chrome.storage.local.get(["sessionStats"]);
  if (storedStats.sessionStats) {
    sessionStats = storedStats.sessionStats;
  } else {
    await chrome.storage.local.set({ sessionStats });
  }

  // Check for last processed prompt index
  const lastIndexResult = await chrome.storage.local.get([
    "lastProcessedPromptIndex",
  ]);
  let startIndex = 0;
  if (lastIndexResult.lastProcessedPromptIndex !== undefined) {
    startIndex = lastIndexResult.lastProcessedPromptIndex;
    console.log(`[Canva Automation] Resuming from prompt index: ${startIndex}`);
  }

  // Natively await storage here. Any pre-flight crash falls to the outer catch block.
  const result = await chrome.storage.local.get([
    "prompts",
    "aspectRatio",
    "imageStyle",
    "downloadCount",
  ]);

  if (!window.location.href.includes("dream-lab")) {
    throw new Error("URL_MISMATCH");
  }

  let prompts = result.prompts || [];
  sessionStats.totalPrompts = prompts.length;
  sessionStats.startTime = Date.now();
  const aspectRatio = result.aspectRatio;
  const imageStyle = result.imageStyle;
  const downloadCountSetting = result.downloadCount || "4";

  if (prompts.length === 0) {
    throw new Error("No prompts found in storage.");
  }

  // Mark status as active automation
  await chrome.storage.local.set({ isAutomating: true });

  // Explicitly attach the debugger before starting the loop
  await new Promise((resolve) =>
    chrome.runtime.sendMessage({ action: "ATTACH_DEBUGGER" }, resolve),
  );

  try {
    // 🌟 INITIAL STARTUP GATEKEEPER 🌟
    // Check if Canva is ALREADY in a cooldown state the moment the user clicks RUN.
    let startupCooldown = getScreenCooldownMs();

    if (startupCooldown > 0) {
      startupCooldown += 5000; // Add 5-second safety buffer
      console.warn(
        `[Canva Automation] 🛑 Startup paused. Pre-existing cooldown detected: ${startupCooldown}ms.`,
      );

      // Stamp the existing warning so it doesn't get double-counted later
      tagGhostCooldowns();

      const targetEndTime = Date.now() + startupCooldown;

      while (Date.now() < targetEndTime) {
        // Allow user to click STOP even while waiting at startup
        if (!isRunning) {
          console.log(
            "[Canva Automation] Automation aborted by user during startup cooldown.",
          );
          return;
        }

        const remainingSecs = Math.ceil((targetEndTime - Date.now()) / 1000);

        // Update the UI panel to inform the user why it's not typing yet
        chrome.runtime.sendMessage({
          action: "STATUS_UPDATE",
          status: `Startup Paused (Limit Active): ${formatTime(remainingSecs)}`,
        });

        await delay(1000);
      }

      // Re-stamp in case React refreshed the page while we were sleeping
      tagGhostCooldowns();

      console.log(
        "[Canva Automation] Startup cooldown cleared. Proceeding to main generation loop...",
      );
      chrome.runtime.sendMessage({
        action: "STATUS_UPDATE",
        status: `Resuming automation...`,
      });
    }

    let isConfigured = false;

    // 🌟 MAIN GENERATION LOOP 🌟
    while (prompts.length > 0 && isRunning) {
      // 1. Pause Gate
      let isPaused = (await chrome.storage.local.get(["isPaused"])).isPaused;
      while (isPaused) {
        if (!isRunning) return; // Allow STOP while paused
        chrome.runtime.sendMessage({
          action: "STATUS_UPDATE",
          status: `⏸ Bot Paused by User...`,
        });
        await delay(1500);
        isPaused = (await chrome.storage.local.get(["isPaused"])).isPaused;
      }

      if (await checkIfStopped()) {
        console.log("[Canva Automation] Loop stopped by user request.");
        sendStatusUpdate("Automation stopped by user.");
        await new Promise((resolve) =>
          chrome.runtime.sendMessage({ action: "DETACH_DEBUGGER" }, resolve),
        );
        return;
      }

      // Check Batch Auto-Stop Limit
      const limits = await chrome.storage.local.get([
        "batchLimit",
        "sessionDownloadCount",
      ]);
      if (
        limits.batchLimit > 0 &&
        (limits.sessionDownloadCount || 0) >= limits.batchLimit
      ) {
        console.log(
          "[Canva Automation] 🛑 Batch Auto-Stop limit reached safely. Stopping loop.",
        );
        sendStatusUpdate("Batch target reached! Stopping...");

        // Trigger audio alert if enabled
        const audioCfg = await chrome.storage.local.get(["playSounds"]);
        if (audioCfg.playSounds !== false) {
          chrome.runtime.sendMessage({ action: "PLAY_COMPLETION_SOUND" });
        }

        // Cleanup: detach debugger and mark as stopped
        await chrome.storage.local.set({ isAutomating: false, step: "IDLE" });
        await new Promise((resolve) =>
          chrome.runtime.sendMessage({ action: "DETACH_DEBUGGER" }, resolve),
        );
        return;
      }

      let currentPrompt = prompts[0];

      // Removed premature prompt saving to avoid rename race condition.

      try {
        await logToTerminal(
          `[Canva Automation] Processing prompt: "${currentPrompt}"`,
        );

        // WARN-1 FIX: Send current progress indicator back to Side Panel UI with standardized action key
        chrome.runtime.sendMessage({
          action: "PROGRESS_UPDATE",
          progress: `${prompts.length} prompts remaining`,
        });
        sendStatusUpdate("Configuring settings...");

        // --- PRE-FLIGHT COOLDOWN CHECK (WITH DOM TAGGING) ---
        let preFlightCooldown = getScreenCooldownMs();

        if (preFlightCooldown > 0) {
          sessionStats.totalCooldowns++;
          await chrome.storage.local.set({ sessionStats });
          preFlightCooldown += 5000; // 5s safety buffer
          console.warn(
            `[Canva Automation] Serving pre-flight cooldown of ${preFlightCooldown}ms...`,
          );

          // Stamp before sleeping
          tagGhostCooldowns();

          // 🌟 ABSOLUTE TIME TRACKING TO BEAT CHROME THROTTLING
          const targetEndTime = Date.now() + preFlightCooldown;

          while (Date.now() < targetEndTime) {
            if (!isRunning) throw new Error("USER_STOPPED");

            const remainingMs = targetEndTime - Date.now();
            const remainingSecs = Math.ceil(remainingMs / 1000);

            chrome.runtime.sendMessage({
              action: "STATUS_UPDATE",
              status: `Limit active: ${formatTime(remainingSecs)} remaining`,
            });

            // Even if Chrome throttles this 1s delay to 10s when the tab is hidden,
            // the Date.now() calculation above will instantly catch up.
            await delay(1000);
          }

          // 🌟 RE-STAMP UPON WAKING UP (In case React wiped the tags on window focus)
          tagGhostCooldowns();

          sendStatusUpdate("Cooldown complete. Resuming prompt injection...");
        }
        // ---------------------------------

        // Action 1 (Configure & Inject):
        // 1. Configure dropdown settings (Aspect Ratio and Image Style only)
        if (!isConfigured) {
          const settings = await chrome.storage.local.get([
            "imageStyle",
            "aspectRatio",
          ]);

          // Check and set Style dynamically
          if (settings.imageStyle === "Random") {
            if (!isRunning) throw new Error("USER_STOPPED");
            sendStatusUpdate(`Setting Style: Random`);
            const styleKeywords = [
              "Smart",
              "Cinematic Concept",
              "Creative",
              "Bokeh",
              "Macro",
              "Illustration",
              "3D Render",
              "Cinematic",
              "Fashion",
              "Minimalist",
              "Moody",
              "Portrait",
              "Sketch - Color",
              "Stock Photo",
              "Ray Traced",
              "Vibrant",
              "Pop Art",
              "Vector",
            ];
            const randomStyle =
              styleKeywords[Math.floor(Math.random() * styleKeywords.length)];
            await safeSelectCanvaConfiguration("Style", randomStyle);
          } else if (settings.imageStyle) {
            if (!isRunning) throw new Error("USER_STOPPED");
            sendStatusUpdate(`Setting Style: ${settings.imageStyle}`);
            await safeSelectCanvaConfiguration("Style", settings.imageStyle);
          }

          // Check and set Ratio dynamically
          if (settings.aspectRatio === "Random") {
            if (!isRunning) throw new Error("USER_STOPPED");
            sendStatusUpdate(`Setting Aspect Ratio: Random`);
            const ratioKeywords = [
              "1:1",
              "16:9",
              "9:16",
              "4:3",
              "3:4",
              "3:2",
              "2:3",
            ];
            const randomRatio =
              ratioKeywords[Math.floor(Math.random() * ratioKeywords.length)];
            await safeSelectCanvaConfiguration("Aspect Ratio", randomRatio);
          } else if (settings.aspectRatio) {
            if (!isRunning) throw new Error("USER_STOPPED");
            sendStatusUpdate(`Setting Aspect Ratio: ${settings.aspectRatio}`);
            await safeSelectCanvaConfiguration(
              "Aspect Ratio",
              settings.aspectRatio,
            );
          }
          isConfigured = true;
        }

        // 2. Find prompt input, clear it, inject text, and strictly verify
        if (!isRunning) throw new Error("USER_STOPPED");
        const textarea = await waitForElement(
          CANVA_SELECTORS.PROMPT_TEXTAREA,
          false,
          15000,
        );
        sendStatusUpdate("Typing prompt...");

        // Focus the textarea, clear it natively, then type via CDP (Human or Instant mode)
        await safeCdpClick(textarea, "prompt textarea");
        await delay(200);
        try {
          textarea.value = "";
          textarea.dispatchEvent(new Event("input", { bubbles: true }));
        } catch (error) {
          console.error(
            `[Canva Automation] 🛑 Failed to clear prompt textarea:`,
            error,
          );
          chrome.runtime.sendMessage({ action: "EMERGENCY_CLEANUP" });
          throw new Error(`Clear interaction failed for prompt textarea`);
        }

        // Fetch the typing mode preference from storage
        const modeConfig = await chrome.storage.local.get(["typingMode"]);

        if (modeConfig.typingMode === "instant") {
          await logToTerminal(
            `[Canva Automation] Injecting prompt instantly (Paste mode)...`,
            true,
          );

          // Execute instant CDP typing
          const typeResponse = await new Promise((resolve) => {
            chrome.runtime.sendMessage(
              { action: "CDP_TYPE", text: currentPrompt },
              resolve,
            );
          });

          if (!typeResponse || typeResponse.success === false) {
            throw new Error(
              typeResponse?.error ||
                chrome.runtime.lastError?.message ||
                "CDP connection lost during instant typing",
            );
          }
        } else {
          // Default to realistic human typing
          await safeCdpTypeHuman(currentPrompt, "prompt textarea");
        }

        // Apply custom safety delay configuration dynamically
        const config = await chrome.storage.local.get(["safetyDelay"]);
        const dynamicDelay = (config.safetyDelay || 0) * 1000;
        await delay(500 + dynamicDelay);

        if (!isRunning) throw new Error("USER_STOPPED");

        // Dispatch standard React events to force state update
        textarea.dispatchEvent(new Event("input", { bubbles: true }));
        textarea.dispatchEvent(new Event("change", { bubbles: true }));

        await delay(1000); // Give React time to process the input

        // Soft verification: Check textContent or just rely on the Generate button becoming active
        let currentValue = textarea.value || textarea.textContent || "";
        if (!currentValue.includes(currentPrompt.substring(0, 5))) {
          console.warn(
            `[Canva Automation] ⚠️ Soft mismatch detected. Value might be masked by React. Proceeding anyway...`,
          );
        }

        // The real source of truth will be whether the "Generate" button is clickable in the next step.

        // 3. Prepare initial variables
        let pendingCooldownMs = 0; // Tracks if we need to sleep AFTER downloading the successful generation

        // 4. Unified Submit & Polling State Machine (Phantom-Success & Stale-DOM Immune)
        let submissionSuccessful = false;

        while (!submissionSuccessful) {
          if (!isRunning) throw new Error("USER_STOPPED");

          let initialButtonCount = 0;
          try {
            const btns = document.querySelectorAll(
              CANVA_SELECTORS.DOWNLOAD_BUTTON,
            );
            if (btns && btns.length > 0) {
              // Ensure we only count visible buttons
              initialButtonCount = Array.from(btns).filter(
                (btn) => btn.offsetParent !== null,
              ).length;
            }
          } catch (e) {
            console.warn(
              "[Canva Automation] Could not query initial download buttons:",
              e,
            );
            initialButtonCount = 0;
          }

          if (initialButtonCount === 0) {
            console.log(
              `[Canva Automation] Baseline button count: 0 (No visible buttons found with selector: ${CANVA_SELECTORS.DOWNLOAD_BUTTON})`,
            );
          } else {
            console.log(
              `[Canva Automation] Baseline button count: ${initialButtonCount}`,
            );
          }

          const submitBtn = await waitForElement(
            CANVA_SELECTORS.SUBMIT_BUTTON,
            false,
            10000,
          );
          await logToTerminal(
            "[Canva Automation] Clicking submit button...",
            true,
          );
          sendStatusUpdate("Generating images...");
          await safeCdpClick(submitBtn, "submit button");

          // Catch immediate rate limit toast
          await delay(1500);

          // 1. Check for FATAL Monthly Limit or Upgrade Pop-up first
          const monthlyLimitWarning = document.evaluate(
            CANVA_SELECTORS.MONTHLY_LIMIT_WARNING,
            document,
            null,
            XPathResult.FIRST_ORDERED_NODE_TYPE,
            null,
          ).singleNodeValue;

          if (monthlyLimitWarning) {
            console.error(
              `[Canva Automation] 🛑 FATAL: Monthly limit or Upgrade pop-up detected.`,
            );
            throw new Error("MONTHLY_LIMIT_REACHED");
          }

          let detectedCooldownMs = getScreenCooldownMs();
          if (detectedCooldownMs > 0) {
            detectedCooldownMs += 5000; // +5s buffer
            console.warn(
              `[Canva Automation] ⏳ Rate limit text detected: Time mapped to ${detectedCooldownMs}ms`,
            );
            // Dismiss toast if present
            const gotItBtn = document.evaluate(
              "//button[.//span[text()='Got it']]",
              document,
              null,
              XPathResult.FIRST_ORDERED_NODE_TYPE,
              null,
            ).singleNodeValue;
            if (gotItBtn) {
              try {
                await safeCdpClick(gotItBtn, "rate limit toast dismiss button");
              } catch (e) {}
            }
          }

          // Polling loop checking every 1000ms until the button count strictly increases
          let currentBtnCount = initialButtonCount;
          let pollAttempts = 0;
          const maxPollAttempts = 90; // 90 seconds timeout for image generation
          let imagesGenerated = false;

          while (pollAttempts <= maxPollAttempts) {
            if (!isRunning) throw new Error("USER_STOPPED");
            await delay(1000);

            // Short-Circuit for content policy violations (NSFW/Filter block)
            // FIXED: Scoped to strictly look inside toast/alert containers to prevent matching the "Privacy Policy" footer.
            const policyWarning = document.evaluate(
              "//div[@role='alert' or @role='status']//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'policy') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'unsafe')]",
              document,
              null,
              XPathResult.FIRST_ORDERED_NODE_TYPE,
              null,
            ).singleNodeValue;

            if (policyWarning) {
              console.error(
                "[Canva Automation] 🛑 Content Policy Violation detected.",
              );
              throw new Error("POLICY_VIOLATION");
            }

            // Dynamic Stale DOM tracker: if React unmounts old off-screen images, lower baseline
            let currentActualCount = currentBtnCount;
            try {
              const currentBtns = document.querySelectorAll(
                CANVA_SELECTORS.DOWNLOAD_BUTTON,
              );
              if (currentBtns && currentBtns.length > 0) {
                // Ensure we only count visible buttons
                currentActualCount = Array.from(currentBtns).filter(
                  (btn) => btn.offsetParent !== null,
                ).length;
              } else {
                currentActualCount = 0;
              }
            } catch (e) {
              currentActualCount = currentBtnCount;
            }
            if (
              currentActualCount < currentBtnCount &&
              currentActualCount <= initialButtonCount
            ) {
              console.log(
                `[Canva Automation] Stale DOM detected! Baseline dropped from ${initialButtonCount} to ${currentActualCount}`,
              );
              initialButtonCount = currentActualCount;
            }
            currentBtnCount = currentActualCount;

            pollAttempts++;
            console.log(
              `[Canva Automation] Polling for new download buttons (attempt ${pollAttempts}). Current count: ${currentBtnCount}, Initial count: ${initialButtonCount}`,
            );

            if (currentBtnCount > initialButtonCount) {
              imagesGenerated = true;
              break;
            }
          }

          if (imagesGenerated) {
            await logToTerminal(
              "[Canva Automation] Images successfully generated!",
            );
            submissionSuccessful = true;
            if (detectedCooldownMs > 0) {
              sessionStats.totalCooldowns++;
              await chrome.storage.local.set({ sessionStats });
              console.log(
                `[Canva Automation] Phantom Success detected. Queuing cooldown of ${detectedCooldownMs}ms for AFTER download.`,
              );
              pendingCooldownMs = detectedCooldownMs;
            }
          } else {
            if (detectedCooldownMs > 0) {
              sessionStats.totalCooldowns++;
              await chrome.storage.local.set({ sessionStats });
              console.log(
                "[Canva Automation] True rate limit hit (no images generated). Serving cooldown before retry...",
              );
              sendStatusUpdate(
                `Rate limit! Resting for ${Math.ceil(detectedCooldownMs / 1000)} seconds...`,
              );

              // Stamp before sleeping
              tagGhostCooldowns();

              // 🌟 ABSOLUTE TIME TRACKING TO BEAT CHROME THROTTLING
              const targetEndTime = Date.now() + detectedCooldownMs;

              while (Date.now() < targetEndTime) {
                if (!isRunning) throw new Error("USER_STOPPED");

                const remainingMs = targetEndTime - Date.now();
                const remainingSecs = Math.ceil(remainingMs / 1000);

                chrome.runtime.sendMessage({
                  action: "STATUS_UPDATE",
                  status: `Limit cooldown: ${formatTime(remainingSecs)} remaining`,
                });

                await delay(1000);
              }

              // 🌟 RE-STAMP UPON WAKING UP
              tagGhostCooldowns();

              console.log(
                "[Canva Automation] Dynamic cooldown complete. Clearing text field and retyping prompt...",
              );
              sendStatusUpdate("Cooldown done. Retyping prompt...");

              // Retype prompt logic with human animation
              const retryTextarea = await waitForElement(
                CANVA_SELECTORS.PROMPT_TEXTAREA,
                false,
                5000,
              );
              if (retryTextarea) {
                await safeCdpClick(retryTextarea, "retry prompt textarea");
                await delay(300);
                try {
                  retryTextarea.value = "";
                  retryTextarea.dispatchEvent(
                    new Event("input", { bubbles: true }),
                  );
                } catch (error) {
                  console.error(
                    `[Canva Automation] 🛑 Failed to clear retry prompt textarea:`,
                    error,
                  );
                  chrome.runtime.sendMessage({ action: "EMERGENCY_CLEANUP" });
                  throw new Error(
                    `Clear interaction failed for retry prompt textarea`,
                  );
                }
                await delay(300);
                await safeCdpTypeHuman(currentPrompt, "retry prompt textarea");
                await delay(500);
              }
            } else {
              throw new Error(
                "Action 2 Failed: Timeout waiting for new generated images, and no rate limit detected.",
              );
            }
          }
        }

        // 2. CRITICAL VISUAL RENDER DELAY: 5000ms to allow Canva to fully paint the high-res image assets
        if (!isRunning) throw new Error("USER_STOPPED");
        console.log(
          "[Canva Automation] New images detected! Awaiting 5s paint delay...",
        );
        sendStatusUpdate("Assets detected. Loading high-res images...");
        await delay(5000);

        // 3. Query buttons again and slice the newest batch from the top
        if (!isRunning) throw new Error("USER_STOPPED");

        let allBtns = document.querySelectorAll(
          CANVA_SELECTORS.DOWNLOAD_BUTTON,
        );
        if (!allBtns || allBtns.length === 0) {
          console.error(
            "[Canva Automation] Download button not found with selector:",
            CANVA_SELECTORS.DOWNLOAD_BUTTON,
          );
          allBtns = [];
        }
        let newestButtons = Array.from(allBtns).slice(0, 4);
        let targetCount = 4;

        if (downloadCountSetting === "Random") {
          targetCount = Math.floor(Math.random() * 4) + 1;
          newestButtons.sort(() => Math.random() - 0.5);
          console.log(
            `[Canva Automation] Random mode chosen. Shuffled list and resolved target count: ${targetCount}`,
          );
        } else {
          targetCount = parseInt(downloadCountSetting, 10);
          if (isNaN(targetCount) || targetCount < 1) {
            targetCount = 4;
          }
          console.log(
            `[Canva Automation] Target download count: ${targetCount}`,
          );
        }

        const buttonsToDownload = newestButtons.slice(0, targetCount);

        // CRITICAL 3 FIX: Set the exact prompt for the background downloader right before clicking download
        // CRITICAL 3 FIX: Set the exact prompt for the background downloader right before clicking download
        await chrome.storage.local.set({ downloadingPrompt: currentPrompt });

        // 4. Download click loop - Re-query DOM setiap iterasi
        if (targetCount > 0) {
          for (let i = 0; i < targetCount; i++) {
            // FRESH QUERY setiap kali untuk menghindari React DOM re-render
            const activeBtnsRaw = document.querySelectorAll(
              CANVA_SELECTORS.DOWNLOAD_BUTTON,
            );
            const activeBtns = Array.from(activeBtnsRaw).map(
              (el) => el.closest("button") || el,
            );
            const targetButton = activeBtns[i];

            if (targetButton && typeof targetButton.click === "function") {
              console.log(
                "[Canva Automation] Downloading image " +
                  (i + 1) +
                  "/" +
                  targetCount,
              );
              sendStatusUpdate(
                "Downloading image " + (i + 1) + " of " + targetCount + "...",
              );
              try {
                targetButton.click();
                sessionStats.downloadCount++;
                const sanitized = sanitizeStats(sessionStats);
                await chrome.storage.local.set({ sessionStats: sanitized });
                chrome.runtime.sendMessage({
                  action: "UPDATE_STATS",
                  stats: sanitized,
                });
                await chrome.storage.local.set({
                  sessionDownloadCount: sessionStats.downloadCount,
                });
                // Gunakan delayWithFallback agar loop tetap lanjut meskipun worker mati
                await delayWithFallback(1500, 3000);
              } catch (clickErr) {
                console.error(
                  "[Canva Automation] Failed to download image " + (i + 1),
                  clickErr,
                );
                continue;
              }
            } else {
              console.warn(
                "[Canva Automation] Button at index " +
                  i +
                  " is missing, skipping.",
              );
            }
          }
          console.log(
            "[Canva Automation] Download batch completed successfully.",
          );
        }

        // 1. Pause Gate
        while (isPausedGlobal) {
          if (!isRunning) return; // Allow STOP while paused
          chrome.runtime.sendMessage({
            action: "STATUS_UPDATE",
            status: `⏸ Bot Paused by User...`,
          });
          await delay(1500);
        }

        if (await checkIfStopped()) {
          console.log("[Canva Automation] Loop stopped by user request.");
          sendStatusUpdate("Automation stopped by user.");
          await new Promise((resolve) =>
            chrome.runtime.sendMessage({ action: "DETACH_DEBUGGER" }, resolve),
          );
          return;
        }

        // Check Batch Auto-Stop Limit
        const limits = await chrome.storage.local.get(["sessionDownloadCount"]);
        if (
          batchLimitGlobal > 0 &&
          (limits.sessionDownloadCount || 0) >= batchLimitGlobal
        ) {
          console.log(
            "[Canva Automation] 🛑 Batch Auto-Stop limit reached safely. Stopping loop.",
          );
          sendStatusUpdate("Batch target reached! Stopping...");

          // Trigger audio alert if enabled
          const audioCfg = await chrome.storage.local.get(["playSounds"]);
          if (audioCfg.playSounds !== false) {
            chrome.runtime.sendMessage({ action: "PLAY_COMPLETION_SOUND" });
          }

          // Cleanup: detach debugger and mark as stopped
          await chrome.storage.local.set({ isAutomating: false, step: "IDLE" });
          await new Promise((resolve) =>
            chrome.runtime.sendMessage({ action: "DETACH_DEBUGGER" }, resolve),
          );
          return;
        }

        // 5. Mandatory save delay
        if (!isRunning) throw new Error("USER_STOPPED");
        console.log(
          "[Canva Automation] Waiting 6 seconds for download files to save to disk...",
        );
        sendStatusUpdate("Saving downloaded images...");
        await delay(6000);

        if (pendingCooldownMs > 0) {
          console.log(
            `[Canva Automation] Serving pending Phantom Success cooldown of ${pendingCooldownMs}ms...`,
          );
          sendStatusUpdate(
            `Phantom Success cooldown: ${Math.ceil(pendingCooldownMs / 1000)} seconds...`,
          );

          // Stamp before sleeping
          tagGhostCooldowns();

          // 🌟 ABSOLUTE TIME TRACKING TO BEAT CHROME THROTTLING
          const targetEndTime = Date.now() + pendingCooldownMs;

          while (Date.now() < targetEndTime) {
            if (!isRunning) throw new Error("USER_STOPPED");

            const remainingMs = targetEndTime - Date.now();
            const remainingSecs = Math.ceil(remainingMs / 1000);

            chrome.runtime.sendMessage({
              action: "STATUS_UPDATE",
              status: `Next prompt in: ${formatTime(remainingSecs)}`,
            });

            await delay(1000);
          }

          // 🌟 RE-STAMP UPON WAKING UP
          tagGhostCooldowns();
        }

        // Save current prompt index after successful processing
        await chrome.storage.local.set({
          lastProcessedPromptIndex: startIndex + 1,
        });

        // Destructive Queue Shift: Remove processed prompt and update storage/UI
        prompts.shift();
        sessionStats.successCount++;
        await chrome.storage.local.set({ sessionStats });
        await chrome.storage.local.set({ prompts: prompts });
        chrome.runtime.sendMessage({
          action: "UPDATE_TEXTAREA",
          remainingPrompts: prompts,
        });
      } catch (error) {
        if (
          error.message === "USER_STOPPED" ||
          error.message === "MONTHLY_LIMIT_REACHED"
        ) {
          console.log(
            `[Canva Automation] Process halted. Reason: ${error.message}`,
          );
          if (error.message === "MONTHLY_LIMIT_REACHED") {
            handleAutomationError(error);
          } else {
            chrome.storage.local.set(
              { isAutomating: false, step: "IDLE" },
              () => {
                sendStatusUpdate("Automation stopped by user.");
              },
            );
          }
          await new Promise((resolve) =>
            chrome.runtime.sendMessage({ action: "DETACH_DEBUGGER" }, resolve),
          );
          return; // Break the main loop and exit completely
        }

        // WARN-02 FIX: Handle policy violation gracefully without page reload
        if (error.message === "POLICY_VIOLATION") {
          console.warn(
            "[Canva Automation] Policy violation. Skipping prompt without reload.",
          );
          chrome.runtime.sendMessage({
            action: "PROMPT_FAILED",
            failedPrompt: currentPrompt,
          });
          prompts.shift();
          await chrome.storage.local.set({ prompts: prompts });
          chrome.runtime.sendMessage({
            action: "UPDATE_TEXTAREA",
            remainingPrompts: prompts,
          });
          sendStatusUpdate("Policy violation. Skipping to next prompt...");
          await delay(2000); // Breathe before next iteration
          continue; // Immediately jump to next loop iteration smoothly
        }

        console.warn(
          "[Canva Automation] Prompt failed/skipped:",
          currentPrompt,
          error,
        );

        // Send the failed prompt to the panel
        chrome.runtime.sendMessage({
          action: "PROMPT_FAILED",
          failedPrompt: currentPrompt,
        });

        // Remove the failed prompt from the queue
        prompts.shift();

        // Update chrome.storage.local with the new prompts array
        await chrome.storage.local.set({ prompts: prompts });

        // Send the "UPDATE_TEXTAREA" message to refresh the main input UI
        chrome.runtime.sendMessage({
          action: "UPDATE_TEXTAREA",
          remainingPrompts: prompts,
        });

        // Send a status update
        sendStatusUpdate("Prompt failed. Recovering and moving to next...");

        // KRITIS-2 FIX: Graceful offline handler before moving on
        if (!navigator.onLine) {
          console.error(
            "[Canva Automation] 🛑 NETWORK_OFFLINE detected. Pausing until reconnected...",
          );
          sendStatusUpdate("Offline. Waiting for internet connection...");
          await new Promise((resolve) => {
            window.addEventListener("online", resolve, { once: true });
          });
          console.log("[Canva Automation] Reconnected! Resuming operation.");
          sendStatusUpdate("Reconnected. Resuming...");
        }

        await delay(2000); // Brief pause before retrying the next prompt
        continue;
      }
    }

    // Finished loop cleanly without cancellation
    if (isRunning && prompts.length === 0) {
      chrome.storage.local.set({ isAutomating: false, step: "IDLE" }, () => {
        console.log(
          "[Canva Automation] Reset state to IDLE. Bulk automation complete.",
        );

        const totalDurationMin = Math.round(
          (Date.now() - sessionStats.startTime) / 1000 / 60,
        );
        console.log(
          `[Canva Automation] =======================================`,
        );
        console.log(`[Canva Automation] 📊 BATCH GENERATION SUMMARY:`);
        console.log(
          `[Canva Automation] - Total Time: ${totalDurationMin} minutes`,
        );
        console.log(
          `[Canva Automation] - Prompts Processed: ${sessionStats.successCount}`,
        );
        console.log(
          `[Canva Automation] - Images Downloaded: ${sessionStats.downloadCount} assets`,
        );
        console.log(
          `[Canva Automation] - Cooldowns Encountered: ${sessionStats.totalCooldowns} times`,
        );
        console.log(
          `[Canva Automation] =======================================`,
        );

        sendStatusUpdate("Bulk generation complete!");
      });
    }
    await new Promise((resolve) =>
      chrome.runtime.sendMessage({ action: "DETACH_DEBUGGER" }, resolve),
    );
  } catch (loopErr) {
    if (loopErr.message === "USER_STOPPED") {
      console.log("[Canva Automation] Loop caught USER_STOPPED outer signal.");
      chrome.storage.local.set({ isAutomating: false, step: "IDLE" }, () => {
        sendStatusUpdate("Automation stopped by user.");
      });
    } else {
      handleAutomationError(loopErr);
    }
    await new Promise((resolve) =>
      chrome.runtime.sendMessage({ action: "DETACH_DEBUGGER" }, resolve),
    );
  }
}

// ==========================================
// Initialization Block
// ==========================================

// Add listener for debugger detachment notification
chrome.runtime.onMessage.addListener((message) => {
  if (message.action === "DEBUGGER_DETACHED") {
    console.warn("[Canva Automation] Debugger detached. Connection lost!");
    sendStatusUpdate("Debugger disconnected - Please refresh page");
  }
});

function teardown() {
  // Guard: HANYA jalankan jika benar-benar halaman ditutup/di-reload, bukan karena event lain
  if (document.visibilityState === 'visible' && !window.closed) {
    console.warn("[Canva Automation] teardown() dipanggil tapi halaman masih aktif - diabaikan.");
    return;
  }
  console.log("[Canva Automation] Teardown initiated. Terminating resources.");
  if (typeof delayWorker !== "undefined" && delayWorker) {
    try {
      delayWorker.terminate();
    } catch (e) {
      console.warn("[Canva Automation] Worker sudah di-terminate.");
    }
    globalThis.delayWorker = null;
  }
}
window.addEventListener("beforeunload", teardown);

// 1. Listen for START_AUTOMATION and STOP_AUTOMATION messages from popup
chrome.runtime.onMessage.addListener(async (message, sender, sendResponse) => {
  if (message) {
    if (message.action === "START_AUTOMATION") {
      console.log("[Canva Automation] START_AUTOMATION trigger received.");

      // Reset lastProcessedPromptIndex to 0 when starting fresh automation
      await chrome.storage.local.set({ lastProcessedPromptIndex: 0 });

      // KRITIS-4 FIX: Graceful loop teardown on rapid Stop/Start toggling
      if (isLoopActive) {
        console.log(
          "[Canva Automation] Previous loop is still winding down. Waiting for cleanup...",
        );
        chrome.runtime.sendMessage({
          action: "STATUS_UPDATE",
          status: `Cleaning up previous session...`,
        });

        // Wait up to 5 seconds for the previous loop to finish
        let retries = 0;
        while (isLoopActive && retries < 10) {
          await new Promise((r) => setTimeout(r, 500));
          retries++;
        }

        if (isLoopActive) {
          chrome.runtime.sendMessage({
            action: "STATUS_UPDATE",
            status: `Error: Could not start. Please refresh page.`,
          });
          sendResponse({
            success: false,
            error: "Previous loop stuck. Please refresh page.",
          });
          return true; // Abort if it's permanently stuck
        }
      }

      if (window.location.href.includes("dream-lab")) {
        isRunning = true;
        isLoopActive = true;
        startMainLoop()
          .catch((err) => handleAutomationError(err))
          .finally(() => {
            isLoopActive = false;
          });
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
    console.log(
      "[Canva Automation] Not on dream-lab page. Exiting initialization.",
    );
    return;
  }
  try {
    const result = await chrome.storage.local.get(["isAutomating"]);
    console.log("[Canva Automation] Local state retrieved on load:", result);
    if (result && result.isAutomating === true) {
      // KRITIS-2 FIX: Guard against concurrent loop on resume
      if (isLoopActive) {
        console.warn(
          "[Canva Automation] Loop already active on resume. Skipping.",
        );
        return;
      }

      // STABILITY BUFFER: Prevent instant crash during hard-refresh state flux
      console.log(
        "[Canva Automation] Auto-resume triggered. Waiting 4 seconds for React SPA stability...",
      );
      await new Promise((resolve) => setTimeout(resolve, 4000));

      // Re-verify that user didn't hit stop during the 4-second buffer
      const doubleCheck = await chrome.storage.local.get(["isAutomating"]);
      if (!doubleCheck || doubleCheck.isAutomating !== true) {
        console.log(
          "[Canva Automation] User stopped during stability buffer. Aborting resume.",
        );
        return;
      }

      isRunning = true;
      isLoopActive = true;
      startMainLoop()
        .catch((err) => handleAutomationError(err))
        .finally(() => {
          isLoopActive = false;
        });
    }
  } catch (err) {
    handleAutomationError(err);
  }
})();

// ==========================================
// Console Interceptor for Side Panel UI
// ==========================================
const originalConsoleLog = console.log;
const originalConsoleWarn = console.warn;
const originalConsoleError = console.error;

let isLogging = false;

function broadcastLog(level, ...args) {
  // Prevent recursive logging
  if (isLogging) return;
  isLogging = true;

  try {
    const msg = args
      .map((a) => (typeof a === "object" ? JSON.stringify(a) : String(a)))
      .join(" ");
    chrome.runtime
      .sendMessage({ action: "CONSOLE_LOG", level: level, message: msg })
      .catch((err) => {
        // Silent fail - do NOT call console methods here
      });
  } catch (e) {
    // Silent fail - do NOT call console methods here
  } finally {
    isLogging = false;
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

// Global unhandled rejection handler
window.addEventListener("unhandledrejection", function (event) {
  console.error(
    "[Canva Automation] Unhandled Promise rejection:",
    event.reason,
  );
  try {
    chrome.runtime
      .sendMessage({
        action: "STATUS_UPDATE",
        status: `Error: ${event.reason?.message || "Unknown promise error"}`,
      })
      .catch(() => {});
  } catch (_) {}
  event.preventDefault();
});

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

function getStyleOptionsFromDOM() {
  const styleOptions = [];
  const popover =
    document.querySelector('[role="dialog"]') ||
    document.querySelector('[role="menu"]');
  if (popover) {
    const buttons = popover.querySelectorAll('[role="button"]');
    buttons.forEach(function (btn) {
      const label = btn.getAttribute("aria-label") || btn.textContent.trim();
      if (label && label.length > 0 && label !== "Style") {
        styleOptions.push(label);
      }
    });
  }
  if (styleOptions.length === 0) {
    return [
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
  }
  return styleOptions;
}

function getRatioOptionsFromDOM() {
  const ratioOptions = [];
  const popover =
    document.querySelector('[role="dialog"]') ||
    document.querySelector('[role="menu"]');
  if (popover) {
    const buttons = popover.querySelectorAll('[role="button"]');
    buttons.forEach(function (btn) {
      const label = btn.getAttribute("aria-label") || btn.textContent.trim();
      if (
        label &&
        (label.includes(":") ||
          label === "1:1" ||
          label === "16:9" ||
          label === "9:16" ||
          label === "4:3" ||
          label === "3:4" ||
          label === "3:2" ||
          label === "2:3")
      ) {
        ratioOptions.push(label);
      }
    });
  }
  if (ratioOptions.length === 0) {
    return ["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3"];
  }
  return ratioOptions;
}

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
// Interval for heartbeat (if used)
let heartbeatInterval = null;
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
let delayWorker = null;

function initWorker() {
  if (delayWorker) {
    try {
      delayWorker.terminate();
    } catch (e) {
      // Abaikan error saat terminate
    }
  }
  const workerBlob = new Blob(
    [
      `self.onmessage = function(e) { setTimeout(() => postMessage(e.data.id), e.data.time); }`,
    ],
    { type: "application/javascript" },
  );

  const workerUrl = URL.createObjectURL(workerBlob);
  delayWorker = new Worker(workerUrl);
  URL.revokeObjectURL(workerUrl); // CRITICAL FIX: Frees the memory immediately
  console.log("[Canva Automation] Web Worker initialized successfully.");
}

// Inisialisasi awal
initWorker();

/**
 * delay(ms): Promise-based timeout hybrid using Web Worker thread & fallback.
 * Web Workers are immune to Chrome's background tab throttling.
 * Jika worker gagal/mati, akan otomatis restart dan menggunakan setTimeout sementara.
 * @param {number} ms
 * @returns {Promise<void>}
 */
function delay(ms) {
  if (ms >= 1000) console.log(`[Canva Automation] Waiting for ${ms}ms...`);
  return new Promise((resolve) => {
    let resolved = false;

    // Waktu tunggu maksimum sebelum fallback (hanya 1 detik ekstra dari target)
    const fallbackMs = ms + 1000;

    // Timer fallback murni (setTimeout)
    const fallbackTimer = setTimeout(() => {
      if (!resolved) {
        resolved = true;
        console.warn(
          `[Canva Automation] ⚠️ Delay fallback triggered after ${fallbackMs}ms (Worker mati atau lambat). Merestart worker...`,
        );
        initWorker(); // Restart worker agar panggilan selanjutnya tidak lambat
        resolve();
      }
    }, fallbackMs);

    try {
      if (!delayWorker) throw new Error("Worker is null");

      const id = Math.random().toString();
      const handler = (e) => {
        if (e.data === id) {
          delayWorker.removeEventListener("message", handler);
          if (!resolved) {
            resolved = true;
            clearTimeout(fallbackTimer); // Berhasil, batalkan fallback timer
            resolve();
          }
        }
      };

      delayWorker.addEventListener("message", handler);
      delayWorker.postMessage({ id: id, time: ms });
    } catch (e) {
      // Terjadi error instan (misal worker mati, memory corrupt), langsung gunakan native
      console.warn(
        `[Canva Automation] ⚠️ Worker error instan: ${e.message}. Menggunakan setTimeout native dan merestart worker...`,
      );
      initWorker(); // Re-init sekarang juga

      // Karena kita tahu postMessage gagal, jadwalkan resolve menggunakan setTimeout sesuai 'ms'
      // tanpa harus menunggu 'fallbackMs' yang lebih lama
      setTimeout(() => {
        if (!resolved) {
          resolved = true;
          clearTimeout(fallbackTimer);
          resolve();
        }
      }, ms);
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

  let pageText = "";

  const alertElements = document.querySelectorAll(
    '[role="alert"], [role="status"]',
  );
  alertElements.forEach(function (el) {
    pageText += el.innerText + " ";
  });

  if (!pageText.trim()) {
    const statusContainers = document.querySelectorAll(
      '[class*="status"], [class*="alert"], [class*="warning"]',
    );
    statusContainers.forEach(function (el) {
      pageText += el.innerText + " ";
    });
  }

  if (!pageText.trim()) {
    pageText = document.body.innerText;
  }

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
  console.log(
    `[Canva Automation] Typing prompt with human animation (chunk size: 4)...`,
  );
  const CHUNK_SIZE = 4;
  for (let i = 0; i < text.length; i += CHUNK_SIZE) {
    const chunk = text.substring(i, i + CHUNK_SIZE);
    const response = await new Promise((resolve) => {
      chrome.runtime.sendMessage({ action: "CDP_TYPE", text: chunk }, resolve);
    });
    if (!response || response.success === false) {
      throw new Error(
        response?.error ||
          chrome.runtime.lastError?.message ||
          "CDP connection lost during typing",
      );
    }
    const chunkDelay = Math.floor(Math.random() * 80) + 40;
    await delay(chunkDelay);
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
    const styleKeywords = getStyleOptionsFromDOM();
    // Add default trigger keywords for Style just in case DOM is not ready
    if (!styleKeywords.includes("Style")) styleKeywords.unshift("Style");
    if (!styleKeywords.includes("None")) styleKeywords.unshift("None");

    const ratioKeywords = getRatioOptionsFromDOM();
    // Add default trigger keywords for Ratio just in case DOM is not ready
    if (!ratioKeywords.includes("Ratio")) ratioKeywords.unshift("Ratio");

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
        `[Canva Automation]   CDP click failed, attempting native DOM click.`,
      );
      targetButton.click();
    }
  }

  await delay(1000); // Stabilize UI before proceeding
}

/**
 * Starts the main bulk automation loop, running sequentially without page reloads.
 */
async function configureStyleAndRatio(imageStyle, aspectRatio) {
  await safeSelectCanvaConfiguration("Style", imageStyle);
  await safeSelectCanvaConfiguration("Ratio", aspectRatio);
}

async function injectPrompt(currentPrompt) {
  const textarea = await waitForElement(CANVA_SELECTORS.PROMPT_TEXTAREA);
  if (!textarea) throw new Error("Textarea not found");
  textarea.value = "";
  textarea.dispatchEvent(new Event("input", { bubbles: true }));
  await safeCdpTypeHuman(currentPrompt, "prompt input");
}

async function submitAndWaitForImages() {
  const generateBtn = await waitForElement(CANVA_SELECTORS.SUBMIT_BUTTON);
  if (!generateBtn) throw new Error("Generate button not found");

  await safeCdpClick(generateBtn, "generate button");

  console.log("[Canva Automation] Menunggu indikator loading muncul...");
  chrome.runtime.sendMessage({
    action: "STATUS_UPDATE",
    status: "Waiting for generation to start...",
  });

  const checkLoadingIndicators = () => {
    const progressBar = document.querySelector('[role="progressbar"]');
    const generatingText = document.evaluate(
      "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'generating') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'creating')]",
      document,
      null,
      XPathResult.FIRST_ORDERED_NODE_TYPE,
      null,
    ).singleNodeValue;
    const currentGenBtn = document.querySelector(CANVA_SELECTORS.SUBMIT_BUTTON);
    const isBtnDisabled = currentGenBtn
      ? currentGenBtn.disabled ||
        currentGenBtn.getAttribute("aria-disabled") === "true"
      : false;

    return !!(progressBar || generatingText || isBtnDisabled);
  };

  // 1. Smart Wait: Tunggu indikator loading MUNCUL (maksimal 10 detik)
  let loadingStarted = false;
  let startElapsed = 0;
  while (!loadingStarted && startElapsed < 10000) {
    if (!isRunning) throw new Error("USER_STOPPED");
    if (checkLoadingIndicators()) {
      loadingStarted = true;
      break;
    }
    await delay(500); // Polling cepat
    startElapsed += 500;
  }

  if (!loadingStarted) {
    console.warn(
      "[Canva Automation] Indikator loading tidak terdeteksi setelah 10 detik. Mencoba melanjutkan pengecekan render...",
    );
  } else {
    console.log(
      "[Canva Automation] Indikator loading terdeteksi. Menunggu render selesai...",
    );
    chrome.runtime.sendMessage({
      action: "STATUS_UPDATE",
      status: "Generating images... (Waiting for render)",
    });
  }

  // 2. Smart Wait: Tunggu indikator loading HILANG (maksimal 60 detik)
  let isGenerating = true;
  let renderElapsed = 0;
  const timeout = 60000;

  while (isGenerating && renderElapsed < timeout) {
    if (!isRunning) throw new Error("USER_STOPPED");

    if (!checkLoadingIndicators()) {
      isGenerating = false;
    } else {
      await delay(1000); // Polling setiap 1 detik
      renderElapsed += 1000;
    }
  }

  if (renderElapsed >= timeout) {
    console.warn(
      "[Canva Automation] Timeout 60 detik terlampaui saat menunggu render gambar. Mencoba melanjutkan...",
    );
  } else {
    console.log("[Canva Automation] Render gambar selesai!");
  }

  // Ekstra delay 1 detik untuk kestabilan DOM sebelum beralih fungsi
  await delay(1000);
}

async function handleDownload(countSetting = "4") {
  console.log(
    "[Canva Automation] Memulai proses unduhan. Target: " +
      countSetting +
      " gambar.",
  );

  let targetCount = 4;
  if (countSetting === "Random") {
    targetCount = Math.floor(Math.random() * 4) + 1;
  } else {
    targetCount = parseInt(countSetting, 10) || 4;
  }

  await delay(2000);

  // Ambil semua tombol download
  let allDownloadButtons = document.querySelectorAll(
    CANVA_SELECTORS.DOWNLOAD_BUTTON,
  );

  if (!allDownloadButtons || allDownloadButtons.length === 0) {
    throw new Error("Download buttons not found.");
  }

  // AMBIL HANYA 4 TOMBOL TERAKHIR (Tombol yang baru muncul saja)
  let latestButtons = Array.from(allDownloadButtons).slice(-4);

  // Batasi sesuai setting count
  let buttonsToClick = latestButtons.slice(0, targetCount);

  console.log(
    "[Canva Automation] Total tombol di layar: " +
      allDownloadButtons.length +
      ". Mengambil " +
      buttonsToClick.length +
      " tombol terbaru.",
  );

  for (let i = 0; i < buttonsToClick.length; i++) {
    const btn = buttonsToClick[i];
    console.log("[Canva Automation] Mengunduh gambar ke-" + (i + 1) + "...");

    await safeCdpClick(btn, "download button " + (i + 1));

    await delay(2500);
  }
}

async function handleCooldown(cooldownMs, isStartup = false) {
  if (!isStartup) sessionStats.totalCooldowns++;
  cooldownMs += 5000;
  console.warn(
    `[Canva Automation] 🛑 ${isStartup ? "Startup paused. Pre-existing cooldown" : "Cooldown"} detected: ${cooldownMs}ms. Waiting...`,
  );
  tagGhostCooldowns();
  const targetEndTime = Date.now() + cooldownMs;
  while (Date.now() < targetEndTime) {
    if (!isRunning) {
      if (isStartup) {
        console.log(
          "[Canva Automation] Automation aborted by user during startup cooldown.",
        );
        return false;
      }
      throw new Error("USER_STOPPED");
    }
    const remainingSecs = Math.ceil((targetEndTime - Date.now()) / 1000);
    chrome.runtime.sendMessage({
      action: "STATUS_UPDATE",
      status: `${isStartup ? "Startup Paused (Limit Active)" : "Cooldown"}: ${formatTime(remainingSecs)}`,
    });
    await delay(1000);
  }
  tagGhostCooldowns();
  console.log(
    `[Canva Automation] ${isStartup ? "Startup cooldown cleared. Proceeding to main generation loop..." : "Cooldown cleared. Resuming..."}`,
  );
  chrome.runtime.sendMessage({
    action: "STATUS_UPDATE",
    status: `Resuming ${isStartup ? "automation" : "after cooldown"}...`,
  });
  return true;
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
  try {
    const result = await chrome.storage.local.get([
      "prompts",
      "aspectRatio",
      "imageStyle",
      "downloadCount",
    ]);

    if (!window.location.href.includes("dream-lab")) {
      throw new Error("URL_MISMATCH");
    }

    let prompts = (result.prompts || []).map((p) => sanitizeInput(p));
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
    await Promise.race([
      new Promise((resolve) =>
        chrome.runtime.sendMessage({ action: "ATTACH_DEBUGGER" }, resolve),
      ),
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error("ATTACH_DEBUGGER_TIMEOUT")), 10000),
      ),
    ]);

    try {
      // 🌟 INITIAL STARTUP GATEKEEPER 🌟
      let startupCooldown = getScreenCooldownMs();
      if (startupCooldown > 0) {
        const proceeded = await handleCooldown(startupCooldown, true);
        if (!proceeded) return;
      }

      let isConfigured = false;

      // 🌟 MAIN GENERATION LOOP 🌟
      while (prompts.length > 0 && isRunning) {
        const storageSnapshot = await chrome.storage.local.get([
          "isPaused",
          "batchLimit",
          "isAutomating",
        ]);

        if (storageSnapshot.isAutomating === false) {
          throw new Error("USER_STOPPED");
        }

        if (storageSnapshot.isPaused === true) {
          console.log("[Canva Automation] Automation paused by user.");
          await delay(1000);
          continue;
        }

        const currentPrompt = prompts.shift();
        const currentIndex =
          startIndex + (sessionStats.totalPrompts - prompts.length);

        chrome.runtime.sendMessage({
          action: "STATUS_UPDATE",
          status: `Processing prompt ${currentIndex + 1}/${sessionStats.totalPrompts}: ${currentPrompt}`,
        });

        if (!isConfigured) {
          await configureStyleAndRatio(imageStyle, aspectRatio);
          isConfigured = true;
        }

        await injectPrompt(currentPrompt);
        await submitAndWaitForImages();

        let cooldownMs = getScreenCooldownMs();
        if (cooldownMs > 0) {
          await handleCooldown(cooldownMs, false);
        }

        // Handle download with retry logic
        let downloadSuccess = false;
        let retryCount = 0;
        const maxRetries = 3;

        while (!downloadSuccess && retryCount < maxRetries) {
          try {
            await handleDownload(downloadCountSetting);
            downloadSuccess = true;
          } catch (error) {
            console.error(
              `[Canva Automation] Download attempt ${retryCount + 1} failed:`,
              error.message,
            );
            retryCount++;

            if (retryCount < maxRetries) {
              console.log(
                `[Canva Automation] Attempting recovery (${retryCount}/${maxRetries})...`,
              );
              // Refresh the page to reset state
              window.location.reload();
              // Wait for page to reload
              await new Promise((resolve) => setTimeout(resolve, 5000));
              // Reconfigure style and ratio after refresh
              await configureStyleAndRatio(imageStyle, aspectRatio);
              // Re-inject the current prompt
              await injectPrompt(currentPrompt);
              // Re-submit the prompt
              await submitAndWaitForImages();
            }
          }
        }

        if (!downloadSuccess) {
          console.error(
            "[Canva Automation] Failed to download images after maximum retries. Skipping to next prompt...",
          );
          // Still increment success counter since we processed the prompt
          sessionStats.successCount++;
        } else {
          // Increment download counter only if download was successful
          sessionStats.downloadCount++;
        }

        // Update session stats in storage
        await chrome.storage.local.set({
          sessionStats: sanitizeStats(sessionStats),
          lastProcessedPromptIndex: currentIndex,
        });

        // Check if we need to stop after this download
        if (
          batchLimitGlobal > 0 &&
          sessionStats.downloadCount >= batchLimitGlobal
        ) {
          console.log(
            `[Canva Automation] Batch limit reached (${batchLimitGlobal}). Stopping.`,
          );
          isRunning = false;
          chrome.storage.local.set({ isAutomating: false }, () => {
            sendStatusUpdate("Batch limit reached. Automation stopped.");
          });
          break;
        }

        // Small delay between iterations
        await delay(2000);
      }

      // Final cleanup
      if (isRunning) {
        console.log("[Canva Automation] All prompts processed successfully.");
        chrome.storage.local.set({ isAutomating: false }, () => {
          sendStatusUpdate("All prompts processed successfully!");
        });
      }
    } catch (err) {
      handleAutomationError(err);
      throw err; // Re-throw to ensure outer catch block handles it
    }
  } catch (err) {
    handleAutomationError(err);
    throw err;
  }
}

// ==========================================
// Message Listener: Menerima perintah dari Panel
// ==========================================
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "PING") {
    sendResponse({ status: "READY" });
    return true;
  }

  if (request.action === "START_AUTOMATION") {
    if (!isLoopActive) {
      console.log("[Canva Automation] Menerima perintah START dari panel.");
      isRunning = true;
      isLoopActive = true;

      startMainLoop()
        .catch((err) => {
          console.error("[Canva Automation] Main loop terhenti:", err);
        })
        .finally(() => {
          isLoopActive = false;
          isRunning = false;
        });

      sendResponse({ success: true });
    } else {
      console.warn(
        "[Canva Automation] Perintah START diabaikan, loop sudah aktif.",
      );
      sendResponse({ success: false, error: "ALREADY_RUNNING" });
    }
    return true;
  }

  if (request.action === "STOP_AUTOMATION") {
    console.log("[Canva Automation] Menerima perintah STOP dari panel.");
    isRunning = false;
    isLoopActive = false;
    // Beri tahu background untuk detach debugger (opsional tapi disarankan)
    chrome.runtime.sendMessage({ action: "EMERGENCY_CLEANUP" }).catch(() => {});
    sendResponse({ success: true });
    return true;
  }
});

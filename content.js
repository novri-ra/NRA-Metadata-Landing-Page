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

async function waitForVisualRender(selector, timeoutMs = 8000) {
  return new Promise((resolve) => {
    let resolved = false;

    const fallbackTimer = setTimeout(() => {
      if (!resolved) {
        resolved = true;
        observer.disconnect();
        resolve();
      }
    }, timeoutMs);

    const observer = new MutationObserver((mutations) => {
      if (resolved) return;

      for (const mutation of mutations) {
        if (mutation.type === "childList" || mutation.type === "attributes") {
          const elements = document.querySelectorAll(selector);
          const visible = Array.from(elements).filter(
            (el) => el.offsetParent !== null,
          );
          if (visible.length > 0) {
            resolved = true;
            clearTimeout(fallbackTimer);
            observer.disconnect();
            resolve();
            return;
          }
        }
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["style", "class", "src"],
    });
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
        await new Promise((resolve) =>
          chrome.runtime.sendMessage({ action: "DETACH_DEBUGGER" }, resolve),
        );
        chrome.storage.local.set({ isAutomating: false, step: "IDLE" });
        return;
      }

      // 2. Get current prompt and update UI
      const currentPrompt = prompts[0];
      const currentIndex = startIndex + prompts.length;
      const remainingCount = prompts.length - 1;
      chrome.runtime.sendMessage({
        action: "PROGRESS_UPDATE",
        progress: `Processing: ${currentIndex}/${sessionStats.totalPrompts} (${remainingCount} remaining)`,
      });

      // 3. Configure Canva settings if not already configured
      if (!isConfigured) {
        console.log("[Canva Automation] Configuring Canva settings...");
        await safeSelectCanvaConfiguration("Style", imageStyle);
        await safeSelectCanvaConfiguration("Ratio", aspectRatio);
        isConfigured = true;
        await delay(1000);
      }

      // 4. Find the prompt input field
      let promptInput;
      try {
        promptInput = await waitForElement(CANVA_SELECTORS.PROMPT_INPUT);
      } catch (err) {
        console.error(
          "[Canva Automation] 🛑 Could not find prompt input field. Aborting.",
          err,
        );
        throw new Error("PROMPT_INPUT_NOT_FOUND");
      }

      // 5. Type the prompt with human-like animation
      await safeCdpTypeHuman(currentPrompt, "prompt input");

      // 6. Click the Generate button
      let generateBtn;
      try {
        generateBtn = await waitForElement(CANVA_SELECTORS.GENERATE_BUTTON);
      } catch (err) {
        console.error(
          "[Canva Automation] 🛑 Could not find Generate button. Aborting.",
          err,
        );
        throw new Error("GENERATE_BUTTON_NOT_FOUND");
      }

      await safeCdpClick(generateBtn, "Generate button");

      // 7. Wait for visual render of the generated image
      await waitForVisualRender(CANVA_SELECTORS.GENERATED_IMAGE);

      // 8. Check for cooldown
      let cooldownMs = getScreenCooldownMs();
      if (cooldownMs > 0) {
        sessionStats.totalCooldowns++;
        cooldownMs += 5000; // Add 5-second safety buffer
        console.warn(
          `[Canva Automation] 🛑 Cooldown detected: ${cooldownMs}ms. Waiting...`,
        );

        // Stamp the warning so it doesn't get double-counted later
        tagGhostCooldowns();

        const targetEndTime = Date.now() + cooldownMs;

        while (Date.now() < targetEndTime) {
          if (!isRunning) {
            console.log(
              "[Canva Automation] Automation aborted by user during cooldown.",
            );
            return;
          }

          const remainingSecs = Math.ceil((targetEndTime - Date.now()) / 1000);
          chrome.runtime.sendMessage({
            action: "STATUS_UPDATE",
            status: `Cooldown Active: ${formatTime(remainingSecs)}`,
          });

          await delay(1000);
        }

        // Re-stamp in case React refreshed the page while we were sleeping
        tagGhostCooldowns();

        console.log("[Canva Automation] Cooldown cleared. Resuming...");
        chrome.runtime.sendMessage({
          action: "STATUS_UPDATE",
          status: `Resuming after cooldown...`,
        });
      }

      // 9. Check for monthly limit reached
      const monthlyLimitReached = document.evaluate(
        "//*[contains(text(), 'You’ve reached your monthly limit')]",
        document,
        null,
        XPathResult.FIRST_ORDERED_NODE_TYPE,
        null,
      ).singleNodeValue;

      if (monthlyLimitReached) {
        throw new Error("MONTHLY_LIMIT_REACHED");
      }

      // 10. Find and click the newest download button
      let newestButtons = Array.from(
        document.querySelectorAll(CANVA_SELECTORS.DOWNLOAD_BUTTON),
      ).map((el) => el.closest("button") || el);

      if (newestButtons.length === 0) {
        console.warn(
          "[Canva Automation] ⚠️ No download buttons found. Retrying...",
        );
        await delay(2000);
        newestButtons = Array.from(
          document.querySelectorAll(CANVA_SELECTORS.DOWNLOAD_BUTTON),
        ).map((el) => el.closest("button") || el);
      }

      if (newestButtons.length === 0) {
        console.error(
          "[Canva Automation] 🛑 No download buttons found after retry. Skipping this prompt.",
        );
        chrome.runtime.sendMessage({
          action: "PROMPT_FAILED",
          failedPrompt: currentPrompt,
        });
        prompts.shift();
        continue;
      }

      // 11. Determine how many images to download
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
        console.log(`[Canva Automation] Target download count: ${targetCount}`);
      }

      const buttonsToDownload = newestButtons.slice(0, targetCount);

      // CRITICAL 3 FIX: Set the exact prompt for the background downloader right before clicking download
      await chrome.storage.local.set({ downloadingPrompt: currentPrompt });

      // 12. Download click loop - Re-query DOM setiap iterasi
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

          if (targetButton) {
            await safeCdpClick(targetButton, `download button #${i + 1}`);
            sessionStats.downloadCount++;
            await delay(1000); // Small delay between downloads
          } else {
            console.warn(
              `[Canva Automation] ⚠️ Download button #${i + 1} not found. Skipping.`,
            );
          }
        }
      }

      // 13. Update session stats and storage
      sessionStats.successCount++;
      await chrome.storage.local.set({
        sessionStats,
        lastProcessedPromptIndex: currentIndex,
      });

      // 14. Remove the processed prompt and update UI
      prompts.shift();
      await chrome.storage.local.set({ prompts });

      // 15. Update UI with remaining prompts
      chrome.runtime.sendMessage({
        action: "UPDATE_TEXTAREA",
        remainingPrompts: prompts,
      });

      // 16. Small delay between iterations
      await delay(1500);
    }

    // 17. Final cleanup and completion
    console.log("[Canva Automation] All prompts processed successfully!");
    chrome.runtime.sendMessage({
      action: "STATUS_UPDATE",
      status: "✅ All prompts processed!",
    });
    chrome.runtime.sendMessage({ action: "PLAY_COMPLETION_SOUND" });
    chrome.storage.local.set({ isAutomating: false, step: "IDLE" });
    await new Promise((resolve) =>
      chrome.runtime.sendMessage({ action: "DETACH_DEBUGGER" }, resolve),
    );
  } catch (err) {
    handleAutomationError(err);
    await new Promise((resolve) =>
      chrome.runtime.sendMessage({ action: "DETACH_DEBUGGER" }, resolve),
    );
  } finally {
    isLoopActive = false;
  }
}

// ==========================================
// MESSAGE LISTENER FOR PANEL COMMUNICATION
// ==========================================
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message) {
    if (message.action === "START_AUTOMATION") {
      if (isRunning) {
        console.warn("[Canva Automation] Automation already running.");
        sendResponse({ success: false, error: "Already running" });
        return;
      }

      if (!window.location.href.includes("dream-lab")) {
        console.error(
          "[Canva Automation] Not on Canva Dream Lab page. Aborting.",
        );
        sendResponse({
          success: false,
          error: "Extension is not currently on a canva.com/dream-lab page.",
        });
        return;
      }

      isRunning = true;
      console.log("[Canva Automation] START_AUTOMATION trigger received.");

      // Start the automation loop
      startMainLoop().catch((err) => {
        console.error("[Canva Automation] Automation failed:", err);
        isRunning = false;
        isLoopActive = false;
        chrome.storage.local.set({ isAutomating: false, step: "ERROR" });
        sendStatusUpdate("Error: " + (err.message || "Unknown error"));
      });

      sendResponse({ success: true });
    } else if (message.action === "STOP_AUTOMATION") {
      console.log("[Canva Automation] STOP_AUTOMATION trigger received.");
      isRunning = false;
      sendResponse({ success: true });
    } else if (message.action === "PING") {
      sendResponse({ status: "READY" });
    }
  }
});

// ==========================================
// SELECTORS FOR CANVA DREAM LAB
// ==========================================
const CANVA_SELECTORS = {
  PROMPT_INPUT: 'textarea[aria-label="Enter a prompt"]',
  GENERATE_BUTTON: 'button[data-testid="generate-button"]',
  DOWNLOAD_BUTTON: 'button[data-testid="download-button"]',
  GENERATED_IMAGE: 'img[alt="Generated image"]',
  ALERT_STATUS: 'div[data-testid="alert-status"]',
};

// ==========================================
// INITIALIZATION
// ==========================================
console.log("[Canva Auto Prompter] Content script loaded and ready.");

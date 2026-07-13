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
    "[NRA DreamLab] Unhandled Promise rejection:",
    event.reason,
  );
  try {
    chrome.runtime
      .sendMessage({
        action: "STATUS_UPDATE",
        status: `Error: ${event.reason?.message || "Unknown promise error"}`,
      })
      .catch(() => { });
  } catch (_) { }
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

// NRA DreamLab - Content Script targeting canva.com/dream-lab
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

async function smartWaitForElement(selector, timeoutMs = 15000) {
  return new Promise((resolve, reject) => {
    const existingElements = Array.from(document.querySelectorAll(selector)).filter(btn => btn.offsetParent !== null);
    if (existingElements.length > 0) {
      return resolve(existingElements);
    }

    let timer; // Deklarasi dinaikkan ke atas untuk mencegah ReferenceError

    const observer = new MutationObserver((mutations, obs) => {
      const elements = Array.from(document.querySelectorAll(selector)).filter(btn => btn.offsetParent !== null);
      if (elements.length > 0) {
        obs.disconnect();
        if (timer) clearTimeout(timer);
        resolve(elements);
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['class', 'style']
    });

    timer = setTimeout(() => {
      observer.disconnect();
      reject(new Error("Timeout: Elemen " + selector + " tidak muncul setelah " + timeoutMs + "ms"));
    }, timeoutMs);
  });
}
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
      failedCount: 0,
    };

  return {
    startTime: stats.startTime || Date.now(),
    successCount: isNaN(stats.successCount) ? 0 : Number(stats.successCount),
    downloadCount: isNaN(stats.downloadCount) ? 0 : Number(stats.downloadCount),
    totalCooldowns: isNaN(stats.totalCooldowns)
      ? 0
      : Number(stats.totalCooldowns),
    totalPrompts: isNaN(stats.totalPrompts) ? 0 : Number(stats.totalPrompts),
    failedCount: isNaN(stats.failedCount) ? 0 : Number(stats.failedCount),
  };
}

/**
 * Sends a status update message to the Side Panel/Popup.
 * @param {string} statusText
 */
function sendStatusUpdate(statusText) {
  console.log(`[NRA DreamLab] Status update: ${statusText}`);
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
  console.log("[NRA DreamLab] Web Worker initialized successfully.");
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
  if (ms >= 1000) console.log(`[NRA DreamLab] Waiting for ${ms}ms...`);
  return new Promise((resolve) => {
    let resolved = false;

    // Waktu tunggu maksimum sebelum fallback (hanya 1 detik ekstra dari target)
    const fallbackMs = ms + 1000;

    // Timer fallback murni (setTimeout)
    const fallbackTimer = setTimeout(() => {
      if (!resolved) {
        resolved = true;
        console.warn(
          `[NRA DreamLab] ⚠️ Delay fallback triggered after ${fallbackMs}ms (Worker mati atau lambat). Merestart worker...`,
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
        `[NRA DreamLab] ⚠️ Worker error instan: ${e.message}. Menggunakan setTimeout native dan merestart worker...`,
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
  } catch (e) { }
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
          "[NRA DreamLab] Server overload detected. Defaulting to 3 minutes cooldown.",
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
  isRunning = false;
  isLoopActive = false;

  // Logging error yang lebih detail
  const errMessage = (err && err.message) ? err.message : JSON.stringify(err);
  console.error("[NRA DreamLab] Loop broken due to:", errMessage);
  if (err && err.stack) console.error("[Stack Trace]:", err.stack);

  if (err && err.message === "USER_STOPPED") {
    console.log("[NRA DreamLab] Process stopped manually.");
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
      "[NRA DreamLab] Monthly AI limit reached. Stopping permanently.",
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

  const errMsg = errMessage || "Unknown error occurred.";
  chrome.storage.local.set({ isAutomating: false, step: "ERROR" }, () => {
    chrome.runtime.sendMessage({
      action: "STATUS_UPDATE",
      status: "Error: " + errMsg,
    });
  });
  chrome.runtime.sendMessage({ action: "RELEASE_AWAKE" }).catch(() => ({}));
}

async function safeCdpClick(element, context = "element") {
  try {
    await cdpClick(element);
  } catch (error) {
    console.error(`[NRA DreamLab] 🛑 Failed to click ${context}:`, error);
    chrome.runtime.sendMessage({ action: "EMERGENCY_CLEANUP" });
    throw new Error(`Click interaction failed for ${context}`); // Throw custom error instead of TypeError
  }
}

async function safeCdpTypeHuman(text, context = "input") {
  try {
    await cdpTypeHuman(text);
  } catch (error) {
    console.error(`[NRA DreamLab] 🛑 Failed to type in ${context}:`, error);
    chrome.runtime.sendMessage({ action: "EMERGENCY_CLEANUP" });
    throw new Error(`Type interaction failed for ${context}`); // Throw custom error instead of TypeError
  }
}
async function cdpClick(element) {
  // Proteksi tambahan: Pastikan elemen masih terhubung ke DOM
  if (!element.isConnected) {
    throw new Error("Element detached from DOM before click");
  }

  element.scrollIntoView({ behavior: "smooth", block: "center" });
  await delay(300);

  // Suntikkan event klik murni ke DOM (mengakali perlindungan React/Next.js)
  element.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true, view: window }));
  element.dispatchEvent(new MouseEvent("mouseup", { bubbles: true, cancelable: true, view: window }));
  element.click();
}

async function cdpTypeHuman(text) {
  const textarea = await waitForElement(CANVA_SELECTORS.PROMPT_TEXTAREA);
  if (!textarea) throw new Error("Textarea not found");

  const storage = await chrome.storage.local.get(["typingMode"]);
  const mode = storage.typingMode || "human";

  // Debugging untuk memastikan mode apa yang terbaca
  console.log(`[NRA DreamLab] Debugging - Current Typing Mode: ${mode}`);

  if (mode === "instant") {
    console.log(`[NRA DreamLab] Executing Instant Paste...`);

    // Pancing state aktif pada elemen
    textarea.focus();

    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
    nativeInputValueSetter.call(textarea, text);

    // Tambahkan cancelable: true agar event disimulasikan lebih realistis
    textarea.dispatchEvent(new Event("input", { bubbles: true, cancelable: true }));
    textarea.dispatchEvent(new Event("change", { bubbles: true, cancelable: true }));

    // Lepas fokus agar Canva menyadari bahwa input telah selesai
    textarea.blur();
  } else {
    console.log(`[NRA DreamLab] Executing Human Typing (200-250 BPM)...`);
    textarea.value = "";
    const typingDelay = 45; // Kecepatan optimal 200-250 BPM
    for (const char of text) {
      textarea.value += char;
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
      await delay(typingDelay);
    }
    textarea.dispatchEvent(new Event("change", { bubbles: true }));
  }
}

async function safeSelectCanvaConfiguration(typeLabel, optionText) {
  try {
    return await selectCanvaConfiguration(typeLabel, optionText);
  } catch (error) {
    console.error(
      `[NRA DreamLab] 🛑 Failed to configure ${typeLabel} with ${optionText}:`,
      error,
    );
    chrome.runtime.sendMessage({ action: "EMERGENCY_CLEANUP" });
    throw new Error(`Configuration interaction failed for ${typeLabel}`);
  }
}

async function selectCanvaConfiguration(label, value) {
  if (!value || value === "None" || value === "" || value === "Random") return true;

  console.info(`[NRA DreamLab] Memulai proses pemilihan: Menu '${label}' -> Opsi '${value}'`);

  // LANGKAH 1: Buka Menu Dropdown (seperti tombol "Style") jika diperlukan
  const buttons = Array.from(document.querySelectorAll('button'));
  const dropdownBtn = buttons.find(btn =>
    (btn.getAttribute('aria-label') && btn.getAttribute('aria-label').toLowerCase().includes(label.toLowerCase())) ||
    (btn.textContent && btn.textContent.toLowerCase().trim() === label.toLowerCase())
  );

  if (dropdownBtn) {
    const isExpanded = dropdownBtn.getAttribute('aria-expanded') === 'true';
    if (!isExpanded) {
      console.info(`[NRA DreamLab] Membuka dropdown menu '${label}'...`);
      dropdownBtn.click();
      await new Promise(r => setTimeout(r, 1200)); // Tunggu animasi menu terbuka
    } else {
      console.info(`[NRA DreamLab] Dropdown menu '${label}' sudah terbuka.`);
    }
  } else {
    console.info(`[NRA DreamLab] Tombol menu '${label}' tidak ditemukan (mungkin opsi langsung tampil di layar).`);
  }

  // LANGKAH 2: Cari dan klik opsi (Style / Aspect Ratio)
  for (let i = 0; i < 10; i++) {
    // Ambil elemen yang berperan sebagai opsi style (role="button") atau opsi ratio (role="option")
    const optionElements = Array.from(document.querySelectorAll('[role="button"], [role="option"]'));

    const targetOption = optionElements.find(el => {
      const ariaLabel = el.getAttribute('aria-label') || "";
      const text = el.textContent || "";
      // Cocokkan persis (case-insensitive) dengan aria-label ATAU teks
      return ariaLabel.toLowerCase() === value.toLowerCase() ||
        text.toLowerCase().trim() === value.toLowerCase();
    });

    if (targetOption) {
      // Hapus kondisi pembatas !isSelected agar bot tidak melewatkan (skip) klik akibat state history lama
      targetOption.click();
      console.info(`[NRA DreamLab] ✅ Pemaksaan klik dieksekusi pada opsi '${value}' untuk menu '${label}'.`);

      await new Promise(r => setTimeout(r, 800)); // Jeda stabilitas DOM
      return true;
    }
    await new Promise(r => setTimeout(r, 1000));
  }

  console.error(`[NRA DreamLab] GAGAL: Opsi '${value}' tidak ditemukan di layar.`);
  return false;
}

/**
 * Starts the main bulk automation loop, running sequentially without page reloads.
 */
async function configureStyleAndRatio(imageStyle, aspectRatio) {
  const styleOk = await safeSelectCanvaConfiguration("Style", imageStyle);
  if (styleOk === false) {
    console.error("[NRA DreamLab] Gagal memilih Style, tidak melanjutkan ke Ratio.");
    return false;
  }
  const ratioOk = await safeSelectCanvaConfiguration("Ratio", aspectRatio);
  if (ratioOk === false) {
    console.error("[NRA DreamLab] Gagal memilih Ratio.");
    return false;
  }
  return true;
}

async function injectPrompt(currentPrompt) {
  const textarea = await waitForElement(CANVA_SELECTORS.PROMPT_TEXTAREA);
  if (!textarea) throw new Error("Textarea not found");
  textarea.value = "";
  textarea.dispatchEvent(new Event("input", { bubbles: true }));
  await safeCdpTypeHuman(currentPrompt, "prompt input");
}

async function submitAndWaitForImages() {
  console.info("[NRA DreamLab] Mencari tombol Generate...");
  const generateBtn = await waitForElement(CANVA_SELECTORS.SUBMIT_BUTTON, false, 15000);
  if (!generateBtn) throw new Error("Generate button not found");

  console.info("[NRA DreamLab] Menekan tombol Generate...");
  await safeCdpClick(generateBtn, "generate button");

  return new Promise((resolve, reject) => {
    console.info("[NRA DreamLab] MutationObserver aktif: Menunggu gambar selesai di-render...");
    
    // Cek instan: jika tombol download baru sudah ada sebelum observer dipasang
    if (document.querySelector(CANVA_SELECTORS.DOWNLOAD_BUTTON)) {
      return resolve();
    }

    const observer = new MutationObserver((mutations, obs) => {
      // Logika Benar: Resolve ketika DOWNLOAD_BUTTON MUN-CUL di layar!
      if (document.querySelector(CANVA_SELECTORS.DOWNLOAD_BUTTON)) {
        obs.disconnect();
        clearTimeout(timeoutHatch);
        resolve();
      }
    });

    observer.observe(document.body, { childList: true, subtree: true });

    // Escape hatch: Beri batas maksimal 90 detik jika rendering macet
    const timeoutHatch = setTimeout(() => {
      observer.disconnect();
      reject(new Error("Timeout: Proses render Canva melampaui 90 detik atau selektor berubah."));
    }, 90000);
  });
}

async function handleDownload(countSetting = "4", currentPrompt = "") {
  console.info(`[NRA DreamLab] Memulai isolasi kontainer untuk prompt aktif: "${currentPrompt}"`);

  // 1. Ambil semua elemen section batch yang ada di halaman
  const sections = Array.from(document.querySelectorAll('section'));
  let targetContainer = null;

  if (currentPrompt) {
    const cleanActivePrompt = currentPrompt.trim().toLowerCase();
    
    // 2. Lakukan perulangan untuk mencari section yang membungkus teks prompt aktif
    for (const section of sections) {
      // Multi-fallback: Cari berdasarkan class Canva saat ini ATAU semua tag paragraf di dalam section jika class berubah
      const promptElements = section.querySelectorAll('p.aWBg0w, p[class*="6klkDA"], p[data-testid*="undefined"], p');
      let matchesPrompt = false;

      for (const p of promptElements) {
        const pText = (p.textContent || p.innerText || "").trim().toLowerCase();
        // Cek apakah teks di DOM mengandung atau sama dengan prompt yang sedang diproses bot
        if (pText === cleanActivePrompt || cleanActivePrompt.includes(pText) || pText.includes(cleanActivePrompt)) {
          matchesPrompt = true;
          break;
        }
      }

      if (matchesPrompt) {
        targetContainer = section;
        console.info("[NRA DreamLab] ✅ Sukses mengunci kontainer section berdasarkan kecocokan teks prompt!");
        break;
      }
    }
  }

  // Fallback 1: Jika pencocokan teks gagal (karena obfuscation), ambil section paling atas di dalam DOM
  if (!targetContainer && sections.length > 0) {
    console.warn("[NRA DreamLab] Pencocokan teks prompt tidak mendeteksi kontainer. Fallback mengambil section teratas di halaman...");
    targetContainer = sections[0]; 
  }

  // Fallback 2: Jika tidak ada section sama sekali
  if (!targetContainer) {
    targetContainer = document.body;
    console.warn("[NRA DreamLab] Fallback ultimate ke document body.");
  }

  let allDownloadButtons = [];
  try {
    // 3. Cari tombol download secara eksklusif HANYA di dalam targetContainer yang telah dikunci
    for (let attempt = 0; attempt < 5; attempt++) {
      const buttons = Array.from(targetContainer.querySelectorAll(CANVA_SELECTORS.DOWNLOAD_BUTTON))
                           .filter(btn => btn.offsetParent !== null); // Pastikan elemennya terlihat di layar
      
      if (buttons && buttons.length > 0) {
        allDownloadButtons = buttons;
        console.info(`[NRA DreamLab] Ditemukan ${buttons.length} tombol unduh di dalam kontainer prompt ini.`);
        break;
      }
      await delay(2000);
    }

    if (allDownloadButtons.length === 0) {
      throw new Error("Tombol download tidak ditemukan di dalam blok hasil render kontainer prompt aktif.");
    }
  } catch (error) {
    throw new Error("Gagal mengisolasi tombol unduh: " + error.message);
  }

  let targetCount = parseInt(countSetting, 10) || 4;
  let buttonsToClick = allDownloadButtons.slice(0, targetCount);
  console.log(`[NRA DreamLab] Mengunduh ${buttonsToClick.length} gambar eksklusif dari kontainer prompt aktif.`);

  for (let i = 0; i < buttonsToClick.length; i++) {
    const btn = buttonsToClick[i];
    
    // Validasi ulang: Pastikan elemen masih terhubung ke DOM sebelum berinteraksi
    if (btn && btn.isConnected) {
      try {
        // Paksa scroll visual agar tombol berada di tengah layar (mencegah terhalang layout)
        btn.scrollIntoView({ behavior: "instant", block: "center" });
        await delay(500); 
        
        await safeCdpClick(btn, `download button ${i + 1} dari kontainer prompt aktif`);
        await delay(3000); // Jeda anti-banned aman
        
        sessionStats.downloadCount++;
        chrome.storage.local.set({ sessionStats: sanitizeStats(sessionStats) });
        chrome.runtime.sendMessage({
          action: "UPDATE_STATS",
          stats: sanitizeStats(sessionStats)
        });
      } catch (clickError) {
        console.warn(`[NRA DreamLab] Percobaan klik tombol ${i + 1} meleset, mencoba fallback klik native...`);
        btn.click();
        await delay(3000);
      }
    } else {
      console.warn(`[NRA DreamLab] Tombol download ${i + 1} terlepas dari DOM sebelum diklik. Melewati...`);
    }
  }
}
async function handleCooldown(cooldownMs, isStartup = false) {
  console.log(`[DEBUG] Entering handleCooldown for ${cooldownMs}ms`);
  if (!isStartup) sessionStats.totalCooldowns++;
  cooldownMs += 5000;
  console.warn(
    `[NRA DreamLab] 🛑 ${isStartup ? "Startup paused. Pre-existing cooldown" : "Cooldown"} detected: ${cooldownMs}ms. Waiting...`,
  );
  tagGhostCooldowns();
  const targetEndTime = Date.now() + cooldownMs;
  while (Date.now() < targetEndTime) {
    if (!isRunning) {
      if (isStartup) {
        console.log(
          "[NRA DreamLab] Automation aborted by user during startup cooldown.",
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
    `[NRA DreamLab] ${isStartup ? "Startup cooldown cleared. Proceeding to main generation loop..." : "Cooldown cleared. Resuming..."}`,
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
  console.log("[NRA DreamLab] Starting main automation loop...");
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
    console.log(`[NRA DreamLab] Resuming from prompt index: ${startIndex}`);
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
    const limitRes = await chrome.storage.local.get(["batchLimit"]);
    batchLimitGlobal = parseInt(limitRes.batchLimit, 10) || 0;
    const downloadCountSetting = result.downloadCount || "4";

    if (prompts.length === 0) {
      throw new Error("No prompts found in storage.");
    }

    // Mark status as active automation
    await chrome.storage.local.set({ isAutomating: true });

    // Request Keep Awake to prevent system sleep during automation
    await chrome.runtime.sendMessage({ action: "KEEP_AWAKE" }).catch(() => ({}));

    try {
      // 🌟 INITIAL STARTUP GATEKEEPER 🌟
      const canProceed = await checkAndHandleStartupCooldown();
      if (!canProceed) return;

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
          console.log("[NRA DreamLab] Automation paused by user.");
          await delay(1000);
          continue;
        }

        // 1. Ambil prompt aktif
        const currentPrompt = prompts.shift();
        const currentIndex = startIndex + (sessionStats.totalPrompts - prompts.length);

        // 2. PRE-FLIGHT GATEKEEPER: Cek dan tahan bot jika ada cooldown aktif SEBELUM mulai mengetik
        let startupCooldown = getScreenCooldownMs();
        if (startupCooldown > 0) {
          console.warn(`[NRA DreamLab] Batasan limit aktif terdeteksi sebelum mulai mengetik! Menahan loop selama ${startupCooldown}ms`);
          await handleCooldown(startupCooldown, false);
        }

        chrome.runtime.sendMessage({
          action: "STATUS_UPDATE",
          status: `Processing prompt ${currentIndex + 1} of ${sessionStats.totalPrompts}...`,
        });

        // 3. Update prompt aktif ke storage untuk penamaan file background.js
        await chrome.storage.local.set({ downloadingPrompt: currentPrompt });

        // 4. Konfigurasi, Injeksi (Mengetik dengan kecepatan baru), dan Submit
        await prepareAndSubmitPrompt(
          currentPrompt,
          isConfigured,
          imageStyle,
          aspectRatio,
        );
        isConfigured = true;

        // 5. Download / Retry Loop
        let downloadSuccess = false;
        let retryCount = 0;
        const maxRetries = 3;

        while (!downloadSuccess && retryCount < maxRetries) {
          try {
            await handleDownload(downloadCountSetting, currentPrompt);
            downloadSuccess = true;
          } catch (error) {
            console.error(`[NRA DreamLab] Download attempt ${retryCount + 1} failed:`, error.message);
            retryCount++;
            if (retryCount < maxRetries) {
              window.location.reload();
              await new Promise((resolve) => setTimeout(resolve, 5000));
              await configureStyleAndRatio(imageStyle, aspectRatio);
              await injectPrompt(currentPrompt);
              await submitAndWaitForImages();
            }
          }
        }

        // 6. POST-FLIGHT CHECK: Cek kembali cooldown jika limit baru lahir pasca-submit
        let postCooldownMs = getScreenCooldownMs();
        if (postCooldownMs > 0) {
          console.warn(`[NRA DreamLab] Limit akun terdeteksi pasca-submit! Waktu tunggu: ${postCooldownMs}ms`);
          await handleCooldown(postCooldownMs, false);
        }

        // 7. Update status ke storage & panel
        if (!downloadSuccess) {
          chrome.runtime.sendMessage({
            action: "PROMPT_FAILED",
            failedPrompt: currentPrompt
          });
        }

        sessionStats.successCount++;
        await chrome.storage.local.set({
          prompts: prompts,
          sessionStats: sanitizeStats(sessionStats),
          lastProcessedPromptIndex: currentIndex,
        });

        chrome.runtime.sendMessage({
          action: "UPDATE_TEXTAREA",
          remainingPrompts: prompts
        });

        if (batchLimitGlobal > 0 && sessionStats.downloadCount >= batchLimitGlobal) {
          isRunning = false;
          chrome.storage.local.set({ isAutomating: false }, () => {
            sendStatusUpdate("Batch limit reached. Automation stopped.");
          });
          break;
        }

        await delay(2000);
      }

      // Final cleanup
      if (isRunning) {
        console.log("[NRA DreamLab] All prompts processed successfully.");
        chrome.storage.local.set({ isAutomating: false }, () => {
          sendStatusUpdate("All prompts processed successfully!");
        });
        chrome.runtime.sendMessage({ action: "RELEASE_AWAKE" }).catch(() => ({}));
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
// Helpher Functions Extracted from startMainLoop
// ==========================================
async function checkAndHandleStartupCooldown() {
  let startupCooldown = getScreenCooldownMs();
  if (startupCooldown > 0) {
    const proceeded = await handleCooldown(startupCooldown, true);
    return proceeded;
  }
  return true;
}

async function prepareAndSubmitPrompt(
  currentPrompt,
  isConfigured,
  imageStyle,
  aspectRatio,
) {
  if (!isConfigured) {
    await configureStyleAndRatio(imageStyle, aspectRatio);
  }
  await injectPrompt(currentPrompt);
  await submitAndWaitForImages();
}

async function executeDownloadBatchWithRetry(downloadCountSetting, maxRetries, currentPrompt, imageStyle, aspectRatio) {
  let downloadSuccess = false;
  let retryCount = 0;
  while (!downloadSuccess && retryCount < maxRetries) {
    try {
      await handleDownload(downloadCountSetting);
      downloadSuccess = true;
    } catch (error) {
      console.error("[Canva Automation] Download attempt " + (retryCount + 1) + " failed:", error.message);
      retryCount++;
      if (retryCount < maxRetries) {
        console.log("[Canva Automation] Attempting recovery...");
        await chrome.storage.local.set({ isRecovering: true });
        window.location.reload();
        return false;
      }
    }
  }
  return downloadSuccess;
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
      console.log("[NRA DreamLab] Menerima perintah START dari panel.");
      isRunning = true;
      isLoopActive = true;

      startMainLoop()
        .catch((err) => {
          console.error("[NRA DreamLab] Main loop terhenti:", err);
        })
        .finally(() => {
          isLoopActive = false;
          isRunning = false;
        });

      sendResponse({ success: true });
    } else {
      console.warn(
        "[NRA DreamLab] Perintah START diabaikan, loop sudah aktif.",
      );
      sendResponse({ success: false, error: "ALREADY_RUNNING" });
    }
    return true;
  }

  if (request.action === "STOP_AUTOMATION") {
    console.log("[NRA DreamLab] Menerima perintah STOP dari panel.");
    isRunning = false;
    isLoopActive = false;
    // Beri tahu background untuk release power
    chrome.runtime.sendMessage({ action: "RELEASE_AWAKE" }).catch(() => ({}));
    sendResponse({ success: true });
    return true;
  }
});

chrome.storage.local.get(['isAutomating', 'isRecovering'], (res) => {
  if (res.isAutomating === true && res.isRecovering === true) {
    console.log("[Canva Automation] Memulihkan sesi setelah reload...");
    chrome.storage.local.set({ isRecovering: false }, () => {
      setTimeout(() => {
        if (!isLoopActive) {
          isRunning = true;
          isLoopActive = true;
          startMainLoop().catch(err => console.error(err)).finally(() => {
            isLoopActive = false;
            isRunning = false;
          });
        }
      }, 3000);
    });
  }
});

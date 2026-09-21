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
    safeSendMessage({ action: "CONSOLE_LOG", level: level, message: msg });
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
  safeSendMessage({
    action: "STATUS_UPDATE",
    status: `Error: ${event.reason?.message || "Unknown promise error"}`,
  });
  event.preventDefault();
});

// NRA DreamLab - Content Script targeting canva.com/dream-lab
// Operates exclusively on https://www.canva.com/dream-lab

// ponytail: removed unused getStyleOptionsFromDOM and getRatioOptionsFromDOM

// Set up a local cache listener to drastically reduce storage I/O
// (globals isPausedGlobal/batchLimitGlobal/isAutomatingGlobal live in automation.js)
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "local") {
    if (changes.isPaused !== undefined) {
      isPausedGlobal = changes.isPaused.newValue === true;
    }
    if (changes.batchLimit !== undefined) {
      batchLimitGlobal = parseInt(changes.batchLimit.newValue, 10) || 0;
    }
    if (changes.isAutomating !== undefined) {
      isAutomatingGlobal = changes.isAutomating.newValue === true;
    }
  }
});

// Seed the variables immediately on script load
chrome.storage.local.get(["isPaused", "batchLimit", "isAutomating"], (res) => {
  if (res.isPaused !== undefined) isPausedGlobal = res.isPaused === true;
  if (res.batchLimit !== undefined)
    batchLimitGlobal = parseInt(res.batchLimit, 10) || 0;
  if (res.isAutomating !== undefined) isAutomatingGlobal = res.isAutomating === true;
});

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
          if (!err || err.message !== "USER_STOPPED") console.error("[NRA DreamLab] Main loop terhenti:", err);
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
    safeSendMessage({ action: "RELEASE_AWAKE" });
    sendResponse({ success: true });
    return true;
  }
});

chrome.storage.local.get(['isAutomating', 'isRecovering'], async (res) => {
  if (res.isAutomating === true && res.isRecovering === true) {
    console.log("[NRA DreamLab] Memulihkan sesi setelah reload. Menunggu elemen Canva siap...");
    await chrome.storage.local.set({ isRecovering: false });

    try {
      // Set flags SEBELUM waitForElement agar tidak langsung di-reject oleh USER_STOPPED check
      isRunning = true;
      isLoopActive = true;

      // Tunggu hingga textarea prompt tersedia di DOM sebelum melanjutkan loop
      await waitForElement(CANVA_SELECTORS.PROMPT_TEXTAREA, 45000);
      if (isLoopActive) {
        startMainLoop().catch(err => { if (!err || err.message !== "USER_STOPPED") console.error(err); }).finally(() => {
          isLoopActive = false;
          isRunning = false;
        });
      }
    } catch (e) {
      console.error("[NRA DreamLab] Gagal memulihkan sesi setelah reload. Elemen tidak ditemukan:", e.message);
      isRunning = false;
      isLoopActive = false;
      chrome.storage.local.set({ isAutomating: false, step: "IDLE" });
    }
  }
});

// Broadcast READY immediately upon script injection/load
setTimeout(() => {
  try {
    safeSendMessage({ action: "STATUS_UPDATE", status: "Canva Connected" });
  } catch (e) { }
}, 500);
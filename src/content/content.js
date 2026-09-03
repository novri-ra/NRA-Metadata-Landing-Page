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

// NRA DreamLab - Content Script targeting canva.com/dream-lab
// Operates exclusively on https://www.canva.com/dream-lab

// ponytail: removed unused getStyleOptionsFromDOM and getRatioOptionsFromDOM

let isPausedGlobal = false;
let batchLimitGlobal = 0;
let isAutomatingGlobal = false;

// Set up a local cache listener to drastically reduce storage I/O
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

// Global execution flag for the automation loop
let isRunning = false;
// Mutex guard: prevents concurrent startMainLoop() invocations (KRITIS-2)
let isLoopActive = false;
// Session Statistics Telemetry
let promptsGlobal = [];
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

// ponytail: replaced over-engineered Web Worker delay with native setTimeout
function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
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
 * Helper to tag processed warnings so they are ignored in the future.
 * Applies data-bot-ignored attribute and visual feedback to ghost cooldown text.
 */
function tagGhostCooldowns() {
  const warnings = document.evaluate(
    "//*[not(@data-bot-ignored='true') and (contains(text(), 'Lots of people are using') or contains(text(), 'generate again in') or contains(text(), 'Try again in'))]",
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
 * Wait for a DOM element to exist via MutationObserver.
 * ponytail: removed unused XPath support
 */
async function waitForElement(selector, timeout = 10000) {
  return new Promise((resolve, reject) => {
    let timer;
    let settled = false;

    function check() {
      if (settled) return null;
      if (!isRunning && !isWaitingForCooldown) {
        settled = true;
        if (timer) clearTimeout(timer);
        reject(new Error("USER_STOPPED"));
        return null;
      }
      const el = document.querySelector(selector);
      if (el) {
        const rect = el.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) return el;
      }
      return null;
    }

    const initial = check();
    if (initial) return resolve(initial);
    if (settled) return;

    const observer = new MutationObserver(() => {
      const el = check();
      if (el) {
        settled = true;
        observer.disconnect();
        if (timer) clearTimeout(timer);
        resolve(el);
      }
    });

    observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["style", "class"] });

    timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      observer.disconnect();
      reject(new Error("Timeout waiting for element matching: " + selector));
    }, timeout);
  });
}

// ponytail: removed unused auditSelectors

/**
 * Extracts the cooldown time remaining from a rate-limit warning element on the screen.
 * Updated radar to strictly ignore tagged ghosts.
 * @returns {number} Cooldown in milliseconds, or 0 if not found.
 */
function getScreenCooldownMs() {
  // Tambahan sanitasi: Jika submit button aktif dan tidak di-disable, abaikan alert stale text
  const btn = document.querySelector(CANVA_SELECTORS.SUBMIT_BUTTON);
  if (btn && !btn.disabled && btn.getAttribute("aria-disabled") !== "true") {
    return 0;
  }

  // Ensure we ignore elements tagged by tagGhostCooldowns
  let ignoredNodes = [];
  try {
    const nodes = document.querySelectorAll('[data-bot-ignored="true"]');
    if (nodes) ignoredNodes = Array.from(nodes);
  } catch (e) { }
  // Hapus teks dari node yang diabaikan agar tidak terdeteksi sama sekali
  ignoredNodes.forEach((node) => {
    node.setAttribute("data-original-text", node.textContent);
    node.textContent = "";
  });

  const COOLDOWN_PATTERNS = {
    BUSY: /Lots of people are using/i,
    GENERATE: /generate again in/i,
    TRY: /Try again in/i,
  };

  let pageText = "";

  // Gunakan selektor terpusat hasil audit untuk memindai status alert halaman
  const alertElements = document.querySelectorAll('[role="alert"], [role="status"]');
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
    pageText = document.body.innerText || ""; // innerText ignores hidden/tagged elements
  }

  // Restore original text
  ignoredNodes.forEach((node) => {
    if (node.hasAttribute("data-original-text")) {
      node.textContent = node.getAttribute("data-original-text");
      node.removeAttribute("data-original-text");
    }
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
        // Ekstrak angka dari teks yang mengikuti pattern match
        // Canva bisa menggunakan format "14:12" atau "14m 12s"
        const timeStr = pageText.substring(match.index);

        // Cari format MM:SS
        const colonMatch = timeStr.match(/(\d+):(\d+)/);
        if (colonMatch) {
          return ((parseInt(colonMatch[1], 10) * 60) + parseInt(colonMatch[2], 10)) * 1000;
        }

        // Cari format Xm Ys
        const textMatch = timeStr.match(/(\d+)\s*m\s*(\d+)\s*s/i);
        if (textMatch) {
          return ((parseInt(textMatch[1], 10) * 60) + parseInt(textMatch[2], 10)) * 1000;
        }

        // Cari format Xs saja (misal "Try again in 45s")
        const secMatch = timeStr.match(/(\d+)\s*s/i);
        if (secMatch) {
          return parseInt(secMatch[1], 10) * 1000;
        }

        // Fallback aman jika teks 'Try again' ada tapi angka gagal diekstrak
        console.warn("[NRA DreamLab] Waktu cooldown tidak dapat diekstrak dari teks. Fallback ke 3 menit.");
        return 3 * 60 * 1000;
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

  const errMessage = (err && err.message) ? err.message : JSON.stringify(err);

  if (errMessage === "USER_STOPPED") {
    console.info("[NRA DreamLab] Process stopped manually.");
    chrome.storage.local.set({ isAutomating: false, step: "IDLE" }, () => {
      sendStatusUpdate("Automation stopped by user.");
    });
    return;
  }

  console.error("[NRA DreamLab] Loop broken due to:", errMessage);
  if (err && err.stack) console.error("[Stack Trace]:", err.stack);

  if (err.message === "MONTHLY_LIMIT_REACHED") {
    console.error(
      "[NRA DreamLab] Monthly AI limit reached. Stopping permanently.",
    );
    chrome.storage.local.set({ isAutomating: false, step: "ERROR" }, () => {
      sendStatusUpdate("Monthly Limit Reached. Stopped.");
      chrome.runtime.sendMessage({
        action: "SHOW_NOTIFICATION",
        title: "Canva Automation Halted",
        message:
          "You've hit your plan's monthly AI limit! Automation has been permanently stopped.",
      }).catch(() => { });
    });
    chrome.runtime.sendMessage({ action: "RELEASE_AWAKE" }).catch(() => ({}));
    return;
  }

  const errMsg = errMessage || "Unknown error occurred.";
  chrome.storage.local.set({ isAutomating: false, step: "ERROR" }, () => {
    chrome.runtime.sendMessage({
      action: "STATUS_UPDATE",
      status: "Error: " + errMsg,
    }).catch(() => { });
  });
  chrome.runtime.sendMessage({ action: "RELEASE_AWAKE" }).catch(() => ({}));
}

async function safeCdpClick(element, context = "element") {
  try {
    await cdpClick(element);
  } catch (error) {
    if (error && error.message === "USER_STOPPED") throw error;
    console.error(`[NRA DreamLab] Failed to click ${context}:`, error);
    chrome.runtime.sendMessage({ action: "EMERGENCY_CLEANUP" }).catch(() => { });
    throw new Error(`Click interaction failed for ${context}`);
  }
}

async function safeCdpTypeHuman(text, context = "input") {
  try {
    await cdpTypeHuman(text);
  } catch (error) {
    if (error && error.message === "USER_STOPPED") throw error;
    console.error(`[NRA DreamLab] Failed to type in ${context}:`, error);
    chrome.runtime.sendMessage({ action: "EMERGENCY_CLEANUP" }).catch(() => { });
    throw new Error(`Type interaction failed for ${context}`);
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
  // Kembalikan posisi halaman ke paling atas agar textarea terlihat jelas oleh pengguna
  window.scrollTo({ top: 0, behavior: "instant" });
  await delay(300);

  const textarea = await waitForElement(CANVA_SELECTORS.PROMPT_TEXTAREA);
  if (!textarea) throw new Error("Textarea not found");

  // Jika textarea ditemukan, pastikan dia masuk ke fokus visual layar kembali
  textarea.scrollIntoView({ behavior: "instant", block: "center" });
  textarea.focus();
  await delay(200);

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
    console.log(`[NRA DreamLab] Executing Super Fast Human Typing (20ms delay)...`);
    textarea.value = "";
    const typingDelay = 20; // Diturunkan ke 20ms agar pengetikan jauh lebih cepat
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
      `[NRA DreamLab] Failed to configure ${typeLabel} with ${optionText}:`,
      error,
    );
    chrome.runtime.sendMessage({ action: "EMERGENCY_CLEANUP" }).catch(() => { });
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
      console.info(`[NRA DreamLab] âœ… Pemaksaan klik dieksekusi pada opsi '${value}' untuk menu '${label}'.`);

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
  if (!textarea || !textarea.isConnected) throw new Error("Textarea not found or stale");

  // Pastikan input bisa diklik/difokuskan sebelum diketik
  await safeCdpClick(textarea, "focus textarea");
  await delay(300);

  textarea.value = "";
  textarea.dispatchEvent(new Event("input", { bubbles: true }));
  await safeCdpTypeHuman(currentPrompt, "prompt input");
}

async function submitAndWaitForImages(currentIndex, totalPrompts) {
  console.info("[NRA DreamLab] Mencari tombol Generate...");
  const generateBtn = await waitForElement(CANVA_SELECTORS.SUBMIT_BUTTON, 15000);
  console.info("[NRA DreamLab] Menekan tombol Generate...");

  // Implement DOM Tagging (Marking): Prevent bot from reading previous generated images
  const oldContainers = getRenderContainers();
  oldContainers.forEach(c => {
    c.setAttribute("data-nra-processed", "true");
  });

  await safeCdpClick(generateBtn, "generate button");

  console.info("[NRA DreamLab] Menunggu inisiasi node kontainer baru...");

  // State Transition Wait: Jeda singkat agar Canva sempat memproses klik & menambah/menghapus DOM
  await delay(1500);

  // Tunggu kontainer render baru muncul (max 60 detik) sebelum mulai pemantauan rendering
  console.info("[NRA DreamLab] Menunggu kontainer render baru muncul di DOM...");
  const sectionWaitStart = Date.now();
  const sectionWaitMax = 60000;
  let newSection = null;
  while (Date.now() - sectionWaitStart < sectionWaitMax) {
    if (!isRunning && !isWaitingForCooldown) throw new Error("USER_STOPPED");
    const candidates = getRenderContainers(true);
    if (candidates.length > 0) {
      newSection = candidates[0]; // Terbaru di paling atas
      console.info("[NRA DreamLab] Kontainer render baru terdeteksi di DOM.");
      break;
    }
    await delay(1000);
  }

  console.info("[NRA DreamLab] Memulai pemantauan adaptif fase rendering (Anti-Blur)...");
  const maxWaitTimeMs = 240000;
  const checkIntervalMs = 1000;
  const startTime = Date.now();
  let detectedFinalizing = false;

  while (Date.now() - startTime < maxWaitTimeMs) {

    if (!isRunning && !isWaitingForCooldown) throw new Error("USER_STOPPED");

    const pageText = document.body.textContent || "";

    const isSketching = /sketching/i.test(pageText);
    const isFinalizing = /finalizing/i.test(pageText);
    const isProcessingText = isSketching || isFinalizing || /refining|generating|memproses|membuat/i.test(pageText) ||
      document.querySelector('[role="progressbar"]') !== null;

    // Tandai jika bot berhasil mendeteksi fase Finalizing dari Canva
    if (isFinalizing) {
      if (!detectedFinalizing) {
        console.info("[NRA DreamLab] 🎯 Fase 'Finalizing your image...' terdeteksi di layar.");
        detectedFinalizing = true;
      }
    }

    // Refresh referensi section terbaru (DOM bisa berubah selama rendering)
    const allNewSections = getRenderContainers(true);
    const latestSection = allNewSections.length > 0 ? allNewSections[0] : newSection;

    // Cek apakah gambar valid sudah ada di section terbaru
    let isImageReady = false;
    if (latestSection) {
      const validImg = latestSection.querySelector(`img[src^="https://"], img[src^="blob:"], canvas`);
      if (validImg) {
        isImageReady = validImg.tagName === "CANVAS" || (validImg.complete && validImg.naturalWidth > 0);
      }
    }

    // Kontainer dianggap siap jika teks pemrosesan hilang DAN (download button ada ATAU gambar siap)
    // Scope ke section baru saja, bukan global (download buttons lama masih ada di DOM)
    const downloadExists = latestSection
      ? latestSection.querySelector(CANVA_SELECTORS.DOWNLOAD_BUTTON) !== null
      : false;

    if ((!isProcessingText && downloadExists) || (!isProcessingText && isImageReady)) {

      // JIKA SEBELUMNYA TERDETEKSI FINALIZING, BERIKAN JEDA AMAN SINKRONISASI ANIMASI 5 DETIK
      if (detectedFinalizing) {
        console.info("[NRA DreamLab] ✨ Teks Finalizing hilang. Menahan download selama 5 detik agar animasi render selesai sempurna...");
        await delay(5000);
      }

      // Ambil ekstra safety delay dari storage jika dikonfigurasi oleh pengguna
      const res = await chrome.storage.local.get(["safetyDelay"]);
      const extraDelay = (parseInt(res.safetyDelay, 10) || 0) * 1000;
      if (extraDelay > 0) {
        console.info(`[NRA DreamLab] Menerapkan Extra Safety Delay sebesar ${extraDelay}ms...`);
        await delay(extraDelay);
      }

      console.info("[NRA DreamLab] ✅ Gambar terdeteksi siap dan tajam! Menuju proses download...");
      return true;
    }

    console.log("[NRA DreamLab] Menunggu proses rendering gambar Canva tuntas...");
    await delay(checkIntervalMs);
  }

  throw new Error("Timeout: Proses pembuatan tajam gambar Canva melampaui batas waktu aman.");
}

async function handleDownload(countSetting = "4", currentPrompt = "", currentIndex, totalPrompts) {
  sendStatusUpdate(`[${currentIndex + 1}/${totalPrompts}] Downloading images...`);
  console.info(`[NRA DreamLab] Memulai isolasi kontainer untuk prompt aktif: "${currentPrompt}"`);

  // 1. Ambil kontainer render (div[role="group"][data-testid] atau section fallback)
  const allContainers = getRenderContainers();
  const newContainers = allContainers.filter(c => !c.hasAttribute('data-nra-processed'));
  // ponytail: prefer unprocessed containers; fall back to all if none found
  const sections = newContainers.length > 0 ? newContainers : allContainers;
  let targetContainer = null;

  if (currentPrompt) {
    const cleanActivePrompt = currentPrompt.trim().toLowerCase();
    // Gunakan 25 karakter pertama untuk mengatasi pemotongan string '...' oleh Canva
    const promptSnippet = cleanActivePrompt.substring(0, 25).trim();

    // 2. Lakukan perulangan untuk mencari kontainer yang membungkus teks prompt aktif
    for (const container of sections) {
      // Multi-fallback: cek span[data-testid], button span, p, lalu textContent keseluruhan
      const titleElements = container.querySelectorAll('span[data-testid], button span, p');
      let matchesPrompt = false;

      for (const el of titleElements) {
        const elText = (el.textContent || el.innerText || "").trim().toLowerCase();
        if (elText.includes(promptSnippet)) {
          matchesPrompt = true;
          break;
        }
      }

      // Fallback: bandingkan langsung textContent kontainer
      if (!matchesPrompt) {
        const fullText = (container.textContent || "").toLowerCase();
        if (fullText.includes(promptSnippet)) {
          matchesPrompt = true;
        }
      }

      if (matchesPrompt) {
        targetContainer = container;
        console.info("[NRA DreamLab] ✅ Sukses mengunci kontainer berdasarkan kecocokan teks prompt!");
        break;
      }
    }
  }

  // Fallback 1: Jika pencocokan teks gagal, ambil kontainer terbaru (indeks 0 = paling atas di DOM)
  if (!targetContainer && sections.length > 0) {
    console.warn("[NRA DreamLab] Pencocokan teks prompt tidak mendeteksi kontainer. Fallback mengambil kontainer teratas/terbaru...");
    targetContainer = sections[0];
  }

  // Fallback 2: Jika tidak ada section sama sekali
  if (!targetContainer) {
    targetContainer = document.body;
    console.warn("[NRA DreamLab] Fallback ultimate ke document body.");
  }

  let targetCount = parseInt(countSetting, 10) || 4;
  let allDownloadButtons = [];
  try {
    // 3. Cari tombol download secara eksklusif HANYA di dalam targetContainer yang telah dikunci
    const MAX_DOWNLOAD_RETRIES = 15;

    for (let attempt = 0; attempt < MAX_DOWNLOAD_RETRIES; attempt++) {
      const buttons = Array.from(targetContainer.querySelectorAll(CANVA_SELECTORS.DOWNLOAD_BUTTON))
        .filter(btn => btn.offsetParent !== null); // Pastikan elemennya terlihat di layar

      allDownloadButtons = buttons;
      if (buttons.length >= targetCount) {
        break;
      } else {
        console.info(`[NRA DreamLab] Baru ditemukan ${buttons.length}/${targetCount} tombol download, menunggu...`);
      }
      console.info(`[NRA DreamLab] Tombol download belum siap, mencoba lagi dalam 2 detik... (Attempt ${attempt + 1}/${MAX_DOWNLOAD_RETRIES})`);
      await delay(2000);
    }

    if (allDownloadButtons.length === 0) {
      throw new Error("Tombol download tidak ditemukan setelah batas waktu penungguan.");
    }
  } catch (error) {
    throw new Error("Gagal mengisolasi tombol unduh: " + error.message);
  }


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
        await delay(1000); // Jeda agresif namun aman

        sessionStats.downloadCount++;
        chrome.storage.local.set({ sessionStats: sanitizeStats(sessionStats) });
        chrome.runtime.sendMessage({
          action: "UPDATE_STATS",
          stats: sanitizeStats(sessionStats)
        }).catch(() => { });
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
let isWaitingForCooldown = false;
let isCooldownActive = false; // Guard
let consecutiveCooldownCount = 0; // Guard for consecutive cooldowns
function getRenderContainers(unprocessedOnly = false) {
  let selector = 'div[role="group"][data-testid]';
  let containers = Array.from(document.querySelectorAll(selector));
  if (containers.length === 0) {
    selector = 'section';
    containers = Array.from(document.querySelectorAll(selector));
  }
  if (unprocessedOnly) {
    return containers.filter(c => !c.hasAttribute('data-nra-processed'));
  }
  return containers;
}

async function handleCooldown(cooldownMs, isStartup = false) {
  if (isCooldownActive) return true;
  isCooldownActive = true;
  isWaitingForCooldown = true;
  console.log(`[DEBUG] Entering handleCooldown for ${cooldownMs}ms`);
  if (!isStartup) sessionStats.totalCooldowns++;
  cooldownMs += 5000;
  console.warn(`[NRA DreamLab] ${isStartup ? "Startup paused. Pre-existing cooldown" : "Cooldown"} detected: ${cooldownMs}ms. Waiting...`);
  tagGhostCooldowns();
  const targetEndTime = Date.now() + cooldownMs;
  while (Date.now() < targetEndTime) {
    if (!isAutomatingGlobal) {
      if (isStartup) {
        console.log("[NRA DreamLab] Automation aborted by user during startup cooldown.");
        isWaitingForCooldown = false;
        isCooldownActive = false;
        return false;
      }
      isWaitingForCooldown = false;
      isCooldownActive = false;
      throw new Error("USER_STOPPED");
    }
    const remainingSecs = Math.ceil((targetEndTime - Date.now()) / 1000);
    chrome.runtime.sendMessage({
      action: "STATUS_UPDATE",
      status: `${isStartup ? "Startup Paused (Limit Active)" : "Cooldown"}: ${formatTime(remainingSecs)}`
    }).catch(() => { });
    await delay(1000);
  }
  tagGhostCooldowns();

  consecutiveCooldownCount++;
  if (consecutiveCooldownCount >= 3) {
    console.error("[NRA DreamLab] Limit akun tercapai secara beruntun. Menghentikan bot.");
    chrome.runtime.sendMessage({ action: "STATUS_UPDATE", status: "Error: Account limit reached. Automation paused." }).catch(() => { });
    chrome.storage.local.set({ isAutomating: false, step: "IDLE", isPaused: true });
    isWaitingForCooldown = false;
    isCooldownActive = false;
    consecutiveCooldownCount = 0;
    throw new Error("MAX_COOLDOWN_REACHED");
  }
  console.log(
    `[NRA DreamLab] ${isStartup ? "Startup cooldown cleared. Proceeding to main generation loop..." : "Cooldown cleared. Resuming..."}`,
  );
  chrome.runtime.sendMessage({
    action: "STATUS_UPDATE",
    status: `Resuming ${isStartup ? "automation" : "after cooldown"}...`,
  }).catch(() => { });
  isWaitingForCooldown = false;
  isCooldownActive = false;
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

    if (!window.location.href.includes("canva.com/dream-lab")) {
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
      // ðŸŒŸ INITIAL STARTUP GATEKEEPER ðŸŒŸ
      const canProceed = await checkAndHandleStartupCooldown();
      if (!canProceed) return;

      let isConfigured = false;

      // ðŸŒŸ MAIN GENERATION LOOP ðŸŒŸ
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

        // 1. Hitung indeks aktif secara akurat sebelum array prompts dikurangi/di-shift
        const currentIndex = startIndex + (sessionStats.totalPrompts - prompts.length);


        // MEMORY LEAK PREVENTION: Reload page natively every 50 processed prompts
        if (sessionStats.successCount > 0 && sessionStats.successCount % 50 === 0) {
          console.info("[NRA DreamLab] 🧹 Preventative memory dump: Reloading tab after 50 prompts to clear Canva DOM bloat.");
          await chrome.storage.local.set({
            isRecovering: true,
            lastProcessedPromptIndex: currentIndex
          });
          window.location.reload();
          return;
        }

        // 2. Baru ambil prompt aktif dari antrean
        const currentPrompt = prompts.shift();

        // 2. PRE-FLIGHT GATEKEEPER: Cek dan tahan bot jika ada cooldown aktif SEBELUM mulai mengetik
        let startupCooldown = getScreenCooldownMs();
        let justFinishedCooldown = false;
        if (startupCooldown > 0) {
          console.warn(`[NRA DreamLab] Batasan limit aktif terdeteksi sebelum mulai mengetik! Menahan loop selama ${startupCooldown}ms`);
          await handleCooldown(startupCooldown, false);

          console.info("[NRA DreamLab] 🛡️ Cooldown selesai. Mengaktifkan Post-Cooldown Recovery Delay selama 5 detik untuk stabilitas sesi...");
          await delay(5000);
          justFinishedCooldown = true;
        }

        chrome.runtime.sendMessage({
          action: "STATUS_UPDATE",
          status: `[${currentIndex + 1}/${sessionStats.totalPrompts}] Typing prompt...`,
        }).catch(() => { });

        // 3. Update prompt aktif ke storage untuk penamaan file background.js
        await chrome.storage.local.set({ downloadingPrompt: currentPrompt });

        // 4. Konfigurasi, Injeksi (Mengetik dengan kecepatan baru), dan Submit
        await prepareAndSubmitPrompt(
          currentPrompt,
          isConfigured,
          imageStyle,
          aspectRatio,
          currentIndex,
          sessionStats.totalPrompts
        );
        isConfigured = true;

        // 5. Download / Retry Loop
        let downloadSuccess = false;
        let retryCount = 0;
        const maxRetries = 3;

        while (!downloadSuccess && retryCount < maxRetries) {
          try {
            await handleDownload(downloadCountSetting, currentPrompt, currentIndex, sessionStats.totalPrompts);
            downloadSuccess = true;
            consecutiveCooldownCount = 0; // Reset guard setelah sukses
          } catch (error) {
            console.error(`[NRA DreamLab] Download attempt ${retryCount + 1} failed:`, error.message);
            retryCount++;
            if (retryCount < maxRetries) {
              console.warn("[NRA DreamLab] Memulai prosedur recovery, mereload halaman...");

              // Simpan state recovery SEBELUM me-reload halaman
              await chrome.storage.local.set({
                isRecovering: true,
                lastProcessedPromptIndex: currentIndex - 1
              });

              window.location.reload();

              // Hentikan eksekusi: instance script ini akan musnah saat page reload
              return;
            }
          }
        }

        // 6. POST-FLIGHT CHECK: Cek kembali cooldown jika limit baru lahir pasca-submit
        if (!justFinishedCooldown) {
          let postCooldownMs = getScreenCooldownMs();
          if (postCooldownMs > 0) {
            console.warn(`[NRA DreamLab] Limit akun terdeteksi pasca-submit! Waktu tunggu: ${postCooldownMs}ms`);
            await handleCooldown(postCooldownMs, false);

            console.info("[NRA DreamLab] 🛡️ Cooldown selesai. Mengaktifkan Post-Cooldown Recovery Delay selama 5 detik untuk stabilitas sesi...");
            await delay(5000);
          }
        } else {
          console.info("[NRA DreamLab] 🛡️ POST-FLIGHT cooldown check dilewati karena sesi ini baru saja bangkit dari cooldown (Stale DOM prevention).");
        }

        justFinishedCooldown = false;

        // 7. Update status ke storage & panel
        if (!downloadSuccess) {
          chrome.runtime.sendMessage({
            action: "PROMPT_FAILED",
            failedPrompt: currentPrompt
          }).catch(() => { });
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
        }).catch(() => { });

        if (batchLimitGlobal > 0 && sessionStats.downloadCount >= batchLimitGlobal) {
          isRunning = false;
          chrome.storage.local.set({ isAutomating: false, step: "IDLE" }, () => {
            sendStatusUpdate("Batch limit reached. Automation stopped.");
          });
          break;
        }

        await delay(2000);
      }

      // Final cleanup
      if (isRunning) {
        console.log("[NRA DreamLab] All prompts processed successfully.");
        chrome.storage.local.set({ isAutomating: false, step: "IDLE" }, () => {
          sendStatusUpdate("All prompts processed successfully!");
        });
        chrome.runtime.sendMessage({ action: "RELEASE_AWAKE" }).catch(() => ({}));
      }
    } catch (err) {
      handleAutomationError(err);
    }
  } catch (err) {
    handleAutomationError(err);
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
  currentIndex,
  totalPrompts
) {
  if (!isConfigured) {
    await configureStyleAndRatio(imageStyle, aspectRatio);
  }
  await injectPrompt(currentPrompt);
  sendStatusUpdate(`[${currentIndex + 1}/${totalPrompts}] Submitting prompt...`);
  await submitAndWaitForImages(currentIndex, totalPrompts);
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
    chrome.runtime.sendMessage({ action: "RELEASE_AWAKE" }).catch(() => ({}));
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
    chrome.runtime.sendMessage({ action: "STATUS_UPDATE", status: "Canva Connected" }).catch(() => { });
  } catch (e) { }
}, 500);




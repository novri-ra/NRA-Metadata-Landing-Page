// dom-utils.js
// DOM and time helpers for NRA DreamLab automation.

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

// ponytail: replaced over-engineered Web Worker delay with native setTimeout
function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Beberapa tombol Canva berada dalam modal/fixed container sehingga
 * `offsetParent` bernilai null meskipun terlihat. Gunakan ukuran rect.
 */
function isVisible(el) {
  if (!el || !el.isConnected) return false;
  const rect = el.getBoundingClientRect();
  return rect.width > 0 && rect.height > 0;
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
        if (typeof observer !== 'undefined') observer.disconnect();
        reject(new AutomationError(ERR.USER_STOPPED));
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
      reject(new AutomationError("TIMEOUT", "Timeout waiting for element matching: " + selector));
    }, timeout);
  });
}

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

  // Hapus teks dari node yang diabaikan agar tidak terdeteksi sama sekali.
  // Batu bangunan: blank + rescan + restore dikunci dalam try/finally agar
  // teks asli SELALU dipulihkan meski scanning melempar exception.
  try {
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
  } finally {
    // Restore original text in ALL cases (success, return, or throw)
    ignoredNodes.forEach((node) => {
      if (node.hasAttribute("data-original-text")) {
        node.textContent = node.getAttribute("data-original-text");
        node.removeAttribute("data-original-text");
      }
    });
  }
}
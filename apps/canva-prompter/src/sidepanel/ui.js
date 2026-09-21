// ui.js
// Panel UI render helpers, shared DOM refs, and UI-only logic (no orchestration).

let isRunning = false;
let isDebugMode = false;

function applyCustomUI(theme, font) {
  document.body.className = "";
  if (theme && font) {
    document.body.classList.add(theme, font);
  }
}

function syncRunButtonUI(isAutomating) {
  const startBtn = document.getElementById("startBtn");
  if (!startBtn) return;
  isRunning = isAutomating; // Keep local tracker updated

  if (isAutomating) {
    startBtn.textContent = "Stop";
    startBtn.style.background = "#e74c3c";
    startBtn.style.boxShadow = "0 4px 15px rgba(231, 76, 60, 0.4)";
  } else {
        startBtn.textContent = "Run";
    startBtn.style.background = "";
    startBtn.style.boxShadow = "";
    startBtn.disabled = false;
    startBtn.style.opacity = "1";
    startBtn.style.cursor = "pointer";
    startBtn.style.pointerEvents = "auto";

    chrome.storage.local.set({ isPaused: false });
    const pauseButton = document.getElementById("pauseButton");
    if (pauseButton) {
      pauseButton.textContent = "⏸ PAUSE";
      pauseButton.style.background = "#f39c12";
    }
  }
}

function updateStatsUI(stats) {
  if (!stats) return;

  const successCount = Number(stats.successCount) || 0;
  const downloadCount = Number(stats.downloadCount) || 0;
  const totalPrompts = Number(stats.totalPrompts) || 0;

  const elProcessed = document.getElementById("stat-processed");
  if (elProcessed) elProcessed.textContent = successCount;

  const elDownloaded = document.getElementById("stat-downloaded");
  if (elDownloaded) elDownloaded.textContent = downloadCount;

  const elRate = document.getElementById("stat-rate");
  if (elRate) {
    if (successCount > 0) {
      const failedCount = Number(stats.failedCount) || 0;
      const successfulPrompts = successCount - failedCount;
      let rate = Math.round((successfulPrompts / successCount) * 100);
      if (isNaN(rate) || rate < 0) rate = 0;
      elRate.textContent = rate + "%";
    } else {
      elRate.textContent = "0%";
    }
  }

  let elapsedSeconds = 0;
  const elTime = document.getElementById("stat-time");
  if (stats.startTime) {
    let elapsedMs = Date.now() - Number(stats.startTime);
    if (isNaN(elapsedMs) || elapsedMs < 0) elapsedMs = 0;
    elapsedSeconds = Math.floor(elapsedMs / 1000);
    const minutes = Math.floor(elapsedSeconds / 60);
    const seconds = elapsedSeconds % 60;
    if (elTime) elTime.textContent = `${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
  } else {
    if (elTime) elTime.textContent = "00:00";
  }

  // --- LOGIKA BARU: AVG SPEED & ETA ---
  const elAvgSpeed = document.getElementById("stat-avg-speed");
  const elEta = document.getElementById("stat-eta");

  if (successCount > 0 && elapsedSeconds > 0) {
    const avgSeconds = elapsedSeconds / successCount;
    if (elAvgSpeed) elAvgSpeed.textContent = Math.round(avgSeconds) + "s/prompt";

    const remainingPrompts = Math.max(0, totalPrompts - successCount);
    if (remainingPrompts > 0) {
      const etaSeconds = Math.round(remainingPrompts * avgSeconds);
      const etaMins = Math.floor(etaSeconds / 60);
      const etaSecs = etaSeconds % 60;
      if (elEta) elEta.textContent = `${etaMins.toString().padStart(2, "0")}:${etaSecs.toString().padStart(2, "0")}`;
    } else {
      if (elEta) elEta.textContent = "00:00";
    }
  } else {
    if (elAvgSpeed) elAvgSpeed.textContent = "--";
    if (elEta) elEta.textContent = "--:--";
  }
}

// Shared DOM Elements
let startBtn,
  promptInput,
  aspectRatioSelect,
  imageStyleSelect,
  downloadCountSelect,
  debugModeSelect,
  progressText,
  statusText,
  statusDot,
  failedPromptsTextarea,
  consoleLogs;

function initUIElements() {
  startBtn = document.getElementById("startBtn");
  promptInput = document.getElementById("promptInput");
  aspectRatioSelect = document.getElementById("aspectRatio");
  imageStyleSelect = document.getElementById("imageStyle");
  downloadCountSelect = document.getElementById("downloadCount");
  debugModeSelect = document.getElementById("debugMode");
  progressText = document.getElementById("progressText");
  statusText = document.getElementById("statusText");
  statusDot = document.getElementById("statusIndicator");
  failedPromptsTextarea = document.getElementById("failedPrompts");
  consoleLogs = document.getElementById("consoleLogs");
}

function initCollapseLogic() {
  const toggleHeaders = document.querySelectorAll(".toggle-header");

  toggleHeaders.forEach((header) => {
    header.addEventListener("click", (e) => {
      // Prevent toggling if the user clicked directly on an icon button
      if (e.target.closest(".icon-btn")) return;

      const targetId = header.getAttribute("data-target");
      const contentDiv = document.getElementById(targetId);
      const toggleIcon = header.querySelector(".toggle-icon");

      if (contentDiv) {
        contentDiv.classList.toggle("collapsed");
        if (contentDiv.classList.contains("collapsed")) {
          toggleIcon.textContent = "[+]";
        } else {
          toggleIcon.textContent = "[-]";
        }
      }
    });
  });
}

// Pleasant, ascending 2-tone chime: 523.25Hz (150ms), then 659.25Hz (300ms)
let sharedAudioCtx = null;

function playAlertSound() {
  try {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) return;

    if (!sharedAudioCtx || sharedAudioCtx.state === "closed") {
      sharedAudioCtx = new AudioContextClass();
    }

    if (sharedAudioCtx.state === "suspended") {
      sharedAudioCtx.resume();
    }

    const osc = sharedAudioCtx.createOscillator();
    const gain = sharedAudioCtx.createGain();

    osc.connect(gain);
    gain.connect(sharedAudioCtx.destination);

    const now = sharedAudioCtx.currentTime;

    // Tone 1: 523.25Hz for 150ms
    osc.frequency.setValueAtTime(523.25, now);
    gain.gain.setValueAtTime(0.15, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.15);

    // Tone 2: 659.25Hz for 300ms
    osc.frequency.setValueAtTime(659.25, now + 0.15);
    gain.gain.setValueAtTime(0.15, now + 0.15);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.45);

    osc.start(now);
    osc.stop(now + 0.45);
  } catch (e) {
    console.warn("[NRA DreamLab] Web Audio alert failed:", e);
    return false;
  }
}

// System Notification
function showBrowserNotification() {
  if (typeof chrome !== "undefined" && chrome.notifications) {
    chrome.notifications.create(
      {
        type: "basic",
        iconUrl: "assets/icon.png",
        title: "NRA DreamLab",
        message: "Success! All prompts have been processed.",
      },
      (id) => {
        if (chrome.runtime.lastError) {
          console.warn(
            "[NRA DreamLab] Notification alert failed:",
            chrome.runtime.lastError.message,
          );
        }
      },
    );
  }
}

/**
 * Expand prompt with {i} placeholder
 * @param {string} prompt - Prompt text containing {i}
 * @param {number} iterations - Number of iterations (default: 1)
 * @returns {string[]} Array of expanded prompts
 */
function expandPromptWithVariable(prompt, iterations) {
  if (!prompt.includes("{i}") || iterations < 1) {
    return [prompt];
  }
  const results = [];
  for (let i = 1; i <= iterations; i++) {
    results.push(prompt.replace(/\{i\}/g, i));
  }
  return results;
}
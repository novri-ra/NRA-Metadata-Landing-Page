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

function initStorageListeners() {
  // Pull existing progress from storage on startup and sync running state
  chrome.storage.local.get(
    [
      "prompts",
      "isAutomating",
      "savedPromptText",
      "aspectRatio",
      "imageStyle",
      "savedDownloadCount",
      "savedFailedPrompts",
      "savedDebugMode",
      "uiTheme",
      "uiFont",
      "batchLimit",
      "safetyDelay",
      "playSounds",
      "typingMode",
      "createSubfolder",
      "lastProcessedPromptIndex",
      "sessionStats",
    ],
    (result) => {
      if (result) {
        if (result.sessionStats) updateStatsUI(result.sessionStats);
        // Load UI Preferences
        const savedTheme = result.uiTheme || "theme-retro";
        const savedFont = result.uiFont || "font-pixel";
        if (document.getElementById("themeSelect"))
          document.getElementById("themeSelect").value = savedTheme;
        if (document.getElementById("fontSelect"))
          document.getElementById("fontSelect").value = savedFont;
        applyCustomUI(savedTheme, savedFont);

        // Load Advanced Settings
        const typingModeSelect = document.getElementById("typingModeSelect");
        const batchLimitInput = document.getElementById("batchLimitInput");
        const safetyDelaySlider = document.getElementById("safetyDelaySlider");
        const safetyDelayVal = document.getElementById("safetyDelayVal");
        const saveDelaySlider = document.getElementById("saveDelaySlider");
        const saveDelayVal = document.getElementById("saveDelayVal");
        const soundToggle = document.getElementById("soundToggle");
        const subfolderToggle = document.getElementById("subfolderToggle");
        const verboseLogsToggle = document.getElementById("verboseLogsToggle");

        if (result.typingMode && typingModeSelect)
          typingModeSelect.value = result.typingMode;
        if (result.batchLimit !== undefined && batchLimitInput)
          batchLimitInput.value = result.batchLimit;
        if (result.safetyDelay !== undefined) {
          if (safetyDelaySlider) safetyDelaySlider.value = result.safetyDelay;
          if (safetyDelayVal) safetyDelayVal.textContent = result.safetyDelay;
        }
        if (result.saveDelay !== undefined) {
          if (saveDelaySlider) saveDelaySlider.value = result.saveDelay;
          if (saveDelayVal) saveDelayVal.textContent = result.saveDelay;
        }
        if (result.playSounds !== undefined && soundToggle)
          soundToggle.checked = result.playSounds;
        if (subfolderToggle)
          subfolderToggle.checked = result.createSubfolder === true;
        if (verboseLogsToggle)
          verboseLogsToggle.checked = result.verboseLogs !== false;

        // Prioritize active processing prompts if automating, otherwise fall back to auto-saved prompt text
        if (
          result.isAutomating === true &&
          result.prompts &&
          result.prompts.length > 0
        ) {
          progressText.textContent = `Progress: ${result.prompts.length} prompts remaining`;
          promptInput.value = result.prompts.join("\n");
        } else if (result.savedPromptText !== undefined) {
          promptInput.value = result.savedPromptText;
        }

        // Restore dropdown settings if they were auto-saved
        if (result.aspectRatio) {
          aspectRatioSelect.value = result.aspectRatio;
        }
        if (result.imageStyle) {
          imageStyleSelect.value = result.imageStyle;
        }
        if (result.savedDownloadCount) {
          downloadCountSelect.value = result.savedDownloadCount;
        }
        if (result.savedDebugMode !== undefined) {
          isDebugMode = result.savedDebugMode === true;
          debugModeSelect.value = isDebugMode ? "true" : "false";
        }

        // Restore failed/skipped prompts log if auto-saved
        if (result.savedFailedPrompts) {
          failedPromptsTextarea.value = result.savedFailedPrompts;
        }

        // Check for lastProcessedPromptIndex and display resume message if needed
        if (result.lastProcessedPromptIndex > 0) {
          const statusContainer = document.getElementById("status-container");
          if (statusContainer) {
            const resumeMessage = document.createElement("div");
            resumeMessage.className = "resume-message";
            resumeMessage.textContent = `Resume from prompt #${result.lastProcessedPromptIndex + 1}?`;
            statusContainer.appendChild(resumeMessage);
          }
        }

        // 🌟 FORCE CHECK ON PANEL LOAD
        // As soon as the panel opens, check reality and force the button to match.
        syncRunButtonUI(result.isAutomating === true);
      }
    },
  );

  // Global storage listener to keep UI in sync if automation state changes elsewhere
  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName === "local") {
      // Handle automation state changes
      if (changes.isAutomating) {
        const isNowAutomating = changes.isAutomating.newValue;
        syncRunButtonUI(isNowAutomating === true);
      }

      // Handle stats updates
      if (changes.sessionStats) {
        updateStatsUI(changes.sessionStats.newValue);
      }
    }
  });

  // Muat folder dari storage saat panel dibuka
  const downloadFolderInput = document.getElementById("downloadFolderInput");
  chrome.storage.local.get(["downloadFolder"], (res) => {
    if (downloadFolderInput && res.downloadFolder !== undefined) {
      downloadFolderInput.value = res.downloadFolder;
    }
  });
}

function handleStartClick() {
  chrome.storage.local.get(
    ["isAutomating", "lastProcessedPromptIndex"],
    (result) => {
      const isCurrentlyRunning = result.isAutomating === true;

      if (isCurrentlyRunning) {
        // WE ARE STOPPING
        chrome.storage.local.set({ isAutomating: false, step: "IDLE" });
        statusText.textContent = "Stopping automation...";
        statusDot.style.backgroundColor = "#ef4444";
        statusDot.classList.remove("active");

        chrome.tabs.query({ url: "*://*.canva.com/dream-lab*" }, (tabs) => {
          if (tabs.length === 0) {
            console.warn("No active Dream Lab tab found.");
            return;
          }
          if (tabs && tabs.length > 0) {
            chrome.tabs.sendMessage(
              tabs[0].id,
              { action: "STOP_AUTOMATION" },
              (response) => {
                if (chrome.runtime.lastError) {
                  console.warn(
                    "[Panel] sendMessage failed:",
                    chrome.runtime.lastError.message,
                  );
                  statusText.textContent =
                    "Error: Cannot communicate with Canva tab. Please refresh.";
                  statusDot.style.backgroundColor = "#ef4444";
                  statusDot.classList.remove("active");
                  chrome.storage.local.set({ isAutomating: false });
                  return;
                }
              },
            );
          }
        });
      } else {
        // WE ARE STARTING
        chrome.storage.local.set({ isPaused: false });
        const rawPromptText = promptInput.value;
        const promptsArray = rawPromptText
          .split("\n")
          .map((p) => sanitizeInput(p.trim()))
          .filter((p) => p.length > 0);

        // Expand prompts with {i} placeholder
        let expandedPrompts = [];
        for (let p of promptsArray) {
          if (p.includes("{i}")) {
            // Tanya user berapa iterasi
            const iterationsInput = prompt(
              `Prompt "${p}" mengandung {i}. Berapa jumlah iterasi yang diinginkan?`,
              "5",
            );
            if (iterationsInput === null) {
              // User cancel, skip ekspansi, gunakan prompt asli
              expandedPrompts.push(p);
              continue;
            }
            const iterations = parseInt(iterationsInput, 10);
            if (isNaN(iterations) || iterations < 1) {
              alert(
                "Jumlah iterasi harus berupa angka positif. Prompt akan digunakan apa adanya.",
              );
              expandedPrompts.push(p);
              continue;
            }
            // Ekspansi prompt
            const expanded = expandPromptWithVariable(p, iterations);
            expandedPrompts.push(...expanded);
          } else {
            expandedPrompts.push(p);
          }
        }

        // Ganti promptsArray dengan hasil ekspansi
        promptsArray.length = 0;
        promptsArray.push(...expandedPrompts);

        // UPDATE UI DAN STORAGE SEKALI SAJA DI AKHIR UNTUK MENCEGAH LAG
        const finalPromptText = promptsArray.join("\n");
        promptInput.value = finalPromptText;
        chrome.storage.local.set({ savedPromptText: finalPromptText });

        if (promptsArray.length === 0) {
          alert("Please enter at least one prompt!");
          return;
        }

        failedPromptsTextarea.value = "";
        chrome.storage.local.set({ savedFailedPrompts: "" });

        // Check if we're resuming from a previous session
        let startIndex = 0;
        if (result.lastProcessedPromptIndex > 0) {
          startIndex = result.lastProcessedPromptIndex;
          // Remove already processed prompts from the array
          const remainingPrompts = promptsArray.slice(startIndex);
          progressText.textContent = `Progress: ${remainingPrompts.length} prompts remaining (resuming from #${startIndex + 1})`;
        } else {
          progressText.textContent = `Progress: ${promptsArray.length} prompts remaining`;
        }

        statusText.textContent = "Starting...";

        const state = {
          isAutomating: true,
          step: "INJECT_PROMPT",
          prompts: promptsArray,
          aspectRatio: aspectRatioSelect.value,
          imageStyle: imageStyleSelect.value,
          downloadCount: downloadCountSelect.value,
        };

        // Setting isAutomating: true will trigger the onChanged listener -> syncRunButtonUI(true)
        chrome.storage.local.set(state, () => {
          console.log(
            "[NRA DreamLab] Bulk automation state saved:",
            state,
          );
          chrome.tabs.query(
            { url: "*://*.canva.com/dream-lab*" },
            (tabs) => {
              if (tabs.length === 0) {
                console.warn("No active Dream Lab tab found.");
                return;
              }
              if (tabs && tabs.length > 0) {
                chrome.tabs.sendMessage(
                  tabs[0].id,
                  { action: "START_AUTOMATION" },
                  (response) => {
                    if (chrome.runtime.lastError) {
                      console.warn(
                        "[Panel] sendMessage failed:",
                        chrome.runtime.lastError.message,
                      );
                      statusText.textContent =
                        "Error: Cannot communicate with Canva tab. Please refresh.";
                      statusDot.style.backgroundColor = "#ef4444";
                      statusDot.classList.remove("active");
                      chrome.storage.local.set({ isAutomating: false }); // Revert state safely
                      return;
                    }
                  },
                );
              }
            },
          );
        });
      }
    },
  );
}

function handlePauseClick() {
  chrome.storage.local.get(["isPaused"], (res) => {
    const newState = !res.isPaused;
    chrome.storage.local.set({ isPaused: newState });
    const pauseButton = document.getElementById("pauseButton");
    if (pauseButton) {
      pauseButton.textContent = newState ? "▶ RESUME" : "⏸ PAUSE";
      pauseButton.style.background = newState ? "#2ecc71" : "#f39c12";
      pauseButton.style.borderColor = newState ? "#2ecc71" : "#f39c12";
      pauseButton.style.boxShadow = newState
        ? "4px 4px 0px #27ae60"
        : "4px 4px 0px #b9770e";
    }
  });
}

function initEventListeners() {
  const buttons = {
    startBtn: { id: "startBtn", event: "click", handler: handleStartClick },
    pauseButton: { id: "pauseButton", event: "click", handler: handlePauseClick },
    settingsBtn: { id: "settingsBtn", event: "click", handler: () => {
      const modal = document.getElementById("settingsModal");
      if (modal) {
        modal.classList.remove("hidden");
        document.body.classList.add("modal-open");
      }
    }},
    closeSettingsBtn: { id: "closeSettingsBtn", event: "click", handler: () => {
      const modal = document.getElementById("settingsModal");
      if (modal) {
        modal.classList.add("hidden");
        document.body.classList.remove("modal-open");
      }
    }},
    importFileBtn: { id: "importFileBtn", event: "click", handler: () => document.getElementById("fileInput").click() },
    exportLogsBtn: { id: "exportLogsBtn", event: "click", handler: () => {
      const logs = document.getElementById("consoleLogs").innerText;
      const blob = new Blob([logs], { type: "text/plain" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Canva_Logs_${new Date().getTime()}.txt`;
      a.click();
      URL.revokeObjectURL(url);
    }},
    clearLogsBtn: { id: "clearLogsBtn", event: "click", handler: () => {
      const consoleLogs = document.getElementById("consoleLogs");
      if (consoleLogs) consoleLogs.innerHTML = "";
    }},
    resetStatsBtn: { id: "resetStatsBtn", event: "click", handler: () => {
      if (confirm("Reset seluruh data Session Analytics ke 0?")) {
        const emptyStats = { startTime: null, successCount: 0, downloadCount: 0, totalCooldowns: 0, totalPrompts: 0, failedCount: 0 };
        chrome.storage.local.set({ sessionStats: emptyStats }, () => { updateStatsUI(emptyStats); });
      }
    }},
    retryQuarantineBtn: { id: "retryQuarantineBtn", event: "click", handler: () => {
      const qInput = document.getElementById("quarantineInput");
      if (!qInput || !qInput.value.trim()) return alert("Quarantine kosong!");
      promptInput.value = (promptInput.value ? promptInput.value + "\n" : "") + qInput.value.trim();
      qInput.value = "";
      chrome.storage.local.set({ savedPromptText: promptInput.value, savedFailedPrompts: "" });
    }},
    clearQuarantineBtn: { id: "clearQuarantineBtn", event: "click", handler: () => {
      const qInput = document.getElementById("quarantineInput");
      if (qInput) { qInput.value = ""; chrome.storage.local.set({ savedFailedPrompts: "" }); }
    }},
    openDreamLabBtn: { id: "openDreamLabBtn", event: "click", handler: () => { chrome.tabs.create({ url: "https://www.canva.com/dream-lab" }); }},
    clearPromptsBtn: { id: "clearPromptsBtn", event: "click", handler: () => {
      if (confirm("Are you sure you want to clear all prompts?")) {
        if (promptInput) {
          promptInput.value = "";
          chrome.storage.local.set({ savedPromptText: "", lastProcessedPromptIndex: 0 });
          if (progressText) progressText.textContent = "Progress: 0 prompts remaining";
          const rm = document.querySelector(".resume-message");
          if (rm) rm.remove();
        }
      }
    }}
  };

  Object.keys(buttons).forEach(key => {
    const b = buttons[key];
    const el = document.getElementById(b.id);
    if (el) {
      el.addEventListener(b.event, (e) => {
        try { b.handler(e); } catch (err) { console.error(`Error pada ${b.id}:`, err); }
      });
    }
  });

  // Listener Input file (Pindahkan ke luar loop)
  const fileInput = document.getElementById("fileInput");
  if (fileInput) {
    fileInput.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (ev) => {
        promptInput.value = (promptInput.value ? promptInput.value + "\n" : "") + ev.target.result.trim();
        chrome.storage.local.set({ savedPromptText: promptInput.value });
      };
      reader.readAsText(file);
    });
  }

  // Real-time Save (Input/Change Listeners to prevent data loss)
  let saveTimeout;
  if (promptInput) {
    promptInput.addEventListener("input", () => {
      clearTimeout(saveTimeout);
      saveTimeout = setTimeout(() => {
        chrome.storage.local.set({ savedPromptText: promptInput.value });
      }, 500); // 500ms debounce
    });
  }

  if (aspectRatioSelect) {
    aspectRatioSelect.addEventListener("change", () => {
      chrome.storage.local.set({ savedAspectRatio: aspectRatioSelect.value });
    });
  }

  if (imageStyleSelect) {
    imageStyleSelect.addEventListener("change", () => {
      chrome.storage.local.set({ savedImageStyle: imageStyleSelect.value });
    });
  }

  if (downloadCountSelect) {
    downloadCountSelect.addEventListener("change", () => {
      chrome.storage.local.set({ savedDownloadCount: downloadCountSelect.value });
    });
  }

  if (debugModeSelect) {
    debugModeSelect.addEventListener("change", () => {
      isDebugMode = debugModeSelect.value === "true";
      chrome.storage.local.set({ savedDebugMode: isDebugMode });
    });
  }

  const subfolderToggle = document.getElementById("subfolderToggle");
  if (subfolderToggle) {
    subfolderToggle.addEventListener("change", () => {
      chrome.storage.local.set({ createSubfolder: subfolderToggle.checked });
    });
  }

  const downloadFolderInput = document.getElementById("downloadFolderInput");
  if (downloadFolderInput) {
    downloadFolderInput.addEventListener("change", () => {
      const folder = downloadFolderInput.value.trim();
      chrome.storage.local.set({ downloadFolder: folder });
      console.log(
        "[NRA DreamLab] 📁 Download folder set to:",
        folder || "(default)",
      );
    });
  }

  const verboseLogsToggle = document.getElementById("verboseLogsToggle");
  if (verboseLogsToggle) {
    verboseLogsToggle.addEventListener("change", () => {
      chrome.storage.local.set({ verboseLogs: verboseLogsToggle.checked });
    });
  }
}

document.addEventListener("DOMContentLoaded", () => {
  console.log(
    "[Panel] DOMContentLoaded fired. Event listeners are being attached...",
  );
  window.addEventListener("unhandledrejection", function (event) {
    console.error("[Panel] Unhandled Promise rejection:", event.reason);
    if (statusText) {
      statusText.textContent = `Error: ${event.reason?.message || "Unknown error"}`;
    }
    event.preventDefault();
  });

  initUIElements();
  initStorageListeners();
  initEventListeners();
  initCollapseLogic();
  initMessageListeners();
  initExtendedFeatures();
}); // End of DOMContentLoaded

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
        iconUrl: "icon.png",
        title: "Canva Auto Prompter",
        message: "Success! All prompts have been processed.",
      },
      (id) => {
        if (chrome.runtime.lastError) {
          console.warn(
            "[Canva Auto Prompter] Notification alert failed:",
            chrome.runtime.lastError.message,
          );
        }
      },
    );
  }
}

function initMessageListeners() {
  // Helper to visually show tab status and progress on load
  chrome.tabs.query({ url: "*://*.canva.com/dream-lab*" }, (tabs) => {
    if (tabs && tabs.length > 0) {
      statusText.textContent = "Canva Connected";
      statusDot.classList.add("active");
      statusDot.style.backgroundColor = "#10b981";
    } else {
      statusText.textContent = "Please open Canva Dream Lab";
      statusDot.classList.remove("active");
      statusDot.style.backgroundColor = "#ef4444";
    }
  });

  // Listen for STATUS_UPDATE or direct status/progress/UI synchronization messages from content.js
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (!request) return false;

    // WARN-7 FIX: Only handle actions explicitly intended for the panel.
    // Ignore CDP/debugger commands so we don't hijack background.js responses.
    const PANEL_ACTIONS = new Set([
      "CONSOLE_LOG",
      "PROMPT_FAILED",
      "UPDATE_TEXTAREA",
      "STATUS_UPDATE",
      "PROGRESS_UPDATE",
      "PLAY_COMPLETION_SOUND",
      "UPDATE_STATS",
    ]);

    // If message has an action that is NOT for the panel, return early without responding
    if (request.action && !PANEL_ACTIONS.has(request.action)) {
      return false; // Do not call sendResponse, do not keep channel open
    }

    if (request.action === "CONSOLE_LOG") {
      // Block verbose INFO logs if Debug Mode is Off
      if (!isDebugMode && request.level === "INFO") {
        sendResponse({ success: true });
        return true;
      }

      if (consoleLogs) {
        const time = new Date().toLocaleTimeString("en-US", { hour12: false });
        const prefix =
          request.level === "ERROR"
            ? "[!]"
            : request.level === "WARN"
              ? "[?]"
              : "[>]";

        const logDiv = document.createElement("div");
        logDiv.className = `log-entry log-${request.level.toLowerCase()}`;
        logDiv.textContent = `${time} ${prefix} ${request.message}`;

        consoleLogs.appendChild(logDiv);

        // OPT-7 FIX: Cap terminal log DOM nodes to prevent memory bloat on long sessions
        const MAX_LOG_ENTRIES = 500;
        while (consoleLogs.childElementCount > MAX_LOG_ENTRIES) {
          consoleLogs.removeChild(consoleLogs.firstElementChild);
        }

        consoleLogs.scrollTop = consoleLogs.scrollHeight; // Auto-scroll
      }
      sendResponse({ success: true });
      return true;
    }

    // Handle failed/skipped prompt reporting
    if (request.action === "PROMPT_FAILED") {
      const qInput = document.getElementById("quarantineInput");
      if (qInput) {
        let raw = request.failedPrompt;

        // Ekstraksi teks aman
        let text = (typeof raw === 'object' && raw !== null)
          ? (raw.text || raw.prompt || JSON.stringify(raw))
          : String(raw);

        // Gunakan metode elemen DOM untuk membersihkan HTML secara total
        const tempDiv = document.createElement("div");
        tempDiv.innerHTML = text;
        const cleanPrompt = tempDiv.textContent || tempDiv.innerText || "";

        // Simpan sebagai teks murni dengan trim
        const finalPrompt = cleanPrompt.replace(/\s+/g, " ").trim();

        qInput.value = (qInput.value ? qInput.value + "\n" : "") + finalPrompt;
        chrome.storage.local.set({ savedFailedPrompts: qInput.value });
      }
      sendResponse({ success: true });
      return true;
    }

    // Direct UI update for the destructive Queue
    if (request.action === "UPDATE_TEXTAREA") {
      promptInput.value = request.remainingPrompts.join("\n");
      progressText.textContent = `Progress: ${request.remainingPrompts.length} prompts remaining`;
      chrome.storage.local.set({ savedPromptText: promptInput.value });
      sendResponse({ success: true });
      return true;
    }

    // Handle progress
    if (request.action === "PROGRESS_UPDATE") {
      if (progressText) progressText.textContent = request.progress;
      sendResponse({ success: true });
      return true;
    }

    // Handle completion sound
    if (request.action === "PLAY_COMPLETION_SOUND") {
      playAlertSound();
      sendResponse({ success: true });
      return true;
    }

    // Handle stats update for analytics dashboard
    if (request.action === "UPDATE_STATS") {
      updateStatsUI(request.stats);
      sendResponse({ success: true });
      return true;
    }

    const statusValue =
      request.status ||
      (request.action === "STATUS_UPDATE" ? request.status : null);

    if (statusValue) {
      console.log("[NRA DreamLab] Received status update:", statusValue);
      statusText.textContent = statusValue;
      statusText.style.whiteSpace = "nowrap";
      statusText.style.overflow = "hidden";
      statusText.style.textOverflow = "ellipsis";
      statusText.style.maxWidth = "250px";
      statusText.style.display = "inline-block";
      statusText.style.verticalAlign = "middle";

      const statusLower = statusValue.toLowerCase();
      if (
        statusLower.includes("error") ||
        statusLower.includes("stopped") ||
        statusLower.includes("complete")
      ) {
        syncRunButtonUI(false);

        if (statusLower.includes("error")) {
          statusDot.style.backgroundColor = "#ef4444";
          statusDot.classList.remove("active");
        } else {
          statusDot.style.backgroundColor = "#10b981";
          statusDot.classList.add("active");

          // Trigger alerts on clean completion
          if (statusLower.includes("complete")) {
            playAlertSound();
            showBrowserNotification();
          }
        }
      } else {
        // Active automation pulse
        statusDot.style.backgroundColor = "#a855f7";
        statusDot.classList.add("active");
      }

      // Dynamically fetch and synchronize progress text from local storage
      chrome.storage.local.get(["prompts"], (result) => {
        if (result && result.prompts) {
          progressText.textContent = `Progress: ${result.prompts.length} prompts remaining`;
        }
      });
    }

    // Respond to acknowledged status/progress messages
    sendResponse({ success: true });
    return true; // Keep channel open
  });
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

function initExtendedFeatures() {
  // Save Delay Slider
  const saveDelaySlider = document.getElementById("saveDelaySlider");
  const saveDelayVal = document.getElementById("saveDelayVal");
  if (saveDelaySlider && saveDelayVal) {
    chrome.storage.local.get(["saveDelay"], function (res) {
      const savedDelay = parseInt(res.saveDelay, 10) || 6;
      saveDelaySlider.value = savedDelay;
      saveDelayVal.textContent = savedDelay;
    });
    saveDelaySlider.addEventListener("input", function () {
      const val = parseInt(this.value, 10);
      saveDelayVal.textContent = val;
      chrome.storage.local.set({ saveDelay: val });
    });
  }

  // 1. Toggle Debug Mode
  const debugModeSelect = document.getElementById("debugMode");
  if (debugModeSelect) {
    debugModeSelect.addEventListener("change", () => {
      chrome.storage.local.set({ debugMode: debugModeSelect.value === "true" });
    });
  }

  // 2. Toggle Verbose Logs
  const verboseLogsToggle = document.getElementById("verboseLogsToggle");
  if (verboseLogsToggle) {
    verboseLogsToggle.addEventListener("change", () => {
      chrome.storage.local.set({ verboseLogs: verboseLogsToggle.checked });
    });
  }

  // 3. Toggle Subfolder
  const subfolderToggle = document.getElementById("subfolderToggle");
  if (subfolderToggle) {
    subfolderToggle.addEventListener("change", () => {
      chrome.storage.local.set({ useSubfolder: subfolderToggle.checked });
    });
  }

  // 4. Custom Download Folder
  const downloadFolderInput = document.getElementById("downloadFolderInput");
  if (downloadFolderInput) {
    downloadFolderInput.addEventListener("change", () => {
      chrome.storage.local.set({ customDownloadFolder: downloadFolderInput.value.trim() });
    });
  }

  // 5. Safety Delay
  if (safetyDelaySlider && safetyDelayVal) {
    safetyDelaySlider.addEventListener("input", () => {
      safetyDelayVal.textContent = safetyDelaySlider.value;
      chrome.storage.local.set({
        safetyDelay: parseInt(safetyDelaySlider.value, 10),
      });
    });
  }

  // 6. Save Delay
  if (saveDelaySlider && saveDelayVal) {
    // Muat nilai saat panel dibuka
    chrome.storage.local.get(["saveDelay"], (res) => {
      const val = res.saveDelay || 6;
      saveDelaySlider.value = val;
      saveDelayVal.textContent = val;
    });
    // Listener input
    saveDelaySlider.addEventListener("input", () => {
      const val = saveDelaySlider.value;
      saveDelayVal.textContent = val;
      chrome.storage.local.set({ saveDelay: parseInt(val, 10) });
    });
  }

  // --- GOD-TIER 6-FEATURE UPDATE LOGIC ---
  // 1. Bulk File Importer
  const importFileBtn = document.getElementById("importFileBtn");
  const fileInput = document.getElementById("fileInput");
  if (importFileBtn && fileInput) {
    importFileBtn.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (event) => {
        const promptInput = document.getElementById("promptInput");
        const content = event.target.result;
        const sanitizedContent = content
          .split("\n")
          .map((line) => sanitizeInput(line))
          .join("\n");
        promptInput.value =
          promptInput.value +
          (promptInput.value ? "\n" : "") +
          sanitizedContent;
        chrome.storage.local.set({ savedPromptText: promptInput.value });
      };
      reader.readAsText(file);
    });
  }

  // 2. Export Logs
  const exportLogsBtn = document.getElementById("exportLogsBtn");
  if (exportLogsBtn) {
    exportLogsBtn.addEventListener("click", () => {
      const logs = document.getElementById("consoleLogs").innerText;
      const blob = new Blob([logs], { type: "text/plain" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Canva_Logs_${new Date().getTime()}.txt`;
      a.click();
      URL.revokeObjectURL(url);
    });
  }

  // 3. Pause / Resume Toggle
  const pauseButton = document.getElementById("pauseButton");
  if (pauseButton) {
    pauseButton.addEventListener("click", () => {
      chrome.storage.local.get(["isPaused"], (res) => {
        const newState = !res.isPaused;
        chrome.storage.local.set({ isPaused: newState });
        pauseButton.textContent = newState ? "▶ RESUME" : "⏸ PAUSE";
        pauseButton.style.background = newState ? "#2ecc71" : "#f39c12";
        pauseButton.style.borderColor = newState ? "#2ecc71" : "#f39c12";
        pauseButton.style.boxShadow = newState
          ? "4px 4px 0px #27ae60"
          : "4px 4px 0px #b9770e";
      });
    });
  }

  // 4. Quarantine Catch Listener
  chrome.runtime.onMessage.addListener((request) => {
    if (request.action === "PROMPT_FAILED") {
      const qInput = document.getElementById("quarantineInput");
      if (qInput) {
        let raw = request.failedPrompt;

        let text = (typeof raw === 'object' && raw !== null)
          ? (raw.text || raw.prompt || JSON.stringify(raw))
          : String(raw);

        const doc = new DOMParser().parseFromString(text, "text/html");
        text = doc.documentElement.textContent;

        const cleanPrompt = text.replace(/<[^>]*>/g, "").replace(/\s+/g, " ").trim();

        qInput.value = (qInput.value ? qInput.value + "\n" : "") + cleanPrompt;
        chrome.storage.local.set({ savedFailedPrompts: qInput.value });
      }
    }
  });

  // 5. Retry Quarantine Logic - Pindahkan semua prompt dari Quarantine ke Prompt Input utama
  const retryQuarantineBtn = document.getElementById("retryQuarantineBtn");
  if (retryQuarantineBtn) {
    retryQuarantineBtn.addEventListener("click", () => {
      const quarantineInput = document.getElementById("quarantineInput");
      const promptInput = document.getElementById("promptInput");
      const quarantineText = quarantineInput.value.trim();

      // Jika quarantine kosong, beri tahu user
      if (!quarantineText) {
        alert("Tidak ada prompt di Quarantine untuk diulang.");
        return;
      }

      // Append teks quarantine ke prompt input utama
      if (promptInput.value.trim()) {
        promptInput.value += "\n" + quarantineText;
      } else {
        promptInput.value = quarantineText;
      }

      // Kosongkan quarantine
      quarantineInput.value = "";

      // Simpan ke Chrome Storage
      chrome.storage.local.set({
        savedPromptText: promptInput.value,
        savedFailedPrompts: "",
      });

      // Update progress text (opsional)
      const progressText = document.getElementById("progressText");
      const currentPrompts = promptInput.value
        .split("\n")
        .filter((p) => p.trim().length > 0);
      if (progressText) {
        progressText.textContent = `Progress: ${currentPrompts.length} prompts remaining (with retry)`;
      }

      console.log(
        "[NRA DreamLab] ✅ Quarantined prompts moved back to main queue.",
      );
    });
  }

  // --- UTILITY ICONS LOGIC ---

  // 1. Open Dream Lab Shortcut
  const openDreamLabBtn = document.getElementById("openDreamLabBtn");
  if (openDreamLabBtn) {
    openDreamLabBtn.addEventListener("click", () => {
      chrome.tabs.create({ url: "https://www.canva.com/dream-lab" });
    });
  }

  // 2. Clear Prompts Trash Can
  const clearPromptsBtn = document.getElementById("clearPromptsBtn");
  if (clearPromptsBtn) {
    // Connection handshake function
    async function initConnection() {
      return new Promise((resolve) => {
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
          if (tabs.length === 0) {
            resolve(false);
            return;
          }

          const timeout = setTimeout(() => {
            resolve(false);
          }, 2000);

          chrome.tabs.sendMessage(
            tabs[0].id,
            { action: "PING" },
            (response) => {
              clearTimeout(timeout);
              if (chrome.runtime.lastError) {
                resolve(false);
              } else {
                resolve(response?.status === "READY");
              }
            },
          );
        });
      });
    }

    // Modify the existing error handling logic
    async function checkConnection() {
      const isConnected = await initConnection();

      if (isConnected) {
        statusText.textContent = "Connected";
        statusDot.classList.add("active");
      } else {
        statusText.textContent = "Error: Please refresh the Canva tab";
        statusDot.classList.remove("active");
      }
    }

    // Call this function when the panel loads
    checkConnection();

    clearPromptsBtn.addEventListener("click", () => {
      if (confirm("Are you sure you want to clear all prompts?")) {
        const promptInput = document.getElementById("promptInput");
        if (promptInput) {
          promptInput.value = "";
          chrome.storage.local.set({
            savedPromptText: "",
            lastProcessedPromptIndex: 0,
          });

          const progressText = document.getElementById("progressText");
          if (progressText)
            progressText.textContent = "Progress: 0 prompts remaining";

          // Remove resume message if it exists
          const resumeMessage = document.querySelector(".resume-message");
          if (resumeMessage) {
            resumeMessage.remove();
          }
        }
      }
    });
  }
  // 3. Clear Terminal Logs Trash Can
  const clearLogsBtn = document.getElementById("clearLogsBtn");
  if (clearLogsBtn) {
    clearLogsBtn.addEventListener("click", () => {
      const consoleLogs = document.getElementById("consoleLogs");
      if (consoleLogs) {
        consoleLogs.innerHTML = ""; // Wipe all log divs
      }
    });
  }

  // 4. Reset Session Analytics
  const resetStatsBtn = document.getElementById("resetStatsBtn");
  if (resetStatsBtn) {
    resetStatsBtn.addEventListener("click", () => {
      if (confirm("Reset seluruh data Session Analytics ke 0?")) {
        const emptyStats = {
          startTime: null,
          successCount: 0,
          downloadCount: 0,
          totalCooldowns: 0,
          totalPrompts: 0,
          failedCount: 0
        };
        chrome.storage.local.set({ sessionStats: emptyStats }, () => {
          updateStatsUI(emptyStats);
          console.log("[NRA DreamLab] 🔄 Session analytics telah direset.");
        });
      }
    });
  }

  // --- UI SETTINGS MODAL LOGIC ---
  const settingsBtn = document.getElementById("settingsBtn");
  const closeSettingsBtn = document.getElementById("closeSettingsBtn");
  const settingsModal = document.getElementById("settingsModal");
  const themeSelect = document.getElementById("themeSelect");
  const fontSelect = document.getElementById("fontSelect");
  const batchLimitInput = document.getElementById("batchLimitInput");
  const safetyDelaySlider = document.getElementById("safetyDelaySlider");
  const safetyDelayVal = document.getElementById("safetyDelayVal");
  const soundToggle = document.getElementById("soundToggle");

  // Open settings modal
  if (settingsBtn) {
    settingsBtn.addEventListener("click", () => {
      settingsModal.classList.remove("hidden");
      document.body.classList.add("modal-open");
    });
  }

  // Close settings modal
  if (closeSettingsBtn) {
    closeSettingsBtn.addEventListener("click", () => {
      settingsModal.classList.add("hidden");
      document.body.classList.remove("modal-open");
    });
  }

  // Close modal when clicking outside
  if (settingsModal) {
    settingsModal.addEventListener("click", (e) => {
      if (e.target === settingsModal) {
        settingsModal.classList.add("hidden");
        document.body.classList.remove("modal-open");
      }
    });
  }

  // Save and apply on change
  if (themeSelect) {
    themeSelect.addEventListener("change", () => {
      chrome.storage.local.set({ uiTheme: themeSelect.value });
      applyCustomUI(themeSelect.value, fontSelect.value);
    });
  }

  if (fontSelect) {
    fontSelect.addEventListener("change", () => {
      chrome.storage.local.set({ uiFont: fontSelect.value });
      applyCustomUI(themeSelect.value, fontSelect.value);
    });
  }

  // Advanced Settings Listeners
  if (safetyDelaySlider && safetyDelayVal) {
    safetyDelaySlider.addEventListener("input", () => {
      safetyDelayVal.textContent = safetyDelaySlider.value;
      chrome.storage.local.set({
        safetyDelay: parseInt(safetyDelaySlider.value, 10),
      });
    });
  }

  if (batchLimitInput) {
    batchLimitInput.addEventListener("change", () => {
      chrome.storage.local.set({
        batchLimit: parseInt(batchLimitInput.value, 10) || 0,
      });
    });
  }

  if (soundToggle) {
    soundToggle.addEventListener("change", () => {
      chrome.storage.local.set({ playSounds: soundToggle.checked });
    });
  }

  const typingModeSelect = document.getElementById("typingModeSelect");
  if (typingModeSelect) {
    typingModeSelect.addEventListener("change", () => {
      chrome.storage.local.set({ typingMode: typingModeSelect.value });
    });
  }

  // 6. Customize Shortcut Button - Buka halaman shortcut Chrome
  const customizeShortcutBtn = document.getElementById("customizeShortcutBtn");
  if (customizeShortcutBtn) {
    customizeShortcutBtn.addEventListener("click", () => {
      // Buka tab baru ke halaman shortcut extensions
      chrome.tabs.create({ url: "chrome://extensions/shortcuts" });
    });
  }

  // Tapi kita bisa deteksi OS untuk menampilkan shortcut yang sesuai
  function updateShortcutDisplay() {
    const isMac = navigator.platform.toUpperCase().indexOf("MAC") >= 0;
    const shortcutDisplay = document.getElementById("shortcutDisplay");
    if (shortcutDisplay) {
      if (isMac) {
        shortcutDisplay.textContent = "Cmd+Shift+P";
      } else {
        shortcutDisplay.textContent = "Ctrl+Shift+P";
      }
    }
  }
  updateShortcutDisplay();

  // ==========================================
  // 7. PROMPT PRESETS (Save, Load, Delete)
  // ==========================================
  const presetNameInput = document.getElementById('presetNameInput');
  const savePresetBtn = document.getElementById('savePresetBtn');
  const presetSelect = document.getElementById('presetSelect');
  const loadPresetBtn = document.getElementById('loadPresetBtn');
  const deletePresetBtn = document.getElementById('deletePresetBtn');

  function loadPresetsList() {
    chrome.storage.local.get(['promptPresets'], (result) => {
      const presets = result.promptPresets || {};
      const presetKeys = Object.keys(presets);
      presetSelect.innerHTML = '<option value="">-- Load Preset --</option>';
      presetKeys.sort().forEach((key) => {
        const option = document.createElement('option');
        option.value = key;
        option.textContent = key;
        presetSelect.appendChild(option);
      });
    });
  }

  function savePreset() {
    const name = presetNameInput.value.trim();
    if (!name) return alert('Masukkan nama preset terlebih dahulu!');
    const promptText = promptInput.value.trim();
    if (!promptText) return alert('Prompt text kosong! Tidak ada yang bisa disimpan.');
    chrome.storage.local.get(['promptPresets'], (result) => {
      const presets = result.promptPresets || {};
      if (presets[name] !== undefined) {
        if (!confirm('Preset "' + name + '" sudah ada. Timpa dengan yang baru?')) return;
      }
      presets[name] = promptText;
      chrome.storage.local.set({ promptPresets: presets }, () => {
        console.log('[Canva Auto Prompter] ✅ Preset "' + name + '" berhasil disimpan.');
        presetNameInput.value = '';
        loadPresetsList();
        savePresetBtn.textContent = '✅ Saved!';
        setTimeout(() => savePresetBtn.textContent = '💾 Save', 1500);
      });
    });
  }

  function loadPreset() {
    const selectedKey = presetSelect.value;
    if (!selectedKey) return alert('Pilih preset terlebih dahulu dari dropdown!');
    chrome.storage.local.get(['promptPresets'], (result) => {
      const presets = result.promptPresets || {};
      const promptText = presets[selectedKey];
      if (promptText) {
        promptInput.value = promptText;
        chrome.storage.local.set({ savedPromptText: promptText });
        const lines = promptText.split('\n').filter(p => p.trim().length > 0);
        if (progressText) progressText.textContent = 'Progress: ' + lines.length + ' prompts loaded from preset';
        console.log('[Canva Auto Prompter] 📂 Preset "' + selectedKey + '" berhasil dimuat.');
        loadPresetBtn.textContent = '✅ Loaded!';
        setTimeout(() => loadPresetBtn.textContent = '📂 Load', 1500);
      } else {
        alert('Preset "' + selectedKey + '" tidak ditemukan.');
      }
    });
  }

  function deletePreset() {
    const selectedKey = presetSelect.value;
    if (!selectedKey) return alert('Pilih preset yang ingin dihapus dari dropdown!');
    if (!confirm('Hapus preset "' + selectedKey + '" secara permanen?')) return;
    chrome.storage.local.get(['promptPresets'], (result) => {
      const presets = result.promptPresets || {};
      delete presets[selectedKey];
      chrome.storage.local.set({ promptPresets: presets }, () => {
        console.log('[Canva Auto Prompter] 🗑️ Preset "' + selectedKey + '" berhasil dihapus.');
        loadPresetsList();
        deletePresetBtn.textContent = '✅ Deleted!';
        setTimeout(() => deletePresetBtn.textContent = '🗑️ Del', 1500);
      });
    });
  }

  if (savePresetBtn) savePresetBtn.addEventListener('click', savePreset);
  if (loadPresetBtn) loadPresetBtn.addEventListener('click', loadPreset);
  if (deletePresetBtn) deletePresetBtn.addEventListener('click', deletePreset);
  if (presetNameInput) {
    presetNameInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); savePreset(); }
    });
  }
  loadPresetsList();
}

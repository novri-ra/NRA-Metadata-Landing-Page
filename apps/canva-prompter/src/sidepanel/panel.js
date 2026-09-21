// panel.js
// Side panel orchestration: storage listeners, run/pause controls, message handling,
// settings/presets logic, and the Canva connection check.

// ==========================================
// Connection Check (Fix #2: single source of truth)
// ==========================================
function setConnectionStatusUI(kind) {
  if (!statusText || !statusDot) return;

  if (kind === "connected") {
    statusText.textContent = "Canva Connected";
    statusDot.classList.add("active");
    statusDot.style.backgroundColor = "#10b981";
    if (startBtn && !isRunning) {
      startBtn.disabled = false;
      startBtn.style.opacity = "1";
      startBtn.style.cursor = "pointer";
    }
  } else if (kind === "not-ready") {
    statusText.textContent = "Error: Please refresh the Canva tab";
    statusDot.classList.remove("active");
    statusDot.style.backgroundColor = "#ef4444";
    if (startBtn) {
      startBtn.disabled = true;
      startBtn.style.opacity = "0.5";
      startBtn.style.cursor = "not-allowed";
    }
  } else {
    statusText.textContent = "Please open Canva Dream Lab";
    statusDot.classList.remove("active");
    statusDot.style.backgroundColor = "#ef4444";
    if (startBtn) {
      startBtn.disabled = true;
      startBtn.style.opacity = "0.5";
      startBtn.style.cursor = "not-allowed";
    }
  }
}

function syncConnectionStatus(onlyIfError = false) {
  chrome.tabs.query({ url: "*://*.canva.com/dream-lab*" }, (tabs) => {
    if (!tabs || tabs.length === 0) {
      if (onlyIfError && statusText && !(statusText.textContent.includes("Error") || statusText.textContent.includes("Please open"))) {
        return;
      }
      setConnectionStatusUI("disconnected");
      return;
    }

    // Tab terbuka & halaman dream-lab ada -> status CONNECTED.
    // PING hanya sebagai readiness check saat RUN ditekan (handleStartClick).
    chrome.tabs.sendMessage(tabs[0].id, { action: "PING" }, () => {
      if (onlyIfError && statusText && !(statusText.textContent.includes("Error") || statusText.textContent.includes("Please open"))) {
        return;
      }
      setConnectionStatusUI("connected");
    });
  });
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

        // Resume message removed (cluttered status bar)

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
                  chrome.storage.local.set({ isAutomating: false, isPaused: false }); syncRunButtonUI(false);
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
                chrome.tabs.sendMessage(tabs[0].id, { action: "PING" }, (pingRes) => {
                  if (chrome.runtime.lastError || !pingRes || pingRes.status !== "READY") {
                    statusText.textContent = "Error: Canva tab is not ready or refreshing.";
                    statusDot.style.backgroundColor = "#ef4444";
                    statusDot.classList.remove("active");
                    chrome.storage.local.set({ isAutomating: false, isPaused: false }); syncRunButtonUI(false);
                    return;
                  }
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
                      chrome.storage.local.set({ isAutomating: false, isPaused: false }); syncRunButtonUI(false); // Revert state safely
                      return;
                    }
                  }
                );
                });
              }
            }
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
    settingsBtn: {
      id: "settingsBtn", event: "click", handler: () => {
        const modal = document.getElementById("settingsModal");
        if (modal) {
          modal.classList.remove("hidden");
          document.body.classList.add("modal-open");
        }
      }
    },
    closeSettingsBtn: {
      id: "closeSettingsBtn", event: "click", handler: () => {
        const modal = document.getElementById("settingsModal");
        if (modal) {
          modal.classList.add("hidden");
          document.body.classList.remove("modal-open");
        }
      }
    },
    importFileBtn: { id: "importFileBtn", event: "click", handler: () => document.getElementById("fileInput").click() },
    exportLogsBtn: {
      id: "exportLogsBtn", event: "click", handler: () => {
        const logs = document.getElementById("consoleLogs").innerText;
        const blob = new Blob([logs], { type: "text/plain" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `Canva_Logs_${new Date().getTime()}.txt`;
        a.click();
        URL.revokeObjectURL(url);
      }
    },
    clearLogsBtn: {
      id: "clearLogsBtn", event: "click", handler: () => {
        const consoleLogs = document.getElementById("consoleLogs");
        if (consoleLogs) consoleLogs.innerHTML = "";
      }
    },
    resetStatsBtn: {
      id: "resetStatsBtn", event: "click", handler: () => {
        if (confirm("Reset seluruh data Session Analytics ke 0?")) {
          const emptyStats = { startTime: null, successCount: 0, downloadCount: 0, totalCooldowns: 0, totalPrompts: 0, failedCount: 0 };
          chrome.storage.local.set({ sessionStats: emptyStats }, () => { updateStatsUI(emptyStats); });
        }
      }
    },
    retryQuarantineBtn: {
      id: "retryQuarantineBtn", event: "click", handler: () => {
        const qInput = document.getElementById("quarantineInput");
        if (!qInput || !qInput.value.trim()) return alert("Quarantine kosong!");
        promptInput.value = (promptInput.value ? promptInput.value + "\n" : "") + qInput.value.trim();
        qInput.value = "";
        chrome.storage.local.set({ savedPromptText: promptInput.value, savedFailedPrompts: "" });
      }
    },
    clearQuarantineBtn: {
      id: "clearQuarantineBtn", event: "click", handler: () => {
        const qInput = document.getElementById("quarantineInput");
        if (qInput) { qInput.value = ""; chrome.storage.local.set({ savedFailedPrompts: "" }); }
      }
    },
    openDreamLabBtn: { id: "openDreamLabBtn", event: "click", handler: () => { chrome.tabs.create({ url: "https://www.canva.com/dream-lab" }); } }
  };

  Object.keys(buttons).forEach(key => {
    const b = buttons[key];
    const el = document.getElementById(b.id);
    if (el) {
      el.addEventListener(b.event, (e) => {
        if (b.id !== "fileInput" && b.event === "click") {
            e.preventDefault();
        }
        try { b.handler(e); } catch (err) { console.error(`Error pada ${b.id}:`, err); }
      });
    } else {
      console.warn(`[NRA DreamLab] Element #${b.id} tidak ditemukan di DOM`);
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

  // Real-time Save (Input/Change Listeners to prevent data loss).
  // Button enable/disable is owned by syncConnectionStatus/syncRunButtonUI only.
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
      chrome.storage.local.set({ aspectRatio: aspectRatioSelect.value });
    });
  }

  if (imageStyleSelect) {
    imageStyleSelect.addEventListener("change", () => {
      chrome.storage.local.set({ imageStyle: imageStyleSelect.value });
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
  syncConnectionStatus(); // Force initial connection check on panel load
}); // End of DOMContentLoaded

function initMessageListeners() {
  // Auto-reconnect interval: only repaint when recovering from an error state
  setInterval(() => {
    syncConnectionStatus(true);
  }, 3000);

  // Listen for STATUS_UPDATE or direct status/progress/UI synchronization messages from content.js
  // Throttled log rendering: batch DOM writes via requestAnimationFrame
  const logQueue = [];
  let logFlushScheduled = false;
  const MAX_LOG_ENTRIES = 500;

  function flushLogs() {
    logFlushScheduled = false;
    if (!consoleLogs || logQueue.length === 0) return;
    const frag = document.createDocumentFragment();
    while (logQueue.length > 0) {
      frag.appendChild(logQueue.shift());
    }
    consoleLogs.appendChild(frag);
    while (consoleLogs.childElementCount > MAX_LOG_ENTRIES) {
      consoleLogs.removeChild(consoleLogs.firstElementChild);
    }
    consoleLogs.scrollTop = consoleLogs.scrollHeight;
  }

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

        logQueue.push(logDiv);
        if (!logFlushScheduled) {
          logFlushScheduled = true;
          requestAnimationFrame(flushLogs);
        }
      }
      sendResponse({ success: true });
      return true;
    }

    // Handle failed/skipped prompt reporting
    if (request.action === "PROMPT_FAILED") {
      const failedEl = document.getElementById("failedPrompts");
      const quarantineEl = document.getElementById("quarantineInput");

      let raw = request.failedPrompt;
      let text = (typeof raw === 'object' && raw !== null)
        ? (raw.text || raw.prompt || JSON.stringify(raw))
        : String(raw);

      const tempDiv = document.createElement("div");
      tempDiv.textContent = text;
      const cleanPrompt = tempDiv.textContent || tempDiv.innerText || "";
      const finalPrompt = cleanPrompt.replace(/\s+/g, " ").trim();

      if (finalPrompt) {
        // Tampilkan di box Failed Prompts
        if (failedEl) {
          failedEl.value = (failedEl.value ? failedEl.value + "\n" : "") + finalPrompt;
        }
        // Tampilkan di box Quarantined Prompts untuk diselamatkan user
        if (quarantineEl) {
          quarantineEl.value = (quarantineEl.value ? quarantineEl.value + "\n" : "") + finalPrompt;
          chrome.storage.local.set({ savedFailedPrompts: quarantineEl.value });
        }
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
      statusText.title = statusValue; // Hover = teks status penuh (tanpa terpotong ellipsis)
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
        statusLower.includes("stopping")
      ) {
        syncRunButtonUI(false);
        statusDot.style.backgroundColor = statusLower.includes("error") ? "#ef4444" : "#6b7280";
        statusDot.classList.remove("active");
      } else if (
        statusLower.includes("paused") ||
        statusLower.includes("cooldown")
      ) {
        // Waiting state: orange pulse
        statusDot.style.backgroundColor = "#f59e0b";
        statusDot.classList.add("active");
      } else if (statusLower.includes("[dl") || statusLower.includes("downloading")) {
        statusDot.style.backgroundColor = "#3b82f6";
        statusDot.classList.add("active");
      } else if (
        statusLower.includes("complete") ||
        statusLower.includes("successfully")
      ) {
        syncRunButtonUI(false);
        statusDot.style.backgroundColor = "#10b981";
        statusDot.classList.add("active");

        // Trigger alerts on clean completion
        if (statusLower.includes("complete") || statusLower.includes("successfully")) {
          playAlertSound();
          showBrowserNotification();
        }
      } else {
        // Active automation pulse
        statusDot.style.backgroundColor = "#10b981";
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

function initExtendedFeatures() {
  // Save Delay Slider - declared here, listeners registered below
  const saveDelaySlider = document.getElementById("saveDelaySlider");
  const saveDelayVal = document.getElementById("saveDelayVal");

  // 1. Toggle Debug Mode - handled in initEventListeners

  // 2. Toggle Verbose Logs - handled in initEventListeners

  // 3. Toggle Subfolder - handled in initEventListeners

  // 4. Custom Download Folder - handled in initEventListeners

  // 5. Safety Delay - handled below after variable declaration

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
  // 1. Bulk File Importer - handled in initEventListeners

  // 2. Export Logs - handled in initEventListeners

  // 3. Pause / Resume Toggle - handled in initEventListeners

  // 4. Quarantine Catch Listener - handled in initMessageListeners

  // 5. Retry Quarantine Logic - handled in initEventListeners

  // --- UTILITY ICONS LOGIC ---

  // 1. Open Dream Lab Shortcut - handled in initEventListeners

  // 2. Clear Prompts Trash Can
  const clearPromptsBtn = document.getElementById("clearPromptsBtn");
  if (clearPromptsBtn) {
    // Connection handshake removed - deduped into syncConnectionStatus (Fix #2)

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
  // 3. Clear Terminal Logs Trash Can - handled in initEventListeners

  // 4. Reset Session Analytics - handled in initEventListeners

  // --- UI SETTINGS MODAL LOGIC ---
  const settingsBtn = document.getElementById("settingsBtn");
  const closeSettingsBtn = document.getElementById("closeSettingsBtn");
  const settingsModal = document.getElementById("settingsModal");
  const themeSelect = document.getElementById("themeSelect");
  const fontSelect = document.getElementById("fontSelect");
  const batchLimitInput = document.getElementById("batchLimitInput");
  const soundToggle = document.getElementById("soundToggle");

  // Open settings modal - handled in initEventListeners

  // Close settings modal - handled in initEventListeners

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
        console.log('[NRA DreamLab] ✅ Preset "' + name + '" berhasil disimpan.');
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
        console.log('[NRA DreamLab] 📂 Preset "' + selectedKey + '" berhasil dimuat.');
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
        console.log('[NRA DreamLab] 🗑️ Preset "' + selectedKey + '" berhasil dihapus.');
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
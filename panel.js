document.addEventListener('DOMContentLoaded', () => {
  const startBtn = document.getElementById('startBtn');
  const promptInput = document.getElementById('promptInput');
  const aspectRatioSelect = document.getElementById('aspectRatio');
  const imageStyleSelect = document.getElementById('imageStyle');
  const downloadCountSelect = document.getElementById('downloadCount');
  const debugModeSelect = document.getElementById('debugMode');
  const progressText = document.getElementById('progressText');
  const statusText = document.getElementById('statusText');
  const statusDot = document.getElementById('statusDot');
  const failedPromptsTextarea = document.getElementById('failedPrompts');
  const consoleLogs = document.getElementById('consoleLogs');

  let isRunning = false;
  let isDebugMode = false;

  // Helper to update button visual state dynamically
  function updateButtonState(running) {
    isRunning = running;
    if (isRunning) {
      startBtn.textContent = 'Stop';
      startBtn.style.background = '#e74c3c';
      startBtn.style.boxShadow = '0 4px 15px rgba(231, 76, 60, 0.4)';
    } else {
      startBtn.textContent = 'Run';
      startBtn.style.background = '';
      startBtn.style.boxShadow = '';
    }
  }

  // Pleasant, ascending 2-tone chime: 523.25Hz (150ms), then 659.25Hz (300ms)
  function playAlertSound() {
    try {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) return;
      const ctx = new AudioContextClass();

      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.connect(gain);
      gain.connect(ctx.destination);

      const now = ctx.currentTime;

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

      // WARN-8 FIX: Close AudioContext after playback to prevent resource exhaustion
      osc.onended = () => ctx.close();
    } catch (e) {
      console.warn('[Canva Auto Prompter] Web Audio alert failed:', e);
    }
  }

  // System Notification
  function showBrowserNotification() {
    if (typeof chrome !== 'undefined' && chrome.notifications) {
      chrome.notifications.create({
        type: 'basic',
        iconUrl: 'icon.png',
        title: 'Canva Auto Prompter',
        message: 'Success! All prompts have been processed.'
      }, (id) => {
        if (chrome.runtime.lastError) {
          console.warn('[Canva Auto Prompter] Notification alert failed:', chrome.runtime.lastError.message);
        }
      });
    }
  }

  // Helper to visually show tab status and progress on load
  chrome.tabs.query({ url: "*://*.canva.com/*" }, (tabs) => {
    if (tabs && tabs.length > 0) {
      statusText.textContent = 'Canva Connected';
      statusDot.classList.add('active');
      statusDot.style.backgroundColor = '#10b981';
    } else {
      statusText.textContent = 'Please open Canva';
      statusDot.classList.remove('active');
      statusDot.style.backgroundColor = '#ef4444';
    }
  });

  // Pull existing progress from storage on startup and sync running state
  chrome.storage.local.get(['prompts', 'isAutomating', 'savedPromptText', 'savedAspectRatio', 'savedImageStyle', 'savedDownloadCount', 'savedFailedPrompts', 'savedDebugMode'], (result) => {
    if (result) {
      // Prioritize active processing prompts if automating, otherwise fall back to auto-saved prompt text
      if (result.isAutomating === true && result.prompts && result.prompts.length > 0) {
        progressText.textContent = `Progress: ${result.prompts.length} prompts remaining`;
        promptInput.value = result.prompts.join('\n');
      } else if (result.savedPromptText !== undefined) {
        promptInput.value = result.savedPromptText;
      }

      // Restore dropdown settings if they were auto-saved
      if (result.savedAspectRatio) {
        aspectRatioSelect.value = result.savedAspectRatio;
      }
      if (result.savedImageStyle) {
        imageStyleSelect.value = result.savedImageStyle;
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

      if (result.isAutomating === true) {
        updateButtonState(true);
      }
    }
  });

  // Real-time Save (Input/Change Listeners to prevent data loss)
  let saveTimeout;
  promptInput.addEventListener('input', () => {
    clearTimeout(saveTimeout);
    saveTimeout = setTimeout(() => {
      chrome.storage.local.set({ savedPromptText: promptInput.value });
    }, 500); // 500ms debounce
  });

  aspectRatioSelect.addEventListener('change', () => {
    chrome.storage.local.set({ savedAspectRatio: aspectRatioSelect.value });
  });

  imageStyleSelect.addEventListener('change', () => {
    chrome.storage.local.set({ savedImageStyle: imageStyleSelect.value });
  });

  downloadCountSelect.addEventListener('change', () => {
    chrome.storage.local.set({ savedDownloadCount: downloadCountSelect.value });
  });

  debugModeSelect.addEventListener('change', () => {
    isDebugMode = debugModeSelect.value === 'true';
    chrome.storage.local.set({ savedDebugMode: isDebugMode });
  });

  // Listen for STATUS_UPDATE or direct status/progress/UI synchronization messages from content.js
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (!request) return false;

    // WARN-7 FIX: Only handle actions explicitly intended for the panel.
    // Ignore CDP/debugger commands so we don't hijack background.js responses.
    const PANEL_ACTIONS = new Set([
      "CONSOLE_LOG", "PROMPT_FAILED", "UPDATE_TEXTAREA", "STATUS_UPDATE", "PROGRESS_UPDATE"
    ]);

    // If message has an action that is NOT for the panel, return early without responding
    if (request.action && !PANEL_ACTIONS.has(request.action)) {
      return false; // Do not call sendResponse, do not keep channel open
    }

    if (request.action === "CONSOLE_LOG") {
      // Block verbose INFO logs if Debug Mode is Off
      if (!isDebugMode && request.level === 'INFO') {
        sendResponse({ success: true });
        return true;
      }

      if (consoleLogs) {
        const time = new Date().toLocaleTimeString('en-US', { hour12: false });
        const prefix = request.level === 'ERROR' ? '[!]' : request.level === 'WARN' ? '[?]' : '[>]';

        const logDiv = document.createElement('div');
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
      if (failedPromptsTextarea.value) {
        failedPromptsTextarea.value += '\n' + request.failedPrompt;
      } else {
        failedPromptsTextarea.value = request.failedPrompt;
      }
      chrome.storage.local.set({ savedFailedPrompts: failedPromptsTextarea.value });
      sendResponse({ success: true });
      return true;
    }

    // Direct UI update for the destructive Queue
    if (request.action === "UPDATE_TEXTAREA") {
      promptInput.value = request.remainingPrompts.join('\n');
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

    const statusValue = request.status || (request.action === 'STATUS_UPDATE' ? request.status : null);

    if (statusValue) {
      console.log('[Canva Auto Prompter] Received status update:', statusValue);
      statusText.textContent = statusValue;

      const statusLower = statusValue.toLowerCase();
      if (statusLower.includes('error') || statusLower.includes('stopped') || statusLower.includes('complete')) {
        updateButtonState(false);

        if (statusLower.includes('error')) {
          statusDot.style.backgroundColor = '#ef4444';
          statusDot.classList.remove('active');
        } else {
          statusDot.style.backgroundColor = '#10b981';
          statusDot.classList.add('active');

          // Trigger alerts on clean completion
          if (statusLower.includes('complete')) {
            playAlertSound();
            showBrowserNotification();
          }
        }
      } else {
        // Active automation pulse
        statusDot.style.backgroundColor = '#a855f7';
        statusDot.classList.add('active');
      }

      // Dynamically fetch and synchronize progress text from local storage
      chrome.storage.local.get(['prompts'], (result) => {
        if (result && result.prompts) {
          progressText.textContent = `Progress: ${result.prompts.length} prompts remaining`;
        }
      });
    }

    // Respond to acknowledged status/progress messages
    sendResponse({ success: true });
    return true; // Keep channel open
  });

  // Global storage listener to keep UI in sync if automation state changes elsewhere
  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName === 'local' && changes.isAutomating) {
      const isNowAutomating = changes.isAutomating.newValue;
      updateButtonState(isNowAutomating);
    }
  });

  // Action dispatcher with Start/Stop toggle
  startBtn.addEventListener('click', () => {
    if (isRunning) {
      // STOP_AUTOMATION trigger
      chrome.storage.local.set({ isAutomating: false, step: 'IDLE' }, () => {
        updateButtonState(false);
        statusText.textContent = 'Stopping automation...';
        statusDot.style.backgroundColor = '#ef4444';
        statusDot.classList.remove('active');

        // Query explicit Canva tab and send "STOP_AUTOMATION" message
        chrome.tabs.query({ url: "*://*.canva.com/*" }, (tabs) => {
          if (tabs && tabs.length > 0) {
            chrome.tabs.sendMessage(tabs[0].id, { action: 'STOP_AUTOMATION' }, (response) => {
              if (chrome.runtime.lastError) {
                console.warn('[Canva Auto Prompter] Could not send stop signal to content script:', chrome.runtime.lastError.message);
              }
            });
          }
        });
      });
    } else {
      // START_AUTOMATION trigger
      const rawPromptText = promptInput.value;
      // Split by newline, trim, and filter out empty lines
      const promptsArray = rawPromptText
        .split('\n')
        .map(p => p.trim())
        .filter(p => p.length > 0);

      if (promptsArray.length === 0) {
        alert('Please enter at least one prompt!');
        return;
      }

      // Clear previous failed prompts log
      failedPromptsTextarea.value = '';
      chrome.storage.local.set({ savedFailedPrompts: '' });

      const aspectRatioVal = aspectRatioSelect.value;
      const imageStyleVal = imageStyleSelect.value;
      const downloadCountVal = downloadCountSelect.value;

      const state = {
        isAutomating: true,
        step: 'INJECT_PROMPT',
        prompts: promptsArray,
        aspectRatio: aspectRatioVal,
        imageStyle: imageStyleVal,
        downloadCount: downloadCountVal
      };

      // Update button UI immediately before async storage operation
      updateButtonState(true);
      progressText.textContent = `Progress: ${promptsArray.length} prompts remaining`;
      statusText.textContent = 'Starting...';

      // Save all state values to chrome.storage.local
      chrome.storage.local.set(state, () => {
        console.log('[Canva Auto Prompter] Bulk automation state saved:', state);

        // Query explicit Canva tab and send "START_AUTOMATION" message
        chrome.tabs.query({ url: "*://*.canva.com/*" }, (tabs) => {
          if (tabs && tabs.length > 0) {
            chrome.tabs.sendMessage(tabs[0].id, { action: 'START_AUTOMATION' }, (response) => {
              if (chrome.runtime.lastError) {
                console.warn('[Canva Auto Prompter] Could not communicate with content script:', chrome.runtime.lastError.message);
                statusText.textContent = "Error: Please refresh the Canva tab and try again.";
                statusDot.style.backgroundColor = '#ef4444';
                statusDot.classList.remove('active');
                updateButtonState(false);
              }
            });
          }
        });
      });
    }
  });

  // --- UTILITY ICONS LOGIC ---

  // 1. Open Dream Lab Shortcut
  const openDreamLabBtn = document.getElementById('openDreamLabBtn');
  if (openDreamLabBtn) {
    openDreamLabBtn.addEventListener('click', () => {
      chrome.tabs.create({ url: 'https://www.canva.com/dream-lab' });
    });
  }

  // 2. Clear Prompts Trash Can
  const clearPromptsBtn = document.getElementById('clearPromptsBtn');
  if (clearPromptsBtn) {
    clearPromptsBtn.addEventListener('click', () => {
      if (confirm('Are you sure you want to clear all prompts?')) {
        const promptInput = document.getElementById('promptInput');
        if (promptInput) {
          promptInput.value = '';
          chrome.storage.local.set({ savedPromptText: '' });

          const progressText = document.getElementById('progressText');
          if (progressText) progressText.textContent = 'Progress: 0 prompts remaining';
        }
      }
    });
  }

  // 3. Clear Terminal Logs Trash Can
  const clearLogsBtn = document.getElementById('clearLogsBtn');
  if (clearLogsBtn) {
    clearLogsBtn.addEventListener('click', () => {
      const consoleLogs = document.getElementById('consoleLogs');
      if (consoleLogs) {
        consoleLogs.innerHTML = ''; // Wipe all log divs
      }
    });
  }
});

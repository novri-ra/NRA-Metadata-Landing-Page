document.addEventListener('DOMContentLoaded', () => {
  const startBtn = document.getElementById('startBtn');
  const promptInput = document.getElementById('promptInput');
  const aspectRatioSelect = document.getElementById('aspectRatio');
  const imageStyleSelect = document.getElementById('imageStyle');
  const downloadCountSelect = document.getElementById('downloadCount');
  const progressText = document.getElementById('progressText');
  const statusText = document.getElementById('statusText');
  const statusDot = document.getElementById('statusDot');
  const failedPromptsTextarea = document.getElementById('failedPrompts');
  const consoleLogs = document.getElementById('consoleLogs');

  let isRunning = false;

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
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs && tabs[0]) {
      const activeTab = tabs[0];
      if (activeTab.url && activeTab.url.includes('canva.com')) {
        statusText.textContent = 'Canva Connected';
        statusDot.classList.add('active');
        statusDot.style.backgroundColor = '#10b981';
      } else {
        statusText.textContent = 'Please open Canva';
        statusDot.classList.remove('active');
        statusDot.style.backgroundColor = '#ef4444';
      }
    }
  });

  // Pull existing progress from storage on startup and sync running state
  chrome.storage.local.get(['prompts', 'isAutomating', 'savedPromptText', 'savedAspectRatio', 'savedImageStyle', 'savedDownloadCount', 'savedFailedPrompts'], (result) => {
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
  promptInput.addEventListener('input', () => {
    chrome.storage.local.set({ savedPromptText: promptInput.value });
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

  // Listen for STATUS_UPDATE or direct status/progress/UI synchronization messages from content.js
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request) {
      if (request.action === "CONSOLE_LOG") {
        if (consoleLogs) {
          const time = new Date().toLocaleTimeString('en-US', { hour12: false });
          const prefix = request.level === 'ERROR' ? '[!]' : request.level === 'WARN' ? '[?]' : '[>]';
          
          const logDiv = document.createElement('div');
          logDiv.className = `log-entry log-${request.level.toLowerCase()}`;
          logDiv.textContent = `${time} ${prefix} ${request.message}`;
          
          consoleLogs.appendChild(logDiv);
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

      if (request.progress) {
        progressText.textContent = `Progress: ${request.progress}`;
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
      sendResponse({ success: true });
    }
    return true; // Keep channel open
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

        // Query active tab and send "STOP_AUTOMATION" message
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
          if (tabs && tabs[0]) {
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

      // Save all state values to chrome.storage.local
      chrome.storage.local.set(state, () => {
        console.log('[Canva Auto Prompter] Bulk automation state saved:', state);
        progressText.textContent = `Progress: ${promptsArray.length} prompts remaining`;
        statusText.textContent = 'Starting...';
        updateButtonState(true);

        // Query active tab and send "START_AUTOMATION" message
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
          if (tabs && tabs[0]) {
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
});

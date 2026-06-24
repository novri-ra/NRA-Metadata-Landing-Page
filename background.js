// Canva Auto Prompter - Background Service Worker

// Enable opening the side panel when the extension action icon is clicked
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });

console.log('[Canva Auto Prompter] Background Service Worker loaded.');

/**
 * WARN-1 FIX: Ensures the debugger is attached before sending CDP commands.
 * After a long cooldown (5+ minutes), the MV3 service worker may have been
 * terminated and restarted, losing the previous debugger attachment.
 * This helper idempotently re-attaches if needed.
 * @param {number} tabId
 */
async function ensureDebuggerAttached(tabId) {
  try {
    await chrome.debugger.attach({ tabId }, "1.3");
  } catch (e) {
    // "Already attached" means we're good — any other error is a real failure
    if (!e.message || !e.message.includes("already attached")) {
      throw e;
    }
  }
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "ATTACH_DEBUGGER") {
    (async () => {
      try {
        const targetId = { tabId: sender.tab.id };

        // Multi-Tab Mutex Guard
        const storage = await chrome.storage.local.get(['activeAutomationTab']);
        if (storage.activeAutomationTab && storage.activeAutomationTab !== targetId.tabId) {
          sendResponse({ success: false, error: "Another Canva tab is already running automation!" });
          return;
        }
        await chrome.storage.local.set({ activeAutomationTab: targetId.tabId });

        await chrome.debugger.attach(targetId, "1.3");

        // Prevent system from sleeping during long automation runs
        chrome.power.requestKeepAwake("system");

        sendResponse({ success: true });
      } catch (e) {
        // If already attached, consider it a success/warning but don't fail
        if (e.message && e.message.includes("already attached")) {
          sendResponse({ success: true, warning: e.message });
        } else {
          sendResponse({ success: false, error: e.message });
        }
      }
    })();
    return true;
  }

  if (request.action === "DETACH_DEBUGGER") {
    (async () => {
      try {
        const targetId = { tabId: sender.tab.id };
        chrome.storage.local.remove(['activeAutomationTab']);

        // Allow system to sleep again
        chrome.power.releaseKeepAwake();

        await chrome.debugger.detach(targetId);
        sendResponse({ success: true });
      } catch (e) {
        sendResponse({ success: false, error: e.message });
      }
    })();
    return true;
  }

  if (request.action === "SHOW_NOTIFICATION") {
    chrome.notifications.create({
      type: 'basic',
      iconUrl: 'icon.png',
      title: request.title,
      message: request.message
    });
    sendResponse({ success: true });
    return true;
  }

  if (request.action === "CDP_CLICK") {
    (async () => {
      try {
        const targetId = { tabId: sender.tab.id };
        // WARN-1 FIX: Re-attach debugger if service worker was restarted
        await ensureDebuggerAttached(sender.tab.id);
        await chrome.debugger.sendCommand(targetId, "Input.dispatchMouseEvent", {
          type: "mousePressed",
          button: "left",
          x: request.x,
          y: request.y,
          clickCount: 1
        });
        await chrome.debugger.sendCommand(targetId, "Input.dispatchMouseEvent", {
          type: "mouseReleased",
          button: "left",
          x: request.x,
          y: request.y,
          clickCount: 1
        });
        sendResponse({ success: true });
      } catch (e) {
        sendResponse({ success: false, error: e.message });
      }
    })();
    return true;
  }

  if (request.action === "CDP_TYPE") {
    (async () => {
      try {
        const targetId = { tabId: sender.tab.id };
        // WARN-1 FIX: Re-attach debugger if service worker was restarted
        await ensureDebuggerAttached(sender.tab.id);
        await chrome.debugger.sendCommand(targetId, "Input.insertText", {
          text: request.text
        });
        sendResponse({ success: true });
      } catch (e) {
        sendResponse({ success: false, error: e.message });
      }
    })();
    return true;
  }
});

// Clear mutex lock if debugger detaches organically or extension unloads
chrome.debugger.onDetach.addListener((source, reason) => {
  chrome.storage.local.remove(['activeAutomationTab']);
  chrome.power.releaseKeepAwake();
});

// Smart Auto-Rename API: Intercept downloads and rename based on current prompt
chrome.downloads.onDeterminingFilename.addListener((item, suggest) => {
  // Only intercept if the automation lock is active
  chrome.storage.local.get(['activeAutomationTab', 'currentActivePrompt'], (res) => {
    if (res.activeAutomationTab && res.currentActivePrompt) {

      // Clean the prompt to make it a valid, SEO-friendly filename
      let cleanName = res.currentActivePrompt
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '_') // Replace non-alphanumeric with underscores
        .replace(/^_+|_+$/g, '')     // Trim edge underscores
        .substring(0, 50);           // Limit to 50 characters to prevent OS path errors

      if (!cleanName) cleanName = "canva_asset";

      // Keep the original extension (e.g., .jpg, .png)
      const fileExt = item.filename.split('.').pop() || "jpg";
      const finalName = `Canva_Auto/${cleanName}_${Date.now()}.${fileExt}`;

      suggest({ filename: finalName, conflictAction: 'uniquify' });
    } else {
      // Let it download normally if bot is not running
      suggest();
    }
  });
  return true; // Indicates asynchronous suggestion
});

// Canva Auto Prompter - Background Service Worker

// Enable opening the side panel when the extension action icon is clicked
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });

console.log("[Canva Auto Prompter] Background Service Worker loaded.");

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
        const storage = await chrome.storage.local.get(["activeAutomationTab"]);
        if (
          storage.activeAutomationTab &&
          storage.activeAutomationTab !== targetId.tabId
        ) {
          sendResponse({
            success: false,
            error: "Another Canva tab is already running automation!",
          });
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
        chrome.storage.local.remove(["activeAutomationTab"]);

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
      type: "basic",
      iconUrl: "icon.png",
      title: request.title,
      message: request.message,
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
        await chrome.debugger.sendCommand(
          targetId,
          "Input.dispatchMouseEvent",
          {
            type: "mousePressed",
            button: "left",
            x: request.x,
            y: request.y,
            clickCount: 1,
          },
        );
        await chrome.debugger.sendCommand(
          targetId,
          "Input.dispatchMouseEvent",
          {
            type: "mouseReleased",
            button: "left",
            x: request.x,
            y: request.y,
            clickCount: 1,
          },
        );
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
          text: request.text,
        });
        sendResponse({ success: true });
      } catch (e) {
        sendResponse({ success: false, error: e.message });
      }
    })();
    return true;
  }
});

// CRITICAL 2 & HIGH 6 FIX: Release mutex and power if tab is forcibly closed
chrome.tabs.onRemoved.addListener((tabId) => {
  chrome.storage.local.get(["activeAutomationTab"], (res) => {
    if (res.activeAutomationTab === tabId) {
      console.log(
        `[Background] Active tab ${tabId} closed. Clearing mutex and power lock.`,
      );
      chrome.storage.local.remove(["activeAutomationTab"]);
      chrome.power.releaseKeepAwake();
    }
  });
});

/**
 * Emergency cleanup routine to reset automation state and release resources.
 * Idempotent: safe to call multiple times.
 */
function emergencyCleanup() {
  chrome.storage.local.set({ isAutomating: false }, () => {
    if (chrome.runtime.lastError) {
      console.warn(
        "[Background] Failed to reset isAutomating:",
        chrome.runtime.lastError.message,
      );
    }
  });

  chrome.power.releaseKeepAwake();
  chrome.storage.local.remove(["activeAutomationTab"], () => {
    if (chrome.runtime.lastError) {
      console.warn(
        "[Background] Failed to clear activeAutomationTab:",
        chrome.runtime.lastError.message,
      );
    }
  });
}

// Add listener for extension unloading
chrome.runtime.onSuspend.addListener(() => {
  console.log("[Background] Extension unloading. Running emergency cleanup...");
  emergencyCleanup();
});

// Clear mutex lock if debugger detaches organically or extension unloads
chrome.debugger.onDetach.addListener((source, reason) => {
  console.log(`[Background] Debugger detached due to: ${reason}`);
  emergencyCleanup();

  // Notify active tab that debugger has detached
  chrome.storage.local.get(["activeAutomationTab"], (res) => {
    if (res.activeAutomationTab) {
      chrome.tabs
        .sendMessage(res.activeAutomationTab, {
          action: "DEBUGGER_DETACHED",
          reason: reason,
        })
        .catch((err) => {
          console.warn("Failed to notify tab about debugger detachment:", err);
        });
    }
  });

  // Send message to active tab with DEBUGGER_DETACHED action
  chrome.storage.local.get(["activeAutomationTab"], (res) => {
    if (res.activeAutomationTab) {
      chrome.tabs
        .sendMessage(res.activeAutomationTab, {
          action: "DEBUGGER_DETACHED",
        })
        .catch((err) => {
          console.warn("Failed to notify tab about debugger detachment:", err);
        });
    }
  });

  // FINAL EDGE-CASE FIX: Force reset automation state in storage
  chrome.storage.local.set(
    {
      isAutomating: false,
      statusMessage:
        "Automation stopped (Tab closed or debugger disconnected).",
    },
    () => {
      if (chrome.runtime.lastError) {
        console.warn(
          "Storage set failed on detach:",
          chrome.runtime.lastError.message,
        );
      }
    },
  );
});

// Add listener for browser suspension/closing
chrome.runtime.onSuspend.addListener(() => {
  console.log("[Background] Browser suspending. Running emergency cleanup...");
  emergencyCleanup();
});

// Smart Auto-Rename API: Intercept downloads and rename based on current prompt
chrome.downloads.onDeterminingFilename.addListener((item, suggest) => {
  // Only intercept if the automation lock is active
  chrome.storage.local.get(
    ["activeAutomationTab", "downloadingPrompt", "createSubfolder"],
    (res) => {
      if (res.activeAutomationTab && res.downloadingPrompt) {
        // Clean the prompt to make it a valid, SEO-friendly filename
        let cleanName = res.downloadingPrompt
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, "_") // Replace non-alphanumeric with underscores
          .replace(/^_+|_+$/g, "") // Trim edge underscores
          .substring(0, 50); // Limit to 50 characters to prevent OS path errors

        if (!cleanName) cleanName = "canva_asset";

        // Keep the original extension (e.g., .jpg, .png)
        const fileExt = item.filename.split(".").pop() || "jpg";

        // Determine if we should add the folder prefix
        const useSubfolder = res.createSubfolder === true;
        const folderPrefix = useSubfolder ? "Canva_Auto/" : "";

        const finalName = `${folderPrefix}${cleanName}_${Date.now()}.${fileExt}`;

        suggest({ filename: finalName, conflictAction: "uniquify" });
      } else {
        // Let it download normally if bot is not running
        suggest();
      }
    },
  );
  return true; // Indicates asynchronous suggestion
});

// NRA DreamLab - Background Service Worker
let isBackgroundCleanup = false;

function sanitizeFilename(filename) {
  return filename
    .replace(/[<>:"/\\|?*]/g, "_")
    .replace(/[\x00-\x1f]/g, "")
    .replace(/^\.+/, "")
    .replace(/\.+$/, "")
    .trim()
    .substring(0, 200);
}

// Enable opening the side panel when the extension action icon is clicked
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });

console.log("[NRA DreamLab] Background Service Worker loaded.");

// Mutex lock for debugger re-attachment to prevent race conditions during rapid CDP requests
let isAttachingDebugger = false;
const attachQueue = [];

/**
 * WARN-1 FIX: Ensures the debugger is attached before sending CDP commands.
 * After a long cooldown (5+ minutes), the MV3 service worker may have been
 * terminated and restarted, losing the previous debugger attachment.
 * This helper idempotently re-attaches if needed, with a mutex lock to prevent concurrent Protocol Errors.
 * @param {number} tabId
 */
async function ensureDebuggerAttached(tabId) {
  // If already attaching, wait in queue
  if (isAttachingDebugger) {
    return new Promise((resolve, reject) => {
      attachQueue.push({ resolve, reject, tabId });
    });
  }

  isAttachingDebugger = true;

  try {
    const targets = await chrome.debugger.getTargets();
    const target = targets.find((t) => t.tabId === tabId);

    if (target && target.attached) {
      isAttachingDebugger = false;
      processQueue();
      return;
    }

    let attached = false;
    for (let attempt = 1; attempt <= 3; attempt++) {
      try {
        const targets = await chrome.debugger.getTargets();
        const target = targets.find((t) => t.tabId === tabId);
        if (target && target.attached) {
          attached = true;
          break;
        }
        await chrome.debugger.attach({ tabId }, "1.3");
        attached = true;
        break;
      } catch (e) {
        if (attempt < 3) {
          await new Promise((r) => setTimeout(r, 500));
        }
      }
    }
    if (!attached) {
      throw new Error("Failed to attach debugger after 3 attempts");
    }
  } finally {
    isAttachingDebugger = false;
    processQueue();
  }
}

function processQueue() {
  while (attachQueue.length > 0) {
    const next = attachQueue.shift();
    ensureDebuggerAttached(next.tabId)
      .then(() => next.resolve())
      .catch((err) => next.reject(err));
  }
}

function clearAttachQueue() {
  while (attachQueue.length > 0) {
    const next = attachQueue.shift();
    next.reject(new Error("DEBUGGER_ATTACH_CANCELLED"));
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

        // Attach with retry logic (max 3 attempts)
        let lastError = null;
        for (let attempt = 1; attempt <= 3; attempt++) {
          try {
            await chrome.debugger.attach(targetId, "1.3");
            lastError = null;
            break;
          } catch (e) {
            lastError = e;
            if (e.message && e.message.includes("already attached")) {
              lastError = null;
              break;
            }
            if (attempt < 3) {
              console.warn(
                `[Background] Attach attempt ${attempt} failed, retrying...`,
              );
              await new Promise((r) => setTimeout(r, 1000));
            }
          }
        }

        if (lastError) throw lastError;

        chrome.power.requestKeepAwake("system");
        sendResponse({ success: true });
      } catch (e) {
        if (e.message && e.message.includes("already attached")) {
          sendResponse({ success: true, warning: e.message });
        } else {
          await chrome.storage.local.remove(["activeAutomationTab"]);
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

        await chrome.storage.local.remove(["activeAutomationTab"]);
        chrome.power.releaseKeepAwake();

        const detachPromise = chrome.debugger.detach(targetId);
        const timeoutPromise = new Promise((_, reject) => {
          setTimeout(() => reject(new Error("DETACH_TIMEOUT")), 5000);
        });

        try {
          await Promise.race([detachPromise, timeoutPromise]);
        } catch (e) {
          if (!e.message || !e.message.includes("not attached")) {
            console.warn("[Background] Detach warning:", e);
          }
        }

        sendResponse({ success: true });
      } catch (e) {
        await chrome.storage.local.remove(["activeAutomationTab"]);
        chrome.power.releaseKeepAwake();
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
    // FIX: Await the async IIFE so the message port doesn't close prematurely.
    // Also, returning true is enough to keep port open.
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
    // FIX: Await the async IIFE so the message port doesn't close prematurely.
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
  clearAttachQueue();
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
  isBackgroundCleanup = true;
  emergencyCleanup();
});

// Clear mutex lock if debugger detaches organically or extension unloads
chrome.debugger.onDetach.addListener((source, reason) => {
  console.log(`[Background] Debugger detached due to: ${reason}`);
  isBackgroundCleanup = true;
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

// ==========================================
// SMART AUTO-RENAME API – dengan Custom Folder
// ==========================================
chrome.downloads.onDeterminingFilename.addListener((item, suggest) => {
  if (!item || !item.filename) {
    suggest();
    return;
  }

  chrome.storage.local.get(
    [
      "activeAutomationTab",
      "downloadingPrompt",
      "createSubfolder",
      "downloadFolder",
    ],
    (res) => {
      if (
        chrome.runtime.lastError ||
        !res.activeAutomationTab ||
        !res.downloadingPrompt
      ) {
        suggest();
        return;
      }

      let cleanName = res.downloadingPrompt
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "")
        .substring(0, 50);

      if (!cleanName) cleanName = "canva_asset";

      const fileExt = item.filename.split(".").pop() || "jpg";
      const safeExt =
        fileExt.replace(/[^a-zA-Z0-9]/g, "").toLowerCase() || "jpg";

      let folderPrefix = "";
      if (res.createSubfolder === true) {
        const customFolder = res.downloadFolder
          ? res.downloadFolder.trim()
          : "";
        if (customFolder) {
          const safeFolder = customFolder
            .replace(/[^a-zA-Z0-9_\-\/]/g, "_")
            .replace(/\/+/g, "/")
            .replace(/^\/|\/$/g, "");
          folderPrefix = safeFolder ? safeFolder + "/" : "Canva_Auto/";
        } else {
          folderPrefix = "Canva_Auto/";
        }
      }

      const timestamp = Date.now();
      const safeBaseName = sanitizeFilename(`${cleanName}_${timestamp}`);
      const finalName = `${folderPrefix}${safeBaseName}.${safeExt}`;

      console.log(`[Background] Downloading: ${finalName}`);
      suggest({ filename: finalName, conflictAction: "uniquify" });
    },
  );
  return true;
});

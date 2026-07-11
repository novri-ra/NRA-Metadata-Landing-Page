// NRA DreamLab - Background Service Worker
let isBackgroundCleanup = false;

function sanitizeFilename(filename) {
  return filename
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "") // Hapus diakritik
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

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "KEEP_AWAKE") {
    (async () => {
      try {
        const tabId = sender.tab.id;

        // Multi-Tab Mutex Guard
        const storage = await chrome.storage.local.get(["activeAutomationTab"]);
        if (
          storage.activeAutomationTab &&
          storage.activeAutomationTab !== tabId
        ) {
          sendResponse({
            success: false,
            error: "Another Canva tab is already running automation!",
          });
          return;
        }
        await chrome.storage.local.set({ activeAutomationTab: tabId });

        chrome.power.requestKeepAwake("system");
        sendResponse({ success: true });
      } catch (e) {
        await chrome.storage.local.remove(["activeAutomationTab"]);
        sendResponse({ success: false, error: e.message });
      }
    })();
    return true;
  }

  if (request.action === "RELEASE_AWAKE") {
    (async () => {
      try {
        await chrome.storage.local.remove(["activeAutomationTab"]);
        chrome.power.releaseKeepAwake();
        sendResponse({ success: true });
      } catch (e) {
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

  if (request.action === "EMERGENCY_CLEANUP") {
    emergencyCleanup();
    sendResponse({ success: true });
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
  isBackgroundCleanup = true;
  emergencyCleanup();
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
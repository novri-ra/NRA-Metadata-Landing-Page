// Service Worker Global Rejection Guard (MV3 Compliant)
self.addEventListener("unhandledrejection", (event) => {
  console.error("[Background] Unhandled Promise Rejection:", event.reason);
});

// NRA DreamLab - Background Service Worker

// Reset stale mutex/state on browser startup or extension install/update
chrome.runtime.onStartup.addListener(() => emergencyCleanup());
chrome.runtime.onInstalled.addListener(() => emergencyCleanup());

function sanitizeFilename(filename) {
  return filename
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .replace(/[<>:"/\\|?*]/g, "_")
    .replace(/[\x00-\x1f]/g, "")
    .replace(/^\.+/, "")
    .replace(/\.+$/, "")
    .trim()
    .substring(0, 200);
}

// Enable opening the side panel when the extension action icon is clicked
try {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
} catch (e) {
  console.warn("[Background] Failed to set panel behavior:", e.message);
}

// In-memory mutex to prevent KEEP_AWAKE race condition between concurrent tab requests
let isAwakeMutexLocked = false;

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "KEEP_AWAKE") {
    if (isAwakeMutexLocked) {
      sendResponse({ success: false, error: "Mutex locked by pending request" });
      return true;
    }
    isAwakeMutexLocked = true;
    (async () => {
      try {
        const tabId = sender.tab.id;
        const storage = await chrome.storage.local.get(["activeAutomationTab"]);
        if (storage.activeAutomationTab && storage.activeAutomationTab !== tabId) {
          sendResponse({ success: false, error: "Another Canva tab is already running automation!" });
          return;
        }
        await chrome.storage.local.set({ activeAutomationTab: tabId });
        chrome.power.requestKeepAwake("system");
        sendResponse({ success: true });
      } catch (e) {
        await chrome.storage.local.remove(["activeAutomationTab"]);
        sendResponse({ success: false, error: e.message });
      } finally {
        isAwakeMutexLocked = false;
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
      iconUrl: "assets/icon.png",
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

// Release mutex and power if tab is forcibly closed
chrome.tabs.onRemoved.addListener((tabId) => {
  chrome.storage.local.get(["activeAutomationTab"], (res) => {
    if (chrome.runtime.lastError) return;
    if (res.activeAutomationTab === tabId) {
      chrome.storage.local.remove(["activeAutomationTab"]);
      chrome.power.releaseKeepAwake();
    }
  });
});

// Release mutex if active tab navigates away from Canva
chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (!changeInfo.url) return;
  chrome.storage.local.get(["activeAutomationTab"], (res) => {
    if (chrome.runtime.lastError) return;
    if (res.activeAutomationTab !== tabId) return;
    if (!changeInfo.url.includes("canva.com")) {
      chrome.storage.local.set({ isAutomating: false });
      chrome.storage.local.remove(["activeAutomationTab"]);
      chrome.power.releaseKeepAwake();
    }
  });
});

function emergencyCleanup() {
  chrome.power.releaseKeepAwake();
  chrome.storage.local.set({ isAutomating: false });
  chrome.storage.local.remove(["activeAutomationTab"]);
}

// Cleanup on service worker suspend
chrome.runtime.onSuspend.addListener(() => emergencyCleanup());

// ==========================================
// SMART AUTO-RENAME API
// ==========================================
chrome.downloads.onDeterminingFilename.addListener((item, suggest) => {
  if (!item || !item.filename) {
    suggest();
    return;
  }

  chrome.storage.local.get(
    ["activeAutomationTab", "downloadingPrompt", "createSubfolder", "downloadFolder"],
    (res) => {
      if (chrome.runtime.lastError || !res.activeAutomationTab || !res.downloadingPrompt) {
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
      const safeExt = fileExt.replace(/[^a-zA-Z0-9]/g, "").toLowerCase() || "jpg";

      let folderPrefix = "";
      if (res.createSubfolder === true) {
        const customFolder = res.downloadFolder ? res.downloadFolder.trim() : "";
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

      suggest({ filename: finalName, conflictAction: "uniquify" });
    },
  );
  return true;
});


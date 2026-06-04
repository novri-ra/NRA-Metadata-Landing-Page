// Canva Auto Prompter - Background Service Worker

// Enable opening the side panel when the extension action icon is clicked
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });

console.log('[Canva Auto Prompter] Background Service Worker loaded.');

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "ATTACH_DEBUGGER") {
    (async () => {
      try {
        const targetId = { tabId: sender.tab.id };
        await chrome.debugger.attach(targetId, "1.3");
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

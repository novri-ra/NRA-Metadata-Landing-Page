// utils.js
function sanitizeInput(input) {
  if (typeof input !== "string") return input;
  // Hapus hanya tag HTML, biarkan karakter khusus teks seperti ( ) [ ] { } tetap ada
  return input.replace(/<[^>]*>/g, "").trim();
}

async function safeSendMessage(message) {
  try {
    return await chrome.runtime.sendMessage(message).catch(() => {});
  } catch (_) {
    return undefined;
  }
}

function sendStatusUpdate(statusText) {
  console.log(`[NRA DreamLab] Status update: ${statusText}`);
  chrome.runtime.sendMessage(
    { action: "STATUS_UPDATE", status: statusText },
    (response) => {
      if (chrome.runtime.lastError) return; // Fail silently but correctly
    },
  );
}
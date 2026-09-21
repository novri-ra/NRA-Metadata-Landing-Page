// errors.js
// Structured error classes for NRA DreamLab automation.

class AutomationError extends Error {
  constructor(code, message) {
    super(message || code);
    this.code = code;
  }
}

// Known automation stop/limit codes. Values double as legacy message strings,
// so existing string-based checks keep working.
const ERR = Object.freeze({
  USER_STOPPED: "USER_STOPPED",
  MAX_COOLDOWN_REACHED: "MAX_COOLDOWN_REACHED",
  MONTHLY_LIMIT_REACHED: "MONTHLY_LIMIT_REACHED",
  URL_MISMATCH: "URL_MISMATCH",
});

const KNOWN_CODES = new Set(Object.values(ERR));

// Normalize any thrown value into an AutomationError so routing can rely on e.code.
function asAutomationError(err) {
  if (err instanceof AutomationError) return err;
  const message =
    err && err.message ? err.message : err ? String(err) : "Unknown error occurred.";
  if (KNOWN_CODES.has(message)) return new AutomationError(message);
  return new AutomationError("UNKNOWN", message || "Unknown error occurred.");
}
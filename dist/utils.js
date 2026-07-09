// utils.js
function sanitizeInput(input) {
  if (typeof input !== "string") return input;
  // Remove HTML tags
  return input.replace(/<[^>]*>/g, "").replace(/[&<>"]/g, function (m) {
    if (m === "&") return "&" + "amp;";
    if (m === "<") return "&" + "lt;";
    if (m === ">") return "&" + "gt;";
    if (m === '"') return "&" + "quot;";
    return m;
  });
}

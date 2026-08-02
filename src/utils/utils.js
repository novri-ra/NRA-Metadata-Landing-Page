// utils.js
function sanitizeInput(input) {
  if (typeof input !== "string") return input;
  // Hapus hanya tag HTML, biarkan karakter khusus teks seperti ( ) [ ] { } tetap ada
  return input.replace(/<[^>]*>/g, "").trim();
}
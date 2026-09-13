// Google Apps Script Serverless Auth Backend
// Spreadsheet columns (Row 1): [UserID, Username, Email, WhatsApp, PasswordHash, Salt, HardwareID, LastIP, SessionToken, LastActive, Status, FullName]
// Passwords are stored as PBKDF2-HMAC-SHA256 (100k iterations, per-user salt) with
// automatic in-place migration of legacy SHA-256 hashes. Session validation requires a
// HWID signature (HMAC-SHA256 of the claimed HWID keyed by the session token) so a client
// cannot blindly swap HWID claims.

function doPost(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  
  try {
    var payload = JSON.parse(e.postData.contents);
    var action = payload.action;
    
    if (action === 'REGISTER') {
      return handleRegister(sheet, payload);
    } else if (action === 'LOGIN') {
      return handleLogin(sheet, payload);
    } else if (action === 'VALIDATE_SESSION') {
      return handleValidate(sheet, payload);
    } else if (action === 'LOGOUT') {
      return handleLogout(sheet, payload);
    } else if (action === 'SAVE_PRESETS') {
      return handleSavePresets(payload);
    } else if (action === 'LOAD_PRESETS') {
      return handleLoadPresets(payload);
    } else {
      return response({"status": "ERROR", "message": "Unknown action"});
    }
  } catch(err) {
    return response({"status": "ERROR", "message": err.message});
  }
}

function handleRegister(sheet, payload) {
  var fullname = payload.full_name || "";
  var username = payload.username;
  var email = payload.email || "";
  var wa = payload.whatsapp || "";
  var password = payload.password;
  var hwid = payload.hwid || "";
  var ip = payload.ip || "UNKNOWN";
  
  var data = sheet.getDataRange().getValues();
  for (var i = 1; i < data.length; i++) {
    if (data[i][1] === username) {
      return response({"status": "ERROR", "message": "Username sudah terdaftar"});
    }
    if (email && data[i][2] === email) {
      return response({"status": "ERROR", "message": "Email sudah terdaftar"});
    }
  }
  
  var salt = Utilities.getUuid();
  var passHash = hashPassword(password, salt);
  var userId = Utilities.getUuid();
  
  sheet.appendRow([userId, username, email, wa, passHash, salt, hwid, ip, "", new Date().toISOString(), "ACTIVE", fullname]);
  return response({"status": "SUCCESS", "message": "Registrasi berhasil"});
}

function handleLogin(sheet, payload) {
  var loginId = payload.identifier; // accepts username OR email
  var password = payload.password;
  var hwid = payload.hwid;
  var ip = payload.ip || "UNKNOWN";
  
  var data = sheet.getDataRange().getValues();
  for (var i = 1; i < data.length; i++) {
    var storedUsername = data[i][1];
    var storedEmail = data[i][2];
    
    if (storedUsername === loginId || storedEmail === loginId) {
      if (data[i][10] !== "ACTIVE") {
        return response({"status": "ERROR", "message": "Akun tidak aktif / banned"});
      }
      var passHash = data[i][4];
      var salt = data[i][5];
      
      if (verifyPassword(password, salt, passHash)) {
        if (isLegacyHash(passHash)) {
          sheet.getRange(i+1, 5).setValue(hashPassword(password, salt));
        }
        var sessionToken = Utilities.getUuid();
        var now = new Date().toISOString();
        // Update HardwareID(7), LastIP(8), SessionToken(9), LastActive(10)
        sheet.getRange(i+1, 7, 1, 4).setValues([[hwid, ip, sessionToken, now]]);
        
        return response({"status": "SUCCESS", "session_token": sessionToken, "message": "Login berhasil", "username": storedUsername});
      } else {
        return response({"status": "ERROR", "message": "Password salah"});
      }
    }
  }
  return response({"status": "ERROR", "message": "User tidak ditemukan"});
}

function handleValidate(sheet, payload) {
  var username = payload.identifier;
  var sessionToken = payload.session_token;
  var hwid = payload.hwid;
  var hwidSig = payload.hwid_sig;
  
  var data = sheet.getDataRange().getValues();
  for (var i = 1; i < data.length; i++) {
    if (data[i][1] === username) {
      var storedToken = data[i][8];
      var storedHwid = data[i][6];
      
      if (storedToken === sessionToken && storedHwid === hwid && verifyHwidSig(storedToken, hwid, hwidSig)) {
        sheet.getRange(i+1, 10).setValue(new Date().toISOString());
        return response({"status": "VALID", "message": "Session valid"});
      } else if (storedToken === sessionToken && !verifyHwidSig(storedToken, hwid, hwidSig)) {
        return response({"status": "INVALID_SESSION", "message": "HWID signature tidak valid, silakan login ulang"});
      } else if (storedToken === sessionToken) {
        return response({"status": "KICKED", "message": "Akun aktif di perangkat lain"});
      } else {
        return response({"status": "INVALID_SESSION", "message": "Session tidak valid, silakan login ulang"});
      }
    }
  }
  return response({"status": "ERROR", "message": "User not found"});
}

function handleLogout(sheet, payload) {
  var username = payload.username;
  var sessionToken = payload.session_token;
  
  var data = sheet.getDataRange().getValues();
  for (var i = 1; i < data.length; i++) {
    if (data[i][1] === username && data[i][8] === sessionToken) {
      sheet.getRange(i+1, 7).setValue("");
      sheet.getRange(i+1, 9).setValue("");
      return response({"status": "SUCCESS", "message": "Logged out"});
    }
  }
  return response({"status": "SUCCESS", "message": "Already logged out"});
}

// ── Cloud Preset Sync ────────────────────────────────────────────────────

function getUserPresetsSheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName("UserPresets");
  if (!sheet) {
    sheet = ss.insertSheet("UserPresets");
    sheet.appendRow(["UserID", "DataJSON"]);
  }
  return sheet;
}

function handleSavePresets(payload) {
  var username = payload.username;
  var sessionToken = payload.session_token;
  var presetsData = payload.presets_data;
  
  if (!validateUserSession(username, sessionToken)) {
    return response({"status": "ERROR", "message": "Invalid session"});
  }
  
  var userId = getUserId(username);
  var sheet = getUserPresetsSheet();
  var data = sheet.getDataRange().getValues();
  
  for (var i = 1; i < data.length; i++) {
    if (data[i][0] === userId) {
      sheet.getRange(i+1, 2).setValue(JSON.stringify(presetsData));
      return response({"status": "SUCCESS", "message": "Presets saved successfully"});
    }
  }
  
  sheet.appendRow([userId, JSON.stringify(presetsData)]);
  return response({"status": "SUCCESS", "message": "Presets created successfully"});
}

function handleLoadPresets(payload) {
  var username = payload.username;
  var sessionToken = payload.session_token;
  
  if (!validateUserSession(username, sessionToken)) {
    return response({"status": "ERROR", "message": "Invalid session"});
  }
  
  var userId = getUserId(username);
  var sheet = getUserPresetsSheet();
  var data = sheet.getDataRange().getValues();
  
  for (var i = 1; i < data.length; i++) {
    if (data[i][0] === userId) {
      return response({"status": "SUCCESS", "presets_data": JSON.parse(data[i][1])});
    }
  }
  return response({"status": "SUCCESS", "presets_data": {}});
}

function validateUserSession(username, sessionToken) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheets()[0];
  var data = sheet.getDataRange().getValues();
  for (var i = 1; i < data.length; i++) {
    if (data[i][1] === username && data[i][8] === sessionToken) {
      return true;
    }
  }
  return false;
}

function getUserId(username) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheets()[0];
  var data = sheet.getDataRange().getValues();
  for (var i = 1; i < data.length; i++) {
    if (data[i][1] === username) {
      return data[i][0];
    }
  }
  return null;
}

// ── Password Hashing & HWID signature ────────────────────────────────────
//
// PBKDF2-HMAC-SHA256 is implemented in the hex-string domain: salt+block index
// and every PRF result are carried as lowercase hex ASCII. This is not the
// byte-exact RFC 2898 form, but hashing happens only inside this script (client
// sends the plaintext password; the stored hash is never sent back), so
// register/login/upgrade stay mutually consistent. New hashes are stored as
// "pbkdf2$<iterations>$<hex>" so iterations are tunable without a migration.
// Legacy rows (bare 64-char SHA-256 hex) still verify and are upgraded in place
// on next successful login.

function toHex(bytes) {
  return bytes.map(function(e) {
    var v = (e < 0 ? e + 256 : e).toString(16);
    return v.length == 1 ? "0" + v : v;
  }).join("");
}

function hmacSha256Hex(key, value) {
  return toHex(Utilities.computeHmacSha256Signature(value, key));
}

function xorHex(a, b) {
  var out = "";
  for (var i = 0; i < a.length; i++) {
    var x = parseInt(a.charAt(i), 16);
    var y = parseInt(b.charAt(i), 16);
    out += (x ^ y).toString(16);
  }
  return out;
}

function pbkdf2Sha256Hex(password, salt, iterations) {
  // dkLen == 32 == SHA-256 output, so a single block (INT(1) suffix) suffices.
  var u = hmacSha256Hex(password, salt + "00000001");
  var t = u;
  for (var i = 1; i < iterations; i++) {
    u = hmacSha256Hex(password, u);
    t = xorHex(t, u);
  }
  return t;
}

function hashPassword(password, salt) {
  return "pbkdf2$100000$" + pbkdf2Sha256Hex(password, salt, 100000);
}

function legacySha256Hex(password, salt) {
  var rawHash = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, password + salt);
  return toHex(rawHash);
}

function isLegacyHash(passHash) {
  return passHash.indexOf("pbkdf2$") !== 0;
}

function verifyPassword(password, salt, passHash) {
  if (isLegacyHash(passHash)) {
    return legacySha256Hex(password, salt) === passHash;
  }
  var parts = passHash.split("$");
  return pbkdf2Sha256Hex(password, salt, parseInt(parts[1], 10)) === parts[2];
}

// HMAC-SHA256 over the claimed hwid keyed by the stored session token. The
// server recomputes this, so validation no longer trusts a bare client HWID.
function verifyHwidSig(storedToken, hwid, hwidSig) {
  return hwidSig === hmacSha256Hex(storedToken, hwid);
}

function response(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

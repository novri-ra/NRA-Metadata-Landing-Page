// Google Apps Script Serverless Auth Backend
// Spreadsheet columns (Row 1): [UserID, Username, Email, WhatsApp, PasswordHash, Salt, HardwareID, LastIP, SessionToken, LastActive, Status, FullName]

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
  var fullname = payload.fullname || "";
  var username = payload.username;
  var email = payload.email || "";
  var wa = payload.wa || "";
  var password = payload.password;
  
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
  
  // [UserID, Username, Email, WhatsApp, PasswordHash, Salt, HardwareID, LastIP, SessionToken, LastActive, Status, FullName]
  sheet.appendRow([userId, username, email, wa, passHash, salt, "", "", "", new Date().toISOString(), "ACTIVE", fullname]);
  return response({"status": "SUCCESS", "message": "Registrasi berhasil"});
}

function handleLogin(sheet, payload) {
  var loginId = payload.username; // accepts username OR email
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
      var calcHash = hashPassword(password, salt);
      
      if (calcHash === passHash) {
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
  var username = payload.username;
  var sessionToken = payload.session_token;
  var hwid = payload.hwid;
  
  var data = sheet.getDataRange().getValues();
  for (var i = 1; i < data.length; i++) {
    if (data[i][1] === username) {
      var storedToken = data[i][8];
      var storedHwid = data[i][6];
      
      if (storedToken === sessionToken && storedHwid === hwid) {
        sheet.getRange(i+1, 10).setValue(new Date().toISOString());
        return response({"status": "SUCCESS", "message": "Session valid"});
      } else {
        return response({"status": "INVALID_SESSION", "message": "Akun aktif di perangkat lain"});
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

// ── Utilities ────────────────────────────────────────────────────────────

function hashPassword(password, salt) {
  var rawHash = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, password + salt);
  return rawHash.map(function(e) {
    var v = (e < 0 ? e + 256 : e).toString(16);
    return v.length == 1 ? "0" + v : v;
  }).join("");
}

function response(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

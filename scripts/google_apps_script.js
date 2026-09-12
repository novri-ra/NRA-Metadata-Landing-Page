// Google Apps Script Serverless Auth Backend
// Spreadsheet columns (Row 1): [UserID, Username, PasswordHash, Salt, HardwareID, LastIP, SessionToken, LastActive, Status, CreatedAt]

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
  var username = payload.username;
  var password = payload.password;
  var hwid = payload.hwid || "";
  var ip = payload.ip || "UNKNOWN";
  
  var data = sheet.getDataRange().getValues();
  for (var i = 1; i < data.length; i++) {
    if (data[i][1] === username) {
      return response({"status": "ERROR", "message": "Username sudah terdaftar"});
    }
  }
  
  var salt = Utilities.getUuid();
  var passHash = hashPassword(password, salt);
  var userId = Utilities.getUuid();
  var sessionToken = Utilities.getUuid();
  var now = new Date().toISOString();
  
  // [UserID, Username, PasswordHash, Salt, HardwareID, LastIP, SessionToken, LastActive, Status, CreatedAt]
  sheet.appendRow([userId, username, passHash, salt, hwid, ip, sessionToken, now, "ACTIVE", now]);
  return response({"status": "SUCCESS", "message": "Registrasi berhasil"});
}

function handleLogin(sheet, payload) {
  var loginId = payload.identifier; // accepts username (lowercased by client)
  var password = payload.password;
  var hwid = payload.hwid;
  var ip = payload.ip || "UNKNOWN";
  
  var data = sheet.getDataRange().getValues();
  for (var i = 1; i < data.length; i++) {
    var storedUsername = data[i][1];
    
    if (storedUsername === loginId) {
      if (data[i][8] !== "ACTIVE") {
        return response({"status": "ERROR", "message": "Akun tidak aktif / banned"});
      }
      var passHash = data[i][2];
      var salt = data[i][3];
      var calcHash = hashPassword(password, salt);
      
      if (calcHash === passHash) {
        var sessionToken = Utilities.getUuid();
        var now = new Date().toISOString();
        // Update HardwareID(5), LastIP(6), SessionToken(7), LastActive(8)
        sheet.getRange(i+1, 5, 1, 4).setValues([[hwid, ip, sessionToken, now]]);
        
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
  
  var data = sheet.getDataRange().getValues();
  for (var i = 1; i < data.length; i++) {
    if (data[i][1] === username) {
      var storedToken = data[i][6];
      var storedHwid = data[i][4];
      
      if (storedToken === sessionToken && storedHwid === hwid) {
        sheet.getRange(i+1, 8).setValue(new Date().toISOString());
        return response({"status": "VALID", "message": "Session valid"});
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
    if (data[i][1] === username && data[i][6] === sessionToken) {
      sheet.getRange(i+1, 5).setValue("");
      sheet.getRange(i+1, 7).setValue("");
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
    if (data[i][1] === username && data[i][6] === sessionToken) {
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

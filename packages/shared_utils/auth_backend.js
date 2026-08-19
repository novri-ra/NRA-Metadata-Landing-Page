// Google Apps Script Serverless Auth Backend
// Spreadsheet columns (Row 1): [UserID, Username, PasswordHash, Salt, HardwareID, LastIP, SessionToken, LastActive, Status]

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
  
  var data = sheet.getDataRange().getValues();
  for (var i = 1; i < data.length; i++) {
    if (data[i][1] === username) {
      return response({"status": "ERROR", "message": "Username already exists"});
    }
  }
  
  var salt = Utilities.getUuid();
  var passHash = hashPassword(password, salt);
  var userId = Utilities.getUuid();
  
  // Append new user
  sheet.appendRow([userId, username, passHash, salt, "", "", "", new Date().toISOString(), "ACTIVE"]);
  return response({"status": "SUCCESS", "message": "User registered successfully"});
}

function handleLogin(sheet, payload) {
  var username = payload.username;
  var password = payload.password;
  var hwid = payload.hwid;
  var ip = payload.ip || "UNKNOWN";
  
  var data = sheet.getDataRange().getValues();
  for (var i = 1; i < data.length; i++) {
    if (data[i][1] === username) {
      if (data[i][8] !== "ACTIVE") {
        return response({"status": "ERROR", "message": "Account is inactive/banned"});
      }
      var passHash = data[i][2];
      var salt = data[i][3];
      var calcHash = hashPassword(password, salt);
      
      if (calcHash === passHash) {
        var sessionToken = Utilities.getUuid();
        var now = new Date().toISOString();
        // Update HardwareID, LastIP, SessionToken, LastActive
        sheet.getRange(i+1, 5, 1, 4).setValues([[hwid, ip, sessionToken, now]]);
        
        return response({"status": "SUCCESS", "session_token": sessionToken, "message": "Login successful"});
      } else {
        return response({"status": "ERROR", "message": "Invalid password"});
      }
    }
  }
  return response({"status": "ERROR", "message": "User not found"});
}

function handleValidate(sheet, payload) {
  var username = payload.username;
  var sessionToken = payload.session_token;
  var hwid = payload.hwid;
  
  var data = sheet.getDataRange().getValues();
  for (var i = 1; i < data.length; i++) {
    if (data[i][1] === username) {
      var storedToken = data[i][6];
      var storedHwid = data[i][4];
      
      if (storedToken === sessionToken && storedHwid === hwid) {
        // Update LastActive
        sheet.getRange(i+1, 8).setValue(new Date().toISOString());
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
    if (data[i][1] === username && data[i][6] === sessionToken) {
      // Clear HWID and SessionToken
      sheet.getRange(i+1, 5).setValue("");
      sheet.getRange(i+1, 7).setValue("");
      return response({"status": "SUCCESS", "message": "Logged out"});
    }
  }
  return response({"status": "SUCCESS", "message": "Already logged out"});
}

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
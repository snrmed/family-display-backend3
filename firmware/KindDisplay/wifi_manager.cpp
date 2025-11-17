#include "wifi_manager.h"

WiFiManager::WiFiManager() : _server(nullptr), _configPortalRunning(false) {
}

bool WiFiManager::hasCredentials() {
    _prefs.begin(NVS_NAMESPACE, true);  // Read-only
    bool hasSSID = _prefs.isKey(NVS_WIFI_SSID);
    _prefs.end();
    return hasSSID;
}

bool WiFiManager::connect() {
    _prefs.begin(NVS_NAMESPACE, true);  // Read-only
    String ssid = _prefs.getString(NVS_WIFI_SSID, "");
    String password = _prefs.getString(NVS_WIFI_PASS, "");
    _prefs.end();

    if (ssid.length() == 0) {
        DEBUG_PRINTLN("WiFi: No credentials stored");
        return false;
    }

    DEBUG_PRINTF("WiFi: Connecting to %s\n", ssid.c_str());
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid.c_str(), password.c_str());

    unsigned long startAttempt = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - startAttempt < WIFI_CONNECT_TIMEOUT) {
        delay(500);
        DEBUG_PRINT(".");
    }
    DEBUG_PRINTLN();

    if (WiFi.status() == WL_CONNECTED) {
        DEBUG_PRINTF("WiFi: Connected! IP: %s\n", WiFi.localIP().toString().c_str());
        return true;
    } else {
        DEBUG_PRINTLN("WiFi: Connection failed");
        return false;
    }
}

void WiFiManager::startConfigPortal() {
    DEBUG_PRINTLN("WiFi: Starting configuration portal");

    // Start Access Point
    WiFi.mode(WIFI_AP);
    WiFi.softAP(AP_SSID, AP_PASSWORD);

    IPAddress IP = WiFi.softAPIP();
    DEBUG_PRINTF("WiFi: AP started - SSID: %s, IP: %s\n", AP_SSID, IP.toString().c_str());

    // Create web server
    _server = new WebServer(80);

    // Register handlers
    _server->on("/", [this]() { this->handleRoot(); });
    _server->on("/scan", [this]() { this->handleScan(); });
    _server->on("/save", [this]() { this->handleSave(); });
    _server->onNotFound([this]() { this->handleNotFound(); });

    _server->begin();
    _configPortalRunning = true;

    DEBUG_PRINTLN("WiFi: Config portal running. Connect to:");
    DEBUG_PRINTF("       SSID: %s\n", AP_SSID);
    DEBUG_PRINTF("       Password: %s\n", AP_PASSWORD);
    DEBUG_PRINTF("       URL: http://%s\n", IP.toString().c_str());

    // Run server until configuration is saved
    while (_configPortalRunning) {
        _server->handleClient();
        delay(10);
    }

    // Clean up
    _server->stop();
    delete _server;
    _server = nullptr;
    WiFi.softAPdisconnect(true);
}

void WiFiManager::handleRoot() {
    DEBUG_PRINTLN("WiFi: Serving config page");

    // Scan for networks
    String networks = "";
    int n = WiFi.scanNetworks();
    for (int i = 0; i < n; i++) {
        networks += "<option value=\"" + WiFi.SSID(i) + "\">" + WiFi.SSID(i) +
                    " (" + String(WiFi.RSSI(i)) + " dBm)</option>";
    }

    _server->send(200, "text/html", generateConfigPage(networks));
}

void WiFiManager::handleScan() {
    DEBUG_PRINTLN("WiFi: Rescanning networks");
    String networks = "";
    int n = WiFi.scanNetworks();
    for (int i = 0; i < n; i++) {
        if (i > 0) networks += ",";
        networks += WiFi.SSID(i) + "|" + String(WiFi.RSSI(i));
    }
    _server->send(200, "text/plain", networks);
}

void WiFiManager::handleSave() {
    DEBUG_PRINTLN("WiFi: Saving configuration");

    String ssid = _server->arg("ssid");
    String password = _server->arg("password");
    String backendUrl = _server->arg("backend");

    // Validate inputs
    if (ssid.length() == 0) {
        _server->send(400, "text/html", generateSavePage(false));
        return;
    }

    // Set default backend URL if not provided
    if (backendUrl.length() == 0) {
        backendUrl = BACKEND_URL;
    }

    // Save to NVS
    bool success = saveCredentials(ssid, password, backendUrl);

    _server->send(200, "text/html", generateSavePage(success));

    if (success) {
        // Stop config portal and reboot
        delay(2000);
        _configPortalRunning = false;
    }
}

void WiFiManager::handleNotFound() {
    // Redirect to root for captive portal behavior
    _server->sendHeader("Location", "/", true);
    _server->send(302, "text/plain", "");
}

bool WiFiManager::saveCredentials(const String& ssid, const String& password, const String& backendUrl) {
    _prefs.begin(NVS_NAMESPACE, false);  // Read-write
    _prefs.putString(NVS_WIFI_SSID, ssid);
    _prefs.putString(NVS_WIFI_PASS, password);
    _prefs.putString(NVS_BACKEND, backendUrl);
    _prefs.end();

    DEBUG_PRINTF("WiFi: Saved - SSID: %s, Backend: %s\n", ssid.c_str(), backendUrl.c_str());
    return true;
}

void WiFiManager::clearCredentials() {
    DEBUG_PRINTLN("WiFi: Clearing credentials (factory reset)");
    _prefs.begin(NVS_NAMESPACE, false);
    _prefs.clear();
    _prefs.end();
}

String WiFiManager::getBackendUrl() {
    _prefs.begin(NVS_NAMESPACE, true);
    String url = _prefs.getString(NVS_BACKEND, BACKEND_URL);
    _prefs.end();
    return url;
}

void WiFiManager::setBackendUrl(const String& url) {
    _prefs.begin(NVS_NAMESPACE, false);
    _prefs.putString(NVS_BACKEND, url);
    _prefs.end();
}

String WiFiManager::generateConfigPage(const String& networks) {
    return R"(<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KIND Display Setup</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 500px;
            margin: 50px auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            text-align: center;
            margin-bottom: 30px;
        }
        label {
            display: block;
            margin-top: 15px;
            color: #555;
            font-weight: bold;
        }
        select, input {
            width: 100%;
            padding: 10px;
            margin-top: 5px;
            border: 1px solid #ddd;
            border-radius: 5px;
            box-sizing: border-box;
        }
        button {
            width: 100%;
            padding: 12px;
            margin-top: 20px;
            background: #007bff;
            color: white;
            border: none;
            border-radius: 5px;
            font-size: 16px;
            cursor: pointer;
        }
        button:hover {
            background: #0056b3;
        }
        .info {
            background: #e7f3ff;
            padding: 10px;
            border-radius: 5px;
            margin-top: 20px;
            font-size: 14px;
            color: #555;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎨 KIND Display Setup</h1>
        <form action="/save" method="POST">
            <label for="ssid">WiFi Network:</label>
            <select id="ssid" name="ssid" required>
                <option value="">-- Select Network --</option>
                )" + networks + R"(
            </select>

            <label for="password">WiFi Password:</label>
            <input type="password" id="password" name="password" placeholder="Enter password">

            <label for="backend">Backend URL:</label>
            <input type="text" id="backend" name="backend"
                   placeholder="http://192.168.1.100:8080"
                   value=")" + String(BACKEND_URL) + R"(">

            <button type="submit">💾 Save & Connect</button>
        </form>

        <div class="info">
            <strong>📌 Instructions:</strong><br>
            1. Select your WiFi network<br>
            2. Enter password<br>
            3. Enter backend server URL<br>
            4. Click Save to connect
        </div>
    </div>
</body>
</html>)";
}

String WiFiManager::generateSavePage(bool success) {
    if (success) {
        return R"(<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Setup Complete</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 500px;
            margin: 50px auto;
            padding: 20px;
            background: #f5f5f5;
            text-align: center;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 { color: #28a745; }
        p { color: #555; font-size: 16px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>✅ Configuration Saved!</h1>
        <p>Your KIND Display is connecting to WiFi...</p>
        <p>The device will reboot shortly.</p>
    </div>
</body>
</html>)";
    } else {
        return R"(<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Setup Failed</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 500px;
            margin: 50px auto;
            padding: 20px;
            background: #f5f5f5;
            text-align: center;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 { color: #dc3545; }
        p { color: #555; }
        a {
            display: inline-block;
            margin-top: 20px;
            padding: 10px 20px;
            background: #007bff;
            color: white;
            text-decoration: none;
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>❌ Configuration Failed</h1>
        <p>Please check your settings and try again.</p>
        <a href="/">← Go Back</a>
    </div>
</body>
</html>)";
    }
}

#include "wifi_manager.h"

WiFiManager::WiFiManager() : _server(nullptr), _dnsServer(nullptr), _configPortalRunning(false) {
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

    // Start DNS server for captive portal (redirect any domain to setup page)
    _dnsServer = new DNSServer();
    _dnsServer->start(53, "*", IP);  // Redirect all domains to AP IP
    DEBUG_PRINTLN("WiFi: DNS server started for captive portal");

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
    DEBUG_PRINTF("       URL: http://%s or http://makeasmile.com\n", IP.toString().c_str());

    // Run server until configuration is saved
    while (_configPortalRunning) {
        _dnsServer->processNextRequest();  // Handle DNS requests
        _server->handleClient();
        delay(10);
    }

    // Clean up
    _dnsServer->stop();
    delete _dnsServer;
    _dnsServer = nullptr;

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
    String deviceName = _server->arg("devicename");

    // Validate inputs
    if (ssid.length() == 0) {
        _server->send(400, "text/html", generateSavePage(false));
        return;
    }

    // Set default backend URL if not provided
    if (backendUrl.length() == 0) {
        backendUrl = BACKEND_URL;
    }

    // Set default device name if not provided
    if (deviceName.length() == 0) {
        deviceName = "familydisplay";
    }

    // Save to NVS (including device name)
    _prefs.begin(NVS_NAMESPACE, false);
    _prefs.putString(NVS_WIFI_SSID, ssid);
    _prefs.putString(NVS_WIFI_PASS, password);
    _prefs.putString(NVS_BACKEND, backendUrl);
    _prefs.putString("device_name", deviceName);
    _prefs.end();

    DEBUG_PRINTF("WiFi: Saved - SSID: %s, Device: %s\n", ssid.c_str(), deviceName.c_str());

    _server->send(200, "text/html", generateSavePage(true));

    // Stop config portal and reboot
    delay(2000);
    _configPortalRunning = false;
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

String WiFiManager::getDeviceName() {
    _prefs.begin(NVS_NAMESPACE, true);
    String name = _prefs.getString("device_name", "familydisplay");
    _prefs.end();
    return name;
}

String WiFiManager::generateConfigPage(const String& networks) {
    return R"(<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kin:D - Setup Your Display</title>
    <style>
        :root {
            --bg: #0f0f0f;
            --panel: #1a1a1a;
            --panel-hover: #212121;
            --border: #2d2d2d;
            --text: #e8e8e8;
            --text-muted: #888;
            --brand: #2d8cf0;
            --brand-hover: #1a6ec0;
            --success: #27ae60;
            --radius: 8px;
            --shadow: 0 4px 16px rgba(0,0,0,0.4);
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            box-shadow: var(--shadow);
            max-width: 500px;
            width: 100%;
            padding: 40px;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        .brand {
            font-size: 32px;
            font-weight: 700;
            color: var(--brand);
            margin-bottom: 8px;
        }
        .tagline {
            font-size: 16px;
            color: var(--text-muted);
            margin-bottom: 24px;
        }
        .welcome {
            background: var(--panel-hover);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 16px;
            margin-bottom: 30px;
            font-size: 14px;
            line-height: 1.6;
            color: var(--text-muted);
        }
        label {
            display: block;
            margin-top: 20px;
            margin-bottom: 8px;
            color: var(--text);
            font-size: 14px;
            font-weight: 500;
        }
        select, input {
            width: 100%;
            padding: 12px;
            background: var(--panel-hover);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            color: var(--text);
            font-size: 14px;
            transition: border-color 0.2s;
        }
        select:focus, input:focus {
            outline: none;
            border-color: var(--brand);
        }
        input::placeholder {
            color: var(--text-muted);
        }
        .optional {
            color: var(--text-muted);
            font-size: 12px;
            font-weight: 400;
            margin-left: 4px;
        }
        button {
            width: 100%;
            padding: 14px;
            margin-top: 30px;
            background: var(--brand);
            color: white;
            border: none;
            border-radius: var(--radius);
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.2s;
        }
        button:hover {
            background: var(--brand-hover);
        }
        .footer {
            margin-top: 24px;
            padding-top: 20px;
            border-top: 1px solid var(--border);
            text-align: center;
            font-size: 12px;
            color: var(--text-muted);
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="brand">Kin:D</div>
            <div class="tagline">make a smile</div>
        </div>

        <div class="welcome">
            Welcome! Let's connect your display to WiFi and give it a name.
            Your display will refresh daily with weather, calendar events, and delightful surprises.
        </div>

        <form action="/save" method="POST">
            <label for="devicename">
                Display Name <span class="optional">(optional)</span>
            </label>
            <input type="text" id="devicename" name="devicename"
                   placeholder="e.g., Living Room, Kitchen, Bedroom"
                   maxlength="32">

            <label for="ssid">WiFi Network</label>
            <select id="ssid" name="ssid" required>
                <option value="">-- Select Network --</option>
                )" + networks + R"(
            </select>

            <label for="password">
                WiFi Password <span class="optional">(if required)</span>
            </label>
            <input type="password" id="password" name="password"
                   placeholder="Enter WiFi password">

            <input type="hidden" id="backend" name="backend"
                   value=")" + String(BACKEND_URL) + R"(">

            <button type="submit">Connect & Continue</button>
        </form>

        <div class="footer">
            Once connected, your display will fetch its first frame.<br>
            This may take 30-60 seconds.
        </div>
    </div>
</body>
</html>)";
}

String WiFiManager::generateSavePage(bool success) {
    if (success) {
        return R"(<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kin:D - Setup Complete</title>
    <style>
        :root {
            --bg: #0f0f0f;
            --panel: #1a1a1a;
            --text: #e8e8e8;
            --text-muted: #888;
            --brand: #2d8cf0;
            --success: #27ae60;
            --radius: 8px;
            --shadow: 0 4px 16px rgba(0,0,0,0.4);
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: var(--panel);
            border: 1px solid var(--success);
            border-radius: var(--radius);
            box-shadow: var(--shadow);
            max-width: 500px;
            width: 100%;
            padding: 50px 40px;
            text-align: center;
        }
        .checkmark {
            font-size: 64px;
            color: var(--success);
            margin-bottom: 20px;
        }
        .brand {
            font-size: 24px;
            font-weight: 700;
            color: var(--brand);
            margin-bottom: 8px;
        }
        h1 {
            font-size: 20px;
            color: var(--success);
            margin-bottom: 16px;
        }
        p {
            color: var(--text-muted);
            line-height: 1.6;
            margin-bottom: 12px;
        }
        .spinner {
            margin: 30px auto;
            width: 40px;
            height: 40px;
            border: 4px solid rgba(45, 140, 240, 0.2);
            border-top-color: var(--brand);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="checkmark">✓</div>
        <div class="brand">Kin:D</div>
        <h1>Setup Complete!</h1>
        <p>Your display is connecting to WiFi...</p>
        <p>Fetching your first frame from the cloud...</p>
        <div class="spinner"></div>
        <p style="font-size: 13px;">This window will close automatically.</p>
    </div>
</body>
</html>)";
    } else {
        return R"(<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kin:D - Setup Error</title>
    <style>
        :root {
            --bg: #0f0f0f;
            --panel: #1a1a1a;
            --border: #2d2d2d;
            --text: #e8e8e8;
            --text-muted: #888;
            --brand: #2d8cf0;
            --danger: #e74c3c;
            --radius: 8px;
            --shadow: 0 4px 16px rgba(0,0,0,0.4);
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: var(--panel);
            border: 1px solid var(--danger);
            border-radius: var(--radius);
            box-shadow: var(--shadow);
            max-width: 500px;
            width: 100%;
            padding: 40px;
            text-align: center;
        }
        h1 {
            font-size: 20px;
            color: var(--danger);
            margin-bottom: 16px;
        }
        p {
            color: var(--text-muted);
            margin-bottom: 24px;
        }
        a {
            display: inline-block;
            padding: 12px 24px;
            background: var(--brand);
            color: white;
            text-decoration: none;
            border-radius: var(--radius);
            font-weight: 500;
        }
        a:hover {
            background: #1a6ec0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Setup Failed</h1>
        <p>Please check your WiFi credentials and try again.</p>
        <a href="/">← Back to Setup</a>
    </div>
</body>
</html>)";
    }
}

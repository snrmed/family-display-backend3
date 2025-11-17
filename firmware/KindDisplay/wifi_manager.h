#ifndef WIFI_MANAGER_H
#define WIFI_MANAGER_H

#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <Preferences.h>
#include "config.h"

// Forward declaration to avoid circular dependency
class LEDStatus;

// ============================================================
// WiFi Configuration Manager
// ============================================================
// Handles WiFi credentials storage and setup portal
// NEW: Integrated with LED status feedback
// ============================================================

class WiFiManager {
public:
    WiFiManager();

    // Check if WiFi credentials are stored
    bool hasCredentials();

    // Load and connect to WiFi (with LED feedback)
    // Pass LED pointer for status indication
    bool connect(LEDStatus* led = nullptr);

    // Start configuration portal (AP mode with LED slow blink)
    // Pass LED pointer for status indication
    void startConfigPortal(LEDStatus* led = nullptr);

    // Save WiFi credentials to NVS
    bool saveCredentials(const String& ssid, const String& password, const String& backendUrl);

    // Clear stored credentials (factory reset)
    void clearCredentials();

    // Get stored backend URL
    String getBackendUrl();

    // Set backend URL
    void setBackendUrl(const String& url);

    // Get stored device name
    String getDeviceName();

    // Get stored email address (optional)
    String getEmail();

    // Get stored admin token (optional)
    String getAdminToken();

private:
    Preferences _prefs;
    WebServer* _server;
    DNSServer* _dnsServer;
    bool _configPortalRunning;
    LEDStatus* _led;  // NEW: LED status indicator

    // Web server handlers
    void handleRoot();
    void handleScan();
    void handleSave();
    void handleNotFound();

    // HTML pages
    String generateConfigPage(const String& networks);
    String generateSavePage(bool success);
};

#endif // WIFI_MANAGER_H

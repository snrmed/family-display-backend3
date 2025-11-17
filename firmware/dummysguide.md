🚀 Dummy's Guide to Flashing Your Kin:D Display
What You'll Need
✅ Your ESP32 e-ink development board
✅ USB-C cable (for programming)
✅ Computer (Windows, Mac, or Linux)
✅ WiFi network nearby
✅ 15 minutes of time
Step 1: Install PlatformIO
Option A: VS Code (Recommended - Easiest)
Download VS Code: https://code.visualstudio.com/
Install VS Code (just click Next, Next, Finish)
Open VS Code
Click the Extensions icon on the left sidebar (looks like 4 squares)
Search for "PlatformIO IDE"
Click Install
Wait 2-3 minutes for it to finish
Restart VS Code when it asks
Option B: Command Line (For Terminal Ninjas)
pip install platformio
Step 2: Get the Firmware Code
If you have the code already:
Open the firmware folder in VS Code (File → Open Folder)
If downloading from GitHub:
git clone https://github.com/snrmed/family-display-backend3.git
cd family-display-backend3/firmware
code .  # Opens VS Code
Step 3: Connect Your ESP32
Plug in your ESP32 to your computer with the USB-C cable
The ESP32 should light up (you might see a small LED)
Wait 10 seconds for drivers to install (Windows may show a notification)
Check if it's detected:
In VS Code:
Bottom blue bar → Click the plug icon → You should see a COM port (Windows) or /dev/tty (Mac/Linux)
Or in Terminal:
# Windows
mode

# Mac/Linux
ls /dev/tty.*
You should see something like COM3 or /dev/ttyUSB0
Step 4: Build & Upload Firmware
Using VS Code (Easy Mode):
Open the firmware folder in VS Code
Look at the bottom blue bar of VS Code
Click the ✓ (checkmark) icon → This builds the firmware
Wait 1-2 minutes... you'll see compilation messages
When it says "SUCCESS", click the → (arrow) icon → This uploads to ESP32
Wait 30 seconds... you'll see upload progress
Look for "SUCCESS" message!
Using Terminal (Pro Mode):
cd firmware
pio run -t upload
Step 5: Watch It Boot (Optional but Fun!)
Open the serial monitor to see what's happening:
In VS Code:
Click the 🔌 (plug) icon in the bottom blue bar
You'll see debug messages scrolling
Or in Terminal:
pio device monitor
You should see:
========================================
  KIND Display - Firmware v1.0
  7-Color E-Ink Display
========================================
Wake Reason: Power On / Reset
SpectraDisplay: Initializing...
QR: Rendering setup screen
WiFi: Starting configuration portal
WiFi: AP started - SSID: KIND-Setup
To exit: Press Ctrl+C
Step 6: First Time Setup
The e-ink display will show:
┌─────────────────────────┐
│    [Blue Bar]           │
│      Kin:D              │
│   make a smile          │
├─────────────────────────┤
│                         │
│   ████████████          │
│   ██        ██  ← QR    │
│   ██  QR    ██          │
│   ██        ██          │
│   ████████████          │
│                         │
├─────────────────────────┤
│  [Yellow Instructions]  │
│  1. Connect: KIND-Setup │
│  2. Pass: kind1234      │
│  3. Scan QR or visit    │
│     http://192.168.4.1  │
└─────────────────────────┘
On Your Phone:
Open WiFi settings
Connect to: KIND-Setup
Password: kind1234
Wait for captive portal to pop up (or manually go to http://192.168.4.1)
You'll see a beautiful setup page:
┌──────────────────────────┐
│        Kin:D             │
│     make a smile         │
│ ────────────────────────│
│                          │
│ Display Name: [______]   │
│ (e.g., "Living Room")   │
│                          │
│ WiFi Network: [Select ▼] │
│                          │
│ WiFi Password: [______]  │
│                          │
│ [Connect & Continue]     │
└──────────────────────────┘
Fill it out:
Display Name: Whatever you want (e.g., "Kitchen", "Bedroom")
WiFi Network: Select your home WiFi
WiFi Password: Your WiFi password
Click Connect & Continue
Step 7: Watch the Magic! ✨
Device reboots (takes 10 seconds)
Connects to your WiFi
Fetches image from backend: https://family-display-backend-867804884116.australia-southeast1.run.app/v1/raw7?device=your-display-name
E-ink display refreshes (takes 30-60 seconds - this is normal!)
Shows your personalized content with weather, calendar, dad jokes!
🎉 You're Done!
Your display will now:
✅ Wake up at 1:00 AM daily to refresh
✅ Show updated weather, calendar, and content
✅ Go back to deep sleep (uses minimal battery)
Button Controls
Your ESP32 has a button (usually labeled "BOOT"):
Short Press (< 6 seconds):
Wakes display
Triggers background reroll (new wallpaper variant)
Fetches fresh image
Goes back to sleep
Long Press (> 6 seconds):
FACTORY RESET
Clears WiFi credentials
Reboots to setup mode
Shows QR code again
Troubleshooting
"Upload failed" or "Device not found"
Check USB cable - Try a different one (some cables are power-only)
Press and hold BOOT button while uploading
Try a different USB port
Install drivers (Windows only):
Download: https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers
Install and restart computer
"WiFi connection failed"
Double-check password - Capital letters matter!
Move closer to router during setup
Check WiFi is 2.4GHz - ESP32 doesn't support 5GHz
Try factory reset - Hold button for 6 seconds
"Display shows red screen"
Red = Error
Connect to serial monitor to see error message:
pio device monitor
Common causes:
WiFi connection failed
Backend unreachable
Check serial output for details
"Display not updating"
Check backend is running - Visit: https://family-display-backend-867804884116.australia-southeast1.run.app/v1/raw7?device=familydisplay in browser
Check WiFi signal
Press button to trigger manual update
Connect to serial monitor to see error messages
"Can't connect to KIND-Setup WiFi"
Factory reset - Hold button 6+ seconds
Wait for e-ink to show QR code
Try again
Advanced: Change Settings
Edit firmware/KindDisplay/config.h:
Change wake time:
#define WAKE_HOUR     7   // Wake at 7 AM instead of 1 AM
#define WAKE_MINUTE   30  // Wake at :30 instead of :00
Change button pin:
#define PIN_BUTTON    0   // GPIO number
Change timezone: Edit KindDisplay.ino line 265:
rtcMgr.begin("pool.ntp.org", 10 * 3600, 0);  // UTC+10 (Australia)
// Or:
rtcMgr.begin("pool.ntp.org", -5 * 3600, 0);  // UTC-5 (US East Coast)
After changes, rebuild and re-upload:
pio run -t upload
Need Help?
Serial Monitor is Your Friend:
pio device monitor
Everything the device does is logged there at 115200 baud. Copy/paste errors to debug!
Check Wiring: Make sure your e-ink display ribbon cable is firmly connected to the FPC connector.
Next Steps
Print QR codes for future devices using firmware/qr_generator.html
Customize layouts in the backend designer
Add calendar integration in backend settings
Enjoy your daily smile! 🎨✨
That's it! Your Kin:D display is now live and will greet you with a smile every morning! 😊

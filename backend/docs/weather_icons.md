# Kin:D Designer – Add Weather Icon Theme Control

Task:
Patch the existing overlay_designer_v3_full.html (do not rewrite). Add a dropdown for selecting the Weather Icon Theme used in the layout JSON, and make sure the chosen value is saved under meta.iconTheme. 

The Designer must now support:
• Reading existing meta.iconTheme when loading layouts.
• Saving the selected icon theme when exporting or saving to backend.
• Defaulting to "happy-skies" if not set.
• Optionally showing a small preview icon (e.g. ☀️) next to each theme name.

Implementation Details:

1. UI Placement
Insert the new control inside the Settings / Meta panel (where layout name and deviceType are set), for example below the Device Type dropdown:

<label>Weather Icon Theme</label>
<select id="iconThemeSelect">
  <option value="happy-skies">😊 Happy Skies</option>
  <option value="soft-skies">🌈 Soft Skies</option>
  <option value="sunny-day">☀️ Sunny Day</option>
  <option value="blue-sky-pro">🌤 Blue Sky Pro</option>
</select>

Make sure it matches the existing panel styling and layout structure.

2. JS Logic
Add these behaviors to the main script section that manages layout metadata:

// When loading layout JSON
if (layout.meta && layout.meta.iconTheme) {
  document.getElementById('iconThemeSelect').value = layout.meta.iconTheme;
} else {
  document.getElementById('iconThemeSelect').value = 'happy-skies';
}

// When exporting JSON
const iconTheme = document.getElementById('iconThemeSelect').value;
layout.meta = layout.meta || {};
layout.meta.iconTheme = iconTheme;

Ensure this logic runs during Save / Export / Upload events so the selected theme is stored in the layout JSON.

3. Default on New Layout
When the Designer starts blank (no JSON loaded), initialize the dropdown to "happy-skies":

document.getElementById('iconThemeSelect').value = 'happy-skies';

4. Optional Visual Enhancement
If possible, show a small preview icon beside the selected theme name. These icons can be loaded from backend paths like:
/assets/weather-icons/happy-skies/01d.svg
/assets/weather-icons/soft-skies/01d.svg
/assets/weather-icons/sunny-day/01d.svg
/assets/weather-icons/blue-sky-pro/01d.svg

You can add a small <img> next to the dropdown label and update its src dynamically whenever the user changes the selection.

5. Validation
When exporting JSON, the result should include:

{
  "meta": {
    "name": "Kin:D layout demo",
    "deviceType": "landscape",
    "iconTheme": "happy-skies"
  },
  "elements": [ ... ]
}

6. Constraints
• Do not modify unrelated Designer functionality (dragging, resizing, shadow, color, etc.).
• Preserve existing JSON structure (meta, elements).
• Match current UI font and style.
• Maintain compatibility with the backend (which reads meta.iconTheme to select the correct weather icons).
• Default to "happy-skies" if no iconTheme is provided.

Deliverable:
A patched overlay_designer_v3_full.html that:
1. Adds the weather icon theme selector (UI + JSON support).
2. Loads and saves the field correctly.
3. Defaults to "happy-skies".
4. Optionally displays a small icon preview beside the selector.

Reference – Icon Themes:
Theme Name (UI)   | Folder / Value   | Description
---------------------------------------------------------
😊 Happy Skies     | happy-skies      | Kids-friendly faces and cheerful colors
🌈 Soft Skies      | soft-skies       | Gentle pastel minimalist icons
☀️ Sunny Day       | sunny-day        | Clean OpenWeather-style defaults
🌤 Blue Sky Pro    | blue-sky-pro     | Detailed Aeris-style professional icons

These names must match the folders stored in your GCS bucket or /assets directory:
/assets/weather-icons/<iconTheme>/<iconCode>.svg

End of file.
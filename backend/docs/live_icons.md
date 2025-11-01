# Kin:D Designer – Add Live Weather Icon Preview Switching

Task:
Patch the existing overlay_designer_v3_full.html (do not rewrite). Extend the new Weather Icon Theme dropdown so that when the user changes the theme, all weather icon elements in the canvas immediately update to display icons from that theme (no reload required). The live preview must reflect the icons that will render on the real display.

Goals:
• When a user selects a new theme in the dropdown, every element that uses a weather icon updates instantly.
• The layout JSON continues to save meta.iconTheme with the chosen value.
• Default remains "happy-skies" when no meta.iconTheme exists.
• Live preview uses actual icon SVGs from the backend or local /assets path.

Implementation Details:

1. Icon element identification
All weather icons on the canvas (elements representing current weather or forecast icons) should be identifiable by a data attribute, e.g. data-kind="weather-icon". When the user adds or imports icons that correspond to weather conditions (01d.svg, 02d.svg, etc.), make sure they carry this attribute so they can be batch-updated.

Example:
<img class="weather-icon" data-kind="weather-icon" data-code="01d" src="/assets/weather-icons/happy-skies/01d.svg" />

2. Hook into the iconThemeSelect change event
Add a listener that fires whenever the dropdown value changes.

Example:
const iconSelect = document.getElementById('iconThemeSelect');
iconSelect.addEventListener('change', () => {
  const newTheme = iconSelect.value;
  // Update all weather icons on screen
  document.querySelectorAll('[data-kind="weather-icon"]').forEach(el => {
    const code = el.getAttribute('data-code') || '01d';
    el.src = `/assets/weather-icons/${newTheme}/${code}.svg`;
  });
});

3. Update preview label / small icon
Next to the dropdown label, display a small 32x32 preview of the current theme's "01d.svg" icon. Update it at the same time:
previewImg.src = `/assets/weather-icons/${newTheme}/01d.svg`;

4. JSON consistency
The live update does not modify existing layout JSON beyond setting meta.iconTheme. When the user saves or exports, meta.iconTheme still reflects the currently selected dropdown value.

5. Default behavior
On initial load:
• If layout.meta.iconTheme exists, preload icons from that theme.
• If not, set dropdown to "happy-skies" and load icons from that folder.

6. Performance notes
• Only update <img> elements with data-kind="weather-icon" to avoid changing other graphical assets.
• Cache the last selected theme to avoid unnecessary reloads if user reselects the same one.
• Optional: preload the 01d.svg icon for each theme to reduce flicker on first switch.

7. Constraints
• Do not alter unrelated Designer functionality (dragging, resizing, JSON export/import, etc.).
• Do not rename layout.meta or existing fields.
• Keep consistent CSS and layout design.
• Maintain compatibility with backend which expects meta.iconTheme for final render.

8. Deliverable
A patched overlay_designer_v3_full.html that:
1. Contains the Weather Icon Theme dropdown (from previous task).
2. Updates all weather icons live when a new theme is selected.
3. Shows a small preview icon next to the dropdown.
4. Saves meta.iconTheme normally on export or save.

Reference – Icon Themes:
😊 Happy Skies   → /assets/weather-icons/happy-skies/
🌈 Soft Skies    → /assets/weather-icons/soft-skies/
☀️ Sunny Day     → /assets/weather-icons/sunny-day/
🌤 Blue Sky Pro  → /assets/weather-icons/blue-sky-pro/

End of file.
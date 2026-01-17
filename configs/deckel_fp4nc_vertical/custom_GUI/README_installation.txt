Gearbox Tab Installation Instructions (for qtdragon_hd)
-------------------------------------------------------

1. Backup your current qtdragon_hd .ui file:
   cp qtdragon_hd.ui qtdragon_hd_backup.ui

2. Open qtdragon_hd.ui in Qt Designer.

3. Copy the layout from 'gearbox_tab.ui' into a new tab in the main tab widget.
   - Or use qtdragon_hd.py to load the UI as an external tab if your version supports it.

4. Ensure object names match the HAL connections provided in gearbox_postgui.hal.
   - This enables live signal feedback from your fp4_gearbox component.

5. Add this line to your INI file:
   [HAL]
   POSTGUI_HALFILE = gearbox_postgui.hal

6. Restart LinuxCNC and verify the new "Gearbox" tab is functional.

Notes:
- Speeds are displayed in RPM (converted from RPS inside your component).
- Only one microswitch per motor should be active at a time.
- State machine state is shown in text and numerically.

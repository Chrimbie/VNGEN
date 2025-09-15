from PySide6 import QtGui

VNMIME = "application/x-vn-asset"
TRACK_ORDER = ["BG", "SPRITE", "DIALOG", "SFX", "MUSIC", "FX", "MENU", "LOGIC"]

TRACK_COLOR = {
    "BG":     QtGui.QColor(140, 200, 255),
    "SPRITE": QtGui.QColor(255, 200, 140),
    "DIALOG": QtGui.QColor(200, 180, 255),
    "SFX":    QtGui.QColor(160, 255, 160),
    "MUSIC":  QtGui.QColor(255, 170, 170),
    "FX":     QtGui.QColor(220, 160, 255),
    "MENU":   QtGui.QColor(255, 220, 150),   # 🟨 pale orange for menus
    "LOGIC":  QtGui.QColor(180, 220, 140),   # 🟩 greenish for labels/jumps
}


COL_BACKGROUND    = QtGui.QColor(26, 26, 34)
COL_ROW           = QtGui.QColor(38, 40, 50)
COL_TEXT          = QtGui.QColor(180, 190, 210)
COL_BLOCK_BORDER  = QtGui.QColor(20, 20, 26)
COL_GRID          = QtGui.QColor(70, 75, 95)
COL_PLAYHEAD      = QtGui.QColor(255, 90, 90)
COL_HANDLE        = QtGui.QColor(20, 20, 26)

# --- new ---
SEC_PX_MIN   = 30.0     # 30 px per second (zoomed out)
# Allow very deep zoom so milliseconds can be readable at high zooms
SEC_PX_MAX   = 8000.0   # px per second (zoomed in)
SEC_PX_STEP  = 10.0
RIGHT_GUTTER = 240      # pixels to add after the end for nicer scrolling
ROW_H        = 28
LEFT_PAD     = 90

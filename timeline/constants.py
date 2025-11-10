from PySide6 import QtGui
from vngen.config import TRACK_ORDER as _TRACK_ORDER, TRACK_COLORS_RGB

VNMIME = "application/x-vn-asset"
TRACK_ORDER = list(_TRACK_ORDER)

TRACK_COLOR = {
    name: QtGui.QColor(*TRACK_COLORS_RGB[name]) for name in TRACK_ORDER
}

COL_BACKGROUND    = QtGui.QColor(26, 26, 34)
COL_ROW           = QtGui.QColor(38, 40, 50)
COL_TEXT          = QtGui.QColor(180, 190, 210)
COL_BLOCK_BORDER  = QtGui.QColor(20, 20, 26)
COL_GRID          = QtGui.QColor(70, 75, 95)
COL_PLAYHEAD      = QtGui.QColor(255, 90, 90)
COL_HANDLE        = QtGui.QColor(20, 20, 26)

SEC_PX_MIN   = 30.0
SEC_PX_MAX   = 8000.0
SEC_PX_STEP  = 10.0
RIGHT_GUTTER = 240
ROW_H        = 28
LEFT_PAD     = 90


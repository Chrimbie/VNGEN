from __future__ import annotations
from PySide6 import QtCore, QtGui, QtWidgets
from model import TimelineModel
from .view import TimelineView
from .constants import SEC_PX_MIN, SEC_PX_MAX, SEC_PX_STEP


class TimelinePanel(QtWidgets.QWidget):
    """A composite widget: toolbar (zoom) + scroll area that hosts TimelineView."""

    # bubble up selection like the old TimelineView
    selChanged = QtCore.Signal(str, int)
    playheadChanged = QtCore.Signal(float)

    def __init__(self, model: TimelineModel, parent=None):
        super().__init__(parent)
        self._model = model

        self.view = TimelineView(model, self)

        self.scroll = QtWidgets.QScrollArea(self)
        self.scroll.setWidgetResizable(False)  # canvas drives width
        self.scroll.setWidget(self.view)
        self.scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.scroll.viewport().setCursor(QtCore.Qt.ArrowCursor)

        # Zoom bar
        tb = QtWidgets.QToolBar(self)
        tb.setIconSize(QtCore.QSize(16, 16))
        actZoomOut = tb.addAction("−")
        actZoomIn = tb.addAction("+")
        tb.addSeparator()

        self.zoomSlider = QtWidgets.QSlider(QtCore.Qt.Horizontal, self)
        self.zoomSlider.setRange(int(SEC_PX_MIN), int(SEC_PX_MAX))
        self.zoomSlider.setSingleStep(int(SEC_PX_STEP))
        self.zoomSlider.setPageStep(int(SEC_PX_STEP * 3))
        self.zoomSlider.setValue(int(self.view.sec_to_px()))
        self.zoomSlider.setFixedWidth(160)
        w = QtWidgets.QWidget(self)
        lw = QtWidgets.QHBoxLayout(w)
        lw.setContentsMargins(0, 0, 0, 0)
        lw.addWidget(QtWidgets.QLabel("Zoom:", self))
        lw.addWidget(self.zoomSlider)
        tb.addWidget(w)

        # Layout
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        lay.addWidget(tb)
        lay.addWidget(self.scroll, 1)

        # Signals
        actZoomOut.triggered.connect(lambda: self._nudge_zoom(-SEC_PX_STEP))
        actZoomIn.triggered.connect(lambda: self._nudge_zoom(+SEC_PX_STEP))
        self.zoomSlider.valueChanged.connect(self._apply_slider_zoom)

        # Bubble up selChanged
        self.view.selChanged.connect(self.selChanged)
        # Bubble up playhead changes
        self.view.playheadChanged.connect(self.playheadChanged)

        # Keep canvas width in sync with duration
        if hasattr(self._model, "durationChanged"):
            self._model.durationChanged.connect(self._refresh_geometry)

        self._refresh_geometry()

    # ---- proxies so MainWindow code keeps working ----
    @property
    def playhead(self) -> float:
        return self.view.playhead

    @playhead.setter
    def playhead(self, t: float):
        # set without double-emitting from gameplay; view emits if changed
        try:
            self.view._set_playhead(float(t))
        except Exception:
            self.view.playhead = float(t)
            self.view.update()

    def update(self):
        self.view.update()
        super().update()

    # Public helpers
    def set_zoom_px_per_sec(self, px: float):
        self.view.set_zoom_px_per_sec(px)
        self.zoomSlider.blockSignals(True)
        self.zoomSlider.setValue(int(self.view.sec_to_px()))
        self.zoomSlider.blockSignals(False)
        self._refresh_geometry()

    def center_on_time(self, t: float):
        self.view.center_on_time(t, self.scroll)

    def center_on_playhead(self):
        self.center_on_time(self.view.playhead)

    # Internals
    def _apply_slider_zoom(self, val: int):
        self.view.set_zoom_px_per_sec(float(val))
        self._refresh_geometry()

    def _nudge_zoom(self, delta: float):
        self.set_zoom_px_per_sec(self.view.sec_to_px() + delta)

    def _refresh_geometry(self):
        # Force the scroll area to re-measure the canvas
        self.view.updateGeometry()
        self.view.adjustSize()
        self.scroll.widget().resize(self.view.sizeHint())


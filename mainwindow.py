# mainwindow.py — timeline at bottom (with TimelinePanel wrapper)
from __future__ import annotations
from PySide6 import QtCore, QtGui, QtWidgets
from model import TimelineModel, Keyframe
from timeline import TimelinePanel          # uses panel wrapper (re-exported in timeline/__init__.py)
from editor import KeyframeEditor
from assets import AssetsDock
from game.widget import GameWidget


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VN Maker — Refactor")
        self.resize(1200, 800)

        self.model = TimelineModel()

        # --- central layout ---
        vsplit = QtWidgets.QSplitter(QtCore.Qt.Vertical, self)

        # Top: game preview
        self.gameWidget = GameWidget(self.model)
        vsplit.addWidget(self.gameWidget)

        # Bottom: [TimelinePanel | KeyframeEditor]
        bottom = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self)

        # Scrollable/zoomable timeline panel
        self.timelinePanel = TimelinePanel(self.model, self)
        # Keep legacy name so the rest of the code can stay the same:
        self.timeline = self.timelinePanel.view

        self.editor = KeyframeEditor()

        bottom.addWidget(self.timelinePanel)
        bottom.addWidget(self.editor)
        vsplit.addWidget(bottom)

        # preview drives timeline playhead (paint-only; no recentering by default)
        self.gameWidget.playheadChanged.connect(
            lambda t: (setattr(self.timeline, "playhead", float(t)), self.timeline.update())
        )

        # timeline scrubbing drives preview playhead
        self.timelinePanel.playheadChanged.connect(
            lambda t: (setattr(self.gameWidget, "playhead", float(t)),
                       self.gameWidget.playheadChanged.emit(self.gameWidget.playhead),
                       self.gameWidget.update())
        )

        # Sizing priorities
        vsplit.setStretchFactor(0, 5)  # preview
        vsplit.setStretchFactor(1, 2)  # bottom strip
        bottom.setStretchFactor(0, 4)  # timeline
        bottom.setStretchFactor(1, 1)  # editor

        # Desired heights/widths
        self.timeline.setMinimumHeight(220)  # canvas height; panel handles width/scroll
        self.timeline.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.editor.setMinimumWidth(280)
        self.editor.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Expanding)

        self.setCentralWidget(vsplit)
        # --- /central layout ---

        # Assets dock on the left
        self.assetsDock = AssetsDock(self)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.assetsDock)

        # signals
        # Use the panel’s bubbled selection signal (works even if internals change)
        self.timelinePanel.selChanged.connect(self._on_sel)
        self.editor.edited.connect(self._apply_edit)
        self.assetsDock.addBG.connect(self._add_bg)
        self.assetsDock.addSPR.connect(self._add_spr)
        self.assetsDock.addSFX.connect(self._add_sfx)
        self.assetsDock.addMUS.connect(self._add_mus)

        # toolbar
        tb = self.addToolBar("Playback")

        # Play / Pause
        self.actPlay = QtGui.QAction("Play/Pause", self)
        self.actPlay.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_P))
        tb.addAction(self.actPlay)
        self.actPlay.triggered.connect(self.gameWidget.toggle_play)

        # Stop (reset to start)
        self.actStop = QtGui.QAction("Stop", self)
        self.actStop.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_S))
        tb.addAction(self.actStop)
        self.actStop.triggered.connect(self.gameWidget.stop)

        tb.addSeparator()

        # Loop controls
        self.loop_enabled = False
        self.loop_a = 0.0
        self.loop_b = min(3.0, self.model.duration)

        self.actLoop = QtGui.QAction("Loop", self, checkable=True, checked=False)
        self.actSetA = QtGui.QAction("Set A", self)
        self.actSetB = QtGui.QAction("Set B", self)

        tb.addAction(self.actLoop)
        tb.addAction(self.actSetA)
        tb.addAction(self.actSetB)

        self.actLoop.toggled.connect(lambda on: setattr(self, "loop_enabled", on))
        self.actSetA.triggered.connect(lambda: setattr(self, "loop_a", float(self.timeline.playhead)))
        self.actSetB.triggered.connect(lambda: setattr(self, "loop_b", float(self.timeline.playhead)))

        # View menu: mutes + zoom helpers
        mView = self.menuBar().addMenu("&View")
        self.actMuteSFX = QtGui.QAction("Mute SFX", self, checkable=True, checked=False)
        self.actMuteMusic = QtGui.QAction("Mute MUSIC", self, checkable=True, checked=False)
        mView.addAction(self.actMuteSFX)
        mView.addAction(self.actMuteMusic)
        self.actMuteSFX.toggled.connect(self._update_mutes)
        self.actMuteMusic.toggled.connect(self._update_mutes)

        mView.addSeparator()

        actZoomIn = QtGui.QAction("Zoom In", self)
        actZoomIn.setShortcut(QtGui.QKeySequence.ZoomIn)
        actZoomOut = QtGui.QAction("Zoom Out", self)
        actZoomOut.setShortcut(QtGui.QKeySequence.ZoomOut)
        actZoomReset = QtGui.QAction("Reset Zoom", self)
        actZoomFitPlayhead = QtGui.QAction("Center on Playhead", self)

        mView.addAction(actZoomIn)
        mView.addAction(actZoomOut)
        mView.addAction(actZoomReset)
        mView.addAction(actZoomFitPlayhead)

        actZoomIn.triggered.connect(lambda: self.timelinePanel.set_zoom_px_per_sec(self.timeline.sec_to_px() + 20))
        actZoomOut.triggered.connect(lambda: self.timelinePanel.set_zoom_px_per_sec(self.timeline.sec_to_px() - 20))
        actZoomReset.triggered.connect(lambda: self.timelinePanel.set_zoom_px_per_sec(120.0))
        actZoomFitPlayhead.triggered.connect(self.timelinePanel.center_on_playhead)

        # File menu
        mFile = self.menuBar().addMenu("&File")
        actSave = QtGui.QAction("Save Project…", self)
        actLoad = QtGui.QAction("Load Project…", self)
        mFile.addAction(actSave)
        mFile.addAction(actLoad)
        actSave.triggered.connect(self._save)
        actLoad.triggered.connect(self._load)

        # Optional: set an initial zoom level via the panel
        QtCore.QTimer.singleShot(0, lambda: self.timelinePanel.set_zoom_px_per_sec(120.0))

        self._update_mutes()

    def _update_mutes(self):
        self.gameWidget.set_mutes(self.actMuteSFX.isChecked(), self.actMuteMusic.isChecked())

    def _on_sel(self, track: str, kf_id: int):
        k = self.model.find_kf(track, kf_id)
        if k:
            self.editor.load(track, k)
        # let the preview know which sprite we’re editing
        if track == "SPRITE":
            self.gameWidget.set_edit_sprite(kf_id)
        else:
            self.gameWidget.set_edit_sprite(None)

    def _apply_edit(self, payload: dict):
        tr = payload["track"]
        kf = self.model.find_kf(tr, payload["kf_id"])
        if not kf:
            return
        kf.t = float(payload["t"])
        for k, v in payload["data"].items():
            kf.data[k] = v
        self.model.tracks[tr].sort(key=lambda x: x.t)
        self.timeline.update()

    # assets adders
    def _add_bg(self, path: str):
        self.model.add_kf("BG", Keyframe(self.timeline.playhead, "BG", {"value": path}), snap=True)
        self.timeline.update()

    def _add_spr(self, path: str):
        self.model.add_kf(
            "SPRITE",
            Keyframe(
                self.timeline.playhead,
                "SPRITE",
                {"value": path, "x": 0.5, "y": 0.62, "w": 0.26, "h": 0.46, "opacity": 1.0},
            ),
            snap=True,
        )
        self.timeline.update()

    def _add_sfx(self, path: str):
        self.model.add_kf("SFX", Keyframe(self.timeline.playhead, "SFX", {"value": path, "vol": 1.0}), snap=True)
        self.timeline.update()

    def _add_mus(self, path: str):
        self.model.add_kf("MUSIC", Keyframe(self.timeline.playhead, "MUSIC", {"value": path, "vol": 1.0}), snap=True)
        self.timeline.update()

    # save/load
    def _save(self):
        fn, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Project", "", "VN Project (*.json)")
        if not fn:
            return
        with open(fn, "w", encoding="utf-8") as f:
            f.write(self.model.to_json())

    def _load(self):
        fn, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load Project", "", "VN Project (*.json)")
        if not fn:
            return
        with open(fn, "r", encoding="utf-8") as f:
            self.model.load_json(f.read())
        # Refresh timeline canvas + geometry after load
        self.timelinePanel.set_zoom_px_per_sec(self.timeline.sec_to_px())
        self.timeline.update()
    # in MainWindow
    def _add_menu_here(self):
        kf = Keyframe(self.timeline.playhead, "MENU",
                      {"prompt": "Choose:",
                       "options": [{"text": "Next", "to": self.timeline.playhead + 5.0}],
                       "duration": 5.0})
        self.model.add_kf("MENU", kf, snap=True)
        self.timeline.update()

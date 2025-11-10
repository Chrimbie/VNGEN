# mainwindow.py — timeline at bottom (with TimelinePanel wrapper)
from __future__ import annotations
from typing import Optional
from pathlib import Path
from PySide6 import QtCore, QtGui, QtWidgets
from model import TimelineModel, Keyframe
from timeline import TimelinePanel          # uses panel wrapper (re-exported in timeline/__init__.py)
from editor import KeyframeEditor
from assets import AssetsDock
from script_editor import ScriptEditorDock
from tutorial import TutorialDialog
from project_manager import ensure_project_structure
from compiler import build_project
from vngen.widget import GameWidget
from vngen.config import SPRITE_DEFAULTS


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VNGen Studio(v3.1.1) [*]")
        self.resize(1920, 1080)

        self.model = TimelineModel()
        self.model.dirtyChanged.connect(self._on_dirty_changed)
        self._selection: Optional[tuple[str, int]] = None

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
        self.model.modelChanged.connect(self.timeline.update)

        self.editor = KeyframeEditor()

        self.timelineControls = self._build_timeline_controls()
        timelineContainer = QtWidgets.QWidget()
        timelineLayout = QtWidgets.QVBoxLayout(timelineContainer)
        timelineLayout.setContentsMargins(0, 0, 0, 0)
        timelineLayout.setSpacing(4)
        timelineLayout.addWidget(self.timelineControls)
        timelineLayout.addWidget(self.timelinePanel)
        bottom.addWidget(timelineContainer)
        bottom.addWidget(self.editor)
        vsplit.addWidget(bottom)

        # preview drives timeline playhead (paint-only; no recentering by default)
        self.gameWidget.playheadChanged.connect(
            lambda t: (setattr(self.timeline, "playhead", float(t)), self.timeline.update())
        )

        # timeline scrubbing drives preview playhead
        self.timelinePanel.playheadChanged.connect(self._on_timeline_scrub)

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
        self.scriptDock = ScriptEditorDock(self.model, self)
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, self.scriptDock)

        # signals
        # Use the panel’s bubbled selection signal (works even if internals change)
        self.timelinePanel.selChanged.connect(self._on_sel)
        self.editor.edited.connect(self._apply_edit)
        self.editor.scriptRequested.connect(lambda path, create: self.open_script_asset(path, create=create))
        self.assetsDock.addBG.connect(self._add_bg)
        self.assetsDock.addSPR.connect(self._add_spr)
        self.assetsDock.addSFX.connect(self._add_sfx)
        self.assetsDock.addMUS.connect(self._add_mus)
        self.assetsDock.addScript.connect(self._add_script_logic)
        self.scriptDock.assignRequested.connect(self._assign_script_to_selection)

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
        self.actSave = QtGui.QAction("Save Project…", self)
        self.actLoad = QtGui.QAction("Load Project…", self)
        self.actBuild = QtGui.QAction("Build/Compile…", self)
        mFile.addAction(self.actSave)
        mFile.addAction(self.actLoad)
        mFile.addAction(self.actBuild)
        self.actSave.triggered.connect(self._save)
        self.actLoad.triggered.connect(self._load)
        self.actBuild.triggered.connect(self._build_dialog)
        self.actSave.setEnabled(False)

        # Help menu
        mHelp = self.menuBar().addMenu("&Help")
        self.actTutorial = QtGui.QAction("Interactive Tutorial", self)
        self.actTutorial.triggered.connect(self._show_tutorial)
        mHelp.addAction(self.actTutorial)

        # Optional: set an initial zoom level via the panel
        QtCore.QTimer.singleShot(0, lambda: self.timelinePanel.set_zoom_px_per_sec(120.0))

        self._update_mutes()
        self._on_dirty_changed(self.model.dirty)

        # show tutorial on first launch
        QtCore.QTimer.singleShot(400, self._maybe_show_tutorial)

    def _update_mutes(self):
        self.gameWidget.set_mutes(self.actMuteSFX.isChecked(), self.actMuteMusic.isChecked())

    def _build_timeline_controls(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget(self)
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(8)
        self.btnPlay = QtWidgets.QPushButton("Play")
        self.btnPause = QtWidgets.QPushButton("Pause")
        self.btnStop = QtWidgets.QPushButton("Stop")
        self.btnNext = QtWidgets.QPushButton("Next Keyframe")
        layout.addWidget(self.btnPlay)
        layout.addWidget(self.btnPause)
        layout.addWidget(self.btnStop)
        layout.addWidget(self.btnNext)
        layout.addStretch(1)
        self.btnPlay.clicked.connect(self._play_preview)
        self.btnPause.clicked.connect(self._pause_preview)
        self.btnStop.clicked.connect(self._stop_preview)
        self.btnNext.clicked.connect(self._jump_next_keyframe)
        return widget

    def open_script_asset(self, path: str, create: bool = False) -> bool:
        if not path:
            return False
        success = self.scriptDock.open_script(path, create=create)
        if not success and create:
            # try resolving via model and retry
            abs_path = self.model.resolve_asset_value(path)
            success = self.scriptDock.open_script(abs_path, create=create)
        if success:
            self.scriptDock.raise_()
            self.scriptDock.activateWindow()
        else:
            QtWidgets.QMessageBox.warning(self, "Script Editor", f"Unable to open script:\n{path}")
        return success

    def _on_timeline_scrub(self, t: float):
        self.gameWidget.scrub_to(float(t))

    def _play_preview(self):
        self.gameWidget.play()

    def _pause_preview(self):
        self.gameWidget.pause()

    def _stop_preview(self):
        self.gameWidget.stop()

    def _jump_next_keyframe(self):
        current = float(self.timeline.playhead)
        next_times = []
        for arr in self.model.tracks.values():
            for k in arr:
                if k.t > current + 1e-6:
                    next_times.append(k.t)
                    break
        if not next_times:
            return
        t = min(next_times)
        self.timelinePanel.playhead = t
        self._on_timeline_scrub(t)

    def _show_tutorial(self):
        steps = [
            {
                "title": "Welcome to VNGen Studio",
                "body": "<p>Drag assets from the dock on the left into the timeline to start building your scene.</p>"
            },
            {
                "title": "Timeline Editing",
                "body": "<p>Right-click blocks to copy, paste, cut, or open the advanced editors. "
                        "Use the scroll wheel + Ctrl to zoom.</p>"
            },
            {
                "title": "Sprite Animation",
                "body": "<p>Select a sprite block and enable animation in the editor to move or resize characters over time.</p>"
            },
            {
                "title": "Menus & Scripts",
                "body": "<p>Create interactive menus with background images and palettes. "
                        "Link options to scripts using the built-in Script Editor dock.</p>"
            },
            {
                "title": "Exporting Builds",
                "body": "<p>Use File → Build/Compile… to package your project, or run "
                        "<code>python compiler.py project.json --platform windows</code> from the CLI.</p>"
            },
        ]
        dlg = TutorialDialog(steps, self)
        dlg.exec()

    def _maybe_show_tutorial(self):
        settings = QtCore.QSettings("VNGEN", "Studio")
        if not settings.value("tutorialShown", False, type=bool):
            self._show_tutorial()
            settings.setValue("tutorialShown", True)

    def _on_dirty_changed(self, dirty: bool):
        self.setWindowModified(bool(dirty))
        if hasattr(self, "actSave"):
            self.actSave.setEnabled(bool(dirty))

    def _on_sel(self, track: str, kf_id: int):
        k = self.model.find_kf(track, kf_id)
        if k:
            self.editor.load(track, k)
            self._selection = (track, kf_id)
        else:
            self._selection = None
        self.scriptDock.set_assign_enabled(self._selection is not None)
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
            if k == "value" and isinstance(v, str):
                v = self.model.normalize_asset_value(v)
            kf.data[k] = v
        self.model.tracks[tr].sort(key=lambda x: x.t)
        self.model.touch(tr, recompute_duration=True)
        self.timeline.update()

    # assets adders
    def _add_bg(self, path: str):
        data = {"value": path, "fit": "cover", "align": "center", "zoom": 1.0}
        self.model.add_kf("BG", Keyframe(self.timeline.playhead, "BG", data), snap=True)
        self.timeline.update()

    def _add_spr(self, path: str):
        w_def, h_def = SPRITE_DEFAULTS.size
        self.model.add_kf(
            "SPRITE",
            Keyframe(
                self.timeline.playhead,
                "SPRITE",
                {"value": path, "x": 0.5, "y": 0.5, "w": w_def, "h": h_def, "opacity": SPRITE_DEFAULTS.opacity},
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

    def _add_script_logic(self, path: str):
        rel = self.model.normalize_asset_value(path)
        data = {"type": "script", "script_path": rel}
        kf = Keyframe(self.timeline.playhead, "LOGIC", data)
        self.model.add_kf("LOGIC", kf, snap=True)
        self.timeline.update()

    def _assign_script_to_selection(self, path: str):
        if not path or not self._selection:
            return
        track, kf_id = self._selection
        kf = self.model.find_kf(track, kf_id)
        if not kf:
            return
        rel = self.model.normalize_asset_value(path)
        kf.data = dict(kf.data or {})
        kf.data["script_path"] = rel
        if track == "LOGIC":
            kf.data.setdefault("type", "script")
        self.model.touch(track)
        self.timeline.update()

    # save/load
    def _save(self):
        fn, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Project", "", "VN Project (*.json)")
        if not fn:
            return
        try:
            project_path = ensure_project_structure(fn)
            self.model.set_project_file(str(project_path))
            with open(project_path, "w", encoding="utf-8") as f:
                f.write(self.model.to_json())
        except OSError as exc:
            QtWidgets.QMessageBox.critical(self, "Save Failed", str(exc))
            return
        self.model.mark_clean()

    def _load(self):
        fn, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load Project", "", "VN Project (*.json)")
        if not fn:
            return
        with open(fn, "r", encoding="utf-8") as f:
            self.model.load_json(f.read(), project_file=fn)
        # Refresh timeline canvas + geometry after load
        self.timelinePanel.set_zoom_px_per_sec(self.timeline.sec_to_px())
        self.timeline.update()

    def _build_dialog(self):
        if not self.model.project_file:
            QtWidgets.QMessageBox.information(self, "Save Required", "Please save your project first.")
            self._save()
            if not self.model.project_file:
                return
        platforms = ["windows", "mac", "linux"]
        platform, ok = QtWidgets.QInputDialog.getItem(self, "Select Platform", "Platform:", platforms, 0, False)
        if not ok or not platform:
            return
        out_dir = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose Output Directory", str(Path.cwd() / "build"))
        if not out_dir:
            return
        try:
            build_project(Path(self.model.project_file), platform, Path(out_dir))
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self, "Build Failed", str(exc))
            return
        QtWidgets.QMessageBox.information(self, "Build Complete",
                                          f"Build generated under {Path(out_dir) / platform}.")
    # in MainWindow
    def _add_menu_here(self):
        kf = Keyframe(self.timeline.playhead, "MENU",
                      {"prompt": "Choose:",
                       "options": [{"text": "Next", "to": self.timeline.playhead + 5.0}],
                       "duration": 5.0})
        self.model.add_kf("MENU", kf, snap=True)
        self.timeline.update()



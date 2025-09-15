# assets.py — drag items out with a custom MIME payload
from __future__ import annotations
from PySide6 import QtCore, QtGui, QtWidgets
import os, json

VNMIME = "application/x-vn-asset"

class AssetList(QtWidgets.QListWidget):
    def __init__(self, track: str, *a, **k):
        super().__init__(*a, **k)
        self._track = track
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.setAlternatingRowColors(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragOnly)

    def mimeTypes(self):  # advertise our custom type
        return [VNMIME, "text/uri-list", "text/plain"]

    def mimeData(self, items):
        md = QtCore.QMimeData()
        paths = []
        for it in items:
            p = it.data(QtCore.Qt.UserRole)
            if p: paths.append(p)
        payload = json.dumps({"track": self._track, "paths": paths})
        md.setData(VNMIME, payload.encode("utf-8"))
        urls = [QtCore.QUrl.fromLocalFile(p) for p in paths if p]
        if urls: md.setUrls(urls)
        return md

class AssetTabBase(QtWidgets.QWidget):
    addRequested = QtCore.Signal(str)

    def __init__(self, title: str, patterns: str, track: str, parent=None):
        super().__init__(parent)
        self.track = track
        self.patterns = patterns

        v = QtWidgets.QVBoxLayout(self); v.setContentsMargins(6,6,6,6)
        self.list = AssetList(track)
        btns = QtWidgets.QHBoxLayout()
        self.btnImport = QtWidgets.QPushButton("Import…")
        self.btnAdd = QtWidgets.QPushButton(f"Add to {track}"); self.btnAdd.setEnabled(False)
        btns.addWidget(self.btnImport,1); btns.addWidget(self.btnAdd,1)
        v.addWidget(self.list,1); v.addLayout(btns)

        self.btnAdd.clicked.connect(self._emit_selected)
        self.list.itemDoubleClicked.connect(lambda _it: self._emit_selected())
        self.list.itemSelectionChanged.connect(lambda: self.btnAdd.setEnabled(len(self.list.selectedItems())>0))

        sc1 = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Return), self); sc1.activated.connect(self._emit_selected)
        sc2 = QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Enter),  self); sc2.activated.connect(self._emit_selected)

    def add_items(self, files: list[str]):
        for f in files:
            if not f: continue
            path = os.path.abspath(f)
            it = QtWidgets.QListWidgetItem(os.path.basename(path))
            it.setToolTip(path)
            it.setData(QtCore.Qt.UserRole, path)
            self.list.addItem(it)

    def _emit_selected(self):
        for it in self.list.selectedItems():
            p = it.data(QtCore.Qt.UserRole)
            if p: self.addRequested.emit(p)

class ImageAssetTab(AssetTabBase):
    def __init__(self, track: str, parent=None):
        super().__init__("Images", "Images (*.png *.jpg *.jpeg *.bmp *.gif)", track, parent)
        self.btnImport.clicked.connect(self._import)
    def _import(self):
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Import Images", "", self.patterns)
        if files: self.add_items(files)

class SfxAssetTab(AssetTabBase):
    def __init__(self, parent=None):
        super().__init__("SFX", "Audio (*.wav *.ogg *.mp3)", "SFX", parent)
        self.btnImport.clicked.connect(self._import)
    def _import(self):
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Import SFX", "", self.patterns)
        if files: self.add_items(files)

class MusicAssetTab(AssetTabBase):
    def __init__(self, parent=None):
        super().__init__("MUSIC", "Audio (*.wav *.ogg *.mp3)", "MUSIC", parent)
        self.btnImport.clicked.connect(self._import)
    def _import(self):
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Import Music", "", self.patterns)
        if files: self.add_items(files)

class AssetsDock(QtWidgets.QDockWidget):
    addBG  = QtCore.Signal(str); addSPR = QtCore.Signal(str); addSFX = QtCore.Signal(str); addMUS = QtCore.Signal(str)
    def __init__(self, parent=None):
        super().__init__("Assets", parent)
        self.setObjectName("AssetsDock")
        w = QtWidgets.QWidget(self); self.setWidget(w)
        tabs = QtWidgets.QTabWidget(w)
        lay = QtWidgets.QVBoxLayout(w); lay.setContentsMargins(6,6,6,6); lay.addWidget(tabs)

        self.bgTab  = ImageAssetTab("BG");     tabs.addTab(self.bgTab,  "Backgrounds")
        self.spTab  = ImageAssetTab("SPRITE"); tabs.addTab(self.spTab,  "Sprites")
        self.sfxTab = SfxAssetTab();           tabs.addTab(self.sfxTab, "SFX")
        self.musTab = MusicAssetTab();         tabs.addTab(self.musTab, "Music")

        self.bgTab.addRequested.connect(self.addBG.emit)
        self.spTab.addRequested.connect(self.addSPR.emit)
        self.sfxTab.addRequested.connect(self.addSFX.emit)
        self.musTab.addRequested.connect(self.addMUS.emit)

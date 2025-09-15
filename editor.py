# editor.py — keyframe property editor (shows per-track fields)
from __future__ import annotations
from typing import Optional, Dict, Any, List
from PySide6 import QtCore, QtGui, QtWidgets
from model import Keyframe

class KeyframeEditor(QtWidgets.QWidget):
    edited = QtCore.Signal(dict)  # {track, kf_id, t, data}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._track: Optional[str] = None
        self._kf: Optional[Keyframe] = None

        self.setLayout(QtWidgets.QVBoxLayout())
        self.layout().setContentsMargins(10, 10, 10, 10)
        self.layout().setSpacing(8)

        # header
        self.lblHeader = QtWidgets.QLabel("No selection")
        self.layout().addWidget(self.lblHeader)

        # stacked editor per track
        self.stack = QtWidgets.QStackedWidget()
        self.layout().addWidget(self.stack, 1)

        # --- BG editor (adds fit/align/zoom) ---
        self.pgBG = QtWidgets.QWidget()
        fbg = QtWidgets.QFormLayout(self.pgBG)
        fbg.setFieldGrowthPolicy(QtWidgets.QFormLayout.ExpandingFieldsGrow)

        self.edBGPath = QtWidgets.QLineEdit()
        btnPickBG = QtWidgets.QPushButton("…")
        btnPickBG.setFixedWidth(28)
        rowBG = QtWidgets.QHBoxLayout()
        rowBG.addWidget(self.edBGPath, 1); rowBG.addWidget(btnPickBG)
        fbg.addRow("Image", rowBG)

        self.cbFit = QtWidgets.QComboBox()
        self.cbFit.addItems(["cover", "contain", "stretch", "native"])
        fbg.addRow("Fit", self.cbFit)

        self.cbAlign = QtWidgets.QComboBox()
        self.cbAlign.addItems([
            "center",
            "top", "bottom", "left", "right",
            "top-left", "top-right", "bottom-left", "bottom-right"
        ])
        fbg.addRow("Align", self.cbAlign)

        self.spZoom = QtWidgets.QDoubleSpinBox()
        self.spZoom.setRange(0.05, 8.0)
        self.spZoom.setSingleStep(0.05)
        self.spZoom.setDecimals(2)
        self.spZoom.setValue(1.0)
        fbg.addRow("Zoom", self.spZoom)

        self.spDurBG = QtWidgets.QDoubleSpinBox()
        self.spDurBG.setRange(0.05, 999.0); self.spDurBG.setDecimals(2); self.spDurBG.setValue(1.0)
        fbg.addRow("Duration (s)", self.spDurBG)

        self.stack.addWidget(self.pgBG)
        btnPickBG.clicked.connect(self._pick_bg)

        # --- SPRITE editor ---
        self.pgSPR = QtWidgets.QWidget()
        fs = QtWidgets.QFormLayout(self.pgSPR)
        self.edSprPath = QtWidgets.QLineEdit()
        btnPickSpr = QtWidgets.QPushButton("…"); btnPickSpr.setFixedWidth(28)
        rowSP = QtWidgets.QHBoxLayout(); rowSP.addWidget(self.edSprPath, 1); rowSP.addWidget(btnPickSpr)
        fs.addRow("Image", rowSP)

        self.spX = _spin(0.0, 1.0, 0.005); self.spY = _spin(0.0, 1.0, 0.005)
        self.spW = _spin(0.01, 1.0, 0.005); self.spH = _spin(0.01, 1.0, 0.005)
        self.spOp = _spin(0.0, 1.0, 0.05)
        self.spDurSPR = _spin(0.05, 999.0, 0.05, decimals=2, start=1.0)

        fs.addRow("Center X", self.spX);  fs.addRow("Center Y", self.spY)
        fs.addRow("Width", self.spW);     fs.addRow("Height", self.spH)
        fs.addRow("Opacity", self.spOp);  fs.addRow("Duration (s)", self.spDurSPR)

        self.stack.addWidget(self.pgSPR)
        btnPickSpr.clicked.connect(self._pick_sprite)

        # --- DIALOG editor ---
        self.pgDLG = QtWidgets.QWidget()
        fd = QtWidgets.QFormLayout(self.pgDLG)
        self.edSpeaker = QtWidgets.QLineEdit()
        self.edText = QtWidgets.QPlainTextEdit()
        self.spCps = _spin(1.0, 200.0, 1.0, decimals=1, start=24.0)
        self.spDurDLG = _spin(0.10, 999.0, 0.05, decimals=2, start=1.5)
        fd.addRow("Speaker", self.edSpeaker)
        fd.addRow("Text", self.edText)
        fd.addRow("Chars/sec", self.spCps)
        fd.addRow("Duration (s)", self.spDurDLG)
        self.stack.addWidget(self.pgDLG)

        # --- SFX editor ---
        self.pgSFX = QtWidgets.QWidget()
        ff = QtWidgets.QFormLayout(self.pgSFX)
        self.edSfxPath = QtWidgets.QLineEdit()
        btnPickSfx = QtWidgets.QPushButton("…"); btnPickSfx.setFixedWidth(28)
        rowSFX = QtWidgets.QHBoxLayout(); rowSFX.addWidget(self.edSfxPath, 1); rowSFX.addWidget(btnPickSfx)
        self.spVolSfx = _spin(0.0, 1.0, 0.05, start=1.0)
        ff.addRow("File", rowSFX); ff.addRow("Volume", self.spVolSfx)
        self.stack.addWidget(self.pgSFX)
        btnPickSfx.clicked.connect(self._pick_audio_sfx)

        # --- MUSIC editor ---
        self.pgMUS = QtWidgets.QWidget()
        fm = QtWidgets.QFormLayout(self.pgMUS)
        self.edMusPath = QtWidgets.QLineEdit()
        btnPickMus = QtWidgets.QPushButton("…"); btnPickMus.setFixedWidth(28)
        rowM = QtWidgets.QHBoxLayout(); rowM.addWidget(self.edMusPath, 1); rowM.addWidget(btnPickMus)
        self.spVolMus = _spin(0.0, 1.0, 0.05, start=1.0)
        fm.addRow("File", rowM); fm.addRow("Volume", self.spVolMus)
        self.stack.addWidget(self.pgMUS)
        btnPickMus.clicked.connect(self._pick_audio_mus)

        # --- FX editor (overlay/shake) ---
        self.pgFX = QtWidgets.QWidget()
        fx = QtWidgets.QFormLayout(self.pgFX)
        self.cbFXMode = QtWidgets.QComboBox()
        self.cbFXMode.addItems(["black", "white", "translucent", "shake"])
        self.spFXDur = _spin(0.05, 60.0, 0.05, decimals=2, start=1.0)
        self.edFXColor = QtWidgets.QLineEdit("#000000")
        self.spFrom = _spin(0.0, 1.0, 0.05, start=0.0)
        self.spTo   = _spin(0.0, 1.0, 0.05, start=1.0)
        # shake
        self.spAmp = _spin(0.0, 64.0, 1.0, start=16.0)
        self.spFreq = _spin(0.0, 60.0, 1.0, start=12.0)
        self.spDecay = _spin(0.0, 10.0, 0.1, start=2.5)
        self.spSeed = QtWidgets.QSpinBox(); self.spSeed.setRange(0, 1_000_000)

        fx.addRow("Mode", self.cbFXMode)
        fx.addRow("Duration (s)", self.spFXDur)
        fx.addRow("Color (hex)", self.edFXColor)
        fx.addRow("From α", self.spFrom); fx.addRow("To α", self.spTo)
        fx.addRow("Amplitude (px)", self.spAmp)
        fx.addRow("Frequency (Hz)", self.spFreq)
        fx.addRow("Decay", self.spDecay)
        fx.addRow("Seed", self.spSeed)
        self.stack.addWidget(self.pgFX)

        # --- MENU editor (prompt + options table) ---
        self.pgMENU = QtWidgets.QWidget()
        ml = QtWidgets.QVBoxLayout(self.pgMENU)
        formM = QtWidgets.QFormLayout()
        self.edMenuPrompt = QtWidgets.QPlainTextEdit()
        self.edMenuPrompt.setPlaceholderText("Prompt/question shown above the options…")
        formM.addRow("Prompt", self.edMenuPrompt)
        ml.addLayout(formM)

        self.tblOptions = QtWidgets.QTableWidget(0, 3)
        self.tblOptions.setHorizontalHeaderLabels(["Text", "Target (label or time)", "Script (optional)"])
        self.tblOptions.horizontalHeader().setStretchLastSection(True)
        self.tblOptions.verticalHeader().setVisible(False)
        self.tblOptions.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.tblOptions.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.tblOptions.setEditTriggers(QtWidgets.QAbstractItemView.DoubleClicked | QtWidgets.QAbstractItemView.SelectedClicked | QtWidgets.QAbstractItemView.EditKeyPressed)
        ml.addWidget(self.tblOptions, 1)

        # Script help (concise cheat-sheet)
        self.lblMenuHelp = QtWidgets.QLabel(
            "Commands: jump <label|sec>; loop <label|sec>; pause; resume"
        )
        self.lblMenuHelp.setWordWrap(True)
        self.lblMenuHelp.setStyleSheet("color: #9aa; font-size: 11px;")
        ml.addWidget(self.lblMenuHelp)

        btnRow = QtWidgets.QHBoxLayout()
        self.btnAddOpt = QtWidgets.QPushButton("Add")
        self.btnRemOpt = QtWidgets.QPushButton("Remove")
        self.btnUpOpt  = QtWidgets.QPushButton("Up")
        self.btnDnOpt  = QtWidgets.QPushButton("Down")
        btnRow.addWidget(self.btnAddOpt); btnRow.addWidget(self.btnRemOpt)
        btnRow.addStretch(1)
        btnRow.addWidget(self.btnUpOpt); btnRow.addWidget(self.btnDnOpt)
        ml.addLayout(btnRow)

        self.stack.addWidget(self.pgMENU)

        self.btnAddOpt.clicked.connect(self._opt_add)
        self.btnRemOpt.clicked.connect(self._opt_remove)
        self.btnUpOpt.clicked.connect(lambda: self._opt_move(-1))
        self.btnDnOpt.clicked.connect(lambda: self._opt_move(1))

        # --- LOGIC editor (label / jump) ---
        self.pgLOG = QtWidgets.QWidget()
        lg = QtWidgets.QFormLayout(self.pgLOG)
        self.cbLogicType = QtWidgets.QComboBox()
        self.cbLogicType.addItems(["label", "jump"])
        self.edLabelName = QtWidgets.QLineEdit()
        self.edJumpTarget = QtWidgets.QLineEdit()
        lg.addRow("Type", self.cbLogicType)
        lg.addRow("Label name", self.edLabelName)
        lg.addRow("Jump target", self.edJumpTarget)
        self.stack.addWidget(self.pgLOG)

        def _logic_changed(_idx: int):
            t = self.cbLogicType.currentText()
            self.edLabelName.setEnabled(t == "label")
            self.edJumpTarget.setEnabled(t == "jump")
        self.cbLogicType.currentIndexChanged.connect(_logic_changed)
        _logic_changed(0)

        # --- common: time + save button ---
        self.spTime = _spin(0.0, 9999.0, 0.05, decimals=3, start=0.0)
        rowBottom = QtWidgets.QHBoxLayout()
        rowBottom.addWidget(QtWidgets.QLabel("Start (s):"))
        rowBottom.addWidget(self.spTime, 1)
        self.btnApply = QtWidgets.QPushButton("Apply")
        rowBottom.addWidget(self.btnApply)
        self.layout().addLayout(rowBottom)

        self.btnApply.clicked.connect(self._emit_update)

        # default page
        self._showPage(None)

    # ---------- public API ----------
    def load(self, track: str, kf: Keyframe):
        self._track = track
        self._kf = kf
        self.lblHeader.setText(f"{track}  •  id={kf.id}")

        d = kf.data or {}
        self.spTime.setValue(float(kf.t))

        if track == "BG":
            self._showPage(self.pgBG)
            self.edBGPath.setText(d.get("value", ""))
            self.cbFit.setCurrentText(str(d.get("fit", "cover")).lower())
            self.cbAlign.setCurrentText(str(d.get("align", "center")))
            self.spZoom.setValue(float(d.get("zoom", 1.0)))
            self.spDurBG.setValue(float(d.get("duration", d.get("xfade", 1.0))))
        elif track == "SPRITE":
            self._showPage(self.pgSPR)
            self.edSprPath.setText(d.get("value", ""))
            self.spX.setValue(float(d.get("x", 0.5)))
            self.spY.setValue(float(d.get("y", 0.6)))
            self.spW.setValue(float(d.get("w", 0.26)))
            self.spH.setValue(float(d.get("h", 0.45)))
            self.spOp.setValue(float(d.get("opacity", 1.0)))
            self.spDurSPR.setValue(float(d.get("duration", 1.0)))
        elif track == "DIALOG":
            self._showPage(self.pgDLG)
            self.edSpeaker.setText(d.get("speaker", ""))
            self.edText.setPlainText(d.get("text", ""))
            self.spCps.setValue(float(d.get("cps", 24.0)))
            self.spDurDLG.setValue(float(d.get("duration", 1.5)))
        elif track == "SFX":
            self._showPage(self.pgSFX)
            self.edSfxPath.setText(d.get("value", ""))
            self.spVolSfx.setValue(float(d.get("vol", 1.0)))
        elif track == "MUSIC":
            self._showPage(self.pgMUS)
            self.edMusPath.setText(d.get("value", ""))
            self.spVolMus.setValue(float(d.get("vol", 1.0)))
        elif track == "FX":
            self._showPage(self.pgFX)
            self.cbFXMode.setCurrentText(str(d.get("mode", "black")).lower())
            self.spFXDur.setValue(float(d.get("duration", 1.0)))
            self.edFXColor.setText(str(d.get("color", "#000000")))
            self.spFrom.setValue(float(d.get("from_alpha", d.get("from", 0.0))))
            self.spTo.setValue(float(d.get("to_alpha",   d.get("to",   1.0))))
            self.spAmp.setValue(float(d.get("amplitude", 16.0)))
            self.spFreq.setValue(float(d.get("frequency", 12.0)))
            self.spDecay.setValue(float(d.get("decay", 2.5)))
            self.spSeed.setValue(int(d.get("seed", 0)))
        elif track == "MENU":
            self._showPage(self.pgMENU)
            self.edMenuPrompt.setPlainText(d.get("prompt", ""))

            # Accept both new format ([{"text","target","script"?}, ...]) and legacy ([str, ...])
            opts = d.get("options", [])
            self.tblOptions.setRowCount(0)
            for opt in opts:
                if isinstance(opt, dict):
                    text = str(opt.get("text", "Option"))
                    target = str(opt.get("target", ""))
                    script = str(opt.get("script", ""))
                else:
                    text = str(opt)
                    target = ""
                    script = ""
                self._opt_append_row(text, target, script)
            if self.tblOptions.rowCount() > 0:
                self.tblOptions.selectRow(0)
        elif track == "LOGIC":
            self._showPage(self.pgLOG)
            t = str(d.get("type", "label")).lower()
            if t not in ("label", "jump"): t = "label"
            self.cbLogicType.setCurrentText(t)
            self.edLabelName.setText(d.get("name", "Start"))
            self.edJumpTarget.setText(d.get("target", "Start"))
        else:
            self._showPage(None)

    # ---------- internals ----------
    def _showPage(self, page: Optional[QtWidgets.QWidget]):
        if page is None:
            self.stack.setCurrentIndex(-1)
            self.stack.hide()
        else:
            self.stack.show()
            self.stack.setCurrentWidget(page)

    def _emit_update(self):
        if not (self._track and self._kf):
            return
        data: Dict[str, Any] = {}
        t = float(self.spTime.value())

        if self._track == "BG":
            data = {
                "value": self.edBGPath.text(),
                "fit": self.cbFit.currentText(),
                "align": self.cbAlign.currentText(),
                "zoom": float(self.spZoom.value()),
                "duration": float(self.spDurBG.value()),
            }
        elif self._track == "SPRITE":
            data = {
                "value": self.edSprPath.text(),
                "x": float(self.spX.value()),
                "y": float(self.spY.value()),
                "w": float(self.spW.value()),
                "h": float(self.spH.value()),
                "opacity": float(self.spOp.value()),
                "duration": float(self.spDurSPR.value()),
            }
        elif self._track == "DIALOG":
            data = {
                "speaker": self.edSpeaker.text(),
                "text": self.edText.toPlainText(),
                "cps": float(self.spCps.value()),
                "duration": float(self.spDurDLG.value()),
            }
        elif self._track == "SFX":
            data = {"value": self.edSfxPath.text(), "vol": float(self.spVolSfx.value())}
        elif self._track == "MUSIC":
            data = {"value": self.edMusPath.text(), "vol": float(self.spVolMus.value())}
        elif self._track == "FX":
            data = {
                "mode": self.cbFXMode.currentText(),
                "duration": float(self.spFXDur.value()),
                "color": self.edFXColor.text(),
                "from_alpha": float(self.spFrom.value()),
                "to_alpha": float(self.spTo.value()),
                "amplitude": float(self.spAmp.value()),
                "frequency": float(self.spFreq.value()),
                "decay": float(self.spDecay.value()),
                "seed": int(self.spSeed.value()),
            }
        elif self._track == "MENU":
            opts: List[Dict[str, str]] = []
            for r in range(self.tblOptions.rowCount()):
                text_item = self.tblOptions.item(r, 0)
                target_item = self.tblOptions.item(r, 1)
                script_item = self.tblOptions.item(r, 2)
                text = text_item.text().strip() if text_item else "Option"
                target = target_item.text().strip() if target_item else ""
                script = script_item.text().strip() if script_item else ""
                row = {"text": text, "target": target}
                if script:
                    row["script"] = script
                opts.append(row)
            data = {
                "prompt": self.edMenuPrompt.toPlainText(),
                "options": opts,
            }
        elif self._track == "LOGIC":
            tname = self.cbLogicType.currentText()
            if tname == "label":
                data = {"type": "label", "name": self.edLabelName.text().strip() or "Start"}
            else:
                data = {"type": "jump", "target": self.edJumpTarget.text().strip() or "Start"}

        self.edited.emit({
            "track": self._track,
            "kf_id": self._kf.id,
            "t": t,
            "data": data,
        })

    # --- menu options helpers ---
    def _opt_append_row(self, text: str, target: str, script: str = ""):
        r = self.tblOptions.rowCount()
        self.tblOptions.insertRow(r)
        self.tblOptions.setItem(r, 0, QtWidgets.QTableWidgetItem(text))
        self.tblOptions.setItem(r, 1, QtWidgets.QTableWidgetItem(target))
        self.tblOptions.setItem(r, 2, QtWidgets.QTableWidgetItem(script))

    def _opt_add(self):
        self._opt_append_row("Option", "", "")
        self.tblOptions.selectRow(self.tblOptions.rowCount() - 1)
        self.tblOptions.editItem(self.tblOptions.item(self.tblOptions.rowCount() - 1, 0))

    def _opt_remove(self):
        r = self.tblOptions.currentRow()
        if r >= 0:
            self.tblOptions.removeRow(r)
            self.tblOptions.selectRow(max(0, min(r, self.tblOptions.rowCount()-1)))

    def _opt_move(self, delta: int):
        r = self.tblOptions.currentRow()
        if r < 0: return
        new_r = r + delta
        if 0 <= new_r < self.tblOptions.rowCount():
            # swap rows r and new_r
            for c in range(2):
                a = self.tblOptions.takeItem(r, c)
                b = self.tblOptions.takeItem(new_r, c)
                self.tblOptions.setItem(r, c, b)
                self.tblOptions.setItem(new_r, c, a)
            self.tblOptions.selectRow(new_r)

    # pickers
    def _pick_bg(self):
        fn, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Pick Background", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)")
        if fn:
            self.edBGPath.setText(fn)

    def _pick_sprite(self):
        fn, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Pick Sprite", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)")
        if fn:
            self.edSprPath.setText(fn)

    def _pick_audio_sfx(self):
        fn, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Pick SFX", "", "Audio (*.wav *.mp3 *.ogg)")
        if fn:
            self.edSfxPath.setText(fn)

    def _pick_audio_mus(self):
        fn, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Pick Music", "", "Audio (*.wav *.mp3 *.ogg)")
        if fn:
            self.edMusPath.setText(fn)


def _spin(lo: float, hi: float, step: float, *, decimals: int = 3, start: float = 0.0):
    s = QtWidgets.QDoubleSpinBox()
    s.setDecimals(decimals)
    s.setRange(lo, hi)
    s.setSingleStep(step)
    s.setValue(start)
    return s

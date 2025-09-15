from __future__ import annotations
from PySide6 import QtCore, QtGui, QtWidgets

# --- tiny editor dialog for DIALOG keyframes --------------------------------
class _DialogEditor(QtWidgets.QDialog):
    def __init__(self, parent=None, *, speaker: str = "", text: str = "", cps: float = 24.0, duration: float = 1.5):
        super().__init__(parent)
        self.setWindowTitle("Dialog")
        self.setModal(True)
        self.resize(420, 300)

        form = QtWidgets.QFormLayout(self)

        self.edSpeaker = QtWidgets.QLineEdit(speaker, self)
        self.edText = QtWidgets.QPlainTextEdit(self)
        self.edText.setPlainText(text)

        self.edCps = QtWidgets.QDoubleSpinBox(self)
        self.edCps.setRange(1.0, 200.0)
        self.edCps.setDecimals(1)
        self.edCps.setValue(float(cps))

        self.edDur = QtWidgets.QDoubleSpinBox(self)
        self.edDur.setRange(0.10, 999.0)
        self.edDur.setDecimals(2)
        self.edDur.setValue(float(duration))

        form.addRow("Speaker", self.edSpeaker)
        form.addRow("Text", self.edText)
        form.addRow("Chars/sec", self.edCps)
        form.addRow("Duration (s)", self.edDur)

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel, self)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def values(self) -> dict:
        return {
            "speaker": self.edSpeaker.text(),
            "text": self.edText.toPlainText(),
            "cps": float(self.edCps.value()),
            "duration": float(self.edDur.value()),
        }


# --- editor for FX blocks (fades + screen shake) -----------------------------
class _FxEditor(QtWidgets.QDialog):
    """Unified FX editor supporting:
       - Fade overlays: modes "black", "white", "translucent" (with color)
       - Screen shake: mode "shake" with amplitude/frequency/decay/seed
    """
    def __init__(self, parent=None, *, data: dict | None = None, default_time: float = 1.0):
        super().__init__(parent)
        self.setWindowTitle("FX")
        self.setModal(True)
        self.resize(420, 300)

        d = data or {}
        mode = (d.get("mode") or "black").lower()

        form = QtWidgets.QFormLayout(self)

        self.cmbMode = QtWidgets.QComboBox(self)
        self.cmbMode.addItems(["black", "white", "translucent", "shake"])
        idx = max(0, self.cmbMode.findText(mode))
        self.cmbMode.setCurrentIndex(idx)

        self.spDur = QtWidgets.QDoubleSpinBox(self)
        self.spDur.setRange(0.05, 999.0)
        self.spDur.setDecimals(2)
        self.spDur.setValue(float(d.get("duration", default_time)))

        # Fade fields
        self.spFrom = QtWidgets.QDoubleSpinBox(self); self.spFrom.setRange(0.0, 1.0); self.spFrom.setDecimals(2)
        self.spTo   = QtWidgets.QDoubleSpinBox(self); self.spTo  .setRange(0.0, 1.0); self.spTo  .setDecimals(2)
        self.spFrom.setValue(float(d.get("from_alpha", d.get("from", 0.0))))
        self.spTo.setValue(float(d.get("to_alpha", d.get("to", 1.0))))
        self.edColor = QtWidgets.QLineEdit(str(d.get("color", "#000000")), self)

        # Shake fields
        self.spAmp  = QtWidgets.QDoubleSpinBox(self); self.spAmp .setRange(0.0, 200.0); self.spAmp .setDecimals(1)
        self.spFreq = QtWidgets.QDoubleSpinBox(self); self.spFreq.setRange(0.0, 120.0); self.spFreq.setDecimals(1)
        self.spDecay= QtWidgets.QDoubleSpinBox(self); self.spDecay.setRange(0.0, 20.0); self.spDecay.setDecimals(2)
        self.spSeed = QtWidgets.QSpinBox(self);       self.spSeed.setRange(0, 1_000_000)
        self.spAmp.setValue(float(d.get("amplitude", 16.0)))
        self.spFreq.setValue(float(d.get("frequency", 12.0)))
        self.spDecay.setValue(float(d.get("decay", 2.5)))
        self.spSeed.setValue(int(d.get("seed", 0)))

        form.addRow("Mode", self.cmbMode)
        form.addRow("Duration (s)", self.spDur)
        form.addRow(QtWidgets.QLabel("— Fade Parameters —"))
        form.addRow("From α (0–1)", self.spFrom)
        form.addRow("To α (0–1)", self.spTo)
        form.addRow("Color (#RRGGBB)", self.edColor)
        form.addRow(QtWidgets.QLabel("— Shake Parameters —"))
        form.addRow("Amplitude (px)", self.spAmp)
        form.addRow("Frequency (Hz)", self.spFreq)
        form.addRow("Decay", self.spDecay)
        form.addRow("Seed", self.spSeed)

        # Enable/disable groups based on mode
        def _refresh_fields():
            m = self.cmbMode.currentText()
            fade_on = (m in ("black", "white", "translucent"))
            shake_on = (m == "shake")
            for w in (self.spFrom, self.spTo, self.edColor):
                w.setEnabled(fade_on)
            for w in (self.spAmp, self.spFreq, self.spDecay, self.spSeed):
                w.setEnabled(shake_on)

        self.cmbMode.currentTextChanged.connect(lambda _: _refresh_fields())
        _refresh_fields()

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel, self)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def values(self) -> dict:
        m = self.cmbMode.currentText()
        out = {"mode": m, "duration": float(self.spDur.value())}
        if m in ("black", "white", "translucent"):
            out.update({
                "from_alpha": float(self.spFrom.value()),
                "to_alpha": float(self.spTo.value()),
                "color": self.edColor.text().strip() if m == "translucent" else ("#000000" if m == "black" else "#FFFFFF"),
            })
        elif m == "shake":
            out.update({
                "amplitude": float(self.spAmp.value()),
                "frequency": float(self.spFreq.value()),
                "decay": float(self.spDecay.value()),
                "seed": int(self.spSeed.value()),
            })
        return out

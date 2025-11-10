from __future__ import annotations
from pathlib import Path
from typing import Callable, Optional, List
from PySide6 import QtCore, QtWidgets
from model import TimelineModel
from menu_palettes import MENU_PALETTES, DEFAULT_MENU_PALETTE


class MenuBuilderDialog(QtWidgets.QDialog):
    """Guided dialog for creating MENU keyframes with script-aware options."""

    def __init__(
        self,
        model: TimelineModel,
        *,
        parent: Optional[QtWidgets.QWidget] = None,
        script_opener: Optional[Callable[[str, bool], None]] = None,
    ):
        super().__init__(parent)
        self._model = model
        self._script_opener = script_opener
        self.setWindowTitle("Create Menu")
        self.setModal(True)
        self.resize(640, 520)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel("Prompt"))
        self.promptEdit = QtWidgets.QPlainTextEdit("Make a selection:")
        self.promptEdit.setPlaceholderText("Prompt/question shown above the options.")
        layout.addWidget(self.promptEdit, 1)

        palette_row = QtWidgets.QHBoxLayout()
        palette_row.addWidget(QtWidgets.QLabel("Color Palette"))
        self.paletteCombo = QtWidgets.QComboBox()
        for palette in MENU_PALETTES.values():
            self.paletteCombo.addItem(palette.name, palette.key)
        self.paletteCombo.setCurrentText(DEFAULT_MENU_PALETTE.name)
        palette_row.addWidget(self.paletteCombo, 1)

        palette_row.addWidget(QtWidgets.QLabel("Panel Opacity"))
        self.panelOpacity = QtWidgets.QDoubleSpinBox()
        self.panelOpacity.setRange(0.1, 1.0)
        self.panelOpacity.setSingleStep(0.05)
        self.panelOpacity.setValue(0.85)
        palette_row.addWidget(self.panelOpacity)
        layout.addLayout(palette_row)

        bg_row = QtWidgets.QHBoxLayout()
        bg_row.addWidget(QtWidgets.QLabel("Background Asset"))
        self.backgroundPath = QtWidgets.QLineEdit()
        bg_row.addWidget(self.backgroundPath, 1)
        self.btnPickBackground = QtWidgets.QPushButton("Browse…")
        bg_row.addWidget(self.btnPickBackground)
        layout.addLayout(bg_row)

        bg_opacity_row = QtWidgets.QHBoxLayout()
        bg_opacity_row.addWidget(QtWidgets.QLabel("Background Opacity"))
        self.backgroundOpacity = QtWidgets.QDoubleSpinBox()
        self.backgroundOpacity.setRange(0.0, 1.0)
        self.backgroundOpacity.setSingleStep(0.05)
        self.backgroundOpacity.setValue(0.3)
        bg_opacity_row.addWidget(self.backgroundOpacity)
        layout.addLayout(bg_opacity_row)

        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(
            ["Text", "Target (label or seconds)", "Script Asset (optional)"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        layout.addWidget(self.table, 3)

        btn_row = QtWidgets.QHBoxLayout()
        self.btnAdd = QtWidgets.QPushButton("Add Option")
        self.btnRemove = QtWidgets.QPushButton("Remove")
        self.btnUp = QtWidgets.QPushButton("Up")
        self.btnDown = QtWidgets.QPushButton("Down")
        self.btnLinkScript = QtWidgets.QPushButton("Link Script…")
        self.btnEditScript = QtWidgets.QPushButton("Edit in Script Editor")
        btn_row.addWidget(self.btnAdd)
        btn_row.addWidget(self.btnRemove)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btnUp)
        btn_row.addWidget(self.btnDown)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btnLinkScript)
        btn_row.addWidget(self.btnEditScript)
        layout.addLayout(btn_row)

        action_row = QtWidgets.QHBoxLayout()
        self.btnCancel = QtWidgets.QPushButton("Cancel")
        self.btnOk = QtWidgets.QPushButton("Create Menu")
        self.btnOk.setDefault(True)
        action_row.addStretch(1)
        action_row.addWidget(self.btnCancel)
        action_row.addWidget(self.btnOk)
        layout.addLayout(action_row)

        self.btnAdd.clicked.connect(self._add_option)
        self.btnRemove.clicked.connect(self._remove_option)
        self.btnUp.clicked.connect(lambda: self._move_option(-1))
        self.btnDown.clicked.connect(lambda: self._move_option(1))
        self.btnLinkScript.clicked.connect(self._link_script)
        self.btnEditScript.clicked.connect(self._edit_script)
        self.btnPickBackground.clicked.connect(self._pick_background)
        self.btnCancel.clicked.connect(self.reject)
        self.btnOk.clicked.connect(self._accept)
        self.table.itemSelectionChanged.connect(self._update_button_states)

        # Seed with two basic options
        self._add_option("Continue", "", "")
        self._add_option("Back", "", "")
        self.table.selectRow(0)
        self._update_button_states()

    # ----- actions -----
    def payload(self) -> dict:
        background = self._normalized_background()
        return {
            "prompt": self.promptEdit.toPlainText().strip(),
            "options": self._collect_options(),
            "palette": self.paletteCombo.currentData(),
            "panel_opacity": float(self.panelOpacity.value()),
            "background": background,
            "background_opacity": float(self.backgroundOpacity.value()),
        }

    def _accept(self):
        if not self._collect_options():
            QtWidgets.QMessageBox.warning(self, "Menu", "Add at least one option.")
            return
        self.accept()

    def _add_option(self, text: str = "", target: str = "", script: str = ""):
        row = self.table.rowCount()
        self.table.insertRow(row)
        for col, value in enumerate((text or "Option", target, script)):
            item = QtWidgets.QTableWidgetItem(value)
            self.table.setItem(row, col, item)
        self.table.selectRow(row)
        self._update_button_states()

    def _remove_option(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            if row > 0:
                self.table.selectRow(row - 1)
        self._update_button_states()

    def _move_option(self, delta: int):
        row = self.table.currentRow()
        if row < 0:
            return
        new_row = row + delta
        if not (0 <= new_row < self.table.rowCount()):
            return
        for col in range(self.table.columnCount()):
            cur = self.table.item(row, col).text() if self.table.item(row, col) else ""
            nxt = self.table.item(new_row, col).text() if self.table.item(new_row, col) else ""
            self.table.item(row, col).setText(nxt)
            self.table.item(new_row, col).setText(cur)
        self.table.selectRow(new_row)
        self._update_button_states()

    def _link_script(self):
        row = self.table.currentRow()
        if row < 0:
            return
        base = str((self._model.asset_root / "scripts").resolve())
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Script", base, "Python Files (*.py)"
        )
        if not path:
            return
        rel = self._model.normalize_asset_value(path)
        self._set_row_value(row, 2, rel)
        if self._script_opener:
            self._script_opener(rel, False)
        self._update_button_states()

    def _edit_script(self):
        row = self.table.currentRow()
        if row < 0:
            return
        existing = self._row_value(row, 2)
        if not existing:
            base = str((self._model.asset_root / "scripts").resolve())
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Create Script", base, "Python Files (*.py)"
            )
            if not path:
                return
            rel = self._model.normalize_asset_value(path)
            self._set_row_value(row, 2, rel)
            existing = rel
        if self._script_opener:
            self._script_opener(existing, True)
        self._update_button_states()

    def _pick_background(self):
        base = str((self._model.asset_root / "menus").resolve())
        Path(base).mkdir(parents=True, exist_ok=True)
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Menu Background", base, "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if not path:
            return
        rel = self._model.normalize_asset_value(path)
        self.backgroundPath.setText(rel)

    # ----- helpers -----
    def _collect_options(self) -> List[dict]:
        options: List[dict] = []
        for row in range(self.table.rowCount()):
            text = self._row_value(row, 0)
            target = self._row_value(row, 1)
            script = self._row_value(row, 2)
            if not text:
                continue
            entry = {"text": text}
            if target:
                entry["target"] = target
            if script:
                entry["script_path"] = script
            options.append(entry)
        return options

    def _normalized_background(self) -> str:
        raw = (self.backgroundPath.text() or "").strip()
        if not raw:
            return ""
        try:
            return self._model.normalize_asset_value(raw)
        except Exception:
            return raw

    def _row_value(self, row: int, col: int) -> str:
        item = self.table.item(row, col)
        return item.text().strip() if item else ""

    def _set_row_value(self, row: int, col: int, value: str):
        if not self.table.item(row, col):
            self.table.setItem(row, col, QtWidgets.QTableWidgetItem(value))
        else:
            self.table.item(row, col).setText(value)

    def _update_button_states(self):
        has_rows = self.table.rowCount() > 0
        row = self.table.currentRow()
        self.btnRemove.setEnabled(has_rows and row >= 0)
        self.btnUp.setEnabled(row > 0)
        self.btnDown.setEnabled(has_rows and 0 <= row < self.table.rowCount() - 1)
        self.btnLinkScript.setEnabled(row >= 0)
        self.btnEditScript.setEnabled(row >= 0)


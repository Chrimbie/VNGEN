# script_editor.py - lightweight dockable editor for Python script assets
from __future__ import annotations
from pathlib import Path
from typing import Optional
from PySide6 import QtCore, QtGui, QtWidgets
from model import TimelineModel

DEFAULT_SCRIPT_TEMPLATE = (
    "# VNGEN script\n"
    "# ctx: {'model','widget','game','layers','keyframe','playhead'}\n\n"
    "def run(ctx):\n"
    "    # Add your custom logic here\n"
    "    pass\n"
)


class ScriptEditorDock(QtWidgets.QDockWidget):
    assignRequested = QtCore.Signal(str)

    def __init__(self, model: TimelineModel, parent=None):
        super().__init__("Script Editor", parent)
        self.setObjectName("ScriptEditorDock")
        self._model = model
        self._current_path: Optional[Path] = None
        self._dirty = False

        container = QtWidgets.QWidget(self)
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)

        btn_row = QtWidgets.QHBoxLayout()
        self.btnNew = QtWidgets.QPushButton("New")
        self.btnOpen = QtWidgets.QPushButton("Open…")
        self.btnSave = QtWidgets.QPushButton("Save")
        self.btnSaveAs = QtWidgets.QPushButton("Save As…")
        self.btnAssign = QtWidgets.QPushButton("Assign to Selection")
        self.btnAssign.setEnabled(False)

        for btn in (self.btnNew, self.btnOpen, self.btnSave, self.btnSaveAs, self.btnAssign):
            btn_row.addWidget(btn)
        layout.addLayout(btn_row)

        self.pathLabel = QtWidgets.QLabel("No script loaded.")
        self.pathLabel.setObjectName("ScriptPathLabel")
        layout.addWidget(self.pathLabel)

        self.editor = QtWidgets.QPlainTextEdit()
        font = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)
        self.editor.setFont(font)
        self.editor.setTabStopDistance(self.editor.fontMetrics().horizontalAdvance(" ") * 4)
        layout.addWidget(self.editor, 1)

        self.setWidget(container)

        # connections
        self.btnNew.clicked.connect(self._new_script)
        self.btnOpen.clicked.connect(self._open_script)
        self.btnSave.clicked.connect(self._save_script)
        self.btnSaveAs.clicked.connect(lambda: self._save_script(save_as=True))
        self.btnAssign.clicked.connect(self._assign_current)
        self.editor.textChanged.connect(lambda: self._set_dirty(True))

    # ----- public helpers -----
    def set_assign_enabled(self, enabled: bool):
        self.btnAssign.setEnabled(bool(enabled) and self._current_path is not None)

    def open_script(self, path: str, *, create: bool = False, template: Optional[str] = None) -> bool:
        if not path:
            return False
        p = Path(path)
        if not p.is_absolute():
            p = (self._model.asset_root / p).resolve()
        template = template or DEFAULT_SCRIPT_TEMPLATE
        if create and not p.exists():
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(template, encoding="utf-8")
            except Exception as exc:
                QtWidgets.QMessageBox.warning(self, "Create Script", f"Unable to create script:\n{exc}")
                return False
        if not p.exists():
            QtWidgets.QMessageBox.warning(self, "Open Script", f"Script not found:\n{p}")
            return False
        try:
            text = p.read_text(encoding="utf-8")
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Open Script", f"Unable to open script:\n{exc}")
            return False
        self._current_path = p
        self.editor.setPlainText(text)
        self._set_dirty(False)
        self._update_path_label()
        self.set_assign_enabled(True)
        self.show()
        self.raise_()
        self.editor.setFocus()
        return True

    # ----- actions -----
    def _new_script(self):
        if not self._confirm_discard():
            return
        self._current_path = None
        self.editor.setPlainText(DEFAULT_SCRIPT_TEMPLATE)
        self._set_dirty(False)
        self._update_path_label()

    def _open_script(self):
        if not self._confirm_discard():
            return
        default_dir = str(self._scripts_dir())
        path_str, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open Script", default_dir, "Python Files (*.py)")
        if not path_str:
            return
        path = Path(path_str)
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Open Failed", f"Could not read script:\n{exc}")
            return
        self._current_path = path
        self.editor.setPlainText(text)
        self._set_dirty(False)
        self._update_path_label()

    def _save_script(self, save_as: bool = False) -> bool:
        path = self._current_path
        if save_as or path is None:
            default_dir = str(self._scripts_dir())
            default_dir_path = self._scripts_dir()
            default_dir_path.mkdir(parents=True, exist_ok=True)
            path_str, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Save Script", default_dir, "Python Files (*.py)")
            if not path_str:
                return False
            path = Path(path_str)
            self._current_path = path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self.editor.toPlainText(), encoding="utf-8")
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Save Failed", f"Could not save script:\n{exc}")
            return False
        self._set_dirty(False)
        self._update_path_label()
        self.set_assign_enabled(True)
        return True

    def _assign_current(self):
        if self._current_path is None:
            if not self._save_script():
                return
        if self._dirty:
            # Require save before assignment to ensure on-disk copy is current.
            if not self._prompt_save_before_assign():
                return
        if self._current_path is None:
            return
        self.assignRequested.emit(str(self._current_path))

    # ----- helpers -----
    def _prompt_save_before_assign(self) -> bool:
        ret = QtWidgets.QMessageBox.question(
            self,
            "Unsaved Changes",
            "Save changes before assigning this script?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel,
            QtWidgets.QMessageBox.Yes,
        )
        if ret == QtWidgets.QMessageBox.Cancel:
            return False
        if ret == QtWidgets.QMessageBox.Yes:
            return self._save_script()
        return True

    def _set_dirty(self, dirty: bool):
        if dirty == self._dirty:
            return
        self._dirty = dirty
        self._update_path_label()

    def _scripts_dir(self) -> Path:
        return self._model.asset_root / "scripts"

    def _update_path_label(self):
        if self._current_path:
            rel = self._rel_path(self._current_path)
            marker = "*" if self._dirty else ""
            self.pathLabel.setText(f"{rel}{marker}")
        else:
            self.pathLabel.setText("No script loaded.")

    def _rel_path(self, path: Path) -> str:
        try:
            return path.relative_to(self._model.asset_root).as_posix()
        except ValueError:
            return str(path)

    def _confirm_discard(self) -> bool:
        if not self._dirty:
            return True
        ret = QtWidgets.QMessageBox.question(
            self,
            "Discard Changes?",
            "You have unsaved changes. Discard them?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        return ret == QtWidgets.QMessageBox.Yes


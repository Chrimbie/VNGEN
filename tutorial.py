from __future__ import annotations
from typing import List, Dict
from PySide6 import QtCore, QtWidgets


class TutorialDialog(QtWidgets.QDialog):
    def __init__(self, steps: List[Dict[str, str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("VNGen Interactive Tutorial")
        self.setModal(True)
        self.resize(520, 360)
        self._steps = steps or [{"title": "Welcome", "body": "No tutorial steps defined."}]
        self._index = 0

        layout = QtWidgets.QVBoxLayout(self)
        self.lblTitle = QtWidgets.QLabel()
        font = self.lblTitle.font()
        font.setPointSize(font.pointSize() + 2)
        font.setBold(True)
        self.lblTitle.setFont(font)
        layout.addWidget(self.lblTitle)

        self.txtBody = QtWidgets.QTextBrowser()
        self.txtBody.setOpenExternalLinks(True)
        layout.addWidget(self.txtBody, 1)

        btns = QtWidgets.QHBoxLayout()
        self.btnPrev = QtWidgets.QPushButton("Back")
        self.btnNext = QtWidgets.QPushButton("Next")
        self.btnClose = QtWidgets.QPushButton("Close")
        btns.addWidget(self.btnPrev)
        btns.addWidget(self.btnNext)
        btns.addStretch(1)
        btns.addWidget(self.btnClose)
        layout.addLayout(btns)

        self.btnPrev.clicked.connect(lambda: self._advance(-1))
        self.btnNext.clicked.connect(lambda: self._advance(1))
        self.btnClose.clicked.connect(self.accept)

        self._refresh()

    def _advance(self, delta: int):
        self._index = max(0, min(len(self._steps) - 1, self._index + delta))
        self._refresh()

    def _refresh(self):
        step = self._steps[self._index]
        self.lblTitle.setText(step.get("title", "Step"))
        self.txtBody.setHtml(step.get(
            "body",
            "<p>No description.</p>"
        ))
        self.btnPrev.setEnabled(self._index > 0)
        if self._index >= len(self._steps) - 1:
            self.btnNext.setText("Finish")
            self.btnNext.clicked.disconnect()
            self.btnNext.clicked.connect(self.accept)
        else:
            if not self.btnNext.isEnabled() or self.btnNext.text() != "Next":
                try:
                    self.btnNext.clicked.disconnect()
                except Exception:
                    pass
                self.btnNext.clicked.connect(lambda: self._advance(1))
            self.btnNext.setText("Next")

import sys
from PySide6 import QtCore, QtGui, QtWidgets
from mainwindow import MainWindow


def _create_splash() -> QtWidgets.QSplashScreen:
    pixmap = QtGui.QPixmap(420, 260)
    pixmap.fill(QtGui.QColor("#1e1f2f"))
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
    painter.setPen(QtCore.Qt.NoPen)
    painter.setBrush(QtGui.QColor("#30324a"))
    painter.drawRoundedRect(10, 10, 400, 240, 12, 12)
    painter.setPen(QtGui.QPen(QtGui.QColor("#8fd3ff")))
    font = QtGui.QFont("Segoe UI", 24, QtGui.QFont.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), QtCore.Qt.AlignCenter, "VNGen Studio")
    painter.end()
    splash = QtWidgets.QSplashScreen(pixmap)
    splash.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, True)
    return splash


def main():
    app = QtWidgets.QApplication(sys.argv)
    splash = _create_splash()
    splash.show()
    app.processEvents()

    w = MainWindow()
    w.show()
    splash.finish(w)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()


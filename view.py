# timeline/view.py
from __future__ import annotations
from typing import Optional, Tuple, List
from PySide6 import QtCore, QtGui, QtWidgets
from model import TimelineModel, Keyframe, TICK_SEC
from .constants import (
    TRACK_ORDER,
    TRACK_COLOR,
    COL_BACKGROUND,
    COL_ROW,
    COL_TEXT,
    COL_BLOCK_BORDER,
    COL_GRID,
    COL_PLAYHEAD,
    COL_HANDLE,
    SEC_PX_MIN,
    SEC_PX_MAX,
    RIGHT_GUTTER,
    ROW_H,
    LEFT_PAD,
    VNMIME,
)


class TimelineView(QtWidgets.QWidget):
    # use shared TRACK_ORDER from constants

    selChanged = QtCore.Signal(str, int)  # (track, keyframe_id)
    playheadChanged = QtCore.Signal(float)

    def __init__(self, model: TimelineModel, parent=None):
        super().__init__(parent)
        self.model = model

        # geometry / zoom
        self._sec_px = 120.0
        self._row_h = ROW_H
        self._left_pad = LEFT_PAD

        # state
        self.playhead = 0.0
        self._selected: Optional[Tuple[str, int]] = None
        self._mode: Optional[str] = None  # None | "drag" | "resize"
        self._grab_dx = 0.0
        self._resize_right = False
        self._panning = False
        self._pan_last_x = 0
        self._pan_last_y = 0

        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)

        # delete shortcut
        act_del = QtGui.QAction("Delete", self)
        act_del.setShortcut(QtGui.QKeySequence.Delete)
        act_del.setShortcutContext(QtCore.Qt.WidgetWithChildrenShortcut)
        act_del.triggered.connect(self._delete_sel)
        self.addAction(act_del)

        # quick add dialog (Ctrl+D)
        act_add_dlg = QtGui.QAction("Add Dialog", self)
        act_add_dlg.setShortcut(QtGui.QKeySequence("Ctrl+D"))
        act_add_dlg.setShortcutContext(QtCore.Qt.WidgetWithChildrenShortcut)
        act_add_dlg.triggered.connect(lambda: self._add_dialog_at(self.playhead))
        self.addAction(act_add_dlg)

    # ------------- playhead helpers -------------
    def _set_playhead(self, t: float):
        t = max(0.0, min(float(self.model.duration), float(t)))
        if abs(t - float(self.playhead)) > 1e-9:
            self.playhead = t
            self.playheadChanged.emit(self.playhead)
        # repaint always for responsive scrub
        self.update()

    # ------------- sizing / zoom -------------
    def sec_to_px(self) -> float:
        return self._sec_px

    def set_zoom_px_per_sec(self, px: float):
        self._sec_px = max(float(SEC_PX_MIN), min(float(SEC_PX_MAX), float(px)))
        self.updateGeometry()
        self.update()

    def px_to_sec(self, x: float) -> float:
        return x / self._sec_px

    def time_to_x(self, t: float) -> int:
        return self._left_pad + int(t * self._sec_px)

    def x_to_time(self, x: float) -> float:
        return max(0.0, (x - self._left_pad) / self._sec_px)

    def sizeHint(self) -> QtCore.QSize:
        # width follows project duration * zoom, add right gutter for nicer scroll
        width = self._left_pad + int(self.model.duration * self._sec_px) + int(RIGHT_GUTTER)
        height = len(TRACK_ORDER) * self._row_h
        return QtCore.QSize(width, height)

    # ------------- hit / snap -------------
    def _track_at_y(self, y: int) -> Optional[str]:
        row = y // self._row_h
        if 0 <= row < len(TRACK_ORDER):
            return TRACK_ORDER[row]
        return None

    def _duration(self, tr: str, k: Keyframe) -> float:
        return self.model._eff_duration(tr, k)

    def _snap(self, t: float, tr: Optional[str] = None, ignore_id: Optional[int] = None) -> float:
        # snap to 1/10 sec and to neighbor edges (within 50 ms)
        candidates: List[float] = [round(t * 10) / 10.0]
        if tr:
            for k in self.model.tracks.get(tr, []):
                if ignore_id is not None and k.id == ignore_id:
                    continue
                candidates += [k.t, k.t + self._duration(tr, k)]
        best = min(candidates, key=lambda x: abs(x - t))
        return best if abs(best - t) <= 0.05 else t

    def _block_at(self, pos: QtCore.QPoint) -> Optional[Tuple[str, Keyframe, QtCore.QRect]]:
        tr = self._track_at_y(pos.y())
        if not tr:
            return None
        y = TRACK_ORDER.index(tr) * self._row_h + 3
        for k in self.model.tracks.get(tr, []):
            t0 = k.t
            t1 = t0 + self._duration(tr, k)
            x0 = self.time_to_x(t0)
            x1 = self.time_to_x(t1)
            rect = QtCore.QRect(x0, y, max(6, x1 - x0), self._row_h - 6)
            if rect.contains(pos):
                return tr, k, rect
        return None

    # ------------- painting -------------
    def paintEvent(self, _):
        p = QtGui.QPainter(self)
        r = self.rect()
        p.fillRect(r, COL_BACKGROUND)

        # rows + labels + blocks
        for i, name in enumerate(TRACK_ORDER):
            y = i * self._row_h
            p.fillRect(0, y, r.width(), self._row_h - 1, COL_ROW)
            p.setPen(COL_TEXT)
            p.drawText(8, y + int(self._row_h * 0.7), name)

            arr = self.model.tracks.get(name, [])
            for k in arr:
                t0 = k.t
                t1 = t0 + self._duration(name, k)
                x0 = self.time_to_x(t0)
                x1 = self.time_to_x(t1)
                rect = QtCore.QRect(x0, y + 3, max(6, x1 - x0), self._row_h - 6)

                base = TRACK_COLOR.get(name, QtGui.QColor(190, 190, 190))
                p.fillRect(rect, base)
                p.setPen(QtGui.QPen(COL_BLOCK_BORDER, 1))
                p.drawRect(rect)

                if self._selected == (name, k.id):
                    p.setPen(QtGui.QPen(QtGui.QColor(10, 10, 10), 2, QtCore.Qt.DashLine))
                    p.drawRect(rect.adjusted(-2, -2, 2, 2))

                # resize handle for all tracks
                p.fillRect(rect.right() - 4, rect.top(), 4, rect.height(), COL_HANDLE)

        # grid + playhead (adaptive units: ms .. hours)
        p.setPen(COL_GRID)
        self._draw_time_grid(p, r)

        px = self.time_to_x(self.playhead)
        p.setPen(QtGui.QPen(COL_PLAYHEAD, 2))
        p.drawLine(px, 0, px, r.height())
        p.end()

    # ---- grid helpers ----
    def _draw_time_grid(self, p: QtGui.QPainter, r: QtCore.QRect):
        # Choose step so adjacent grid lines are ~>= 80 px apart
        min_px = 80
        sec_per_px = 1.0 / max(1e-6, self._sec_px)
        min_step = min_px * sec_per_px

        # Candidate steps in seconds (covers ms to hours)
        steps = [
            0.001, 0.002, 0.005,
            0.010, 0.020, 0.050,
            0.100, 0.200, 0.500,
            1.0, 2.0, 5.0, 10.0, 15.0, 30.0,
            60.0, 120.0, 300.0, 600.0, 900.0, 1800.0,
            3600.0, 7200.0, 14400.0
        ]
        step = steps[-1]
        for s in steps:
            if s >= min_step:
                step = s
                break

        # Visible time range
        t0 = self.x_to_time(r.left())
        t1 = self.x_to_time(r.right())
        if t1 < t0:
            t0, t1 = t1, t0

        # Start from a multiple of step
        import math
        start = math.floor(t0 / step) * step
        # Safety guard
        max_lines = 2000
        n = 0
        t = start
        while t <= t1 and n < max_lines:
            x = self.time_to_x(t)
            p.drawLine(x, 0, x, r.height())
            label = self._format_time(t, step)
            p.drawText(x + 2, 12, label)
            t += step
            n += 1

    def _format_time(self, t: float, step: float) -> str:
        t = max(0.0, float(t))
        # If under a second, show ms
        if step < 0.95 and t < 1.0 and step <= 0.5:
            ms = int(round(t * 1000.0))
            return f"{ms} ms"
        # Under an hour: M:SS or S.s if small step
        if t < 3600.0:
            if step < 1.0:
                # show seconds with decimals depending on step
                # choose decimals so labels look stable
                decimals = 3 if step < 0.01 else (2 if step < 0.1 else 1)
                return f"{t:.{decimals}f}s"
            m = int(t // 60)
            s = int(round(t - m * 60))
            return f"{m}:{s:02d}"
        # 1 hour or more: H:MM:SS
        h = int(t // 3600)
        rem = t - h * 3600
        m = int(rem // 60)
        s = int(round(rem - m * 60))
        return f"{h}:{m:02d}:{s:02d}"

    # ------------- selection / mouse -------------
    def mousePressEvent(self, e: QtGui.QMouseEvent):
        # Middle-button panning start
        if e.button() == QtCore.Qt.MiddleButton:
            self._panning = True
            self._pan_last_x = e.pos().x()
            self._pan_last_y = e.pos().y()
            self.setCursor(QtCore.Qt.ClosedHandCursor)
            e.accept()
            return

        if e.button() != QtCore.Qt.LeftButton:
            return
        self.setFocus(QtCore.Qt.MouseFocusReason)
        t = self.x_to_time(e.pos().x())
        self._set_playhead(t)
        self._mode = None
        self._selected = None

        hit = self._block_at(e.pos())
        if hit:
            tr, k, rect = hit
            self._selected = (tr, k.id)
            self.selChanged.emit(tr, k.id)
            self._resize_right = (abs(e.pos().x() - rect.right()) <= 6)
            self._mode = "resize" if self._resize_right else "drag"
            self._grab_dx = t - k.t
            # cursor feedback
            if self._mode == "resize":
                self.setCursor(QtCore.Qt.SizeHorCursor)
            else:
                self.setCursor(QtCore.Qt.ClosedHandCursor)

        self.update()

    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        # Panning (middle mouse)
        if self._panning:
            dx = e.pos().x() - self._pan_last_x
            dy = e.pos().y() - self._pan_last_y
            self._pan_last_x = e.pos().x()
            self._pan_last_y = e.pos().y()
            scroll = self._scroll_area()
            if scroll:
                hbar = scroll.horizontalScrollBar()
                vbar = scroll.verticalScrollBar()
                if dx:
                    hbar.setValue(max(0, hbar.value() - int(dx)))
                if dy:
                    vbar.setValue(max(0, vbar.value() - int(dy)))
            e.accept()
            return
        t = self._snap(self.x_to_time(e.pos().x()))
        if self._mode and self._selected:
            tr, kf_id = self._selected
            k = self.model.find_kf(tr, kf_id)
            if not k:
                return
            if self._mode == "drag":
                new_t = max(0.0, t - self._grab_dx)
                k.t = self._snap(new_t, tr, ignore_id=k.id)
                self.model.tracks[tr].sort(key=lambda x: x.t)
                self._maybe_transition(tr)
            elif self._mode == "resize":
                new_end = max(k.t + 0.05, t)
                dur = new_end - k.t
                k.data["duration"] = float(dur)
                self._maybe_transition(tr)
            self.update()
        else:
            # Do not move playhead on hover; only on explicit clicks or playback
            pass

    def mouseReleaseEvent(self, _):
        self._mode = None
        if self._panning:
            self._panning = False
        self.setCursor(QtCore.Qt.ArrowCursor)
        if self._panning:
            self._panning = False
            self.setCursor(QtCore.Qt.ArrowCursor)

    def mouseDoubleClickEvent(self, e: QtGui.QMouseEvent):
        hit = self._block_at(e.pos())
        if hit:
            tr, k, _ = hit
            # double-click to select/edit (use side editor)
            self._selected = (tr, k.id)
            self.selChanged.emit(tr, k.id)
            return
        tr = self._track_at_y(e.pos().y())
        if tr == "DIALOG":
            self._add_dialog_at(self.x_to_time(e.pos().x()))
            return
        if tr == "FX":
            self._add_fx_at(self.x_to_time(e.pos().x()))
            return
        if tr == "MENU":
            self._add_menu_at(self.x_to_time(e.pos().x()))
            return
        if tr == "LOGIC":
            self._add_logic_at(self.x_to_time(e.pos().x()))
            return
        super().mouseDoubleClickEvent(e)

    # ------------- context menu -------------
    def contextMenuEvent(self, e: QtGui.QContextMenuEvent):
        pos = e.pos()
        hit = self._block_at(pos)
        tr_under = self._track_at_y(pos.y())

        menu = QtWidgets.QMenu(self)

        actDel = menu.addAction("Delete Selected")
        actDel.setShortcutVisibleInContextMenu(True)
        actDel.setEnabled(self._selected is not None)

        actAddDialog = None
        actAddMenu = None
        actAddFx = None
        actEditDialog = None
        actEditMenu = None
        actEditFx = None

        # row-specific "Add … here"
        if tr_under == "DIALOG":
            actAddDialog = menu.addAction("Add Dialog Here…")
        if tr_under == "MENU":
            actAddMenu = menu.addAction("Add Menu Here…")
        if tr_under == "FX":
            actAddFx = menu.addAction("Add FX Here…")

        # right-clicking a block → ensure selection + per-track Edit
        if hit:
            tr, k, _ = hit
            if self._selected != (tr, k.id):
                self._selected = (tr, k.id)
                self.selChanged.emit(tr, k.id)
            if tr == "DIALOG":
                actEditDialog = menu.addAction("Edit Dialog…")
            elif tr == "MENU":
                actEditMenu = menu.addAction("Edit Menu…")
            elif tr == "FX":
                actEditFx = menu.addAction("Edit FX…")

        action = menu.exec_(e.globalPos())
        if not action:
            return

        if action == actDel:
            self._delete_sel()
        elif action == actAddDialog:
            self._add_dialog_at(self.x_to_time(pos.x()))
        elif action == actAddMenu:
            self._add_menu_at(self.x_to_time(pos.x()))
        elif action == actAddFx:
            self._add_fx_at(self.x_to_time(pos.x()))
        elif action == actEditDialog and hit and hit[0] == "DIALOG":
            self._select_only(hit[0], hit[1].id)
        elif action == actEditMenu and hit and hit[0] == "MENU":
            self._select_only(hit[0], hit[1].id)
        elif action == actEditFx and hit and hit[0] == "FX":
            self._select_only(hit[0], hit[1].id)

    # ------------- create / edit helpers -------------
    def _select_only(self, track: str, kf_id: int):
        self._selected = (track, kf_id)
        self.selChanged.emit(track, kf_id)
        self.update()

    def _add_dialog_at(self, t: float):
        t = self._snap(t, "DIALOG", ignore_id=None)
        kf = Keyframe(t, "DIALOG", {"speaker": "", "text": "", "cps": 24.0, "duration": 1.5})
        self.model.add_kf("DIALOG", kf, snap=True)
        self._select_only("DIALOG", kf.id)

    def _add_menu_at(self, t: float):
        # Minimal default menu; detailed editing via side panel
        t = self._snap(t, "MENU", ignore_id=None)
        data = {"prompt": "Choose an option:", "options": ["Option A", "Option B"]}
        kf = Keyframe(t, "MENU", data)
        self.model.add_kf("MENU", kf, snap=True)
        self._select_only("MENU", kf.id)

    def _add_fx_at(self, t: float):
        t = self._snap(t, "FX", ignore_id=None)
        data = {"mode": "black", "duration": 1.0, "from_alpha": 0.0, "to_alpha": 1.0, "color": "#000000"}
        kf = Keyframe(t, "FX", data)
        self.model.add_kf("FX", kf, snap=True)
        self._select_only("FX", kf.id)

    def _add_logic_at(self, t: float):
        t = self._snap(t, "LOGIC", ignore_id=None)
        # default to a label; edit in the sidebar
        data = {"type": "label", "name": "Start"}
        kf = Keyframe(t, "LOGIC", data)
        self.model.add_kf("LOGIC", kf, snap=True)
        self._select_only("LOGIC", kf.id)

    # ------------- transitions (overlap → xfade duration) -------------
    def _maybe_transition(self, tr: str):
        if tr not in ("BG", "SPRITE"):
            return
        arr = self.model.tracks.get(tr, [])
        # clear xfade first
        for k in arr:
            k.data.pop("xfade", None)
        # for each consecutive pair: overlap → xfade = overlap
        for i in range(len(arr) - 1):
            a, b = arr[i], arr[i + 1]
            a_end = a.t + self._duration(tr, a)
            if b.t < a_end:
                overlap = max(0.0, a_end - b.t)
                a.data["xfade"] = float(overlap)
                b.data["xfade"] = float(overlap)

    # ------------- delete -------------
    def _delete_sel(self):
        if not self._selected:
            return
        tr, kf_id = self._selected
        self.model.remove_kf(tr, kf_id)
        self._selected = None
        if tr in ("BG", "SPRITE"):
            self._maybe_transition(tr)
        self.update()

    # ------------- drag & drop (assets) -------------
    def dragEnterEvent(self, e: QtGui.QDragEnterEvent):
        # Accept from assets dock or file URLs
        if e.mimeData().hasFormat(VNMIME) or e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dragMoveEvent(self, e: QtGui.QDragMoveEvent):
        # Do not alter playhead during drag; only update on click or playback
        e.acceptProposedAction()

    def dropEvent(self, e: QtGui.QDropEvent):
        import json
        t = self._snap(self.x_to_time(e.pos().x()))
        tr = self._track_at_y(e.pos().y()) or "SPRITE"
        paths: List[str] = []
        if e.mimeData().hasFormat(VNMIME):
            payload = json.loads(bytes(e.mimeData().data(VNMIME)).decode("utf-8"))
            tr = payload.get("track", tr)
            paths = payload.get("paths", [])
        elif e.mimeData().hasUrls():
            paths = [u.toLocalFile() for u in e.mimeData().urls()]

        for p in paths:
            if not p:
                continue
            data = {"value": p}
            if tr in ("SPRITE", "FX"):
                data.update({"x": 0.5, "y": 0.62, "w": 0.26, "h": 0.46, "opacity": 1.0, "duration": 1.0})
            self.model.add_kf(tr, Keyframe(t, tr, data), snap=True)
            t += 0.1  # slight offset if dropping many
        self._maybe_transition(tr)
        self.update()

    # ------------- viewport helpers -------------
    def _scroll_area(self) -> Optional[QtWidgets.QScrollArea]:
        w: Optional[QtWidgets.QWidget] = self
        while w is not None:
            if isinstance(w, QtWidgets.QScrollArea):
                return w
            w = w.parentWidget()
        return None

    def center_on_time(self, t: float, scroll: Optional[QtWidgets.QScrollArea] = None):
        scroll = scroll or self._scroll_area()
        if not scroll:
            return
        x = self.time_to_x(max(0.0, float(t)))
        bar = scroll.horizontalScrollBar()
        target = max(0, int(x - scroll.viewport().width() // 2))
        bar.setValue(target)

    # Zoom with Ctrl+Wheel, keeping mouse time stable
    def wheelEvent(self, e: QtGui.QWheelEvent):
        mods = QtWidgets.QApplication.keyboardModifiers()
        if mods & QtCore.Qt.ControlModifier:
            # time under cursor before
            pos_x = e.position().x()
            t_under = self.x_to_time(pos_x)
            delta = e.angleDelta().y()
            step = 10.0 if delta > 0 else -10.0
            old_px = self.sec_to_px()
            self.set_zoom_px_per_sec(old_px + step)
            # keep time under cursor stationary by adjusting scroll
            scroll = self._scroll_area()
            if scroll:
                new_x = self.time_to_x(t_under)
                dx = int(new_x - pos_x)
                bar = scroll.horizontalScrollBar()
                bar.setValue(max(0, bar.value() + dx))
            e.accept()
            return
        # Scroll when not zooming: default vertical; Shift for horizontal
        scroll = self._scroll_area()
        if scroll:
            dy = e.angleDelta().y()
            dx = e.angleDelta().x()
            step = 60
            if mods & QtCore.Qt.ShiftModifier:
                # horizontal scroll
                hbar = scroll.horizontalScrollBar()
                delta = dy or dx
                if mods & QtCore.Qt.AltModifier:
                    step *= 3
                hbar.setValue(max(0, hbar.value() - (step if delta > 0 else -step)))
            else:
                # vertical scroll
                vbar = scroll.verticalScrollBar()
                delta = dy or dx
                if mods & QtCore.Qt.AltModifier:
                    step *= 3
                vbar.setValue(max(0, vbar.value() - (step if delta > 0 else -step)))
            e.accept()
            return
        super().wheelEvent(e)

    # No keyboard-based playhead movement; only via playback, stop, or timeline click


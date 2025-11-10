# widget.py — Qt wrapper around GameCore, integrates TimelineModel
from __future__ import annotations
import os
from pathlib import Path
from typing import Optional
import pygame
from PySide6 import QtCore, QtGui, QtWidgets
from model import TimelineModel, Keyframe, TICK_SEC
from .logic import parse_script, LogicAction
from audio import stop_music, pause_music, resume_music
from menu_palettes import MENU_PALETTES, DEFAULT_MENU_PALETTE
from .core import GameCore
from .layers import Layers


class GameWidget(QtWidgets.QWidget):
    playheadChanged = QtCore.Signal(float)

    def __init__(self, model: TimelineModel, parent=None):
        super().__init__(parent)
        self.setMinimumSize(640, 360)
        self.model = model
        self.game = GameCore(960, 540)
        self.layers = Layers(model, (self.game.w, self.game.h))

        self.playhead = 0.0
        self._last_ms = 0
        self._playing = False
        self._dialog_end = -1.0
        self._music_end = -1.0
        self._mute_sfx = False
        self._mute_music = False

        # editing (sprite drag)
        self._edit_sprite_id: Optional[int] = None
        self._dragging = False
        self._drag_off = QtCore.QPoint(0, 0)

        # LABEL/JUMP index for branching
        self._label_index: dict[str, float] = {}

        # MENU overlay state (Qt-drawn, pauses playback)
        self._menu_active = False
        self._menu_prompt = "Choose:"
        self._menu_options: list[dict] = []          # [{text:str, to:float, script?, logic?}, ...]
        self._menu_rects: list[QtCore.QRect] = []    # clickable option rows
        self._menu_btn_text: list[QtCore.QRect] = []
        self._menu_btn_target: list[QtCore.QRect] = []
        self._menu_btn_script: list[QtCore.QRect] = []
        self._menu_kf_id: Optional[int] = None
        self._menu_active_kf: Optional[Keyframe] = None
        self._menu_palette_key: str = DEFAULT_MENU_PALETTE.key
        self._menu_panel_opacity: float = 0.85
        self._menu_background_rel: str = ""
        self._menu_background_path: str = ""
        self._menu_background_pixmap: Optional[QtGui.QPixmap] = None
        self._menu_background_opacity: float = 0.3
        # logic: pending jump target (applied at end of tick)
        self._pending_jump: Optional[float] = None

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)  # ~60 FPS

    # ----- external controls -----
    def set_mutes(self, sfx: bool, music: bool):
        self._mute_sfx, self._mute_music = sfx, music

    def toggle_play(self):
        # If a menu is up, toggling play does nothing (modal)
        if self._menu_active:
            return
        was_playing = self._playing
        self._playing = not self._playing
        if was_playing and not self._playing:
            self._pause_active_audio()
        elif not was_playing and self._playing:
            self._resume_or_realign_audio()

    def stop(self):
        self._playing = False
        self.scrub_to(0.0)
        self._music_paused = False

    def play(self):
        if not self._playing:
            self.toggle_play()

    def pause(self):
        if self._playing:
            self.toggle_play()

    @property
    def playing(self) -> bool:
        return self._playing

    def scrub_to(self, t: float, *, emit_signal: bool = True):
        """Jump preview/playback to *t* seconds and refresh state."""
        clamped = max(0.0, min(self.model.duration, float(t)))
        self.playhead = clamped
        self._last_ms = QtCore.QDateTime.currentMSecsSinceEpoch()
        self._pending_jump = None
        self._sync_states_for_current_time()
        self._update_visual_layers()
        if emit_signal:
            self.playheadChanged.emit(self.playhead)
        self.update()

    def set_edit_sprite(self, kf_id: Optional[int]):
        self._edit_sprite_id = kf_id

    # ----- input -----
    def keyPressEvent(self, e: QtGui.QKeyEvent):
        # If menu is active, allow quick numeric selection (1..9)
        if self._menu_active:
            if QtCore.Qt.Key_1 <= e.key() <= QtCore.Qt.Key_9:
                idx = e.key() - QtCore.Qt.Key_1
                if 0 <= idx < len(self._menu_options):
                    # run any per-option logic/script
                    self._run_menu_option(idx)
                    # then jump (if any target provided)
                    target = float(self._menu_options[idx].get("to", self.playhead))
                    # close and resume
                    self._menu_active = False
                    self._menu_rects = []
                    self._playing = True
                    self._menu_active_kf = None
                    self.scrub_to(target)
                    e.accept()
                    return
            # ignore other keys while menu is up
            e.accept()
            return

        if e.key() == QtCore.Qt.Key_Space:
            self.toggle_play()
        else:
            super().keyPressEvent(e)

    def _to_game_pt(self, pos: QtCore.QPoint) -> QtCore.QPoint:
        sx = self.game.w / max(1, self.width())
        sy = self.game.h / max(1, self.height())
        return QtCore.QPoint(int(pos.x() * sx), int(pos.y() * sy))

    def mousePressEvent(self, e: QtGui.QMouseEvent):
        # If a menu is active, clicks choose an option (Qt overlay rects)
        if self._menu_active and e.button() == QtCore.Qt.LeftButton:
            # Check per-option edit buttons first
            for idx, br in enumerate(self._menu_btn_text):
                if br.contains(e.pos()):
                    self._edit_menu_option(idx, "text")
                    e.accept(); return
            for idx, br in enumerate(self._menu_btn_target):
                if br.contains(e.pos()):
                    self._edit_menu_option(idx, "target")
                    e.accept(); return
            for idx, br in enumerate(self._menu_btn_script):
                if br.contains(e.pos()):
                    self._edit_menu_option(idx, "script")
                    e.accept(); return
            for idx, rect in enumerate(self._menu_rects):
                if rect.contains(e.pos()) and idx < len(self._menu_options):
                    # run any per-option logic/script
                    self._run_menu_option(idx)
                    # then jump and resume
                    target = float(self._menu_options[idx].get("to", self.playhead))
                    self._menu_active = False
                    self._menu_rects = []
                    self._playing = True
                    self._menu_active_kf = None
                    self.scrub_to(target)
                    e.accept()
                    return
            # clicked outside: keep paused
            e.accept()
            return

        # sprite dragging (only when no menu)
        if (e.button() == QtCore.Qt.LeftButton and
            not self._menu_active and
            self._edit_sprite_id is not None and self.game.spr_img):
            gp = self._to_game_pt(e.pos())
            r = self.game.spr_rect
            if r.collidepoint(gp.x(), gp.y()):
                self._dragging = True
                self._drag_off = QtCore.QPoint(gp.x() - r.x, gp.y() - r.y)
                self.setCursor(QtCore.Qt.ClosedHandCursor)
                e.accept()
                return

        super().mousePressEvent(e)

    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        # no hover effects for menu; keep it simple

        if self._dragging and self._edit_sprite_id is not None:
            gp = self._to_game_pt(e.pos())
            r = self.game.spr_rect.copy()
            tlx = gp.x() - self._drag_off.x()
            tly = gp.y() - self._drag_off.y()
            tlx = max(0, min(self.game.w - r.width, tlx))
            tly = max(0, min(self.game.h - r.height, tly))
            r.topleft = (tlx, tly)

            kf = self.model.find_kf("SPRITE", self._edit_sprite_id)
            if kf is not None:
                w_norm = r.width / self.game.w
                h_norm = r.height / self.game.h
                cx = (r.x + r.width / 2) / self.game.w
                cy = (r.y + r.height / 2) / self.game.h
                kf.data.update({"x": cx, "y": cy, "w": w_norm, "h": h_norm})

            self.game.spr_rect = r
            if hasattr(self.window(), "timeline"):
                self.window().timeline.update()
            self.update()
            e.accept()
            return

        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        if e.button() == QtCore.Qt.LeftButton and self._dragging:
            self._dragging = False
            self.setCursor(QtCore.Qt.ArrowCursor)
            e.accept()
            return
        super().mouseReleaseEvent(e)

    # ----- tick -----
    def _tick(self):
        cur_ms = QtCore.QDateTime.currentMSecsSinceEpoch()
        if self._last_ms == 0:
            self._last_ms = cur_ms
        dt = max(0.0, min(0.05, (cur_ms - self._last_ms) * 1e-3))
        self._last_ms = cur_ms

        # keep label index fresh (tiny scan)
        self._rebuild_labels()

        jumped = False
        if self._playing:
            prev = self.playhead
            self.playhead = min(self.model.duration, self.playhead + dt)

            # preview loop A/B (UI loop)
            main = self.window()
            if getattr(main, "loop_enabled", False) and self._playing:
                a = getattr(main, "loop_a", 0.0)
                b = getattr(main, "loop_b", self.model.duration)
                if b > a + 1e-6 and self.playhead >= b:
                    self.playhead = a
                    prev = a - TICK_SEC
                    jumped = True

            # fire keyframe entries
            for track, k in self.model.keyframes_at(prev, self.playhead):
                self._apply_keyframe_enter(track, k)

            # end gates
            eps = 1e-6
            if self._dialog_end >= 0 and self.playhead > self._dialog_end + eps:
                self.game.set_dialog("", "", 24.0, -1.0, -1.0)
            if self._music_end >= 0 and self.playhead > self._music_end + eps:
                stop_music()
                self._music_paused = False

        # Apply pending jump from LOGIC after processing entries
        if self._pending_jump is not None:
            self.playhead = max(0.0, min(self.model.duration, float(self._pending_jump)))
            self._pending_jump = None
            jumped = True

        if jumped:
            self._sync_states_for_current_time()

        self._update_visual_layers()
        self.playheadChanged.emit(self.playhead)
        self.update()

    def _sync_states_for_current_time(self):
        """Rebuild dialog/music/menu state after a non-linear jump."""
        self._dialog_end = -1.0
        self._music_end = -1.0
        self._music_paused = False
        stop_music()

        # clear modal UI state; per-frame update will repopulate if needed
        self._menu_active = False
        self._menu_rects = []
        self._menu_options = []
        self._menu_btn_text = []
        self._menu_btn_target = []
        self._menu_btn_script = []
        self._menu_kf_id = None
        self._menu_active_kf = None

        dlg_blocks = self.layers.active_blocks("DIALOG", self.playhead)
        if dlg_blocks:
            self._apply_dialog_block(dlg_blocks[-1])
        else:
            self.game.set_dialog("", "", 24.0, -1.0, -1.0)

        music_blocks = self.layers.active_blocks("MUSIC", self.playhead)
        if self._playing and music_blocks and not self._mute_music:
            k = music_blocks[-1]
            offset = self.playhead - k.t
            self._start_music_block(k, offset=offset)

    def _apply_dialog_block(self, k: Keyframe):
        d = k.data or {}
        eff_end = k.t + self.model._eff_duration("DIALOG", k)
        self.game.set_dialog(d.get("speaker", ""), d.get("text", ""),
                             float(d.get("cps", 24.0)), k.t, eff_end)
        self._dialog_end = eff_end

    def _start_music_block(self, k: Keyframe, *, offset: Optional[float] = None):
        if self._mute_music:
            return
        d = k.data or {}
        path = self.model.resolve_asset_value(d.get("value", ""))
        vol = float(d.get("vol", 1.0))
        if os.path.isfile(path):
            from audio import play_music
            if offset is None:
                offset = max(0.0, self.playhead - k.t)
            else:
                offset = max(0.0, float(offset))
            play_music(path, vol, loop=False, start=offset)
            self._music_end = k.t + self.model._eff_duration("MUSIC", k)
            self._music_paused = False
        else:
            stop_music()
            self._music_end = -1.0
            self._music_paused = False

    def _ensure_music_for_current_time(self):
        if self._mute_music:
            return
        blocks = self.layers.active_blocks("MUSIC", self.playhead)
        if blocks:
            k = blocks[-1]
            offset = self.playhead - k.t
            self._start_music_block(k, offset=offset)

    def _pause_active_audio(self):
        if self._mute_music:
            return
        try:
            if pygame.mixer.music.get_busy():
                pause_music()
                self._music_paused = True
        except Exception:
            self._music_paused = False

    def _resume_or_realign_audio(self):
        if self._mute_music:
            return
        if self._music_paused:
            try:
                resume_music()
                self._music_paused = False
                return
            except Exception:
                self._music_paused = False
        self._ensure_music_for_current_time()

    # ----- per-frame layers -----
    def _update_visual_layers(self):
        t = self.playhead

        # BG
        bg_overlap = self.layers.active_blocks("BG", t)
        if len(bg_overlap) == 0:
            self.game.set_backgrounds_ex(None, None, 0.0, 0.0,
                                         fit="cover", align="center", zoom=1.0)
        elif len(bg_overlap) == 1:
            cur = bg_overlap[-1]
            cur_path = self.model.resolve_asset_value(cur.data.get("value", ""))
            fit, align, zoom = self._bg_params(cur)
            self.game.set_backgrounds_ex(cur_path, None, 0.0, 0.0,
                                         fit=fit, align=align, zoom=zoom)
        else:
            prev = bg_overlap[-2]; cur = bg_overlap[-1]
            cur_path = self.model.resolve_asset_value(cur.data.get("value", ""))
            prev_path = self.model.resolve_asset_value(prev.data.get("value", ""))
            prev_end = prev.t + self.model._eff_duration("BG", prev)
            overlap  = prev_end - cur.t
            fit, align, zoom = self._bg_params(cur)
            if overlap > 0:
                self.game.set_backgrounds_ex(cur_path, prev_path,
                                             float(overlap), float(cur.t),
                                             fit=fit, align=align, zoom=zoom)
            else:
                self.game.set_backgrounds_ex(cur_path, None, 0.0, 0.0,
                                             fit=fit, align=align, zoom=zoom)

        # SPRITE
        spr_overlap = self.layers.active_blocks("SPRITE", t)
        if len(spr_overlap) == 0:
            self.game.set_sprite_layers(None, None, 0.0, 0.0)
        elif len(spr_overlap) == 1:
            cur = spr_overlap[-1]
            r, op = self.layers.sprite_rect_opacity(cur, t)
            cur_path = self.model.resolve_asset_value(cur.data.get("value", ""))
            self.game.set_sprite_layers((cur_path, r, op), None, 0.0, 0.0)
        else:
            prev = spr_overlap[-2]; cur = spr_overlap[-1]
            prev_end = prev.t + self.model._eff_duration("SPRITE", prev)
            overlap  = prev_end - cur.t
            r_cur, op_cur = self.layers.sprite_rect_opacity(cur, t)
            prev_rect, _ = self.layers.sprite_rect_opacity(prev, t)
            cur_path = self.model.resolve_asset_value(cur.data.get("value", ""))
            prev_path = self.model.resolve_asset_value(prev.data.get("value", ""))
            if overlap > 0:
                self.game.set_sprite_layers((cur_path, r_cur, op_cur),
                                            (prev_path, prev_rect, 1.0),
                                            float(overlap), float(cur.t))
            else:
                self.game.set_sprite_layers((cur_path, r_cur, op_cur), None, 0.0, 0.0)

        # FX (overlay/shake)
        fx_overlap = self.layers.active_blocks("FX", t)
        if fx_overlap:
            fxk = fx_overlap[-1]
            d = fxk.data; mode = (d.get("mode") or "").lower()
            dur  = float(d.get("duration", 1.0))
            fa   = float(d.get("from_alpha", d.get("from", 0.0)))
            ta   = float(d.get("to_alpha",   d.get("to",   1.0)))
            color = self.layers.hex_to_rgb(str(d.get("color", "#000000")))
            if mode in ("black", "white", "translucent"):
                self.game.set_fx_overlay(mode, dur, fa, ta, start_time=fxk.t, color=color)
            elif mode == "shake":
                amp = float(d.get("amplitude", 16.0))
                freq = float(d.get("frequency", 12.0))
                dec = float(d.get("decay", 2.5))
                seed = int(d.get("seed", 0))
                self.game.start_shake(start_time=fxk.t, duration=dur, amplitude_px=amp,
                                      frequency_hz=freq, decay=dec, seed=seed)
        else:
            self.game.set_fx_overlay(None, 0.0, 0.0, 0.0, start_time=t, color=(0, 0, 0))

        # MENU: if any active, enable overlay and pause playback
        menu_overlap = self.layers.active_blocks("MENU", t)
        if menu_overlap:
            mk = menu_overlap[-1]
            d = mk.data or {}
            self._menu_kf_id = mk.id
            self._menu_active_kf = mk
            self._menu_prompt = str(d.get("prompt", "Choose:"))

            # normalize options → list[{text, to: seconds}]
            norm_opts: list[dict] = []
            for opt in d.get("options", []):
                if isinstance(opt, dict):
                    text = (opt.get("text") or "").strip() or "(option)"
                    # accept either "target" (label or seconds) or already-resolved "to"
                    target_raw = str(opt.get("target", opt.get("to", "")))
                    to_time = self._resolve_target_to_time(target_raw, default=t)
                    row = {"text": text, "to": to_time}
                    script = str(opt.get("script", "")).strip()
                    if script:
                        row["script"] = script
                    script_asset = str(opt.get("script_path") or opt.get("script_asset") or "").strip()
                    if script_asset:
                        row["script_path"] = script_asset
                    logic = opt.get("logic", None)
                    if logic is not None:
                        row["logic"] = logic
                    norm_opts.append(row)
                else:
                    norm_opts.append({"text": str(opt), "to": t})
            self._menu_options = norm_opts

            # Pause playback while menu is shown
            self._playing = False
            self._menu_active = True
        # do not auto-clear here: we keep menu until the user clicks

    # ----- “enter” events: audio/dialog only -----
    def _apply_keyframe_enter(self, track: str, k: Keyframe):
        d = k.data or {}

        if track == "DIALOG":
            self._apply_dialog_block(k)
        elif track == "SFX":
            if not self._mute_sfx:
                path = self.model.resolve_asset_value(d.get("value",""))
                vol = float(d.get("vol",1.0))
                if os.path.isfile(path):
                    from audio import play_sfx
                    play_sfx(path, vol)
        elif track == "MUSIC":
            self._start_music_block(k, offset=0.0)
        elif track == "LOGIC":
            self._exec_logic_action(d)
            script_path = d.get("script_path") or d.get("script_asset")
            if script_path:
                self._run_script_asset(script_path, k)

    def _exec_logic_action(self, d: dict | LogicAction):
        """Execute a normalized logic action.
        Accepts either a LogicAction or a dict with keys {type, target?}.
        jump/goto/loop schedule a jump at end of tick; pause/stop/resume/play update playback state.
        """
        if isinstance(d, LogicAction):
            t = d.type.lower()
            target_val = d.target or ""
        else:
            t = str(d.get("type", "")).lower()
            target_val = str(d.get("target", d.get("to", "")))

        if t in ("jump", "goto", "loop"):
            self._pending_jump = self._resolve_target_to_time(target_val, default=self.playhead)
        elif t in ("pause", "stop"):
            self._playing = False
        elif t in ("resume", "play"):
            self._playing = True

    def _parse_script(self, script: str) -> list[dict]:
        cmds: list[dict] = []
        for raw in (script or "").split(";"):
            s = raw.strip()
            if not s:
                continue
            parts = s.split()
            cmd = parts[0].lower()
            arg = " ".join(parts[1:]) if len(parts) > 1 else ""
            if cmd in ("jump", "goto", "loop"):
                cmds.append({"type": cmd if cmd != "goto" else "jump", "target": arg})
            elif cmd in ("pause", "stop", "resume", "play"):
                cmds.append({"type": cmd})
        return cmds

    def _run_menu_option(self, idx: int):
        if not (0 <= idx < len(self._menu_options)):
            return
        opt = self._menu_options[idx]
        # run structured logic first, if provided
        logic = opt.get("logic")
        if isinstance(logic, dict):
            self._exec_logic_action(logic)
        elif isinstance(logic, list):
            for it in logic:
                if isinstance(it, dict):
                    self._exec_logic_action(it)
        # then parse and run script text, if any
        script = str(opt.get("script", ""))
        if script:
            for act in parse_script(script):
                self._exec_logic_action(act)
        script_asset = str(opt.get("script_path") or opt.get("script_asset") or "").strip()
        if script_asset:
            menu_kf = self._menu_active_kf
            if menu_kf is None and self._menu_kf_id is not None:
                menu_kf = self.model.find_kf("MENU", self._menu_kf_id)
            menu_kf = menu_kf or Keyframe(self.playhead, "MENU", {})
            self._run_script_asset(script_asset, menu_kf)

        # NOTE: MENU is handled per-frame (modal) and LABEL/JUMP are handled
        # by _rebuild_labels() + _resolve_target_to_time().

    # ----- helpers -----
    def _apply_menu_theme(self, data: dict):
        palette_key = str(data.get("palette") or DEFAULT_MENU_PALETTE.key).lower()
        palette = MENU_PALETTES.get(palette_key, DEFAULT_MENU_PALETTE)
        self._menu_palette_key = palette.key
        self._menu_panel_opacity = max(0.1, min(1.0, float(data.get("panel_opacity", 0.85))))
        rel_bg = str(data.get("background", "")).strip()
        self._set_menu_background(rel_bg)
        self._menu_background_opacity = max(0.0, min(1.0, float(data.get("background_opacity", 0.3))))

    def _set_menu_background(self, rel_path: str):
        if rel_path == self._menu_background_rel:
            return
        self._menu_background_rel = rel_path
        resolved = self.model.resolve_asset_value(rel_path) if rel_path else ""
        self._menu_background_path = resolved
        self._menu_background_pixmap = None
        if resolved and os.path.isfile(resolved):
            pix = QtGui.QPixmap(resolved)
            if not pix.isNull():
                self._menu_background_pixmap = pix

    def _menu_palette(self):
        return MENU_PALETTES.get(self._menu_palette_key, DEFAULT_MENU_PALETTE)

    def _run_script_asset(self, path: str, keyframe: Keyframe):
        resolved = self.model.resolve_asset_value(path)
        if not resolved or not os.path.isfile(resolved):
            print(f"[SCRIPT] missing: {path}")
            return
        try:
            source = Path(resolved).read_text(encoding="utf-8")
        except Exception as exc:
            print(f"[SCRIPT] read error {resolved}: {exc}")
            return
        scope = {"__name__": "__vn_script__", "__file__": resolved}
        try:
            exec(compile(source, resolved, "exec"), scope, scope)
        except Exception as exc:
            print(f"[SCRIPT] exec error {resolved}: {exc}")
            return
        func = scope.get("run") or scope.get("main")
        if callable(func):
            ctx = {
                "model": self.model,
                "widget": self,
                "game": self.game,
                "layers": self.layers,
                "keyframe": keyframe,
                "playhead": self.playhead,
            }
            try:
                func(ctx)
            except Exception as exc:
                print(f"[SCRIPT] run error {resolved}: {exc}")

    def _bg_params(self, k: Keyframe) -> tuple[str, str, float]:
        d = k.data or {}
        fit = str(d.get("fit", "cover")).lower()
        align = str(d.get("align", "center"))
        zoom = float(d.get("zoom", 1.0))
        return fit, align, zoom

    def _rebuild_labels(self):
        """Build name -> time index from LOGIC blocks of type 'label'."""
        idx: dict[str, float] = {}
        for k in self.model.tracks.get("LOGIC", []):
            d = k.data or {}
            if str(d.get("type","")).lower() == "label":
                name = (d.get("name") or "").strip()
                if name:
                    idx[name] = float(k.t)
        self._label_index = idx

    def _resolve_target_to_time(self, target: str, default: float) -> float:
        """Accept a label name or a numeric seconds string."""
        if target in self._label_index:
            return self._label_index[target]
        try:
            return float(target)
        except Exception:
            return float(default)

    # ----- paint -----
    def paintEvent(self, _):
        surf = self.game.render_surface(self.playhead)
        raw = pygame.image.tostring(surf, "RGBA", False)
        img = QtGui.QImage(raw, surf.get_width(), surf.get_height(), QtGui.QImage.Format.Format_RGBA8888)
        p = QtGui.QPainter(self)
        p.drawImage(self.rect(), img)

        if self._menu_active:
            self._draw_menu_overlay(p)

        p.end()

    def _edit_menu_option(self, idx: int, field: str):
        """Edit a MENU option field (text|target|script) of the active MENU keyframe."""
        if self._menu_kf_id is None:
            return
        kf = self.model.find_kf("MENU", self._menu_kf_id)
        if not kf:
            return
        data = kf.data or {}
        opts = list(data.get("options", []))
        if not (0 <= idx < len(opts)):
            return
        # ensure dict option
        if not isinstance(opts[idx], dict):
            opts[idx] = {"text": str(opts[idx])}
        opt = dict(opts[idx])

        title = f"Edit {field.capitalize()}"
        current = str(opt.get(field, ""))
        val, ok = QtWidgets.QInputDialog.getText(self, title, title, text=current)
        if not ok:
            return
        opt[field] = val
        opts[idx] = opt
        kf.data = dict(data)
        kf.data["options"] = opts
        # Rebuild active menu UI from model content
        self.model.touch("MENU")
        self._refresh_active_menu_from_model()
        self.update()

    def _draw_menu_overlay(self, p: QtGui.QPainter):
        r = self.rect()
        palette = self._menu_palette()
        panel_color = QtGui.QColor(*palette.panel)
        panel_color.setAlpha(int(max(0.1, min(1.0, self._menu_panel_opacity)) * 255))
        text_color = QtGui.QColor(*palette.text)
        button_color = QtGui.QColor(*palette.button)
        button_color.setAlpha(200)
        button_text_color = QtGui.QColor(*palette.button_text)
        accent_color = QtGui.QColor(*palette.accent)

        if self._menu_background_pixmap:
            p.save()
            p.setOpacity(self._menu_background_opacity)
            p.drawPixmap(r, self._menu_background_pixmap)
            p.restore()

        panel_w = int(r.width() * 0.6)
        panel_h = int(r.height() * 0.5)
        panel_x = r.center().x() - panel_w // 2
        panel_y = r.center().y() - panel_h // 2
        panel = QtCore.QRect(panel_x, panel_y, panel_w, panel_h)

        p.setRenderHint(QtGui.QPainter.Antialiasing, True)
        p.fillRect(panel, panel_color)
        pen = QtGui.QPen(accent_color, 2)
        p.setPen(pen)
        p.drawRect(panel)

        p.setPen(text_color)
        prompt_rect = panel.adjusted(16, 12, -16, -12)
        p.drawText(prompt_rect, QtCore.Qt.TextWordWrap, self._menu_prompt)
        fm = p.fontMetrics()
        prompt_height = fm.boundingRect(prompt_rect, QtCore.Qt.TextWordWrap, self._menu_prompt).height()

        top = panel_y + prompt_height + 28
        btn_h = max(32, fm.height() + 10)
        btn_gap = 8
        btn_rects: list[QtCore.QRect] = []
        self._menu_btn_text = []
        self._menu_btn_target = []
        self._menu_btn_script = []

        for opt in self._menu_options:
            rect = QtCore.QRect(panel_x + 16, top, panel_w - 32, btn_h)
            top += btn_h + btn_gap
            p.fillRect(rect, button_color)
            p.setPen(QtGui.QPen(accent_color, 1))
            p.drawRect(rect)

            p.setPen(button_text_color)
            main_rect = rect.adjusted(8, 0, -160, 0)
            p.drawText(main_rect, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, str(opt.get("text", "")))

            btn_w = 52
            gap = 6
            x = rect.right() - 8

            def draw_btn(xpos: int, label: str) -> QtCore.QRect:
                brect = QtCore.QRect(xpos - btn_w, rect.bottom() - btn_h, btn_w, btn_h)
                p.fillRect(brect, panel_color)
                p.setPen(QtGui.QPen(accent_color, 1))
                p.drawRect(brect)
                p.setPen(button_text_color)
                p.drawText(brect, QtCore.Qt.AlignCenter, label)
                return brect

            b_script = draw_btn(x, "Script"); x -= (btn_w + gap)
            b_target = draw_btn(x, "Target"); x -= (btn_w + gap)
            b_text = draw_btn(x, "Text")

            self._menu_btn_text.append(b_text)
            self._menu_btn_target.append(b_target)
            self._menu_btn_script.append(b_script)

            btn_rects.append(rect)

        self._menu_rects = btn_rects

    def _refresh_active_menu_from_model(self):
        """Re-read the active MENU block for current playhead and rebuild prompt/options/rects."""
        t = self.playhead
        menu_overlap = self.layers.active_blocks("MENU", t)
        if not menu_overlap:
            self._menu_active = False
            self._menu_rects = []
            self._menu_btn_text = []
            self._menu_btn_target = []
            self._menu_btn_script = []
            self._menu_active_kf = None
            self._menu_background_pixmap = None
            self._menu_background_path = ""
            self._menu_background_rel = ""
            return
        mk = menu_overlap[-1]
        self._menu_kf_id = mk.id
        self._menu_active_kf = mk
        d = mk.data or {}
        self._menu_prompt = str(d.get("prompt", "Choose:"))
        self._apply_menu_theme(d)
        # normalize options
        norm_opts: list[dict] = []
        for opt in d.get("options", []):
            if isinstance(opt, dict):
                text = (opt.get("text") or "").strip() or "(option)"
                target_raw = str(opt.get("target", opt.get("to", "")))
                to_time = self._resolve_target_to_time(target_raw, default=t)
                row = {"text": text, "to": to_time}
                script = str(opt.get("script", "")).strip()
                if script:
                    row["script"] = script
                script_asset = str(opt.get("script_path") or opt.get("script_asset") or "").strip()
                if script_asset:
                    row["script_path"] = script_asset
                logic = opt.get("logic", None)
                if logic is not None:
                    row["logic"] = logic
                norm_opts.append(row)
            else:
                norm_opts.append({"text": str(opt), "to": t})
        self._menu_options = norm_opts


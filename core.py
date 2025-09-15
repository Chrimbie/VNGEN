# core.py — low-level pygame render engine (no Qt, no model)
from __future__ import annotations
import pygame
from typing import Optional, Tuple, List
from .transitions import overlay_fade
from .effects import shake_offset


class GameCore:
    """Stateless-per-frame renderer. Higher layers set state every frame."""

    def __init__(self, w: int = 960, h: int = 540):
        if not pygame.get_init():
            pygame.init()
        self._ensure_display()

        self.w, self.h = w, h
        self.ui_font = pygame.font.SysFont("arial", 22)

        # Background crossfade
        self.bg_img: Optional[pygame.Surface] = None
        self.bg_prev: Optional[pygame.Surface] = None
        self.bg_xfade: float = 0.0
        self.bg_xstart: float = 0.0

        # Background sizing behavior
        self.bg_fit: str = "cover"     # cover | contain | stretch | native
        self.bg_align: str = "center"  # center | top | bottom | left | right | combos like "top-left"
        self.bg_zoom: float = 1.0      # extra scale factor

        # Sprite crossfade
        self.spr_img: Optional[pygame.Surface] = None
        self.spr_prev: Optional[pygame.Surface] = None
        self.spr_xfade: float = 0.0
        self.spr_xstart: float = 0.0
        self.spr_rect = pygame.Rect(int(w * 0.37), int(h * 0.28), int(w * 0.26), int(h * 0.46))
        self.spr_opacity: float = 1.0

        # Dialog
        self.dialog = {"speaker": "", "text": "", "cps": 24.0, "start": -1.0, "end": -1.0}

        # FX overlay (scene fades)
        self.fx_mode: Optional[str] = None              # "black" | "white" | "translucent" | None
        self.fx_color: Tuple[int, int, int] = (0, 0, 0)
        self.fx_from: float = 0.0
        self.fx_to: float = 0.0
        self.fx_start: float = 0.0
        self.fx_dur: float = 0.0

        # Screen shake (applies to world layer)
        self.shake_start: float = -1.0
        self.shake_dur: float = 0.0
        self.shake_amp: float = 0.0
        self.shake_freq: float = 0.0
        self.shake_decay: float = 2.5
        self.shake_seed: int = 0

        # --- Menu overlay (prompt + options) ---
        self.menu_active: bool = False
        self.menu_prompt: str = ""
        self.menu_options: List[str] = []
        self.menu_hover_idx: int = -1
        self.menu_layout: List[pygame.Rect] = []  # computed each frame

    # -------- platform quirk: need a display surface for convert_alpha()
    def _ensure_display(self):
        if not pygame.display.get_init():
            pygame.display.init()
        if pygame.display.get_surface() is None:
            try:
                pygame.display.set_mode((1, 1), flags=pygame.HIDDEN)
            except Exception:
                pygame.display.set_mode((1, 1))

    # -------- loaders
    def _load_image(self, path: Optional[str]) -> Optional[pygame.Surface]:
        if not path:
            return None
        try:
            self._ensure_display()
            return pygame.image.load(path).convert_alpha()
        except Exception as e:
            print("[IMG] fail:", path, e)
            return None

    # -------- align + scaling helpers (flexible bg sizing)
    def _parse_align(self, align: str) -> tuple[float, float]:
        a = (align or "center").lower().replace("_", "-").strip()
        ax, ay = 0.5, 0.5
        if "left" in a: ax = 0.0
        if "right" in a: ax = 1.0
        if "top" in a: ay = 0.0
        if "bottom" in a: ay = 1.0
        if a == "left": ax = 0.0
        if a == "right": ax = 1.0
        if a == "top": ay = 0.0
        if a == "bottom": ay = 1.0
        return ax, ay

    def _scale_and_position(self, img: pygame.Surface, *,
                            mode: str = "cover",
                            align: str = "center",
                            zoom: float = 1.0) -> tuple[pygame.Surface, tuple[int, int]]:
        iw, ih = img.get_width(), img.get_height()
        dw, dh = self.w, self.h
        zoom = max(0.01, float(zoom))

        if mode == "stretch":
            nw, nh = max(1, int(dw * zoom)), max(1, int(dh * zoom))
            scaled = pygame.transform.smoothscale(img, (nw, nh))
            ax, ay = self._parse_align(align)
            return scaled, (int((dw - nw) * ax), int((dh - nh) * ay))

        if mode == "native":
            nw, nh = max(1, int(iw * zoom)), max(1, int(ih * zoom))
            scaled = pygame.transform.smoothscale(img, (nw, nh)) if zoom != 1.0 else img
            ax, ay = self._parse_align(align)
            return scaled, (int((dw - nw) * ax), int((dh - nh) * ay))

        # contain / cover (AR-preserving)
        if iw <= 0 or ih <= 0:
            return img, (0, 0)
        scale_cover   = max(dw / iw, dh / ih)   # fill (crop)
        scale_contain = min(dw / iw, dh / ih)   # fit (letterbox)
        scale = (scale_cover if mode == "cover" else scale_contain) * zoom
        nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
        scaled = pygame.transform.smoothscale(img, (nw, nh))
        ax, ay = self._parse_align(align)
        return scaled, (int((dw - nw) * ax), int((dh - nh) * ay))

    def _blit_bg(self, s: pygame.Surface, img: pygame.Surface, *,
                 alpha: Optional[int] = None,
                 offset: tuple[int, int] = (0, 0),
                 mode: str = "cover", align: str = "center", zoom: float = 1.0):
        scaled, (x, y) = self._scale_and_position(img, mode=mode, align=align, zoom=zoom)
        if alpha is not None:
            scaled = scaled.copy()
            scaled.set_alpha(alpha)
        ox, oy = offset
        s.blit(scaled, (x + int(ox), y + int(oy)))

    # -------- state setters (called by layers/widget each frame)
    def set_backgrounds_ex(self, current_path: Optional[str], prev_path: Optional[str],
                           xfade: float, xstart: float, *,
                           fit: str = "cover", align: str = "center", zoom: float = 1.0):
        self.bg_img  = self._load_image(current_path)
        self.bg_prev = self._load_image(prev_path)
        self.bg_xfade, self.bg_xstart = max(0.0, xfade), float(xstart)
        self.bg_fit   = (fit or "cover").lower()
        self.bg_align = align or "center"
        self.bg_zoom  = float(zoom)

    def set_backgrounds(self, current_path: Optional[str], prev_path: Optional[str],
                        xfade: float, xstart: float):
        # backward-compatible default behavior
        self.set_backgrounds_ex(current_path, prev_path, xfade, xstart,
                                fit="cover", align="center", zoom=1.0)

    def set_sprite_layers(self, current_desc: Optional[Tuple[str, pygame.Rect, float]],
                          prev_desc: Optional[Tuple[str, pygame.Rect, float]],
                          xfade: float, xstart: float):
        # current_desc / prev_desc: (path, rect, opacity)
        if current_desc:
            p, r, op = current_desc
            self.spr_img = self._load_image(p)
            self.spr_rect = r
            self.spr_opacity = max(0.0, min(1.0, op))
        else:
            self.spr_img = None
        if prev_desc:
            p2, _r2, _op2 = prev_desc
            self.spr_prev = self._load_image(p2)
        else:
            self.spr_prev = None
        self.spr_xfade, self.spr_xstart = max(0.0, xfade), float(xstart)

    def set_dialog(self, speaker: str, text: str, cps: float, t_start: float, t_end: float):
        self.dialog.update({"speaker": speaker or "", "text": text or "", "cps": max(1.0, cps),
                            "start": t_start, "end": t_end})

    def set_fx_overlay(self, mode: Optional[str], duration: float, from_alpha: float, to_alpha: float,
                       start_time: float, color: Tuple[int, int, int] = (0, 0, 0)):
        self.fx_mode = (mode or "").lower() if mode else None
        self.fx_dur = max(0.0, float(duration))
        self.fx_from = max(0.0, min(1.0, float(from_alpha)))
        self.fx_to   = max(0.0, min(1.0, float(to_alpha)))
        self.fx_start = float(start_time)
        self.fx_color = tuple(int(c) for c in color)

    def start_shake(self, start_time: float, duration: float, amplitude_px: float, frequency_hz: float,
                    decay: float = 2.5, seed: int = 0):
        self.shake_start = float(start_time)
        self.shake_dur   = max(0.0, float(duration))
        self.shake_amp   = max(0.0, float(amplitude_px))
        self.shake_freq  = max(0.0, float(frequency_hz))
        self.shake_decay = max(0.0, float(decay))
        self.shake_seed  = int(seed)

    # --- menu state setters ---
    def set_menu(self, prompt: str, options: List[str]):
        self.menu_active = True
        self.menu_prompt = prompt or ""
        self.menu_options = list(options or [])
        self.menu_hover_idx = -1
        self.menu_layout = []

    def clear_menu(self):
        self.menu_active = False
        self.menu_prompt = ""
        self.menu_options = []
        self.menu_hover_idx = -1
        self.menu_layout = []

    # -------- single-frame render (stateless apart from fields above)
    def render_surface(self, playhead: float) -> pygame.Surface:
        s_world = pygame.Surface((self.w, self.h), flags=pygame.SRCALPHA)
        s_final = pygame.Surface((self.w, self.h), flags=pygame.SRCALPHA)

        # screen shake offset
        shake_xy = (0, 0)
        if self.shake_dur > 0.0 and self.shake_start >= 0.0:
            elapsed = playhead - self.shake_start
            shake_xy = shake_offset(
                elapsed, self.shake_dur, self.shake_amp, self.shake_freq,
                decay=self.shake_decay, seed=self.shake_seed
            )

        # Background (with crossfade + flexible sizing)
        if self.bg_img:
            if (self.bg_prev and self.bg_xfade > 0.0 and
                (self.bg_xstart <= playhead <= self.bg_xstart + self.bg_xfade)):
                t = (playhead - self.bg_xstart) / max(1e-6, self.bg_xfade)
                t = max(0.0, min(1.0, t))
                self._blit_bg(s_world, self.bg_prev, alpha=int(255 * (1.0 - t)),
                              offset=shake_xy, mode=self.bg_fit, align=self.bg_align, zoom=self.bg_zoom)
                self._blit_bg(s_world, self.bg_img,  alpha=int(255 * t),
                              offset=shake_xy, mode=self.bg_fit, align=self.bg_align, zoom=self.bg_zoom)
            else:
                self._blit_bg(s_world, self.bg_img,
                              offset=shake_xy, mode=self.bg_fit, align=self.bg_align, zoom=self.bg_zoom)
        else:
            s_world.fill((28, 32, 40))

        # Sprite (with crossfade + opacity)
        if self.spr_img:
            cur = pygame.transform.smoothscale(self.spr_img, (self.spr_rect.width, self.spr_rect.height))
            if self.spr_opacity < 1.0:
                cur = cur.copy()
                cur.set_alpha(int(self.spr_opacity * 255))
            topleft = (self.spr_rect.x + int(shake_xy[0]), self.spr_rect.y + int(shake_xy[1]))
            if (self.spr_prev and self.spr_xfade > 0.0 and
                (self.spr_xstart <= playhead <= self.spr_xstart + self.spr_xfade)):
                t = (playhead - self.spr_xstart) / max(1e-6, self.spr_xfade)
                t = max(0.0, min(1.0, t))
                prev = pygame.transform.smoothscale(self.spr_prev, (self.spr_rect.width, self.spr_rect.height))
                prev.set_alpha(int(255 * (1.0 - t)))
                cur2 = cur.copy()
                cur2.set_alpha(int(255 * t))
                s_world.blit(prev, topleft)
                s_world.blit(cur2, topleft)
            else:
                s_world.blit(cur, topleft)

        # Copy world
        s_final.blit(s_world, (0, 0))

        # FX overlay (black/white/translucent)
        if self.fx_mode and self.fx_dur > 0.0:
            t = (playhead - self.fx_start) / max(1e-6, self.fx_dur)
            if 0.0 <= t <= 1.0:
                alpha = (1.0 - t) * self.fx_from + t * self.fx_to
                if self.fx_mode == "black":
                    overlay_fade(s_final, (0, 0, 0), alpha)
                elif self.fx_mode == "white":
                    overlay_fade(s_final, (255, 255, 255), alpha)
                elif self.fx_mode == "translucent":
                    overlay_fade(s_final, self.fx_color, alpha)

        # Dialog
        active = (0 <= self.dialog["start"] <= playhead <= self.dialog["end"]
                  and (self.dialog["speaker"] or self.dialog["text"]))
        if active:
            box_h_ratio = 0.20
            dlg_rect = pygame.Rect(0, int(self.h * (1.0 - box_h_ratio)), self.w, int(self.h * box_h_ratio))
            pygame.draw.rect(s_final, (18, 18, 22, 190), dlg_rect)
            pygame.draw.rect(s_final, (200, 210, 255, 230), dlg_rect, 2)

            cps = self.dialog["cps"]
            n = int(max(0.0, (playhead - self.dialog["start"])) * cps)
            full = self.dialog["text"]
            typed_txt = full[:min(len(full), n)]

            pad = 24
            y0 = dlg_rect.top + 10
            if self.dialog["speaker"]:
                nm = self.ui_font.render(self.dialog["speaker"] + ":", True, (230, 235, 255))
                s_final.blit(nm, (pad, y0))
                y0 += nm.get_height() + 4

            if typed_txt:
                wmax = self.w - pad * 2
                words = typed_txt.split()
                cur_line = ""
                lines: List[str] = []
                for w in words:
                    test = (cur_line + " " + w).strip()
                    if self.ui_font.size(test)[0] <= wmax:
                        cur_line = test
                    else:
                        if cur_line:
                            lines.append(cur_line)
                        cur_line = w
                if cur_line:
                    lines.append(cur_line)
                y = y0
                for ln in lines[:4]:
                    surf = self.ui_font.render(ln, True, (235, 240, 255))
                    s_final.blit(surf, (pad, y))
                    y += surf.get_height() + 4

        # --- Menu overlay (drawn above dialog/UI) ---
        if self.menu_active and self.menu_options:
            panel_h = int(self.h * 0.35)
            panel = pygame.Rect(int(self.w*0.08), int(self.h*0.5 - panel_h/2),
                                int(self.w*0.84), panel_h)
            pygame.draw.rect(s_final, (16, 18, 24, 210), panel)
            pygame.draw.rect(s_final, (210, 220, 255, 230), panel, 2)

            pad = 18
            y = panel.top + pad
            if self.menu_prompt:
                pr = self.ui_font.render(self.menu_prompt, True, (235, 240, 255))
                s_final.blit(pr, (panel.left + pad, y))
                y += pr.get_height() + 10

            btn_h = 34
            gap = 8
            self.menu_layout = []
            for idx, text in enumerate(self.menu_options):
                r = pygame.Rect(panel.left + pad, y, panel.width - pad*2, btn_h)
                is_hover = (idx == self.menu_hover_idx)
                bg = (70, 100, 255, 90) if is_hover else (44, 48, 60, 160)
                pygame.draw.rect(s_final, bg, r)
                pygame.draw.rect(s_final, (200, 210, 255, 230), r, 1)
                lbl = self.ui_font.render(text, True, (235, 240, 255))
                s_final.blit(lbl, (r.left + 10, r.centery - lbl.get_height()//2))
                self.menu_layout.append(r)
                y += btn_h + gap

        return s_final


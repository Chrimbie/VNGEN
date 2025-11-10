# layers.py — pure data/layer helpers that compute per-frame state for GameCore
from __future__ import annotations
import pygame
from typing import List, Tuple, Optional
from model import TimelineModel, Keyframe
from vngen.config import SPRITE_DEFAULTS


class Layers:
    """Derives what should be on screen at a given playhead from the TimelineModel."""

    def __init__(self, model: TimelineModel, game_size: Tuple[int, int]):
        self.model = model
        self.w, self.h = game_size

    def active_blocks(self, track: str, t: float) -> List[Keyframe]:
        arr = self.model.tracks.get(track, [])
        out: List[Keyframe] = []
        for k in arr:
            t0 = k.t
            t1 = t0 + self.model._eff_duration(track, k)
            if t0 - 1e-9 <= t <= t1 + 1e-9:
                out.append(k)
        out.sort(key=lambda k: k.t)
        return out

    def sprite_rect_opacity(self, k: Keyframe, t: Optional[float] = None) -> Tuple[pygame.Rect, float]:
        d = k.data or {}
        cx_default, cy_default = SPRITE_DEFAULTS.center
        size_default_w, size_default_h = SPRITE_DEFAULTS.size

        x1 = float(d.get("x", cx_default))
        y1 = float(d.get("y", cy_default))
        w1 = float(d.get("w", size_default_w))
        h1 = float(d.get("h", size_default_h))
        op1 = float(d.get("opacity", SPRITE_DEFAULTS.opacity))

        x2 = float(d.get("x2", x1))
        y2 = float(d.get("y2", y1))
        w2 = float(d.get("w2", w1))
        h2 = float(d.get("h2", h1))
        op2 = float(d.get("opacity2", op1))

        if t is None:
            p = 0.0
        else:
            duration = max(1e-6, self.model._eff_duration("SPRITE", k))
            p = max(0.0, min(1.0, (float(t) - k.t) / duration))

        def lerp(a: float, b: float) -> float:
            return a + (b - a) * p

        x = lerp(x1, x2)
        y = lerp(y1, y2)
        w = lerp(w1, w2)
        h = lerp(h1, h2)
        op = lerp(op1, op2)

        rect = pygame.Rect(
            int((0.5 - w / 2 + (x - 0.5)) * self.w),
            int((0.5 - h / 2 + (y - 0.5)) * self.h),
            int(self.w * w),
            int(self.h * h),
        )
        return rect, op

    @staticmethod
    def hex_to_rgb(s: str) -> Tuple[int, int, int]:
        ss = s.strip()
        if ss.startswith("#"): ss = ss[1:]
        if len(ss) == 3:
            ss = "".join(c*2 for c in ss)
        try:
            r = int(ss[0:2], 16); g = int(ss[2:4], 16); b = int(ss[4:6], 16)
            return (r, g, b)
        except Exception:
            return (0, 0, 0)


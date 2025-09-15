# layers.py — pure data/layer helpers that compute per-frame state for GameCore
from __future__ import annotations
import pygame
from typing import List, Tuple, Optional
from model import TimelineModel, Keyframe


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

    def sprite_rect_opacity(self, k: Keyframe) -> Tuple[pygame.Rect, float]:
        d = k.data
        x = float(d.get("x", 0.5)); y = float(d.get("y", 0.6))
        w = float(d.get("w", 0.25)); h = float(d.get("h", 0.45))
        op = float(d.get("opacity", 1.0))
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

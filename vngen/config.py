from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple

# ---- Timeline / Track metadata ----
TRACK_ORDER: Tuple[str, ...] = (
    "BG", "SPRITE", "DIALOG", "SFX", "MUSIC", "FX", "MENU", "LOGIC"
)

TRACK_COLORS_RGB: Dict[str, Tuple[int, int, int]] = {
    "BG":     (140, 200, 255),
    "SPRITE": (255, 200, 140),
    "DIALOG": (200, 180, 255),
    "SFX":    (160, 255, 160),
    "MUSIC":  (255, 170, 170),
    "FX":     (220, 160, 255),
    "MENU":   (255, 220, 150),
    "LOGIC":  (180, 220, 140),
}

DEFAULT_TRACK_DURATIONS: Dict[str, float] = {
    "BG": 0.6,
    "SPRITE": 0.4,
    "DIALOG": 2.5,
    "SFX": 0.2,
    "MUSIC": 5.0,
    "FX": 0.6,
    "MENU": 30.0,
    "LOGIC": 0.01,
}

MIN_TRACK_DURATIONS: Dict[str, float] = {
    "SFX": 0.0333333,
    "MUSIC": 0.0333333,
    "MENU": 0.0333333,
    "LOGIC": 0.01,
}

# ---- Runtime rendering defaults ----
@dataclass(frozen=True)
class SpriteDefaults:
    center: Tuple[float, float] = (0.5, 0.62)
    size: Tuple[float, float] = (0.26, 0.46)
    opacity: float = 1.0

SPRITE_DEFAULTS = SpriteDefaults()

@dataclass(frozen=True)
class DialogBoxStyle:
    height_ratio: float = 0.26
    background_rgba: Tuple[int, int, int, int] = (18, 18, 22, 190)
    border_rgba: Tuple[int, int, int, int] = (200, 210, 255, 230)
    text_color: Tuple[int, int, int, int] = (240, 242, 250, 255)
    name_color: Tuple[int, int, int, int] = (180, 190, 255, 255)

DIALOG_STYLE = DialogBoxStyle()

@dataclass(frozen=True)
class MenuOverlayStyle:
    panel_rgba: Tuple[int, int, int, int] = (16, 18, 24, 210)
    border_rgba: Tuple[int, int, int, int] = (210, 220, 255, 230)
    option_hover_rgba: Tuple[int, int, int, int] = (80, 90, 140, 220)
    option_idle_rgba: Tuple[int, int, int, int] = (26, 28, 36, 210)
    option_text_rgba: Tuple[int, int, int, int] = (240, 242, 250, 255)

MENU_STYLE = MenuOverlayStyle()

HUD_BUTTON_COLORS = {
    "idle": (32, 36, 48, 210),
    "hover": (64, 160, 220, 230),
    "text": (240, 242, 250, 255),
}

# Pixel margins for preview HUD
HUD_LAYOUT = {
    "padding": 12,
    "button_size": (96, 36),
    "button_gap": 8,
}



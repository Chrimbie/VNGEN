from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class MenuPalette:
    key: str
    name: str
    panel: Tuple[int, int, int]
    panel_alpha: int
    text: Tuple[int, int, int]
    button: Tuple[int, int, int]
    button_text: Tuple[int, int, int]
    accent: Tuple[int, int, int]


MENU_PALETTES: Dict[str, MenuPalette] = {
    "midnight": MenuPalette(
        key="midnight",
        name="Midnight",
        panel=(16, 18, 32),
        panel_alpha=220,
        text=(240, 242, 255),
        button=(54, 97, 255),
        button_text=(250, 252, 255),
        accent=(255, 255, 255),
    ),
    "ember": MenuPalette(
        key="ember",
        name="Ember",
        panel=(45, 18, 12),
        panel_alpha=215,
        text=(255, 237, 224),
        button=(230, 98, 43),
        button_text=(255, 255, 255),
        accent=(255, 205, 178),
    ),
    "forest": MenuPalette(
        key="forest",
        name="Forest",
        panel=(12, 28, 22),
        panel_alpha=215,
        text=(220, 255, 240),
        button=(41, 146, 123),
        button_text=(240, 255, 249),
        accent=(108, 214, 174),
    ),
    "violet": MenuPalette(
        key="violet",
        name="Violet",
        panel=(30, 12, 38),
        panel_alpha=215,
        text=(250, 240, 255),
        button=(157, 92, 255),
        button_text=(255, 255, 255),
        accent=(199, 156, 255),
    ),
}

DEFAULT_MENU_PALETTE = MENU_PALETTES["midnight"]


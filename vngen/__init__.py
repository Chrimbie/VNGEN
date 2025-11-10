from __future__ import annotations
from typing import Any

__all__ = ["GameCore", "GameWidget", "Layers", "parse_script", "LogicAction"]


def __getattr__(name: str) -> Any:
    if name == "GameCore":
        from .core import GameCore  # late import to avoid circular deps
        return GameCore
    if name == "GameWidget":
        from .widget import GameWidget  # delayed because widget imports model
        return GameWidget
    if name == "Layers":
        from .layers import Layers
        return Layers
    if name == "parse_script":
        from .logic import parse_script
        return parse_script
    if name == "LogicAction":
        from .logic import LogicAction
        return LogicAction
    raise AttributeError(f"module 'vngen' has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)


from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class LogicAction:
    """A normalized logic action.

    type: one of 'jump', 'loop', 'pause', 'resume', 'stop', 'play'
    target: optional label or seconds string (for jump/loop)
    """
    type: str
    target: Optional[str] = None


def parse_script(script: str) -> List[LogicAction]:
    """Parse a semicolon-separated mini script into LogicAction items.

    Grammar (case-insensitive):
      - jump <label|seconds>
      - goto <label|seconds>     (alias of jump)
      - loop <label|seconds>     (treated as jump at runtime)
      - pause | stop
      - resume | play

    Returns a list of LogicAction in the order they appear.
    Unknown commands are ignored.
    """
    actions: List[LogicAction] = []
    if not script:
        return actions
    for raw in script.split(";"):
        s = (raw or "").strip()
        if not s:
            continue
        parts = s.split()
        cmd = parts[0].lower()
        arg = " ".join(parts[1:]) if len(parts) > 1 else ""

        if cmd in ("jump", "goto", "loop"):
            actions.append(LogicAction("jump" if cmd == "goto" else cmd, arg))
        elif cmd in ("pause", "stop", "resume", "play"):
            actions.append(LogicAction(cmd))
        else:
            # ignore unknown tokens
            continue
    return actions


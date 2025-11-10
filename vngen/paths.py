from __future__ import annotations
from pathlib import Path


def _safe_resolve(p: Path) -> Path:
    try:
        return p.resolve(strict=False)
    except Exception:
        return p


def normalize_asset_path(path: str, base: Path) -> str:
    """Return a path string relative to *base* when possible, POSIX-separated."""
    if not path:
        return ""
    p = Path(path).expanduser()
    resolved = _safe_resolve(p if p.is_absolute() else base / p)
    if base:
        try:
            rel = resolved.relative_to(_safe_resolve(base))
            return rel.as_posix()
        except Exception:
            pass
    return resolved.as_posix()


def resolve_asset_path(path: str, base: Path) -> str:
    """Return an absolute filesystem path for an asset relative to *base*."""
    if not path:
        return ""
    p = Path(path)
    if p.is_absolute():
        return _safe_resolve(p).as_posix()
    return _safe_resolve(base / p).as_posix()


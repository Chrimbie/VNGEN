# model.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Iterable, Optional
from pathlib import Path
import os, json
import pygame
from PySide6 import QtCore
from vngen.config import TRACK_ORDER, DEFAULT_TRACK_DURATIONS, MIN_TRACK_DURATIONS
from vngen.paths import normalize_asset_path, resolve_asset_path

TICK_SEC = 0.0333333  # visual minimum footprint in seconds

# Central list of tracks used across the app
TRACKS: Tuple[str, ...] = tuple(TRACK_ORDER)

# Friendly names for track identifiers (keeps string usage centralized)
BG = "BG"
SPRITE = "SPRITE"
DIALOG = "DIALOG"
SFX = "SFX"
MUSIC = "MUSIC"
FX = "FX"
MENU = "MENU"
LOGIC = "LOGIC"

# Common key names used inside keyframe data dictionaries
VALUE_KEY = "value"
DURATION_KEY = "duration"


@dataclass
class Keyframe:
    t: float
    track: str
    data: Dict = field(default_factory=dict)
    id: int = field(default=-1)


class TimelineModel(QtCore.QObject):
    """Holds tracks -> [Keyframe], emits change signals, and tracks dirty state."""

    durationChanged = QtCore.Signal(float)
    tracksChanged = QtCore.Signal(str)
    modelChanged = QtCore.Signal()
    dirtyChanged = QtCore.Signal(bool)

    def __init__(self, parent: Optional[QtCore.QObject] = None):
        super().__init__(parent)
        self._duration: float = 60.0
        self.tracks: Dict[str, List[Keyframe]] = {name: [] for name in TRACKS}
        self._next_id = 1
        self._listeners: List = []
        self._dirty = False
        self._project_file: Optional[Path] = None
        self._asset_root: Path = Path.cwd()

        # ensure pygame mixer can be used for length guessing
        if not pygame.get_init():
            pygame.init()
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init()
            except Exception:
                pass

    # ---- properties ----
    @property
    def duration(self) -> float:
        return self._duration

    @duration.setter
    def duration(self, value: float):
        self._set_duration(float(value))

    @property
    def dirty(self) -> bool:
        return self._dirty

    @property
    def project_file(self) -> Optional[Path]:
        return self._project_file

    @property
    def asset_root(self) -> Path:
        return self._asset_root

    def set_project_file(self, filename: Optional[str]):
        if filename:
            p = Path(filename)
            self._project_file = p
            self._asset_root = p.parent.resolve()
        else:
            self._project_file = None
            self._asset_root = Path.cwd()

    def normalize_asset_value(self, value: str) -> str:
        if not value:
            return ""
        return normalize_asset_path(value, self._asset_root)

    def resolve_asset_value(self, value: str) -> str:
        if not value:
            return ""
        return resolve_asset_path(value, self._asset_root)

    # ---- listeners (legacy hooks) ----
    def add_listener(self, fn):
        self._listeners.append(fn)

    def _emit(self):
        for fn in list(self._listeners):
            try:
                fn()
            except Exception:
                pass
        self.modelChanged.emit()

    # ---- dirty helpers ----
    def mark_clean(self):
        self._set_dirty(False)

    def touch(self, track: Optional[str] = None, *, recompute_duration: bool = False):
        """Notify listeners that track data changed and mark the project dirty."""
        if recompute_duration:
            self._recompute_duration()
        self._emit()
        if track is None:
            self.tracksChanged.emit("__all__")
        else:
            self.tracksChanged.emit(track)
        self._set_dirty(True)

    def _set_dirty(self, value: bool):
        value = bool(value)
        if self._dirty != value:
            self._dirty = value
            self.dirtyChanged.emit(self._dirty)

    def _set_duration(self, value: float):
        value = float(value)
        if abs(value - self._duration) > 1e-6:
            self._duration = value
            self.durationChanged.emit(self._duration)

    def _recompute_duration(self):
        longest = 0.0
        for track, arr in self.tracks.items():
            for k in arr:
                longest = max(longest, k.t + self._eff_duration(track, k))
        self._set_duration(max(longest, 60.0))

    # ---- audio helpers ----
    def _guess_audio_len(self, path: str) -> float:
        if not path:
            return 0.0
        resolved = self.resolve_asset_value(path)
        try:
            if os.path.isfile(resolved):
                snd = pygame.mixer.Sound(resolved)
                return float(snd.get_length())
        except Exception:
            pass
        return 0.0

    # ---- API ----
    def add_kf(self, track: str, kf: Keyframe, snap: bool = False):
        # ensure bucket exists (defensive against older code)
        self.tracks.setdefault(track, [])
        kf.track = track
        kf.id = self._next_id
        self._next_id += 1

        if snap:
            kf.t = round(kf.t / TICK_SEC) * TICK_SEC

        # normalize resource references
        if isinstance(kf.data, dict):
            val = kf.data.get(VALUE_KEY)
            if isinstance(val, str):
                kf.data[VALUE_KEY] = self.normalize_asset_value(val)

        # defaults
        if kf.data.get(DURATION_KEY) is None:
            if track == MUSIC:
                path = str(kf.data.get(VALUE_KEY, ""))
                length = self._guess_audio_len(path)
                kf.data[DURATION_KEY] = length if length > 0 else DEFAULT_TRACK_DURATIONS.get(track, 0.0)
            else:
                kf.data[DURATION_KEY] = DEFAULT_TRACK_DURATIONS.get(track, 0.0)

        self.tracks[track].append(kf)
        self.tracks[track].sort(key=lambda k: k.t)
        end_t = kf.t + self._eff_duration(track, kf)
        self._set_duration(max(self._duration, end_t))
        self.touch(track)

    def remove_kf(self, track: str, kf_id: int):
        arr = self.tracks.get(track, [])
        new_arr = [k for k in arr if k.id != kf_id]
        if len(new_arr) == len(arr):
            return
        self.tracks[track] = new_arr
        self.touch(track, recompute_duration=True)

    def find_kf(self, track: str, kf_id: int) -> Optional[Keyframe]:
        for k in self.tracks.get(track, []):
            if k.id == kf_id:
                return k
        return None

    def _eff_duration(self, track: str, k: Keyframe) -> float:
        base = DEFAULT_TRACK_DURATIONS.get(track, 0.0)
        d = float(k.data.get(DURATION_KEY, base))
        if track in (BG, SPRITE, FX, DIALOG, MUSIC, SFX):
            return max(d, TICK_SEC)
        if track == MENU:
            # menus stay modal; ensure a substantial footprint
            return max(d if d > 0 else base, TICK_SEC)
        if track == LOGIC:
            return max(d if d > 0 else base, TICK_SEC)
        return max(d, TICK_SEC)


    def keyframes_at(self, t0: float, t1: float) -> Iterable[Tuple[str, Keyframe]]:
        """Return (track, keyframe) whose start time is in (t0, t1]."""
        if t1 < t0:
            t0, t1 = t1, t0
        for track, arr in self.tracks.items():
            for k in arr:
                if t0 < k.t <= t1:
                    yield (track, k)

    # ---- serialization ----
    def to_json(self) -> str:
        doc = {"duration": self.duration, "tracks": {}}
        for tr, arr in self.tracks.items():
            serialized = []
            for k in arr:
                data = dict(k.data)
                val = data.get("value")
                if isinstance(val, str):
                    normalized = self.normalize_asset_value(val)
                    data["value"] = normalized
                    k.data["value"] = normalized
                serialized.append({"t": k.t, "track": k.track, "data": data, "id": k.id})
            doc["tracks"][tr] = serialized
        return json.dumps(doc, indent=2)

    def load_json(self, s: str, project_file: Optional[str] = None):
        doc = json.loads(s or "{}")
        if project_file is None:
            project_file = doc.get("projectFile")
        self.set_project_file(project_file)
        self._duration = float(doc.get("duration", 60.0))
        # start with all known tracks
        self.tracks = {name: [] for name in TRACKS}
        self._next_id = 1

        for tr, arr in (doc.get("tracks", {}) or {}).items():
            bucket = self.tracks.setdefault(tr, [])
            for it in (arr or []):
                data = dict(it.get("data", {}))
                val = data.get("value")
                if isinstance(val, str):
                    normalized = self.normalize_asset_value(val)
                    data["value"] = normalized
                k = Keyframe(float(it.get("t", 0.0)), tr, data, int(it.get("id", -1)))
                if k.id < 0:
                    k.id = self._next_id
                    self._next_id += 1
                else:
                    self._next_id = max(self._next_id, k.id + 1)
                bucket.append(k)
            bucket.sort(key=lambda m: m.t)

        # make sure any newly added tracks (future) exist
        for name in TRACKS:
            self.tracks.setdefault(name, [])

        self._recompute_duration()
        self._emit()
        self.tracksChanged.emit("__all__")
        self.mark_clean()

    def delete_keyframes(self, items: list[tuple[str, int]]) -> int:
        """Remove keyframes by (track, keyframe_id). Returns number removed."""
        removed = 0
        dirty_tracks: set[str] = set()
        for track, kid in items:
            arr = self.tracks.get(track, [])
            new_arr = [k for k in arr if getattr(k, "id", None) != kid]
            removed += len(arr) - len(new_arr)
            if len(new_arr) != len(arr):
                self.tracks[track] = new_arr
                dirty_tracks.add(track)
        if removed:
            self._recompute_duration()
            self._emit()
            if dirty_tracks:
                for tr in dirty_tracks:
                    self.tracksChanged.emit(tr)
            else:
                self.tracksChanged.emit("__all__")
            self._set_dirty(True)
        return removed


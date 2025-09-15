# model.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Iterable, Optional
import pygame, os, json

TICK_SEC = 0.0333333  # visual minimum footprint in seconds

# Central list of tracks used across the app
TRACKS: Tuple[str, ...] = (
    "BG", "SPRITE", "DIALOG", "SFX", "MUSIC", "FX",
    "MENU",   # modal choice overlay
    "LOGIC",  # label/jump/loop etc. (instant by default)
)

@dataclass
class Keyframe:
    t: float
    track: str
    data: Dict = field(default_factory=dict)
    id: int = field(default=-1)

class TimelineModel:
    """
    Holds tracks -> [Keyframe]. Calculates effective duration and emits change callbacks.
    """
    def __init__(self):
        self.duration: float = 60.0
        self.tracks: Dict[str, List[Keyframe]] = {name: [] for name in TRACKS}
        self._next_id = 1
        self._listeners: List = []

        # ensure pygame mixer can be used for length guessing
        if not pygame.get_init():
            pygame.init()
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init()
            except Exception:
                pass

    # ---- listeners ----
    def add_listener(self, fn):
        self._listeners.append(fn)

    def _emit(self):
        for fn in list(self._listeners):
            try:
                fn()
            except Exception:
                pass

    # ---- audio helpers ----
    def _guess_audio_len(self, path: str) -> float:
        try:
            if os.path.isfile(path):
                snd = pygame.mixer.Sound(path)
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

        # defaults
        if kf.data.get("duration", None) is None:
            if track == "BG":
                kf.data["duration"] = 0.6
            elif track == "SPRITE":
                kf.data["duration"] = 0.4
            elif track == "DIALOG":
                kf.data["duration"] = 2.5
            elif track == "MUSIC":
                path = str(kf.data.get("value", ""))
                L = self._guess_audio_len(path)
                kf.data["duration"] = L if L > 0 else 5.0
            elif track == "MENU":
                # menus are modal, but need a visible span on the timeline
                kf.data["duration"] = 30.0
            elif track == "LOGIC":
                # essentially instantaneous (label/jump); still draw a sliver
                kf.data["duration"] = 0.01
            else:
                kf.data["duration"] = 0.0

        self.tracks[track].append(kf)
        self.tracks[track].sort(key=lambda k: k.t)
        self.duration = max(self.duration, kf.t + self._eff_duration(track, kf))
        self._emit()

    def remove_kf(self, track: str, kf_id: int):
        arr = self.tracks.get(track, [])
        self.tracks[track] = [k for k in arr if k.id != kf_id]
        self._emit()

    def find_kf(self, track: str, kf_id: int) -> Optional[Keyframe]:
        for k in self.tracks.get(track, []):
            if k.id == kf_id:
                return k
        return None

    def _eff_duration(self, track: str, k: Keyframe) -> float:
        d = float(k.data.get("duration", 0.0))
        if track in ("BG", "SPRITE", "FX", "DIALOG", "MUSIC"):
            return max(d, TICK_SEC)
        if track == "SFX":
            return max(d, TICK_SEC)
        if track == "MENU":
            # long default so it's easy to see/place; UI remains modal until click
            return max(d if d > 0 else 30.0, TICK_SEC)
        if track == "LOGIC":
            # nearly instantaneous
            return max(d if d > 0 else 0.01, TICK_SEC)
        return max(d, TICK_SEC)

    def keyframes_at(self, t0: float, t1: float) -> Iterable[Tuple[str, Keyframe]]:
        """
        Return (track, keyframe) whose start time is in (t0, t1].
        """
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
            doc["tracks"][tr] = [
                {"t": k.t, "track": k.track, "data": k.data, "id": k.id} for k in arr
            ]
        return json.dumps(doc, indent=2)

    def load_json(self, s: str):
        doc = json.loads(s or "{}")
        self.duration = float(doc.get("duration", 60.0))
        # start with all known tracks
        self.tracks = {name: [] for name in TRACKS}
        self._next_id = 1

        for tr, arr in (doc.get("tracks", {}) or {}).items():
            bucket = self.tracks.setdefault(tr, [])
            for it in (arr or []):
                k = Keyframe(float(it.get("t", 0.0)), tr, dict(it.get("data", {})), int(it.get("id", -1)))
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

        self._emit()

    def delete_keyframes(self, items: list[tuple[str, int]]) -> int:
        """Remove keyframes by (track, keyframe_id). Returns number removed."""
        removed = 0
        for track, kid in items:
            arr = self.tracks.get(track, [])
            # remove all with matching id in that track
            new_arr = [k for k in arr if getattr(k, "id", None) != kid]
            removed += len(arr) - len(new_arr)
            self.tracks[track] = new_arr
        # (Optional) recompute duration if you derive it from content
        # self.duration = max([k.t + self._eff_duration(t, k) for t in self.tracks for k in self.tracks[t]] or [self.duration])
        if removed:
            self._emit()
        return removed


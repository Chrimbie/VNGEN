# transitions.py — reusable visual transition & shake helpers for VNGEN
import math
import pygame
from typing import Optional, Tuple


# --------- Fades on image layers (used for BG/SPRITE crossfades) ---------

def fade_in(surf: pygame.Surface,
            cur: Optional[pygame.Surface],
            progress: float,
            topleft: Tuple[int, int] = (0, 0)):
    """Image fade-in: 0→1 alpha."""
    if not cur:
        return
    a = max(0.0, min(1.0, float(progress)))
    tmp = cur.copy()
    tmp.set_alpha(int(255 * a))
    surf.blit(tmp, topleft)


def fade_out(surf: pygame.Surface,
             cur: Optional[pygame.Surface],
             progress: float,
             topleft: Tuple[int, int] = (0, 0)):
    """Image fade-out: 1→0 alpha."""
    if not cur:
        return
    a = max(0.0, min(1.0, float(progress)))
    tmp = cur.copy()
    tmp.set_alpha(int(255 * (1.0 - a)))
    surf.blit(tmp, topleft)


def crossfade(surf: pygame.Surface,
              prev: Optional[pygame.Surface],
              cur: Optional[pygame.Surface],
              progress: float,
              topleft: Tuple[int, int] = (0, 0)):
    """Crossfade two images with 0..1 progress."""
    p = max(0.0, min(1.0, float(progress)))
    if prev:
        tprev = prev.copy()
        tprev.set_alpha(int(255 * (1.0 - p)))
        surf.blit(tprev, topleft)
    if cur:
        tcur = cur.copy()
        tcur.set_alpha(int(255 * p))
        surf.blit(tcur, topleft)


# --------- Full-screen overlay fades (scene fades) ---------

def overlay_fade(surf: pygame.Surface, color: Tuple[int, int, int], progress: float):
    """Draw a full-screen color overlay with 0..1 alpha progress."""
    p = max(0.0, min(1.0, float(progress)))
    ov = pygame.Surface(surf.get_size(), flags=pygame.SRCALPHA)
    ov.fill((*color, int(255 * p)))
    surf.blit(ov, (0, 0))


def fade_out_black(surf: pygame.Surface, progress: float):
    overlay_fade(surf, (0, 0, 0), progress)


def fade_in_black(surf: pygame.Surface, progress: float):
    overlay_fade(surf, (0, 0, 0), 1.0 - progress)


def fade_out_white(surf: pygame.Surface, progress: float):
    overlay_fade(surf, (255, 255, 255), progress)


def fade_in_white(surf: pygame.Surface, progress: float):
    overlay_fade(surf, (255, 255, 255), 1.0 - progress)


# --------- Screen shake (deterministic, smooth-ish) ---------

def _smooth_noise(t: float, seed: int) -> float:
    """
    Cheap periodic noise: blend two sinusoids with prime-based phases.
    Output ~[-1,1].
    """
    # Different primes to decorrelate seeds
    f1 = 2.0 + (seed % 7) * 0.31
    f2 = 3.0 + (seed % 13) * 0.23
    return math.sin(2 * math.pi * f1 * t + seed * 1.111) * 0.66 + \
           math.sin(2 * math.pi * f2 * t + seed * 2.333) * 0.34


def shake_offset(elapsed: float,
                 duration: float,
                 amplitude_px: float,
                 frequency_hz: float,
                 decay: float = 2.5,
                 seed: int = 0) -> Tuple[int, int]:
    """
    Compute a (dx, dy) offset for a camera/screen shake.
    - elapsed: seconds since shake start
    - duration: total shake duration
    - amplitude_px: max pixel offset before decay
    - frequency_hz: base oscillation rate
    - decay: exp decay factor; larger = quicker falloff
    - seed: any int→ deterministic motion
    """
    if duration <= 0.0 or elapsed < 0.0 or elapsed > duration or amplitude_px <= 0.0:
        return (0, 0)
    # Normalize progress 0..1 and envelope
    p = max(0.0, min(1.0, elapsed / duration))
    env = math.exp(-decay * p)

    # Time-scaled param for noise
    t = elapsed * max(0.01, frequency_hz)

    # Two perpendicular noise channels
    nx = _smooth_noise(t, seed * 92821 + 17)
    ny = _smooth_noise(t, seed * 31337 + 53)

    dx = int(amplitude_px * env * nx)
    dy = int(amplitude_px * env * ny)
    return (dx, dy)

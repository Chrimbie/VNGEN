# effects.py — time-based visual effects like screen shake
import math

def _smooth_noise(t: float, seed: int) -> float:
    f1 = 2.0 + (seed % 7) * 0.31
    f2 = 3.0 + (seed % 13) * 0.23
    return math.sin(2 * math.pi * f1 * t + seed * 1.111) * 0.66 + \
           math.sin(2 * math.pi * f2 * t + seed * 2.333) * 0.34

def shake_offset(elapsed: float, duration: float, amplitude_px: float, frequency_hz: float,
                 decay: float = 2.5, seed: int = 0):
    """Return (dx, dy) shake offset in pixels for this time."""
    if duration <= 0.0 or elapsed < 0.0 or elapsed > duration or amplitude_px <= 0.0:
        return (0, 0)
    p = max(0.0, min(1.0, elapsed / duration))
    env = math.exp(-decay * p)
    t = elapsed * max(0.01, frequency_hz)
    nx = _smooth_noise(t, seed * 92821 + 17)
    ny = _smooth_noise(t, seed * 31337 + 53)
    dx = int(amplitude_px * env * nx)
    dy = int(amplitude_px * env * ny)
    return (dx, dy)

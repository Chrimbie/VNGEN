# transitions.py — fades and crossfades for VNGEN
import pygame
from typing import Optional, Tuple
import math

def overlay_fade(surf: pygame.Surface, color: Tuple[int, int, int], progress: float):
    """Full-screen overlay with alpha 0..1."""
    p = max(0.0, min(1.0, float(progress)))
    ov = pygame.Surface(surf.get_size(), flags=pygame.SRCALPHA)
    ov.fill((*color, int(255 * p)))
    surf.blit(ov, (0, 0))

def fade_in(surf: pygame.Surface, cur: Optional[pygame.Surface], progress: float, topleft=(0, 0)):
    if not cur: return
    a = max(0.0, min(1.0, float(progress)))
    tmp = cur.copy(); tmp.set_alpha(int(255 * a))
    surf.blit(tmp, topleft)

def fade_out(surf: pygame.Surface, cur: Optional[pygame.Surface], progress: float, topleft=(0, 0)):
    if not cur: return
    a = max(0.0, min(1.0, float(progress)))
    tmp = cur.copy(); tmp.set_alpha(int(255 * (1.0 - a)))
    surf.blit(tmp, topleft)

def crossfade(surf: pygame.Surface, prev: Optional[pygame.Surface], cur: Optional[pygame.Surface],
              progress: float, topleft=(0, 0)):
    p = max(0.0, min(1.0, float(progress)))
    if prev:
        tprev = prev.copy(); tprev.set_alpha(int(255 * (1.0 - p))); surf.blit(tprev, topleft)
    if cur:
        tcur = cur.copy();   tcur.set_alpha(int(255 * p));           surf.blit(tcur, topleft)


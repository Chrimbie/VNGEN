import pygame

def ensure_audio():
    if not pygame.get_init():
        pygame.init()
    if not pygame.mixer.get_init():
        try:
            pygame.mixer.init()
        except Exception:
            pass

def play_sfx(path: str, volume: float = 1.0):
    ensure_audio()
    try:
        s = pygame.mixer.Sound(path)
        s.set_volume(max(0.0, min(1.0, volume)))
        s.play()
    except Exception as e:
        print("[SFX] fail:", e)

def play_music(path: str, volume: float = 1.0, loop: bool = False):
    ensure_audio()
    try:
        pygame.mixer.music.load(path)
        pygame.mixer.music.set_volume(max(0.0, min(1.0, volume)))
        pygame.mixer.music.play(-1 if loop else 0)
    except Exception as e:
        print("[MUSIC] fail:", e)

def stop_music():
    try:
        pygame.mixer.music.stop()
    except Exception:
        pass

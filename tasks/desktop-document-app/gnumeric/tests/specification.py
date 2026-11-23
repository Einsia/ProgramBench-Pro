"""User-facing functional goals and their independent artifact assertions."""
import backend


def build():
    from gui import build as gui_episodes
    return [*gui_episodes(),*backend.build()]

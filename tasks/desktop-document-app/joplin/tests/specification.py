"""One manifest for user goals and broad program interface coverage."""
import backend
import gui_spec


def build():
    return gui_spec.build() + backend.build()

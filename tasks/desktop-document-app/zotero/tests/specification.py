"""The manifest's episodes: reviewed user goals on the desktop interface (gui.py) and program episodes on the
local API (program.py)."""
import gui
import program


def build():
    return gui.build() + program.build()

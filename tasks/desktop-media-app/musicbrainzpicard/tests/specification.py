"""Reviewed user goals, acceptance conditions, public setup and program checks for the GUI.

Reference recipes (reference/recipes.py) implement these specifications for the pinned standard; goals are authored
here and never translated from a click trace. An episode's input documents are uploaded into the runtime's input
folder before its first checkpoint (setup item "documents"); settings it needs are imported as a profile with
picard-cli followed by a restart (setup item "profile"); files it starts with are loaded with the LOAD remote
command (setup item "load"). Every assessed operation is a GUI goal; program checks read the files the goal saved,
moved or exported, and the session the application writes when it quits.
"""


def build():
    import gui_formats
    import gui_more
    import gui_naming
    import gui_options
    import gui_scripts
    import gui_episodes
    import gui_writing
    episodes = []
    for module in (gui_episodes, gui_more, gui_options, gui_formats, gui_writing, gui_scripts, gui_naming):
        episodes.extend(module.build())
    return episodes

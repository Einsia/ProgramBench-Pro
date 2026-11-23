"""One executable manifest source for record and candidate compare.

Program episodes carry the broad backend coverage: deterministic key sequences through the terminal and commands
of the application's command line, whose results are read through the command line (`task export` and command
output) and screen facts parsed by the reference's screen conventions (see harness.py). GUI episodes are user goals
judged by the evaluator with backend companions. The frozen reference recording defines the exact expected values;
requirement text describes the behaviour and must also hold for an equivalent reimplementation. Each area lives in
its own spec_*.py module.
"""
import spec_nav
import spec_add
import spec_tasks
import spec_filter
import spec_reports
import spec_context
import spec_views
import spec_details
import spec_edit
import spec_settings
import spec_taskwarrior
import spec_life
import spec_cli
import spec_more
import spec_gui

MODULES = (spec_nav, spec_add, spec_tasks, spec_filter, spec_reports, spec_context, spec_views,
           spec_details, spec_edit, spec_settings, spec_taskwarrior, spec_life, spec_cli, spec_more, spec_gui)


def build():
    episodes = []
    for module in MODULES:
        episodes.extend(module.episodes())
    return episodes

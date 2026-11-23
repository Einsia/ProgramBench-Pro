"""Reviewed user goals, acceptance conditions, deterministic recipes and program checks for micro 2.0.15.

Program episodes carry the broad backend coverage; GUI episodes are user goals judged by the evaluator with
backend companions. The families live in the spec_* modules; this module assembles them in a fixed order.
"""
import spec_actions
import spec_cli
import spec_commands
import spec_editing
import spec_filetypes
import spec_gui
import spec_keys
import spec_more
import spec_options
import spec_plugins
import spec_search
import spec_text
import spec_views


def build():
    episodes = []
    for module in (spec_keys, spec_commands, spec_actions, spec_options, spec_search, spec_editing, spec_plugins,
                   spec_filetypes, spec_views, spec_cli, spec_text, spec_more, spec_gui):
        episodes.extend(module.episodes())
    return episodes

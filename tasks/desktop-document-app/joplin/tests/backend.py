"""Isolated program episodes and their executable case registry."""
import api_notes
import api_organization
import api_resources
import api_lists
import api_todos
import api_search
import api_history
import api_options
import api_search_edges


SUITES = {s.key: s for s in [api_notes.build(), api_notes.clipping(), api_organization.folders(),
          api_organization.tags(), api_resources.build(), api_lists.build(), api_todos.build(),
          api_search.build(), api_history.build(), api_options.build(), api_search_edges.build()]}


def build():
    return [suite.manifest() for suite in SUITES.values()]


def case(episode, key):
    return next(c for c in SUITES[episode].cases if c.key == key)


def setup(episode, key):
    return next(fn for name, fn, _before in SUITES[episode].setups if name == key)

'''One executable manifest source for record and candidate compare.

Program episodes carry the broad backend coverage: deterministic batch runs (vd -b IN -o OUT, vd -b -p LOG.vdj)
and terminal key sequences whose results are read through the workspace inspector, the input history and
layout-independent screen facts. GUI episodes are user goals judged by the evaluator with backend companions.
The frozen reference recording defines the exact expected values; requirement text describes the behaviour and
must also hold for an equivalent reimplementation. Each area lives in its own spec_*.py module.
'''
import spec_convert
import spec_logs
import spec_tui
import spec_matrix
import spec_shapes
import spec_variants
import spec_extra
import spec_gui
import spec_more

MODULES = (spec_convert, spec_logs, spec_tui, spec_matrix, spec_shapes, spec_variants, spec_extra, spec_more, spec_gui)


def build():
    episodes = []
    for module in MODULES:
        episodes.extend(module.episodes())
    return episodes

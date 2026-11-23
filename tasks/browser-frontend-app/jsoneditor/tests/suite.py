"""One executable manifest for record and candidate compare."""
import json

import program
import specification
from evaluation.contract import load_frozen, manifest


def build():
    # A JSON round trip keeps the executable manifest identical to its frozen JSON copy (no tuples).
    return manifest(json.loads(json.dumps(program.build() + specification.build())))


def load(directory):
    return load_frozen(directory, build())

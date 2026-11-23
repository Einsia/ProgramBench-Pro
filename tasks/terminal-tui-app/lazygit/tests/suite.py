"""One executable manifest for record and candidate compare."""
import specification
from evaluation.contract import load_frozen, manifest


def build():
    return manifest(specification.build())


def load(directory):
    return load_frozen(directory, build())

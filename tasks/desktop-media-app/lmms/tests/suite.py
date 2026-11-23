'''One executable manifest for record and candidate compare.'''
import backend
import specification
from evaluation.contract import load_frozen, manifest


def build():
    return manifest(specification.build() + backend.build())


def load(directory):
    return load_frozen(directory, build())

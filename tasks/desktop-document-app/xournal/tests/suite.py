import specification
from evaluation.contract import manifest, load_frozen


def build():
    return manifest(specification.build())


def load(directory):
    return load_frozen(directory, build())

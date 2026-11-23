import json
import program
import specification
import extended
from evaluation.contract import load_frozen, manifest

def build():
    return manifest(json.loads(json.dumps(program.build() + specification.build() + extended.build())))

def load(directory):
    return load_frozen(directory, build())

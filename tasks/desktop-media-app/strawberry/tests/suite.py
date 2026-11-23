"""Executable manifest shared by record and comparison."""
import backend
import specification
from evaluation.contract import load_frozen,manifest

def build():return manifest(specification.build()+backend.build())
def load(directory):return load_frozen(directory,build())

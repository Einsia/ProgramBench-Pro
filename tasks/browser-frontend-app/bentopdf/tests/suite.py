"""Executable episode manifest and frozen-bundle validation."""
import json
from evaluation.contract import manifest,load_frozen
import specification
import features
import editor_features
import form_features
import editing
import remaining
import signatures
import finishing
import extended
import extended_ui
import extra_signatures
import final_branches

def build():return manifest(json.loads(json.dumps(specification.build()+features.build()+editor_features.build()+form_features.build()+editing.build()+remaining.build()+signatures.build()+finishing.build()+extended.build()+extended_ui.build()+extra_signatures.build()+final_branches.build())))
def load(directory):return load_frozen(directory,build())

"""Episode evaluation package; task identity is in task.py."""
from pathlib import Path

# Images contain the scorer copied at build time. Source-tree checks use the
# same module directly from the repository's tools directory.
if not Path(__file__).with_name('scoring.py').is_file():
    for parent in Path(__file__).resolve().parents:
        tools = parent / 'tools'
        if (tools / 'scoring.py').is_file():
            __path__.append(str(tools))
            break

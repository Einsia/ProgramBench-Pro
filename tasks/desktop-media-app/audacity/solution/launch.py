#!/usr/bin/env python3
"""Launch Audacity with private user configuration and the supplied scripting endpoint."""
from __future__ import annotations

import datetime
import os
import importlib.util

# The installation root is traversable but not listable; load the known helper path directly.
_isolation_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'isolation.py')
_isolation_spec = importlib.util.spec_from_file_location('application_isolation', _isolation_path)
_isolation = importlib.util.module_from_spec(_isolation_spec)
_isolation_spec.loader.exec_module(_isolation)
confine = _isolation.confine
from pathlib import Path


def main() -> None:
    state = Path(os.environ.get("DATA_DIR", "/app/state")).resolve()
    state.mkdir(parents=True, exist_ok=True)
    home = Path(os.environ.get("HOME", str(state / "home"))).resolve()
    config_dir = home / ".audacity-data"
    config_dir.mkdir(parents=True, exist_ok=True)

    package = Path(__file__).resolve().parent
    binary = package / "runtime" / "bin" / "audacity"
    module = package / "runtime" / "lib" / "audacity" / "modules" / "mod-script-pipe.so"
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise SystemExit(f"reference Audacity binary is unavailable: {binary}")
    if not module.is_file():
        raise SystemExit(f"reference scripting module is unavailable: {module}")

    # The runtime separates simultaneous processes of one user with
    # PBP_AUDIO_PIPE_DIR; without it the pipes are in /tmp as usual.
    pipe_dir = Path(os.environ.get("PBP_AUDIO_PIPE_DIR", "/tmp")).resolve()
    pipe_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.fromtimestamp(module.stat().st_mtime).strftime("%Y-%m-%dT%H:%M:%S")
    config = config_dir / "audacity.cfg"
    if not config.exists():
        config.write_text(
            f"""PrefsVersion=1.1.1r1
[Version]
Major=2
Minor=4
Micro=2
[Module]
mod-script-pipe=1
[ModulePath]
mod-script-pipe={module}
[ModuleDateTime]
mod-script-pipe={stamp}
[GUI]
ShowSplashScreen=0
[Directories]
TempDir={state}/tmp/audio-temp
[AudioIO]
PlaybackDevice=pulse
RecordingDevice=pulse
Host=ALSA
[Quality]
DitherAlgorithmChoice=None
HQDitherAlgorithmChoice=None
[Warnings]
FirstProjectSave=0
"""
        )

    os.environ.setdefault("TMPDIR", str(state / "tmp"))
    os.environ["PBP_AUDIO_PIPE_DIR"] = str(pipe_dir)
    os.environ["AUDACITY_MODULES_PATH"] = str(module.parent)
    os.environ["AUDACITY_PATH"] = str(binary.parent.parent / "share" / "audacity")
    # solve.sh made the scripting module's FIFO names relative; creating them
    # from this directory honors the documented PBP_AUDIO_PIPE_DIR contract.
    os.chdir(pipe_dir)
    confine(binary, package)
    os.execv(str(binary), [str(binary)])


if __name__ == "__main__":
    main()

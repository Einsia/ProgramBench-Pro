#!/usr/bin/env python3
"""Launch Strawberry using the supplied private profile."""
from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import sys

SCHEMA_VERSION = 25


def seed_database(path: Path, schema: Path, collection: str) -> None:
    """The database a first start of Strawberry 1.2.31 creates (its own schema file), plus the task's
    collection folder. Written to a temporary name and renamed, so a half-written database is never used."""
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + '.partial')
    partial.unlink(missing_ok=True)
    connection = sqlite3.connect(partial)
    try:
        connection.executescript(schema.read_text(encoding='utf-8'))
        version = connection.execute('SELECT version FROM schema_version').fetchone()
        if version != (SCHEMA_VERSION,):
            raise SystemExit(f'unexpected Strawberry schema version {version}')
        connection.execute("INSERT INTO playlists (name) VALUES ('Playlist 1')")
        if collection:
            connection.execute('INSERT INTO directories (path, subdirs) VALUES (?, 1)', (collection,))
        connection.commit()
    finally:
        connection.close()
    partial.replace(path)


def main() -> None:
    package = Path(__file__).resolve().parent
    binary = package / 'runtime' / 'usr' / 'bin' / 'strawberry'
    schema = package / 'schema.sql'
    if not os.access(binary, os.X_OK):
        raise SystemExit(f'Strawberry binary is unavailable: {binary}')

    data = Path(os.environ.get('DATA_DIR', str(package / 'state'))).resolve()
    config_home = data / 'config'
    data_home = data / 'share'
    for directory in (data, config_home, data_home):
        directory.mkdir(parents=True, exist_ok=True)
    os.environ['XDG_CONFIG_HOME'] = str(config_home)
    os.environ['XDG_DATA_HOME'] = str(data_home)
    os.environ.setdefault('XDG_CACHE_HOME', str(data / 'cache'))
    os.environ.setdefault('TMPDIR', str(data / 'tmp'))
    Path(os.environ['TMPDIR']).mkdir(parents=True, exist_ok=True)

    settings = config_home / 'strawberry' / 'strawberry.conf'
    if not settings.exists():
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text('[MainWindow]\ndo_not_show_sponsor_message=true\nfile_path='+os.environ.get('PBP_COLLECTION_DIR','')+'\n[FileView]\ntree_root_paths='+os.environ.get('PBP_COLLECTION_DIR','')+'\n[Collection]\nscan_on_startup=true\n', encoding='utf-8')
    database = data_home / 'strawberry' / 'strawberry' / 'strawberry.db'
    if not database.exists():
        collection = os.environ.get('PBP_COLLECTION_DIR', '')
        if collection:
            collection = str(Path(collection).resolve())
            Path(collection).mkdir(parents=True, exist_ok=True)
        seed_database(database, schema, collection)

    # Qt finds the accessibility bus through the D-Bus session; a preset bus address keeps it from registering.
    os.environ.pop('AT_SPI_BUS_ADDRESS', None)
    os.environ['QT_QPA_PLATFORM'] = 'xcb'
    os.environ.setdefault('QT_ACCESSIBILITY', '1')
    os.environ.setdefault('QT_LINUX_ACCESSIBILITY_ALWAYS_ON', '1')
    # GStreamer loads only the system plug-ins (never a per-user plug-in folder) and scans them in-process.
    os.environ['GST_PLUGIN_SYSTEM_PATH_1_0'] = '/usr/lib/x86_64-linux-gnu/gstreamer-1.0'
    os.environ['GST_REGISTRY_FORK'] = 'no'
    os.environ['LD_PRELOAD'] = str(package / 'process_guard.so')
    os.execv(str(binary), [str(binary), *sys.argv[1:]])


if __name__ == '__main__':
    main()

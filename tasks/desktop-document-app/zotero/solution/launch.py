#!/usr/bin/env python3
"""Start the pinned Zotero release with all of its state under DATA_DIR.

DATA_DIR/profile is the application profile and DATA_DIR/zotero the Zotero data directory (database, attached
files, styles and translators). Before every start the launcher writes the profile's user.js: the data directory,
the local HTTP server on PORT with the local API enabled, online services (updates, sync, repository and
retraction checks, metadata retrieval) and first-run notices off, reduced motion, and developer tools and add-on
installation disabled. It then grants the runtime's local API key (PBP_API_KEY) in the profile's
localAPIKeys.json, the file in which Zotero keeps the keys a user allowed, and runs the upstream zotero launcher
script in the foreground. The application itself is not changed.
"""
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRODUCT = HERE / 'zotero'


def preferences(library, port):
    return {
        'extensions.zotero.dataDir': str(library),
        'extensions.zotero.useDataDir': True,
        'extensions.zotero.httpServer.enabled': True,
        'extensions.zotero.httpServer.port': port,
        'extensions.zotero.httpServer.localAPI.enabled': True,
        # Online services: there is no network.
        'extensions.zotero.automaticScraperUpdates': False,
        'extensions.zotero.sync.autoSync': False,
        'extensions.zotero.sync.reminder.setUp.enabled': False,
        'extensions.zotero.sync.reminder.autoSync.enabled': False,
        'extensions.zotero.streaming.enabled': False,
        'extensions.zotero.retractions.enabled': False,
        'extensions.zotero.autoRecognizeFiles': False,
        'app.update.auto': False,
        'app.update.enabled': False,
        # First-run and upgrade notices.
        'extensions.zotero.showPostUpgradeBanner': False,
        'extensions.zotero.firstRunGuidance': False,
        'toolkit.startup.max_resumed_crashes': -1,
        # A fixed English interface without animations.
        'intl.locale.requested': 'en-US',
        'ui.prefersReducedMotion': 1,
        'toolkit.cosmeticAnimations.enabled': False,
        # No developer tools, add-on installation or external launcher.
        'devtools.policy.disabled': True,
        'devtools.chrome.enabled': False,
        'devtools.debugger.remote-enabled': False,
        'xpinstall.enabled': False,
        'extensions.zotero.fallbackLauncher.unix': '',
    }


def write_atomic(path, text):
    pending = path.with_name(path.name + '.pending')
    pending.write_text(text, encoding='utf-8')
    os.replace(pending, path)


def grant_key(profile, key):
    """The runtime's key as a remembered ("Always Allow") local API key."""
    path = profile / 'localAPIKeys.json'
    try:
        keys = json.loads(path.read_text(encoding='utf-8')).get('keys', [])
        keys = [entry for entry in keys if isinstance(entry, dict)]
    except (OSError, ValueError, AttributeError):
        keys = []
    if not any(entry.get('key') == key for entry in keys):
        keys.append({'key': key, 'appName': 'Black-box runtime', 'remember': True,
                     'createdAt': '2024-01-01T00:00:00.000Z'})
    write_atomic(path, json.dumps({'keys': keys}, indent=4))


def main():
    data = Path(os.environ['DATA_DIR'])
    port = int(os.environ.get('PORT') or 23119)
    profile, library = data / 'profile', data / 'zotero'
    for path in (profile, library):
        path.mkdir(parents=True, exist_ok=True)
    lines = [f'user_pref({json.dumps(name)}, {json.dumps(value)});\n'
             for name, value in preferences(library, port).items()]
    write_atomic(profile / 'user.js', ''.join(lines))
    if os.environ.get('PBP_API_KEY'):
        grant_key(profile, os.environ['PBP_API_KEY'])
    env = dict(os.environ, GNOME_ACCESSIBILITY='1', MOZ_CRASHREPORTER_DISABLE='1')
    # File dialogs without a remembered folder open in the working directory: the exchange outbox when there is one.
    exports = os.environ.get('PBP_OUTBOX')
    os.chdir(exports if exports and os.path.isdir(exports) else data)
    script = str(PRODUCT / 'zotero')
    os.execve(script, [script, '-profile', str(profile), '-no-remote'], env)


if __name__ == '__main__':
    main()

"""Driving the application through the black-box runtime.

The same high-level steps drive the standard answer during record (GUI
reference recipes) and the candidate during program-episode preparation, so
every step uses only runtime operations that work on any faithful
reimplementation: opening inbox documents with the runtime's `open`, keyboard
shortcuts and typed text, the accessible application menu, and, for file
dialogs, a typed exchange path confirmed with the dialog's confirm button.
Coordinates are used only to focus the editor body and to press a file
dialog's confirm button (its bottom bar), both of which a maximized editor
window and a centered dialog place deterministically.
"""
from __future__ import annotations

import time

EDITOR_POINT = (640, 470)


class DriveError(RuntimeError):
    pass


def folders(ctx):
    info = ctx.episode['inputs']
    return info['input_folder'], info['output_folder']


def resolve(ctx, name):
    """An episode file name ('inbox/x.md', 'outbox/y.md' or a bare inbox name) to its absolute exchange path."""
    inbox, outbox = folders(ctx)
    if name.startswith('inbox/'):
        return inbox + '/' + name[len('inbox/'):]
    if name.startswith('outbox/'):
        return outbox + '/' + name[len('outbox/'):]
    return inbox + '/' + name


def call(ctx, request, **kw):
    return ctx.broker.call(request, **kw)


def settle(ctx, seconds=0.6):
    time.sleep(seconds)


def active_dialog(ctx):
    """Bounds [x,y,w,h] of the active native file dialog window, or None."""
    windows = call(ctx, {'op': 'windows'})['windows']
    active = next((w for w in windows if w.get('active')), None)
    if active and not (active.get('title') or '').endswith('- MarkText'):
        return active.get('bounds')
    return None


def focus_editor(ctx):
    call(ctx, {'op': 'click', 'x': EDITOR_POINT[0], 'y': EDITOR_POINT[1]})
    settle(ctx, 0.2)


def menu_item_ref(ctx, label):
    """Ref of a visible menu item whose accessible name is the label or the label followed by its accelerator."""
    obs = call(ctx, {'op': 'observe', 'tree': True})
    for node in obs['nodes']:
        if node['role'] in ('menu item', 'check menu item'):
            name = node['name']
            if name == label or name.startswith(label + ' ') or name.startswith(label + '\t'):
                return node['ref']
    raise DriveError(f'menu item {label!r} is not visible')


def menu(ctx, path):
    """Open the application menu and walk the named items/submenus (names may carry a trailing accelerator)."""
    call(ctx, {'op': 'click', 'target': {'role': 'push button', 'name': 'Application Menu'}})
    settle(ctx, 0.5)
    for i, label in enumerate(path):
        ref = menu_item_ref(ctx, label)
        if i < len(path) - 1:
            call(ctx, {'op': 'move', 'target': ref})
            settle(ctx, 0.4)
            ref = menu_item_ref(ctx, label)
        call(ctx, {'op': 'click', 'target': ref})
        settle(ctx, 0.4)


def confirm_dialog(ctx, timeout=10.0):
    """Click the confirm button in the bottom-right of the active native file dialog, until the dialog closes."""
    deadline = time.monotonic() + timeout
    bounds = None
    while time.monotonic() < deadline:
        bounds = active_dialog(ctx)
        if bounds:
            break
        settle(ctx, 0.3)
    if not bounds:
        raise DriveError('no native file dialog is open to confirm')
    x, y, w, h = bounds
    for dx, dy in ((w - 50, h - 28), (w - 48, h - 26), (w - 62, h - 30), (w - 50, h - 42)):
        call(ctx, {'op': 'click', 'x': x + dx, 'y': y + dy})
        settle(ctx, 1.2)
        if active_dialog(ctx) is None:
            return
    raise DriveError('the file dialog did not close after confirming')


def type_path_and_confirm(ctx, path, open_location=False):
    """In the active file dialog, enter an absolute exchange path and confirm it."""
    if not active_dialog(ctx):
        # give the dialog a moment to appear
        for _ in range(20):
            settle(ctx, 0.3)
            if active_dialog(ctx):
                break
    if open_location:
        call(ctx, {'op': 'press', 'key': 'Control+L'})
        settle(ctx, 0.3)
    call(ctx, {'op': 'press', 'key': 'Control+A'})
    call(ctx, {'op': 'type', 'value': path})
    settle(ctx, 0.3)
    confirm_dialog(ctx)


STEP = {}


def step(name):
    def register(fn):
        STEP[name] = fn
        return fn
    return register


@step('open')
def _open(ctx, s):
    paths = [resolve(ctx, n) for n in s['files']]
    request = {'op': 'open', 'paths': paths}
    if s.get('new_window'):
        request['new_window'] = True
    call(ctx, request, timeout=90)
    settle(ctx, s.get('settle', 3.0))
    # Whether the open succeeded is enforced by the artifact comparison, not by an appearance detail such as the
    # window-title text: every serialization fixture is authored in a non-canonical form, so a document that did
    # not open (leaving a stale untitled buffer) re-serializes to something other than the frozen canonical output
    # and cannot be mistaken for a round-trip. This keeps the check independent of how a faithful editor chooses to
    # label the open document (window title, tab or breadcrumb).


@step('focus')
def _focus(ctx, s):
    focus_editor(ctx)


@step('key')
def _key(ctx, s):
    call(ctx, {'op': 'press', 'key': s['key']})
    settle(ctx, s.get('settle', 0.25))


@step('keys')
def _keys(ctx, s):
    for key in s['keys']:
        call(ctx, {'op': 'press', 'key': key})
        settle(ctx, 0.15)
    settle(ctx, s.get('settle', 0.2))


@step('type')
def _type(ctx, s):
    if s.get('focus', False):
        focus_editor(ctx)
    call(ctx, {'op': 'type', 'value': s['value']})
    settle(ctx, s.get('settle', 0.3))


@step('dirty')
def _dirty(ctx, s):
    # A content-neutral edit at the end of the document to mark it modified so a save rewrites it.
    focus_editor(ctx)
    call(ctx, {'op': 'press', 'key': 'Control+End'})
    settle(ctx, 0.15)
    call(ctx, {'op': 'type', 'value': ' '})
    settle(ctx, 0.15)
    call(ctx, {'op': 'press', 'key': 'BackSpace'})
    settle(ctx, 0.3)


@step('save')
def _save(ctx, s):
    call(ctx, {'op': 'press', 'key': 'Control+S'})
    settle(ctx, s.get('settle', 1.5))


@step('save-as')
def _save_as(ctx, s):
    call(ctx, {'op': 'press', 'key': 'Control+Shift+S'})
    settle(ctx, 2.0)
    type_path_and_confirm(ctx, resolve(ctx, s['path']))
    settle(ctx, s.get('settle', 1.0))


@step('export')
def _export(ctx, s):
    # File > Export > Export as HTML/PDF opens an export settings dialog with an Export button, then the native
    # save dialog takes the path.
    menu(ctx, ['File', 'Export', s['menu']])
    settle(ctx, 1.5)
    call(ctx, {'op': 'click', 'target': {'role': 'push button', 'name': 'Export'}})
    settle(ctx, 2.5)
    type_path_and_confirm(ctx, resolve(ctx, s['path']))
    settle(ctx, s.get('settle', 2.5))


@step('select-all')
def _select_all(ctx, s):
    focus_editor(ctx)
    call(ctx, {'op': 'press', 'key': 'Control+A'})
    settle(ctx, 0.3)


@step('copy-html-ready')
def _copy_html_ready(ctx, s):
    """Retry the ordinary copy action while asynchronous document selection settles.

    The clipboard's previous contents are only a readiness signal, never an
    expected answer. Identical consecutive copies remain valid at the deadline.
    """
    def read():
        try:
            return call(ctx, {'op': 'clipboard_html'}).get('html', '') or ''
        except Exception:
            return ''

    previous = read()
    deadline = time.monotonic() + 12.0
    while True:
        _select_all(ctx, {})
        call(ctx, {'op': 'press', 'key': 'Control+Shift+C'})
        settle(ctx, 0.9)
        current = read()
        if current.strip() and current != previous:
            settle(ctx, 0.3)
            if read() == current:
                return
        if time.monotonic() >= deadline:
            return


@step('menu')
def _menu(ctx, s):
    menu(ctx, s['path'])


@step('wait')
def _wait(ctx, s):
    settle(ctx, s.get('seconds', 0.5))


@step('clear')
def _clear(ctx, s):
    """Replace the whole document with the given markdown text (select all, type)."""
    focus_editor(ctx)
    call(ctx, {'op': 'press', 'key': 'Control+A'})
    settle(ctx, 0.2)
    call(ctx, {'op': 'type', 'value': s['value']})
    settle(ctx, s.get('settle', 0.5))


def run(ctx, steps):
    for s in steps:
        fn = STEP.get(s['op'])
        if fn is None:
            raise DriveError('unknown drive step ' + s['op'])
        fn(ctx, s)

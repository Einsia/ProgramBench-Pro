"""Desktop interface boundaries for the offline reference appliance."""
import re

import blackbox_desktop as desktop
from joplin_api import Refused, safe_document

MENUS = {'menu item', 'check menu item', 'radio menu item'}
CONTROLS = MENUS | {'push button', 'button', 'toggle button', 'link', 'page tab', 'list item',
                    'entry', 'text', 'check box', 'combo box', 'radio button', 'spin button'}
MENU_KEYS = {'Up', 'Down', 'Left', 'Right', 'Home', 'End', 'Return', 'KP_Enter', 'Escape', 'space'}
DENIED_KEYS = {'ctrl+e', 'ctrl+shift+p', 'ctrl+shift+i', 'ctrl+shift+j', 'ctrl+s', 'F1', 'F12'}
DENIED = {
    'toggle development tools', 'toggle safe mode', 'open profile directory', 'copy dev command',
    'open secondary app instance', 'open primary app instance', 'switch profile', 'command palette',
    'toggle external editing', 'open in external editor', 'edit in external editor', 'toggle ai chat', 'insert drawing',
    'plugins', 'synchronisation', 'synchronization', 'synchronize', 'web clipper', 'external editor',
    'keyboard shortcuts', 'advanced settings', 'ocr', 'optical character recognition', 'ai',
    'custom stylesheet for rendered markdown', 'custom stylesheet for joplin-wide app styles',
    'open', 'open with', 'reveal file in folder', 'reveal in folder', 'show in folder',
    'open item location', 'open containing directory', 'edit source', 'inspect element',
    'website and documentation', 'join us on bluesky', 'make a donation', 'export deletion log', 'publish note', 'share notebook', 'joplin website', 'joplin forum', 'joplin cloud', 'check for updates', 'donate',
    'help and documentation', 'usage', 'privacy', 'documentation', 'other applications',
}
PREFIXES = ('install plugin', 'manage plugin', 'open plugin', 'open dev', 'open config', 'copy dev',
            'export debug', 'download debug', 'custom stylesheet', 'edit css', 'external text editor',
            'text editor command', 'proxy', 'custom tls', 'ocr:', 'synchronisation target', 'synchronization target')


def plain(value):
    value = (value or '').replace('&', '').strip()
    value = re.split(r'\s+(?:Ctrl|Alt|Shift)\+', value)[0]
    return value.rstrip('.\u2026 ').casefold()


def denied(node, in_chooser=False):
    name = plain(node.get('name'))
    role = node.get('role')
    if in_chooser and name in {'open', 'save', 'select', 'export', 'import'}:
        return False
    if role == 'link':
        # Internal note links have a joplin resource address or a note name. A
        # link which could launch another application is never followed.
        description = node.get('description', '')
        if re.search(r'(?:https?|file|mailto|javascript|joplin)://|mailto:', name + ' ' + description, re.I):
            return True
    return role in CONTROLS and (name in DENIED or name.startswith(PREFIXES))


def guard(rt, data, view, chain, key):
    op = data['op']
    nodes = view['nodes']
    chooser = any(n['role'] == 'file chooser' for n in nodes)
    menu_open = any(n['role'] in MENUS for n in nodes)
    why = 'this control loads code, starts another application or reaches outside the document exchange'
    if op == 'press' and key in DENIED_KEYS:
        raise Refused(why)
    if op in ('type', 'fill', 'press') and key not in ('Escape', 'Tab', 'shift+Tab'):
        if any('focused' in n.get('states', ()) and denied(n, chooser) for n in nodes):
            raise Refused(why)
    if op in ('click', 'activate', 'check', 'fill', 'type', 'drag') or (op == 'press' and data.get('target')):
        if any(denied(n, chooser) for n in (chain or [])[:3]):
            raise Refused(why)
    if op == 'press' and key in ('Return', 'KP_Enter', 'space'):
        for node in nodes:
            if {'focused', 'selected'} & set(node.get('states', ())) and denied(node, chooser):
                raise Refused(why)
    if menu_open:
        if op == 'press' and key not in MENU_KEYS:
            raise Refused('while a menu is open use movement keys, Return, space or Escape')
        if op in ('type', 'fill'):
            raise Refused('text cannot be entered while a menu is open')
    # A settings category can also be selected with the keyboard. Refuse input
    # in a restricted category after such navigation, but permit leaving it.
    restricted = [n for n in nodes if n['role'] in ('page tab', 'list item') and denied(n)
                  and {'selected', 'checked'} & set(n.get('states', ()))]
    if restricted:
        exit_action = op == 'press' and key == 'Escape'
        exit_action |= op in ('click', 'activate') and any(
            plain(n.get('name')) in {'back', 'cancel', 'ok'} or n['role'] == 'page tab' for n in chain or [])
        if not exit_action:
            raise Refused('this settings category is unavailable; return to another category')
    if op in ('type', 'fill') and not chooser:
        safe_document(data.get('value', ''))
    paste = op == 'press' and key in {'ctrl+v', 'ctrl+shift+v', 'shift+Insert'}
    paste |= op == 'click' and data.get('button') == 'middle'
    paste |= op in ('click', 'activate') and any(plain(n.get('name')).startswith('paste') for n in chain or [])
    if paste and not chooser:
        try:
            safe_document(rt.ui.clipboard('UTF8_STRING', 400000).decode('utf-8', 'replace'))
        except desktop.DesktopError:
            pass

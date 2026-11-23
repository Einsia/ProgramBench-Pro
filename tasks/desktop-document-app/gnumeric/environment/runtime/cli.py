"""Bounded access to the product's real command-line tools and exchange files."""
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import time

MAX_OUTPUT = 262144
SECONDS = 90
FLAGS = {
    'ssconvert': {'--help', '--help-all', '--version', '--list-importers', '--list-exporters',
                  '--list-image-formats', '--recalc', '--export-file-per-sheet', '--export-graphs', '--verbose'},
    'ssgrep': {'--help','--help-all','--version','--count','--string-table-count','--fixed-strings','--with-filename','--without-filename','--ignore-case','--files-with-matches','--files-without-matches','--print-locus','--quiet','--search-results','--print-type','--invert-match','--word-regexp','--recalc'},
    'ssdiff': {'--help','--help-all','--version','--highlight','--xml'},
    'ssindex': {'--help', '--help-all', '--version', '--index', '--list-mime-types'},
}
VALUES = {
    'ssconvert': {'--import-type', '--export-type', '--import-encoding', '--export-options', '--set', '--merge-to'},
    'ssindex': {'--encoding'},
    'ssgrep': {'--pattern-file'},
    'ssdiff': {'--output'},
}
SHORT = {'-I': '--import-type', '-T': '--export-type', '-E': '--import-encoding', '-O': '--export-options',
         '-M': '--merge-to', '-S': '--export-file-per-sheet', '-v': '--verbose'}
DOCUMENTS = {'.gnumeric', '.xlsx', '.xls', '.ods', '.csv', '.tsv', '.txt', '.xml', '.html', '.htm',
             '.sylk', '.slk', '.dif', '.dbf', '.wk1', '.wks', '.wk4', '.wb1', '.wb2', '.wb3', '.qpw',
             '.pln', '.as', '.oleo', '.sc', '.mps', '.psion', '.sxc', '.stc', '.xlw', '.xlt',
             '.xltx', '.otc', '.ots', '.fods', '.pdf', '.tex', '.troff', '.svg', '.png', '.jpg', '.jpeg'}

SPEC = {'kind': 'files', 'summary': 'Run ssconvert, ssindex, ssgrep or ssdiff with its normal public command-line options; '
        'files must be in the exchange folders. Returns exit_code, stdout and stderr. '
        'No shell interpretation. stdout/stderr are capped at 262144 bytes each; timeout 90 seconds.',
        'fields': {'tool': {'type': 'string', 'enum': ['ssconvert', 'ssindex', 'ssgrep', 'ssdiff'], 'required': True,
                            'description': 'The executable of the same name supplied in the solution directory.'},
                   'args': {'type': 'array', 'items': {'type': 'string'}, 'required': True,
                            'description': 'Up to 256 native arguments. Accepted flags: --help, --help-all, '
                            '--version; ssconvert --list-importers, --list-exporters, --list-image-formats, '
                            '--recalc, --export-file-per-sheet/-S, --export-graphs, --verbose/-v, '
                            '--import-type/-I ID, --export-type/-T ID, --import-encoding/-E ENCODING, '
                            '--export-options/-O OPTIONS, --set CELL=VALUE, --merge-to/-M OUTPUT; '
                            'ssindex --index, --list-mime-types, --encoding; ssgrep --count, --string-table-count, '
                            '--pattern-file, --fixed-strings, --with-filename, --without-filename, --ignore-case, '
                            '--files-with-matches, --files-without-matches, --print-locus, --quiet, '
                            '--search-results, --print-type, --invert-match, --word-regexp, --recalc; '
                            'ssdiff --xml, --highlight, --output. The first positional ssgrep argument is the pattern '
                            'unless --pattern-file is supplied. Native positional file arguments are '
                            'absolute exchange paths, or inbox/NAME and outbox/NAME. Option values may use =.'}}}


def path(runtime, value):
    if not isinstance(value, str) or '\x00' in value:
        raise ValueError('file argument must be a string')
    for area in ('inbox', 'outbox'):
        if value.startswith(area + '/'):
            value = str(runtime.areas[area] / value[len(area)+1:])
            break
    p = Path(value)
    if not p.is_absolute() or '..' in p.parts or not runtime.inside(str(p)):
        raise ValueError('command files must be inside the inbox or outbox')
    if len(p.name.encode()) > 240 or p.name.startswith('.') or p.suffix.casefold() not in DOCUMENTS:
        raise ValueError('command files must have an allowed document extension; see help')
    # The final file may not exist, but every existing path component must be plain.
    if not runtime.inside(str(p.resolve())) or any(x.is_symlink() for x in [p, *p.parents] if runtime.inside(str(x))):
        raise ValueError('command files cannot use symbolic links')
    if p.exists() and (not p.is_file() or p.stat().st_nlink != 1):
        raise ValueError('command files must be regular files')
    return str(p)


def arguments(runtime, tool, args):
    if not isinstance(args, list) or len(args) > 256 or any(not isinstance(a, str) or '\x00' in a or len(a) > 32768 for a in args):
        raise ValueError('args must contain at most 256 strings of at most 32768 characters')
    result, i, pattern_seen = [], 0, any(a == '--pattern-file' or a.startswith('--pattern-file=') for a in args)
    while i < len(args):
        value = args[i]
        option, equal, inline = value.partition('=')
        option = SHORT.get(option, option) if tool == 'ssconvert' else option
        if option in FLAGS[tool]:
            if equal:
                raise ValueError('flag does not accept a value')
            result.append(option)
        elif option in VALUES[tool]:
            if equal:
                val = inline
            else:
                i += 1
                if i >= len(args):
                    raise ValueError('missing command option value')
                val = args[i]
            if option in ('--merge-to','--pattern-file','--output'):
                val = path(runtime, val)
            elif option == '--set':
                if '=' not in val or len(val) > 20000:
                    raise ValueError('--set takes CELL=VALUE')
                runtime.check_document_text(val)
            elif option in ('--import-type', '--export-type', '--import-encoding','--encoding'):
                if not re.fullmatch(r'[A-Za-z0-9_.:+-]{1,160}', val):
                    raise ValueError('invalid format or encoding identifier')
            elif any(c in val for c in ('\x00', '\n', '\r')) or len(val) > 4000:
                raise ValueError('invalid export option string')
            result.extend([option, val])
        elif value.startswith('-'):
            raise ValueError('command option is not available; see help')
        elif tool == 'ssgrep' and not pattern_seen:
            result.append(value)
            pattern_seen = True
        else:
            result.append(path(runtime, value))
        i += 1
    return result


def run(runtime, data):
    tool = data['tool']
    args = arguments(runtime, tool, data['args'])
    executable = runtime.product.solution / tool
    if not executable.is_file():
        return {'exit_code': 127, 'stdout': '', 'stderr': tool + ' is not supplied by the application', 'timed_out': False}
    env = runtime.product.environment()
    kwargs = {}
    if runtime.product.switching():
        account = runtime.product.account()
        kwargs = {'user': account.pw_uid, 'group': account.pw_gid, 'extra_groups': []}
    proc = subprocess.Popen([str(executable), *args], cwd=str(runtime.product.solution), env=env,
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            start_new_session=True, **kwargs)
    streams = {'stdout': bytearray(), 'stderr': bytearray()}
    truncated, timed_out = False, False
    selector = selectors.DefaultSelector()
    selector.register(proc.stdout, selectors.EVENT_READ, 'stdout')
    selector.register(proc.stderr, selectors.EVENT_READ, 'stderr')
    deadline = time.monotonic() + SECONDS
    try:
        while selector.get_map():
            if time.monotonic() >= deadline:
                timed_out = True
                break
            for key, _ in selector.select(min(.2, max(0, deadline-time.monotonic()))):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                retained = streams[key.data]
                capacity = MAX_OUTPUT-len(retained)
                retained.extend(chunk[:capacity])
                truncated |= len(chunk) > capacity
        if timed_out:
            os.killpg(proc.pid, signal.SIGKILL)
        code = proc.wait(timeout=5)
    finally:
        selector.close()
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=5)
        proc.stdout.close()
        proc.stderr.close()
    result = {key: runtime.private_text(bytes(value).decode('utf-8', 'replace'))[0] for key, value in streams.items()}
    return {'exit_code': code, **result, 'timed_out': timed_out, 'truncated': truncated}

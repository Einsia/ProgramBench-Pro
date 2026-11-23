"""Validation of application inputs and repository configuration."""
import re
import shlex

VIEWS = ('main', 'diff', 'log', 'reflog', 'tree', 'blob', 'blame', 'refs', 'status', 'stage', 'stash', 'grep', 'pager', 'help')
PROMPT_KEY, GREP_KEY = '\ue000', '\ue001'
RESERVED = (PROMPT_KEY, GREP_KEY)
BUILTIN_COMMANDS = {
    ('main','C'): '?git cherry-pick %(commit)',
    ('stash','A'): '?git stash apply %(stash)',
    ('stash','P'): '?git stash pop %(stash)',
    ('stash','!'): '?git stash drop %(stash)',
    ('refs','C'): '?git checkout %(branch)',
    ('refs','!'): '?git branch -D %(branch)',
    ('reflog','C'): '?git checkout %(branch)',
    ('reflog','!'): '?git reset --hard %(commit)',
}
ACTIONS = set('none enter back next previous parent view-next refresh maximize view-close quit move-up move-down move-half-page-up move-half-page-down move-page-up move-page-down move-first-line move-last-line scroll-first-col scroll-left scroll-right scroll-line-up scroll-line-down scroll-page-up scroll-page-down scroll-half-page-up scroll-half-page-down search search-back find-next find-prev options screen-redraw stop-loading show-version status-update status-revert stage-update-line stage-update-part stage-split-chunk'.split()) | {'view-' + v for v in VIEWS if v != 'grep'}
ACTIONS.update(('view-close-no-quit','move-next-merge','move-prev-merge'))
OPTIONS = set('diff-options blame-options log-options main-options reference-format line-graphics truncation-delimiter horizontal-scroll git-colors show-notes show-changes show-untracked vertical-split split-view-height split-view-width status-show-untracked-dirs status-show-untracked-files tab-size diff-context word-diff diff-highlight diff-indicator diff-noprefix ignore-space commit-order ignore-case mailmap wrap-lines wrap-search focus-child send-child-enter editor-line-number history-size mouse mouse-scroll mouse-wheel-cursor pager-autoscroll recurse-tree pgrp start-on-head refresh-mode refresh-interval file-args rev-args id-width'.split())
OPTIONS.update(('file-filter','rev-filter'))
COLUMNS = set('author committer commit-title date file-name file-size id line-number mode ref status text'.split())
COL_OPTIONS = set('display width maxwidth graph refs overflow use-author local format color interval commit-title-overflow'.split())
SAFE_FLAGS = set('--all --branches --tags --remotes --first-parent --no-merges --merges --reverse --topo-order --date-order --author-date-order --walk-reflogs --no-walk --follow --full-history --simplify-merges --ancestry-path --boundary --cherry --cherry-pick --left-right --right-only --left-only --no-decorate --decorate --stat --numstat --shortstat --summary --raw --patch --no-patch --name-only --name-status --root --cc --combined-all-paths --minimal --patience --histogram --ignore-all-space --ignore-space-change --ignore-space-at-eol --ignore-blank-lines --word-diff --no-renames --find-copies-harder --no-notes --show-signature -w -b -M -C -m -s -p -t -l -f -e --line-porcelain --porcelain --show-name --show-number --show-email'.split())

def printable(text, name='text', limit=4096):
    if not isinstance(text, str) or len(text) > limit or any(ord(c) < 32 or ord(c) == 127 or c in RESERVED for c in text):
        raise ValueError(f'{name} must be printable text of at most {limit} characters')
    return text

def multiline(text,name='message',limit=8192):
    if not isinstance(text,str) or len(text)>limit or any((ord(c)<32 and c not in '\n\t') or ord(c)==127 for c in text):
        raise ValueError(f'{name} must be text of at most {limit} characters')
    return text

def path(text, empty=False):
    printable(text, 'path', 1024)
    if text.startswith('/workspace/'):
        text = text[len('/workspace/'):]
    if empty and text in ('', '.', '/workspace'):
        return ''
    text=text.rstrip('/')
    parts = text.split('/')
    if not text or '\\' in text or any(p in ('', '.', '..', '.git') or len(p.encode()) > 255 for p in parts) or text.startswith('-'):
        raise ValueError('path must name an entry inside /workspace, outside Git metadata')
    return text

def ref(text):
    printable(text, 'revision', 240)
    if not text or text.startswith(('-', '/')) or not re.fullmatch(r'[A-Za-z0-9_@{}^~.+/:-]+', text):
        raise ValueError('invalid repository revision')
    if text.startswith(':') or '\\' in text:
        raise ValueError('invalid repository revision')
    return text

def git_args(args, *, files=True):
    if not isinstance(args, list) or len(args) > 40:
        raise ValueError('arguments must be an array of at most 40 strings')
    after = False
    for a in args:
        printable(a, 'argument', 512)
        if after:
            path(a)
        elif a == '--':
            after = True
        elif a in SAFE_FLAGS:
            continue
        elif re.fullmatch(r'-(?:n|U|M|C)\d{1,4}|\+\d{1,6}', a):
            continue
        elif re.fullmatch(r'--(?:max-count|skip|unified|abbrev|inter-hunk-context)=\d{1,4}', a):
            continue
        elif re.fullmatch(r'--(?:author|committer|grep|since|until|after|before)=.{1,160}', a):
            continue
        elif re.fullmatch(r'--(?:diff-algorithm)=(?:myers|minimal|patience|histogram)', a):
            continue
        elif re.fullmatch(r'--(?:date)=(?:default|iso|iso-strict|short|raw|unix|rfc|relative|local)', a):
            continue
        elif re.fullmatch(r'--(?:pretty|format)=(?:oneline|short|medium|full|fuller|raw|reference)', a):
            continue
        elif a.startswith('-'):
            raise ValueError('unsupported Git option')
        else:
            ref(a)
    return args

def git_config(name,value):
    """Only native Tig configuration, validated like tigrc; never executable Git settings."""
    printable(name,'Git configuration name',160)
    printable(value,'Git configuration value',4096)
    if name in {'core.abbrev','core.ignorecase','core.filemode','i18n.commitencoding','gui.encoding'}:
        return
    if name.startswith('tig.color.'):
        config_command('color '+shlex.quote(name[len('tig.color.'):])+' '+value)
    elif name.startswith('tig.bind.'):
        config_command('bind '+name[len('tig.bind.'):]+' '+value)
    elif name.startswith('tig.'):
        config_command('set '+name[4:]+' = '+value)
    else:raise ValueError('unsupported Git configuration field')

def option_name(name):
    if name in OPTIONS:
        return
    if name in (v + '-view' for v in VIEWS):
        return
    for view in VIEWS:
        prefix = view + '-view-'
        if name.startswith(prefix):
            suffix = name[len(prefix):]
            for col in COLUMNS:
                if suffix == col or suffix.startswith(col + '-') and suffix[len(col) + 1:] in COL_OPTIONS:
                    return
    raise ValueError('unsupported option name')

def config_command(text):
    printable(text, 'configuration command')
    tokens = shlex.split(text, comments=True)
    if not tokens:
        return ''
    command = tokens[0]
    if command == 'set':
        if len(tokens) < 3 or tokens[2] not in ('=', '+='):
            raise ValueError('set requires option = value')
        name = tokens[1]
        option_name(name)
        values = tokens[3:]
        if name == 'diff-highlight' and values not in (['no'], ['false'], ['0'], ['']):
            raise ValueError('external filters are unavailable')
        if name == 'pgrp' and values not in (['no'], ['false'], ['0']):
            raise ValueError('process group changes are unavailable')
        if name.endswith('-options'):
            git_args(values)
        if name == 'file-args':
            for v in values: path(v)
        if name == 'rev-args':
            git_args(values)
        if any('%(prompt' in v for v in values):
            raise ValueError('nested prompts are unavailable')
    elif command == 'color':
        if not 4 <= len(tokens) <= 10:
            raise ValueError('color requires area foreground background and optional attributes')
    elif command == 'bind':
        if len(tokens) < 4 or tokens[1] not in (*VIEWS, 'generic', 'search'):
            raise ValueError('bind requires keymap key action')
        if tokens[2] in (':', 'g') or any(c in tokens[2] for c in RESERVED):
            raise ValueError('reserved binding')
        action = ' '.join(tokens[3:])
        normalized=action.lower().replace('_','-').replace('.','-')
        if normalized not in ACTIONS and action != BUILTIN_COMMANDS.get((tokens[1],tokens[2])):
            if not action.startswith(':'):
                raise ValueError('only internal product actions can be bound')
            safe_command(action[1:], binding=True)
    else:
        raise ValueError('configuration accepts set, color and internal bind commands')
    return text

def configuration(text):
    if not isinstance(text, str) or len(text.encode()) > 128000:
        raise ValueError('configuration must be at most 128000 bytes')
    lines = text.replace('\\\n', ' ').splitlines()
    for line in lines:config_command(line)
    # Validate logical lines, but let the product parse the original comments,
    # continuation syntax and quoting rather than rewriting them in the runtime.
    return text if text.endswith('\n') else text+'\n'

def safe_command(text, binding=False):
    printable(text, 'command')
    args = shlex.split(text)
    if not args:
        raise ValueError('empty command')
    cmd = args[0]
    if cmd in ('set','color') or cmd=='bind' and not binding:
        config_command(text)
    elif cmd == 'toggle':
        if not 2 <= len(args) <= 8:
            raise ValueError('toggle requires an option')
        name = args[1]
        if name in ('diff-highlight', 'pgrp'):
            raise ValueError('unsupported toggle')
        if name not in ('sort-order', 'sort-field', 'file-filter', 'rev-filter') and name not in COLUMNS:
            try: option_name(name)
            except ValueError:
                if not any(name == c + '-' + o for c in COLUMNS for o in COL_OPTIONS): raise
        if name.endswith('-options') or name == 'rev-args': git_args(args[2:])
        if name == 'file-args':
            for a in args[2:]: path(a)
    elif cmd in ('save-options', 'save-display') and not binding:
        if len(args) != 2 or not re.fullmatch(r'/outbox/[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\.(?:txt|tigrc)', args[1]):
            raise ValueError('export path must be /outbox/<basename>.txt or .tigrc')
    elif cmd == 'goto':
        if len(args) != 2: raise ValueError('goto requires one revision')
        ref(args[1])
    elif cmd == 'echo':
        if '%(prompt' in text: raise ValueError('nested prompts are unavailable')
    elif cmd.lower().replace('_','-').replace('.','-') in ACTIONS and len(args) == 1:
        pass
    elif len(args) == 1 and (cmd.isdecimal() or re.fullmatch(r'[0-9a-f]{7,40}', cmd)):
        pass
    elif text.startswith(('/', '?')) and '%(' not in text:
        pass
    else:
        raise ValueError('unsupported console command; use help')
    return text

LOCKDOWN = '\n'.join([
    'bind generic : none', 'bind generic g none', 'bind generic e none',
    'bind status M none', 'bind status C none',
    f'bind generic {PROMPT_KEY} prompt', f'bind generic {GREP_KEY} view-grep',
    'set diff-highlight = no', 'set pgrp = no',
]) + '\n'

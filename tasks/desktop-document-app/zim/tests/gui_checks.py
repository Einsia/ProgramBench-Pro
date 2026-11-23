'''Independent program checks of GUI checkpoints; never shown to the evaluator agent.

A check names public state that the goal produced: a page file of the notebook folder, the list of pages, the clipboard, the window
titles, the files of an export folder or a search run. Everything is read through the runtime channels (download, list_files,
clipboard_text, windows and cli); nothing reads the application.
'''
import time

import checks

KINDS = ('page', 'pages', 'absent', 'clipboard', 'titles', 'files', 'tree', 'search', 'config')


def observe(c, episode, checkpoint, check):
    kind = check['kind']
    c.prepare_root()
    wait = check.get('wait', 20)
    if kind == 'page':
        text = c.settled('notebook', check['path'], wait).decode('utf-8', 'replace')
        shown = checks.page_file(text, dates=check.get('dates', False))
        if check.get('tail'):
            shown['body'] = shown['body'][-int(check['tail']):]
        return {'page': shown}
    if kind == 'pages':
        return {'pages': checks.page_names(sorted(c.listing('notebook')))}
    if kind == 'absent':
        return {'exists': check['path'] in c.listing('notebook')}
    if kind == 'clipboard':
        return {'text': checks.scrub(c.clipboard(), c.root)}
    if kind == 'titles':
        titles = sorted(checks.scrub(title, c.root) for title in c.window_titles())
        if check.get('match'):
            # Only the named windows count, so that the route to them (and the page of other windows) is free.
            titles = [title for title in titles if title in check['match']]
        return {'titles': titles}
    if kind == 'files':
        folder = check['folder']
        deadline = time.monotonic() + wait
        while True:
            names = sorted(name[len(folder) + 1:] for name in c.listing('outbox', folder))
            if names or time.monotonic() >= deadline:
                return {'names': names}
            time.sleep(.5)
    if kind == 'tree':
        tree = checks.export_tree(c.tree('outbox', check['folder']), c.root)
        return {'files': {name: (value.replace('Zim 0.77.2', 'Zim <version>') if isinstance(value, str) else value) for name, value in tree.items()}}
    if kind == 'search':
        options = list(check.get('options', []))
        got = c.cli('search', *options, c.path('notebook'), check['query'])
        return checks.search(got, scores='-s' in options, ordered=check.get('ordered'), root=c.root)
    if kind == 'config':
        text = c.settled('notebook', 'notebook.zim', wait).decode('utf-8', 'replace')
        keys = tuple(check.get('keys', ('name',)))
        return {'settings': [line for line in checks.lines(text) if line.split('=', 1)[0] in keys]}
    raise AssertionError('unknown check kind ' + str(kind))

'''Projections of the observations that the program checks freeze: page files, search results, export trees and command line runs.

A projection keeps what a user can see of the behaviour and drops what is generated or free to choose: the order of
results without an explicit sort, line endings, trailing white space, log lines of the command line and the absolute location
of the exchange folders.
'''

NL = chr(10)
TAB = chr(9)
NOTES = ('WARNING', 'ERROR', 'CRITICAL')
LOG_PREFIXES = ('INFO: ', 'DEBUG: ')


def scrub(text, root=None):
    '''Text with line feeds as line endings and without the absolute location of the exchange folders.'''
    text = text.replace(chr(13) + NL, NL).replace(chr(13), '')
    return text.replace(str(root), '<files>') if root else text


def lines(text):
    return [line.rstrip() for line in text.split(NL)]


def page_file(text, dates=True):
    '''A page file as its header fields and its body lines (dates=False leaves the creation date out).'''
    head, _, body = text.partition(NL + NL)
    fields = {}
    for line in head.split(NL):
        key, _, value = line.partition(': ')
        if key and (dates or key != 'Creation-Date'):
            fields[key] = value
    return {'header': fields, 'body': lines(body.rstrip(NL))}


def page_name(path):
    '''Page name of a page file path relative to the notebook folder (None for other files).'''
    if not path.endswith('.txt'):
        return None
    return path[:-len('.txt')].replace('_', ' ').replace('/', ':')


def page_names(paths):
    return sorted(name for name in map(page_name, paths) if name)


def run(result, root=None):
    '''A command line run: its exit code and the printed lines without log lines.'''
    printed = [line for line in lines(scrub(result.get('output', ''), root)) if line and not line.startswith(LOG_PREFIXES)]
    return {'exit_code': result.get('exit_code'), 'output': printed}


def search(result, scores=False, ordered=None, root=None):
    '''Result lines of a search run. Results form a sorted set unless the run asked for an order: ordered is name
    (--sorted without scores) or score (-s --sorted, equal scores form a group whose members are sorted).'''
    rows = [line for line in lines(scrub(result.get('output', ''), root)) if line and not line.startswith(LOG_PREFIXES)]
    notes = [line for line in rows if line.startswith(NOTES)]
    rows = [line for line in rows if not line.startswith(NOTES)]
    if not scores:
        return {'exit_code': result.get('exit_code'), 'results': rows if ordered == 'name' else sorted(rows), 'notes': notes}
    pairs = []
    for line in rows:
        score, _, name = line.partition(TAB)
        pairs.append((int(score) if score.isdigit() else score, name))
    if ordered == 'score':
        groups = []
        for score, name in pairs:
            if groups and groups[-1][0] == score:
                groups[-1][1].append(name)
            else:
                groups.append([score, [name]])
        found = [[score, sorted(names)] for score, names in groups]
    else:
        found = sorted(([score, name] for score, name in pairs),
                       key=lambda pair: (not isinstance(pair[0], int), pair[0] if isinstance(pair[0], int) else 0, pair[1]))
    return {'exit_code': result.get('exit_code'), 'results': found, 'notes': notes}


def export_tree(tree, root=None):
    '''Every exported file by relative name: its text (scrubbed) for text files, its size for the others.'''
    return {name: (scrub(value, root) if isinstance(value, str) else value) for name, value in sorted(tree.items())}


def file_names(tree):
    return sorted(tree)

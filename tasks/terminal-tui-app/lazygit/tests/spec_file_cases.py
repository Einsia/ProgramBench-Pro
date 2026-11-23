'''File representation and path boundaries, ignore rules and persistence after terminal-driven commits.'''
import base64
from spec_base import *  # noqa: F401,F403

CASES = [
    ('empty', {'empty.txt': ''}),
    ('binary', {'image.bin': {'base64': base64.b64encode(bytes(range(256))).decode()}}),
    ('utf8-content', {'text.txt': text('résumé', '中文内容', 'end')}),
    ('utf8-name', {'café.txt': text('accented path')}),
    ('spaces', {'two words.txt': text('spaced path')}),
    ('apostrophe', {"reader's.txt": text('quoted path')}),
    ('double-quote', {'say"hello.txt': text('double quote')}),
    ('leading-dash', {'-option.txt': text('literal path')}),
    ('glob-literal', {'item[1]*.txt': text('literal glob characters')}),
    ('nested', {'outer/inner/data.txt': text('nested path')}),
    ('dotfile', {'.hidden': text('hidden file')}),
    ('executable', {'tool.sh': {'text': '#!/bin/sh\necho example\n', 'mode': '755'}}),
    ('symlink', {'link.txt': {'symlink': 'anchor.txt'}}),
    ('crlf', {'windows.txt': 'first\r\nsecond\r\n'}),
    ('no-newline', {'last.txt': 'no terminal newline'}),
    ('tabs', {'tabbed.txt': '\tfirst\n  second\tcolumn\n'}),
    ('long-line', {'long.txt': '0123456789' * 30 + '\n'}),
    ('mode-only', {'anchor.txt': {'text': 'anchor\n', 'mode': '755'}}),
]


def await_commit(subject):
    return {'await_git': {'argv': ['log', '-1', '--format=%s'], 'stdout': subject + '\n', 'seconds': 10}}


def build():
    W=[]
    for name,files in CASES:
        fixture=S(commit('base',{'anchor.txt':text('anchor')}),put(files))
        W.append(program('file-'+name,'file-formats',fixture,[
            step('stage','Stage the prepared file changes.',K('2','a'),
                 [('status','The file changes are staged.',repo('status')),
                  ('patch','The index preserves the exact file bytes, path and mode.',gitc('diff','--cached','--binary'))]),
            step('unstage','Unstage all changes without modifying the files.',K('a'),
                 [('status','All changes are back in the working tree.',repo('status'))],depends=['stage']),
            step('commit','Stage and commit the changes as `file case`.',
                 S(K('a','c'),prompt('file case'),await_commit('file case')),
                 [('log','The new commit follows base.',repo('log')),
                  ('patch','The committed patch retains the file representation.',gitc('show','--format=','--binary','HEAD'))],
                 depends=['unstage']),
            step('restart','Restart and retain the committed files.',[restart()],
                 [('tree','The worktree retains the file bytes, mode or link target.',tree(fields=['sha256','mode','target']))],
                 depends=['commit']),
        ]))
    for name,change in [
        ('deletion',S(git('rm','-q','anchor.txt'),git('reset','-q','--mixed','HEAD'))),
        ('rename',S(git('mv','anchor.txt','renamed.txt'),git('reset','-q','--mixed','HEAD'))),
    ]:
        W.append(program('file-'+name,'file-formats',S(commit('base',{'anchor.txt':text('anchor')}),change),[
            step('stage','Stage the '+name+' from the files panel.',K('2','a'),
                 [('patch','The index records the '+name+'.',gitc('diff','--cached','--binary'))]),
            step('commit','Commit the file operation as `file operation`.',
                 S(K('c'),prompt('file operation'),await_commit('file operation')),
                 [('log','The file operation is committed.',repo('log')),
                  ('tree','The commit records the expected paths and modes.',gitc('ls-tree','-r','HEAD'))],depends=['stage']),
        ]))
    ignore_cases=[
        ('suffix', '*.log\n', {'debug.log':'ignored','keep.txt':'kept'}),
        ('directory','cache/\n', {'cache/item.txt':'ignored','keep.txt':'kept'}),
        ('negated','*.txt\n!keep.txt\n', {'hidden.txt':'ignored','keep.txt':'kept'}),
        ('root-only','/root.txt\n', {'root.txt':'ignored','nested/root.txt':'kept'}),
        ('question','temp?.txt\n', {'temp1.txt':'ignored','temp12.txt':'kept'}),
    ]
    for name,rule,files in ignore_cases:
        W.append(program('ignore-rule-'+name,'files',S(commit('ignore rules',{'.gitignore':rule}),put(files)),[
            step('stage','Stage visible changes while respecting the ignore rules.',K('2','a'),
                 [('index','Only nonignored files enter the index.',gitc('diff','--cached','--name-status')),
                  ('ignored','The ignored paths stay outside the index.',gitc('status','--porcelain','--ignored'))]),
        ]))
    return W

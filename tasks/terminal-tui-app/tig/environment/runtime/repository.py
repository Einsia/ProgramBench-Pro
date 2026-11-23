"""Confined Git repository preparation and inspection."""
import base64
import hashlib
import os
from pathlib import Path
import re
import stat
import policy
import files as safe_files
import blackbox_runtime as runtime
from commands import run_bounded

LIMIT = 1024 * 1024
FIXED_TIME = '2024-06-01T12:00:00+0000'
GIT_ENV = {
    'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
    'GIT_CONFIG_COUNT': '8',
    'GIT_CONFIG_KEY_0': 'core.hooksPath', 'GIT_CONFIG_VALUE_0': '/dev/null',
    'GIT_CONFIG_KEY_1': 'core.fsmonitor', 'GIT_CONFIG_VALUE_1': 'false',
    'GIT_CONFIG_KEY_2': 'commit.gpgsign', 'GIT_CONFIG_VALUE_2': 'false',
    'GIT_CONFIG_KEY_3': 'tag.gpgsign', 'GIT_CONFIG_VALUE_3': 'false',
    'GIT_CONFIG_KEY_4': 'core.pager', 'GIT_CONFIG_VALUE_4': 'cat',
    'GIT_CONFIG_KEY_5': 'protocol.allow', 'GIT_CONFIG_VALUE_5': 'never',
    'GIT_CONFIG_KEY_6': 'core.quotepath', 'GIT_CONFIG_VALUE_6': 'false',
    'GIT_CONFIG_KEY_7': 'gc.auto', 'GIT_CONFIG_VALUE_7': '0',
    'GIT_AUTHOR_NAME': 'Alex Example', 'GIT_AUTHOR_EMAIL': 'alex@example.test',
    'GIT_COMMITTER_NAME': 'Alex Example', 'GIT_COMMITTER_EMAIL': 'alex@example.test',
    'GIT_AUTHOR_DATE': FIXED_TIME, 'GIT_COMMITTER_DATE': FIXED_TIME,
    'GIT_EDITOR': '/bin/false', 'GIT_SEQUENCE_EDITOR': '/bin/false',
    'GIT_TERMINAL_PROMPT': '0', 'GIT_NO_REPLACE_OBJECTS': '1',
}

def run(product, args, *, input=None, extra=None, check=True):
    kwargs = {}
    if product.switching():
        a = product.account()
        kwargs = dict(user=a.pw_uid, group=a.pw_gid, extra_groups=[])
    env = dict(product.environment(), **GIT_ENV)
    env.update(extra or {})
    env.pop('LD_PRELOAD', None)
    p = run_bounded(['/usr/bin/git', '--no-pager', *args], cwd=product.workspace, env=env,
                    input=input, stream_limit=4*LIMIT, total_limit=4*LIMIT, timeout=20, **kwargs)
    if check and p.returncode:
        raise ValueError('Git operation failed: ' + p.stderr.decode('utf-8', 'replace')[:500])
    return p

def content(spec):
    if isinstance(spec, str): data = spec.encode()
    elif isinstance(spec, dict) and 'base64' in spec: data = base64.b64decode(spec['base64'], validate=True)
    elif isinstance(spec, dict) and 'text' in spec: data = spec['text'].encode()
    else: raise ValueError('file needs text or base64 content')
    if len(data) > LIMIT: raise ValueError('file exceeds 1 MiB')
    return data

def validate_files(files):
    if not isinstance(files, dict) or len(files) > 512: raise ValueError('files must map at most 512 paths to data')
    total = 0
    for name, spec in files.items():
        policy.path(name)
        if spec is None: continue
        if isinstance(spec, dict):
            if set(spec) - {'text', 'base64', 'mode', 'symlink'}: raise ValueError('unknown file field')
            if 'symlink' in spec:
                target = policy.printable(spec['symlink'], 'symlink', 1024)
                if target.startswith('/') or '\\' in target: raise ValueError('symlink must be relative')
                resolved = list(Path(name).parent.parts)
                for p in target.split('/'):
                    if p == '..':
                        if not resolved: raise ValueError('symlink must stay in workspace')
                        resolved.pop()
                    elif p not in ('', '.'): resolved.append(p)
                if '.git' in resolved: raise ValueError('symlink must stay outside Git metadata')
                continue
            if spec.get('mode', 0o644) not in (0o644, 0o755): raise ValueError('file mode must be 420 or 493')
        total += len(content(spec))
    if total > 4 * LIMIT: raise ValueError('file batch exceeds 4 MiB')

def place(product, files):
    validate_files(files)
    account=product.account()
    with runtime.open_directory(product.workspace) as root:
        for name,spec in files.items():
            parts=policy.path(name).split('/')
            if spec is None:
                try:runtime.remove_entry(root,'/'.join(parts),missing_ok=True)
                except FileNotFoundError:pass
                continue
            with safe_files.directory(product,root,parts[:-1],create=spec is not None) as parent:
                leaf=parts[-1]
                try:info=os.stat(leaf,dir_fd=parent,follow_symlinks=False)
                except FileNotFoundError:info=None
                if info is not None and stat.S_ISLNK(info.st_mode):
                    runtime.unlink_entry(parent,leaf)
                if isinstance(spec,dict) and 'symlink' in spec:
                    runtime.unlink_entry(parent,leaf,missing_ok=True)
                    os.symlink(spec['symlink'],leaf,dir_fd=parent)
                    if product.switching():
                        os.chown(leaf,account.pw_uid,account.pw_gid,dir_fd=parent,follow_symlinks=False)
                else:
                    data=content(spec)
                    mode=spec.get('mode',0o644) if isinstance(spec,dict) else 0o644
                    runtime.atomic_write(parent,leaf,data,mode=0o600,uid=account.pw_uid,gid=account.pw_gid)
                    stamp=946684800+int(hashlib.sha256(data).hexdigest()[:8],16)%31536000
                    with runtime.open_relative(parent,leaf) as fd:
                        info=os.fstat(fd)
                        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1:
                            raise ValueError('file changed during placement')
                        runtime.set_metadata(fd,mode=mode,ns=(stamp*1_000_000_000,)*2,
                                             uid=account.pw_uid,gid=account.pw_gid)
        validate_links(root)


def validate_links(root):
    """Keep composed link targets inside the worktree and outside Git metadata."""
    top=os.path.realpath('/proc/self/fd/'+str(root))
    count=0
    def visit(fd):
        nonlocal count
        for name,info in runtime.list_directory(fd):
            if name=='.git':continue
            count+=1
            if count>10000:raise ValueError('tree exceeds 10000 entries')
            if stat.S_ISLNK(info.st_mode):
                real=os.path.realpath('/proc/self/fd/'+str(fd)+'/'+name)
                inside=real==top or real.startswith(top+'/')
                if not inside or '.git' in Path(real[len(top):]).parts:
                    runtime.unlink_entry(fd,name)
                    raise ValueError('symlink must stay inside the worktree, outside Git metadata')
            elif stat.S_ISDIR(info.st_mode):
                with runtime.open_relative(fd,name,directory=True) as child:visit(child)
    visit(root)


def prepare_repository(product, spec):
    if not isinstance(spec, dict) or set(spec) - {'commits','refs','head','worktree','index','stashes','config','tags','notes','checkout_history'}:
        raise ValueError('unknown repository field')
    commits = spec.get('commits', [])
    if not isinstance(commits, list) or len(commits) > 100: raise ValueError('at most 100 commits')
    for c in commits:
        if not isinstance(c, dict) or set(c) - {'id','message','files','parents','author','email','committer','committer_email','date','commit_date'}:
            raise ValueError('unknown commit field')
        policy.ref(c['id']); policy.multiline(c.get('message','Commit'), 'message')
        validate_files(c.get('files', {}))
    for k in ('index','worktree'): validate_files(spec.get(k, {}))
    root = product.workspace
    account=product.account()
    with runtime.open_directory(product.directories['DATA_DIR']) as data_fd:
        runtime.remove_entry(data_fd,'repository',missing_ok=True)
        with runtime.owned_directory(data_fd,'repository',uid=account.pw_uid,gid=account.pw_gid,mode=0o755):pass
    run(product, ['init','-b','main'])
    run(product, ['config','user.name','Alex Example'])
    run(product, ['config','user.email','alex@example.test'])
    ids = {}
    previous = None
    for i, c in enumerate(commits):
        parents = c.get('parents', [previous] if previous else [])
        if not isinstance(parents, list) or any(x not in ids for x in parents): raise ValueError('parents must name earlier commits')
        if parents: run(product, ['read-tree','--reset','-u',ids[parents[0]]])
        else:
            run(product, ['read-tree','--empty'])
            with runtime.open_directory(root) as root_fd:
                for name,_ in runtime.list_directory(root_fd):
                    if name!='.git':runtime.remove_entry(root_fd,name,missing_ok=True)
        place(product, c.get('files', {}))
        run(product, ['add','-A','--','.'])
        tree = run(product,['write-tree']).stdout.decode().strip()
        args = ['commit-tree',tree]
        for parent in parents: args += ['-p',ids[parent]]
        args += ['-m', c.get('message','Commit')]
        date = c.get('date', f'2024-01-{i % 28 + 1:02d}T12:00:00+0000')
        extra = {'GIT_AUTHOR_NAME':c.get('author','Alex Example'), 'GIT_AUTHOR_EMAIL':c.get('email','alex@example.test'),
                 'GIT_COMMITTER_NAME':c.get('committer','Jordan Example'), 'GIT_COMMITTER_EMAIL':c.get('committer_email','jordan@example.test'),
                 'GIT_AUTHOR_DATE':date, 'GIT_COMMITTER_DATE':c.get('commit_date', date)}
        for value in extra.values(): policy.printable(value, 'commit identity', 160)
        sha = run(product, args, extra=extra).stdout.decode().strip()
        ids[c['id']] = sha; previous = c['id']
    if not commits:
        run(product, ['commit','--allow-empty','-m','Start repository'])
        ids['root'] = run(product,['rev-parse','HEAD']).stdout.decode().strip()
        previous = 'root'
    refs = spec.get('refs', {'main':previous})
    if not isinstance(refs, dict) or len(refs) > 100: raise ValueError('at most 100 refs')
    for name, target in refs.items():
        policy.ref(name)
        if target not in ids: raise ValueError('ref must target a named commit')
        full = name if name.startswith('refs/') else 'refs/heads/' + name
        if not full.startswith(('refs/heads/','refs/tags/','refs/remotes/','refs/notes/')): raise ValueError('unsupported ref namespace')
        run(product,['update-ref',full,ids[target]])
    for name, tag in spec.get('tags',{}).items():
        policy.ref(name)
        if not isinstance(tag,dict) or set(tag)-{'target','message'} or tag['target'] not in ids:raise ValueError('invalid annotated tag')
        run(product,['tag','-a',name,ids[tag['target']],'-m',policy.multiline(tag.get('message',name),'tag message')])
    for name,message in spec.get('notes',{}).items():
        if name not in ids:raise ValueError('note must name a prepared commit')
        run(product,['notes','add','-m',policy.multiline(message,'note'),ids[name]])
    head = spec.get('head','main')
    policy.ref(head)
    for old in spec.get('checkout_history',[]):
        policy.ref(old)
        if old not in refs:raise ValueError('checkout history must name prepared branches')
        run(product,['checkout','-f',old])
    if head in ids and head not in refs:
        run(product,['checkout','--detach','-f',ids[head]])
    else: run(product,['checkout','-f',head])
    config = spec.get('config', {})
    if not isinstance(config,dict) or len(config)>128:raise ValueError('configuration must map at most 128 keys')
    for k,v in config.items():
        values=v if isinstance(v,list) else [v]
        if len(values)>32:raise ValueError('at most 32 values per configuration key')
        for item in values:
            value=policy.printable(str(item),'config value',4096)
            policy.git_config(k,value)
            run(product,['config','--add',k,value])
    for stash in spec.get('stashes', []):
        if set(stash) - {'files','message'}: raise ValueError('unknown stash field')
        place(product, stash['files']);run(product,['add','-A','--','.'])
        run(product,['stash','push','-m',policy.multiline(stash.get('message','Saved work'),'stash message')])
    place(product,spec.get('index',{}))
    if spec.get('index'): run(product,['add','-A','--','.'])
    place(product,spec.get('worktree',{}))
    return {'commits':ids, 'head':run(product,['rev-parse','HEAD']).stdout.decode().strip()}

def inspect(product, data):
    action = data['action']
    if action == 'status': args=['status','--porcelain=v1','-z','--untracked-files=all']
    elif action == 'index': args=['ls-files','--stage','-z']
    elif action == 'refs': args=['for-each-ref','--format=%(refname) %(objectname)']
    elif action == 'log': args=['log','--all','--format=%H%x00%P%x00%an%x00%ae%x00%s%x00']
    elif action == 'head':args=['show','--no-patch','--format=%H%x00%P%x00%T%x00%s%x00','HEAD']
    elif action == 'raw-log':
        revisions=data.get('revisions',['HEAD'])
        if not isinstance(revisions,list) or not 1<=len(revisions)<=100:raise ValueError('1–100 revisions required')
        for value in revisions:policy.ref(value)
        args=['log','--no-walk','--pretty=raw',*revisions]
    elif action == 'stash': args=['stash','list','--format=%gd%x00%gs']
    elif action == 'diff': args=['diff','--no-ext-diff','--no-textconv',*(['--cached'] if data.get('cached') else []),'--',policy.path(data['path'])] if data.get('path') else ['diff','--no-ext-diff','--no-textconv',*(['--cached'] if data.get('cached') else [])]
    elif action == 'blob':
        name=policy.path(data['path']);revision=data.get('revision','HEAD')
        if revision != ':': policy.ref(revision)
        args=['show', (':' if revision==':' else revision+':')+name]
    elif action in ('tree','read','stat'):
        name=policy.path(data.get('path',''), empty=action=='tree')
        if action=='read':
            raw=safe_files.read(product.workspace,name,LIMIT)
            return {'text':raw.decode('utf-8','replace'),'body_base64':base64.b64encode(raw).decode()}
        return safe_files.inspect(product.workspace,name,tree=action=='tree')
    else: raise ValueError('unknown inspector action')
    p=run(product,args,check=False)
    return {'exit_code':p.returncode,'stdout':p.stdout.decode('utf-8','replace'),'stderr':p.stderr.decode('utf-8','replace'),
            'body_base64':base64.b64encode(p.stdout).decode() if action=='blob' else None}

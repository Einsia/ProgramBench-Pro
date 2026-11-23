#!/usr/bin/env python3
"""Terminal runtime for the reference application and local development."""
from __future__ import annotations
import base64
import http.server
import json
import os
import stat
from pathlib import Path
import shlex
import socketserver
import sys
import threading
import time

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import blackbox_runtime as runtime
import terminal
import policy
import repository
import files as safe_files
from commands import run_bounded

MAX_REQUEST=6*1024*1024

class Product(terminal.TerminalProduct):
    def __init__(self,config,**kw):
        super().__init__(config,**kw)
        self.argv=[]
        self.config_text=''
        self.pager=None

    @property
    def outbox(self):return Path(self.directories['DATA_DIR'])/'outbox'

    def environment(self):
        env=super().environment()
        env.update(repository.GIT_ENV)
        env.update(TIGRC_SYSTEM='',TIGRC_USER=str(Path(self.directories['HOME'])/'.tigrc'),
                   TIG_EDITOR='/bin/false',INPUTRC='/dev/null',TIG_ARGS=json.dumps(self.argv),
                   TIG_PAGER_FILE=str(Path(self.directories['DATA_DIR'])/'pager.txt') if self.pager is not None else '',
                   TEST_TIME_NOW='1717243200')
        return env

    def prepare(self,fresh):
        super().prepare(fresh)
        if fresh:self.argv=[];self.config_text='';self.pager=None
        account=self.account()
        with runtime.open_directory(self.directories['DATA_DIR']) as data_fd:
            try:exists=stat.S_ISDIR(os.stat('repository',dir_fd=data_fd,follow_symlinks=False).st_mode)
            except FileNotFoundError:exists=False
            if not exists:repository.prepare_repository(self,{})
            with runtime.owned_directory(data_fd,'outbox',uid=account.pw_uid,gid=account.pw_gid,mode=0o700):pass
            if self.pager is not None:
                runtime.atomic_write(data_fd,'pager.txt',self.pager,uid=account.pw_uid,gid=account.pw_gid,mode=0o600)
        with runtime.open_directory(self.directories['HOME']) as home_fd:
            try:
                if stat.S_ISLNK(os.stat('.inputrc',dir_fd=home_fd,follow_symlinks=False).st_mode):
                    runtime.unlink_entry(home_fd,'.inputrc')
            except FileNotFoundError:pass
            runtime.atomic_write(home_fd,'.tigrc',self.config_text+'\n'+policy.LOCKDOWN,
                                 uid=account.pw_uid,gid=account.pw_gid,mode=0o600)

def field(type,description,**kw):
    if type=='array':kw.setdefault('items',{'type':'string'})
    return dict(type=type,description=description,**kw)
def op(kind,summary,**fields):return dict(kind=kind,summary=summary,fields=fields)
OPERATIONS=runtime.check_operations({
    'help':op('info','Machine-readable operations, limits and product controls.'),
    'status':op('lifecycle','Report whether the application is running and ready.'),
    'reset':op('lifecycle','Start with a fresh data directory and an initial local Git repository.'),
    'restart':op('lifecycle','Restart with the same repository, user configuration and arguments.'),
    'screen':op('observe','Settled terminal rows, cursor and styled text spans.'),
    'key':op('gui','Press one terminal key.',key=field('string',terminal.KEY_HELP,required=True)),
    'keys':op('gui','Press up to 128 terminal keys in sequence.',keys=field('array','Array of named keys or printable characters.',required=True)),
    'type':op('gui','Type printable text, for example a search expression.',text=field('string','1–4096 printable characters.',required=True)),
    'wait':op('gui','Wait for terminal output.',seconds=field('number','0–3 seconds, default 0.5.')),
    'resize':op('gui','Resize the terminal.',columns=field('integer','40–240 columns.',required=True),rows=field('integer','10–80 rows.',required=True)),
    'mouse':op('gui','Send a terminal mouse click or wheel event. Native mouse support must be enabled in the application.',column=field('integer','Zero-based terminal column.',required=True),row=field('integer','Zero-based terminal row.',required=True),button=field('string','Mouse button or wheel direction.',enum=['left','middle','right','wheel-up','wheel-down'],required=True)),
    'console':op('gui','Execute one native Tig prompt command. Supported: set, toggle, color, internal bind, goto, echo, internal actions, line numbers, searches, save-options and save-display.',command=field('string','Native command without leading colon. Export paths must be /outbox/<basename>.txt or .tigrc.',required=True)),
    'grep':op('gui','Open the native repository grep view with a literal pattern and supported options.',pattern=field('string','Search pattern up to 256 printable characters.',required=True),flags=field('array','Optional -i, -w, -F, -E, -v, --cached; default [].'),paths=field('array','Optional workspace-relative file paths.')),
    'open':op('lifecycle','Restart with native Tig command-line arguments or pager input.',args=field('array','Optional Tig subcommand and supported Git revision/filter options; default [].'),stdin=field('string','Optional pager/raw-log text, up to 1 MiB. With --stdin: 1–100 full hexadecimal commit IDs, optionally prefixed with ^. Omitted for repository mode.')),
    'configure':op('files','Replace the user tigrc with validated native set/color/internal-bind commands and restart. Runtime safety bindings are always applied last.',text=field('string','Native tigrc text, at most 128000 bytes. Empty text restores defaults.',required=True)),
    'repository':op('files','Replace the repository with Git repository data, then restart. Existing repository contents are replaced.',spec=field('object','commits [{id,message,files,parents,author,email,committer,committer_email,date,commit_date}], refs {name:commit_id}, head, index/worktree {path:text|{text|base64,mode}|{symlink:relative_target}|null}, stashes [{files,message}], tags {name:{target:commit_id,message}}, notes {commit_id:message}, checkout_history [branch names], config {key:value or [values]} supports core.abbrev/core.ignorecase/core.filemode/i18n.commitencoding/gui.encoding, safe tig.<option>, tig.color.<area>, tig.bind.<keymap>. Tig values use the same validator as configure; external actions remain unavailable. Omitted parents use the previous commit. Null deletes a file. Default head/main; dates default to January 2024.',required=True)),
    'place':op('files','Write workspace input files without changing the index. By default stop and restart; restart=false leaves the application running so it can observe an external edit on refresh.',files=field('object','Workspace-relative paths mapped to the same file specifications as repository.',required=True),restart=field('boolean','Whether to restart after placement; default true.')),
    'inspect':op('files','Read public Git status/index/refs/log/head/raw-log/stash/diff/blob or workspace tree/read/stat. No implementation or arbitrary filesystem access.',action=field('string','Inspection action.',enum=['status','index','refs','log','head','raw-log','stash','diff','blob','tree','read','stat'],required=True),path=field('string','Workspace-relative path, required for blob/read/stat.'),revision=field('string','For blob: revision, or : for staged content. Default HEAD.'),cached=field('boolean','For diff: inspect staged changes. Default false.'),revisions=field('array','For raw-log: 1–100 safe revisions; default [HEAD].')),
    'download':op('files','Read a native product export from /outbox.',name=field('string','Export basename ending .txt or .tigrc.',required=True)),
    'state':op('files','Read the user tigrc or the native readline history file.',file=field('string','Native state file.',enum=['config','history'],required=True)),
    'cli':op('info','Run start.sh once with a native help/version option and return its output.',option=field('string','Native one-shot option.',enum=['--version','-v','--help','-h'],required=True)),
})
NOTES=[
    'The application starts in DATA_DIR/repository, a real Git repository initialized by this runtime. Initial repository: branch main with one empty commit, Start repository. Git and Python curses are available to your application.',
    'A 120×36 xterm-256color PTY is used. screen and GUI actions wait at least 0.4 seconds and for 0.3 seconds of quiet, at most 4 seconds. The screen lists NN|text rows and styles; NN is a row index added by the runtime.',
    'start.sh receives TIG_ARGS as a JSON array of native arguments. TIG_PAGER_FILE is empty in repository mode or names the input file to feed to standard input in pager mode. HOME/.tigrc is prepared by configure; private HOME, TMPDIR and DATA_DIR persist across restart.',
    'Terminal transport for console: Escape, U+E000, Control+U, the validated native command, Enter. grep uses U+E001 instead of U+E000. The reference maps those two characters through its normal key-binding configuration. Implementations receive the same terminal input. /outbox export names are mapped to DATA_DIR/outbox before being sent.',
    'Use console for native prompt commands and grep for the grep prompt. Raw prompt/editor/mergetool entry and arbitrary commands, scripts and external filters are unavailable. Only confined repository inputs and /outbox exports are accepted. This applies to custom bindings too.',
    'Programmatic preparation and inspection operations are available to exploration and evaluation alike. repository and place only prepare data; scoring actions operate the application.',
    'Raw terminal entry cannot send the private-use characters reserved for validated prompt transport. Requests with unknown fields are rejected, including repository fields. File channels never follow symbolic links.',
    'Git input timestamps and product wall time are fixed to 2024-06-01 12:00 UTC for reproducible dates. Monotonic time is not frozen.',
]

class Runtime:
    def __init__(self,config):
        self.config=config;self.lock=threading.RLock()
        self.log=runtime.BoundedLog(config.log_dir)
        self.audit=runtime.Audit(Path(config.log_dir)/'rpc-audit.jsonl')
        self.product=Product(config,log=self.log)
        p=self.product
        self.paths=sorted([(str(p.workspace),'/workspace'),(str(p.outbox),'/outbox'),
                           (str(p.directories['HOME']),'~'),(str(config.state),'[data]'),
                           (str(config.solution),'[private]'),(str(config.work),'[private]'),
                           (str(config.log_dir),'[private]'),('/opt/blackbox','[private]')],key=lambda p:len(p[0]),reverse=True)

    def clean(self,v):
        if isinstance(v,str):
            for old,new in self.paths:v=v.replace(old,new)
            return v
        if isinstance(v,list):return [self.clean(x) for x in v]
        if isinstance(v,dict):return {k:self.clean(x) for k,x in v.items()}
        return v

    def launch(self,fresh=False):
        if self.product.start(fresh=fresh):terminal.wait_ready(self.product)
        return self.clean(self.product.status())

    def settle(self):
        start=time.monotonic()
        while self.product.terminal and time.monotonic()-start<4:
            if time.monotonic()-self.product.terminal.last_output>=.3 and time.monotonic()-start>=.4:break
            time.sleep(.02)

    def observe(self):
        self.settle()
        p=self.product
        return p.terminal.observe(p.process(),lambda text:self.clean(text)) if p.terminal else terminal.blank_observation(p.process())

    def send(self,text):
        self.product.write(text);return self.observe()

    def command(self,text):
        policy.safe_command(text)
        args=shlex.split(text)
        if args[0] in ('save-options','save-display'):
            name=args[1].split('/')[-1]
            target=self.product.outbox/name
            if target.is_symlink():raise ValueError('export target must not be a symlink')
            text=args[0]+' '+shlex.quote(str(target))
        # Escape cancels an incremental search or menu; clear the readline input before entering the command.
        self.send('\x1b');self.send(policy.PROMPT_KEY)
        return self.send('\x15'+text+'\r')

    def dispatch(self,d):
        operation=runtime.validate(OPERATIONS,d)
        with self.lock:
            p=self.product
            if operation=='help':
                return runtime.help_document('tig','terminal',OPERATIONS,limits={'screen':[120,36],'request_bytes':MAX_REQUEST,'key_batch':128,'read_bytes':repository.LIMIT},notes=NOTES,
                    reference_controls={'views':'m main; d diff; l log; L reflog; t tree; f blob; b blame; r refs; y stash; h help; s status; c stage; p pager. Use grep operation for repository search.',
                    'navigation':'j/k move; arrows move parent selection in split view; Home/End first/last; Space/PageDown/PageUp; Tab focus; Enter open; q back/close; O maximize; R refresh; , parent; < back; / and ? search; n/N next/previous; o options.',
                    'changes':'status u stage/unstage; ! revert with confirmation; stage u hunk, 1 line, 2 part, backslash split hunk, @ next hunk, [/] context; refs C checkout, ! delete branch; stash A apply/P pop/! drop; main C cherry-pick.',
                    'display':'# line numbers; D date; A author; T committer; G main graph; F refs/filenames; X ids; W whitespace; ~ graph style; % file filter; ^ revision filter; $ title overflow; v version.',
                    'console':'Native set/toggle/color/bind/goto/echo, internal action names, line numbers and searches. echo supports documented browsing variables: %(commit), %(head), %(blob), %(branch), %(tag), %(refname), %(stash), %(directory), %(file), %(lineno), %(text), %(repo:head), %(repo:head-id). Export options or display to /outbox/name.tigrc or /outbox/name.txt.'},
                    examples=[{'op':'screen'},{'op':'key','key':'s'},{'op':'console','command':'toggle line-number'},{'op':'console','command':'save-options /outbox/settings.tigrc'},{'op':'inspect','action':'status'}])
            if operation=='status':return self.clean(p.status())
            if operation=='reset':return self.launch(True)
            if operation=='restart':return self.launch()
            if operation=='screen':return self.observe()
            if operation in ('key','keys'):
                keys=[d['key']] if operation=='key' else d['keys']
                if not isinstance(keys,list) or not 1<=len(keys)<=128:raise ValueError('1–128 keys required')
                raw=''
                for k in keys:
                    policy.printable(k,'key',32)
                    raw+=terminal.key_bytes(k,p.terminal and p.terminal.application_cursor())
                return self.send(raw)
            if operation=='type':
                text=policy.printable(d['text'])
                if not text:raise ValueError('empty text')
                return self.send(text)
            if operation=='wait':
                seconds=d.get('seconds',.5)
                if not 0<=seconds<=3:raise ValueError('wait requires 0–3 seconds')
                time.sleep(seconds);return self.observe()
            if operation=='resize':
                if not 40<=d['columns']<=240 or not 10<=d['rows']<=80:raise ValueError('unsupported terminal size')
                p.resize(d['columns'],d['rows']);return self.observe()
            if operation=='mouse':
                x,y=d['column'],d['row']
                if p.terminal is None or not 0<=x<p.terminal.columns or not 0<=y<p.terminal.rows:raise ValueError('mouse position is outside the terminal')
                b={'left':0,'middle':1,'right':2,'wheel-up':64,'wheel-down':65}[d['button']]
                text=f'\x1b[<{b};{x+1};{y+1}M'
                result=self.send(text)
                if b<64:result=self.send(f'\x1b[<{b};{x+1};{y+1}m')
                return result
            if operation=='console':return self.command(d['command'])
            if operation=='grep':
                pattern=policy.printable(d['pattern'],'pattern',256)
                flags=d.get('flags',[]);paths=d.get('paths',[])
                if not isinstance(flags,list) or len(flags)>8 or any(x not in ('-i','-w','-F','-E','-v','--cached') for x in flags):raise ValueError('unsupported grep option')
                if not isinstance(paths,list) or len(paths)>32:raise ValueError('at most 32 paths')
                args=[*flags,'-e',pattern,'--',*[policy.path(x) for x in paths]]
                self.send('\x1b');self.send(policy.GREP_KEY)
                return self.send('\x15'+shlex.join(args)+'\r')
            if operation=='open':
                args=d.get('args',[])
                if not isinstance(args,list):raise ValueError('args must be an array')
                if args and args[0]=='-C':raise ValueError('working directory is fixed to the repository')
                policy.git_args([x for x in (args[1:] if args and args[0] in ('status','blame','grep','show','log','reflog','stash','refs') else args) if x!='--stdin'])
                if args and args[0]=='grep':raise ValueError('use the grep operation')
                text=d.get('stdin')
                if text is not None and (not isinstance(text,str) or len(text.encode())>repository.LIMIT):raise ValueError('pager input exceeds 1 MiB')
                if '--stdin' in args:
                    if text is None:raise ValueError('--stdin requires commit-list text')
                    lines=text.splitlines()
                    if not 1<=len(lines)<=100 or any(not __import__('re').fullmatch(r'\^?[0-9a-fA-F]{40}',line) for line in lines):
                        raise ValueError('commit-list input requires 1–100 full hexadecimal commit IDs, optionally prefixed with ^')
                p.argv=args;p.pager=text;return self.launch()
            if operation=='configure':
                p.config_text=policy.configuration(d['text']);return self.launch()
            if operation in ('repository','place'):
                if operation=='place' and not d.get('restart',True):
                    repository.place(p,d['files'])
                    return {'status':self.clean(p.status()),'repository':None}
                p.stop()
                try:
                    result=repository.prepare_repository(p,d['spec']) if operation=='repository' else repository.place(p,d['files'])
                finally:status=self.launch()
                return {'status':status,'repository':result}
            if operation=='inspect':return self.clean(repository.inspect(p,d))
            if operation in ('download','state'):
                if operation=='download':
                    name=d['name']
                    if not isinstance(name,str) or not __import__('re').fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\.(?:txt|tigrc)',name):raise ValueError('invalid export basename')
                    target=p.outbox/name
                else:target=Path(p.directories['HOME'])/('.tigrc' if d['file']=='config' else '.tig_history')
                try:raw=safe_files.read(target.parent,target.name,repository.LIMIT)
                except FileNotFoundError:return {'exists':False,'text':''}
                text=self.clean(raw.decode('utf-8','replace'))
                return {'exists':True,'text':text,'body_base64':base64.b64encode(text.encode()).decode()}
            if operation=='cli':
                kwargs={}
                if p.switching():
                    a=p.account();kwargs=dict(user=a.pw_uid,group=a.pw_gid,extra_groups=[])
                env=p.environment();env['TIG_ARGS']=json.dumps([d['option']]);env['TIG_PAGER_FILE']=''
                done=run_bounded([str(p.solution/'start.sh')],cwd=p.workspace,env=env,
                                 stream_limit=repository.LIMIT,merge_stderr=True,timeout=20,**kwargs)
                return self.clean({'exit_code':done.returncode,'stdout':done.stdout.decode('utf-8','replace')[:repository.LIMIT]})
            raise ValueError('unknown operation')

class Server(socketserver.ThreadingMixIn,socketserver.UnixStreamServer):daemon_threads=True
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self,*_):pass
    def do_POST(self):
        rt=self.server.runtime;op='invalid';start=time.monotonic();status=200
        try:
            if self.path!='/rpc':raise ValueError('POST JSON to /rpc')
            n=int(self.headers.get('Content-Length','0'))
            if self.headers.get('Transfer-Encoding') or not 0<n<=MAX_REQUEST:raise ValueError('request size limit exceeded')
            self.connection.settimeout(90)
            d=runtime.strict_json_loads(self.rfile.read(n));op=d.get('op') if isinstance(d,dict) else 'invalid'
            result=rt.dispatch(d)
        except Exception as exc:
            status=400;result={'error':type(exc).__name__,'detail':rt.clean(str(exc))[:600]}
        body=json.dumps(result,ensure_ascii=False).encode()
        self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers()
        try:self.wfile.write(body)
        finally:rt.audit.record(str(op)[:40],status,time.monotonic()-start)

def main():
    config=runtime.options(socket_mode='0600',ready_timeout=30).parse_args()
    rt=Runtime(config);runtime.exit_on_sigterm()
    try:
        rt.launch(True)
        sock=runtime.listen(config.socket,config.socket_mode)
        server=Server(config.socket,Handler,bind_and_activate=False)
        server.socket.close();server.socket=sock;server.runtime=rt
        try:server.serve_forever(.25)
        finally:server.server_close()
    finally:
        rt.product.stop()
        try:os.unlink(config.socket)
        except OSError:pass

if __name__=='__main__':main()

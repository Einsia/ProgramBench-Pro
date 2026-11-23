"""Program-check vocabulary and public access to one candidate through the black-box runtime.

One request with all its assertions is one CASE. Every request reaches the candidate through the runtime's api
operation, the channel the model also has on the reference: the JSON-RPC 2.0 API at /jsonrpc.php, the RSS and
iCalendar feeds, the cron job URL and the health check. Nothing here reads candidate files, databases or processes.

Observations are normalized before they are compared (Normalize, AliasGraph): generated identities become typed
aliases whose relationships must stay consistent across the episode (a bijection), generated timestamps become the
day they fall on relative to the application clock's first day, and opaque generated strings (tokens, file paths,
fingerprints) become aliases as well. Records may carry fields the reference does not have; every reference field
must be present and equal. Maps (objects keyed by data) and lists keep their exact members; lists keep the order
the product defines unless a case declares them unordered.
"""
from __future__ import annotations

import base64
import calendar
from collections import Counter
import dataclasses
import json
import re
import time

from evaluation.broker import BrokerError

ADMIN = 'admin'
APP_USER = 'jsonrpc'
# The initial state's fixed secrets (published in the runtime help and the instruction).
APP_TOKEN = '9c5f44bb170a8f12f4c83369f3e0e68ca40fe1d3fec515cbfe067076cfff'
WEBHOOK_TOKEN = 'e697933b51bbe13cb78af51a5d83e81060f4d8a8bd1ebbf6f150ebecd78c'
# Midnight UTC of the application clock's first day (the clock starts at 08:00 that day, when the runtime starts).
DAY0 = calendar.timegm((2026, 4, 14, 0, 0, 0))
CLOCK_WINDOW = 400 * 86400

# Fields whose numeric value is the identity of another record.
ID_FIELDS = {
    'project_id': 'project', 'dest_project_id': 'project', 'src_project_id': 'project',
    'task_id': 'task', 'opposite_task_id': 'task', 'recurrence_parent': 'task', 'recurrence_child': 'task',
    'column_id': 'column', 'src_column_id': 'column', 'dst_column_id': 'column', 'dest_column_id': 'column',
    'swimlane_id': 'swimlane', 'src_swimlane_id': 'swimlane', 'dst_swimlane_id': 'swimlane',
    'dest_swimlane_id': 'swimlane',
    'owner_id': 'user', 'creator_id': 'user', 'user_id': 'user', 'assignee_id': 'user', 'task_assignee_id': 'user',
    'category_id': 'category', 'link_id': 'link', 'opposite_id': 'link', 'group_id': 'group',
    'comment_id': 'comment', 'subtask_id': 'subtask', 'file_id': 'file', 'action_id': 'action', 'tag_id': 'tag',
    'task_link_id': 'task-link', 'opposite_link_id': 'link',
}
# Timestamps the product draws from its clock; they are compared by the day they fall on.
GENERATED_TIME = {'date_creation', 'date_modification', 'date_moved', 'date_completed', 'last_modified', 'date',
                  'last_login', 'timer_start_date', 'lock_expiration_date', 'date_last_activity', 'start', 'end'}
# Business dates and times. A date given without a time of day takes the time of day of the application clock when
# the request is handled, so these are compared as moments: equal within MOMENT_TOLERANCE seconds (the clock starts at
# the same instant for every episode, and an episode runs far shorter than that), never by the day alone.
MOMENTS = {'date_due', 'date_started'}
MOMENT_TOLERANCE = 1800
# Generated opaque strings: compared as typed aliases (presence, identity, consistency), never by value.
OPAQUE = {'etag', 'credentials_fingerprint', 'api_access_token', 'twofactor_secret', 'avatar_path', 'token',
          'webhook_token', 'api_token'}
# Nested records whose own id belongs to another table.
NESTED = {'columns': 'column', 'tasks': 'task', 'task': 'task', 'comment': 'comment', 'subtask': 'subtask',
          'project': 'project', 'file': 'task-file', 'swimlanes': 'swimlane', 'swimlane': 'swimlane',
          'column': 'column', 'user': 'user', 'users': 'user', 'category': 'category', 'subtasks': 'subtask'}
# Objects keyed by data: their members must be exactly the reference's.
MAP_FIELDS = {'params', 'changes', 'url'}
TOKEN_URLS = re.compile(r'(/(?:public/board|feed/project|ical/project|feed/user|ical/user|public/task/\d+)/)([0-9a-f]{16,})')
URL_IDS = [(re.compile(r'(/task/)(\d+)'), 'task'), (re.compile(r'(/board/)(\d+)'), 'project'),
           (re.compile(r'(/list/)(\d+)'), 'project'), (re.compile(r'(/project/)(\d+)'), 'project'),
           (re.compile(r'([?&]task_id=)(\d+)'), 'task'), (re.compile(r'([?&]project_id=)(\d+)'), 'project')]
FILE_PATH = re.compile(r'(tasks|projects)/(\d+)/([0-9a-f]{40})')
# Records that the store creates inside another record (method: kind, owner kind, owner parameter name and position),
# and the procedures that remove a record (method: kind, parameter name and position). A removal forgets the removed
# records and everything removed with them: a store may give their freed ids to new records, which are other records.
CREATIONS = {
    'createTask': ('task', 'project', 'project_id', 1), 'duplicateTaskToProject': ('task', 'project', 'project_id', 1),
    'createSubtask': ('subtask', 'task', 'task_id', 0), 'createComment': ('comment', 'task', 'task_id', 0),
    'createTaskFile': ('task-file', 'task', 'task_id', 1), 'createProjectFile': ('project-file', 'project', 'project_id', 0),
    'addColumn': ('column', 'project', 'project_id', 0), 'addSwimlane': ('swimlane', 'project', 'project_id', 0),
    'createCategory': ('category', 'project', 'project_id', 0), 'createTag': ('tag', 'project', 'project_id', 0),
    'createAction': ('action', 'project', 'project_id', 0), 'createTaskLink': ('task-link', 'task', 'task_id', 0),
    'createExternalTaskLink': ('external-link', 'task', 'task_id', 0),
}
REMOVALS = {
    'removeTask': ('task', 'task_id', 0), 'removeProject': ('project', 'project_id', 0),
    'removeColumn': ('column', 'column_id', 0), 'removeSwimlane': ('swimlane', 'swimlane_id', 1),
    'removeCategory': ('category', 'category_id', 0), 'removeUser': ('user', 'user_id', 0),
    'removeGroup': ('group', 'group_id', 0), 'removeComment': ('comment', 'comment_id', 0),
    'removeSubtask': ('subtask', 'subtask_id', 0), 'removeTaskLink': ('task-link', 'task_link_id', 0),
    'removeExternalTaskLink': ('external-link', 'link_id', 1), 'removeTaskFile': ('task-file', 'file_id', 0),
    'removeProjectFile': ('project-file', 'file_id', 1), 'removeLink': ('link', 'link_id', 0),
    'removeTag': ('tag', 'tag_id', 0), 'removeAction': ('action', 'action_id', 0),
}


# How each procedure's result is observed: the record type of the result (or of its items), and whether it is an
# object keyed by identities of a type (keys) or by data (mapping). Unlisted procedures return plain values.
RESULTS = {
    'getDefaultTaskColors': {'mapping': True}, 'getColorList': {'mapping': True},
    'getApplicationRoles': {'mapping': True}, 'getProjectRoles': {'mapping': True},
    'getAvailableActions': {'mapping': True}, 'getAvailableActionEvents': {'mapping': True},
    'getCompatibleActionEvents': {'mapping': True}, 'getActions': {'kind': 'action'}, 'createAction': {'kind': 'action'},
    'getBoard': {'kind': 'swimlane'},
    'getCategory': {'kind': 'category'}, 'getAllCategories': {'kind': 'category'}, 'createCategory': {'kind': 'category'},
    'getColumns': {'kind': 'column'}, 'getColumn': {'kind': 'column'}, 'addColumn': {'kind': 'column'},
    'getComment': {'kind': 'comment'}, 'getAllComments': {'kind': 'comment'}, 'createComment': {'kind': 'comment'},
    'getMemberGroups': {'kind': 'group'}, 'getGroupMembers': {'kind': 'user'}, 'createGroup': {'kind': 'group'},
    'getGroup': {'kind': 'group'}, 'getAllGroups': {'kind': 'group'},
    'getLinkById': {'kind': 'link'}, 'getLinkByLabel': {'kind': 'link'}, 'getOppositeLinkId': {'kind': 'link'},
    'getAllLinks': {'kind': 'link'}, 'createLink': {'kind': 'link'},
    'getMe': {'kind': 'user'}, 'getMyDashboard': {'kind': 'task'}, 'getMyActivityStream': {'kind': 'event'},
    'createMyPrivateProject': {'kind': 'project'}, 'getMyProjectsList': {'keys': 'project'},
    'getMyOverdueTasks': {'kind': 'task'}, 'getMyProjects': {'kind': 'project'},
    'getProjectFile': {'kind': 'project-file'}, 'getAllProjectFiles': {'kind': 'project-file'},
    'createProjectFile': {'kind': 'project-file'},
    'getProjectMetadata': {'mapping': True}, 'getTaskMetadata': {'mapping': True},
    'getProjectUsers': {'keys': 'user'}, 'getAssignableUsers': {'keys': 'user'},
    'getProjectById': {'kind': 'project'}, 'getProjectByName': {'kind': 'project'},
    'getProjectByIdentifier': {'kind': 'project'}, 'getProjectByEmail': {'kind': 'project'},
    'getAllProjects': {'kind': 'project'}, 'createProject': {'kind': 'project'},
    'getProjectActivities': {'kind': 'event'}, 'getProjectActivity': {'kind': 'event'},
    'getSubtask': {'kind': 'subtask'}, 'getAllSubtasks': {'kind': 'subtask'}, 'createSubtask': {'kind': 'subtask'},
    'getActiveSwimlanes': {'kind': 'swimlane'}, 'getAllSwimlanes': {'kind': 'swimlane'},
    'getSwimlaneById': {'kind': 'swimlane'}, 'getSwimlaneByName': {'kind': 'swimlane'},
    'getSwimlane': {'kind': 'swimlane'}, 'addSwimlane': {'kind': 'swimlane'},
    'getAllTags': {'kind': 'tag'}, 'getTagsByProject': {'kind': 'tag'}, 'createTag': {'kind': 'tag'},
    'getTaskTags': {'keys': 'tag'},
    'getExternalTaskLinkTypes': {'mapping': True}, 'getExternalTaskLinkProviderDependencies': {'mapping': True},
    'getExternalTaskLinkById': {'kind': 'external-link'}, 'getAllExternalTaskLinks': {'kind': 'external-link'},
    'createExternalTaskLink': {'kind': 'external-link'},
    'getTaskFile': {'kind': 'task-file'}, 'getAllTaskFiles': {'kind': 'task-file'}, 'createTaskFile': {'kind': 'task-file'},
    'getTaskLinkById': {'kind': 'task-link'}, 'getAllTaskLinks': {'kind': 'task-link'},
    'createTaskLink': {'kind': 'task-link'},
    'searchTasks': {'kind': 'task'}, 'getTask': {'kind': 'task'}, 'getTaskByReference': {'kind': 'task'},
    'getAllTasks': {'kind': 'task'}, 'getOverdueTasks': {'kind': 'task'}, 'getOverdueTasksByProject': {'kind': 'task'},
    'duplicateTaskToProject': {'kind': 'task'}, 'createTask': {'kind': 'task'},
    'getUser': {'kind': 'user'}, 'getUserByName': {'kind': 'user'}, 'getAllUsers': {'kind': 'user'},
    'createUser': {'kind': 'user'}, 'createLdapUser': {'kind': 'user'},
}


class MissingDependency(AssertionError):
    pass


class State(dict):
    def __missing__(self, key):
        raise MissingDependency(f'missing successful prerequisite {key}')


@dataclasses.dataclass
class Case:
    id: str
    family: str
    scenario: str
    channel: str
    description: str
    action: object
    after: tuple = ()
    uses: tuple = ()
    requires: tuple = ()


class Ref:
    """A value saved by an earlier step (state key and a path into it)."""

    def __init__(self, key, *path):
        self.key, self.path = key, path

    def get(self, ctx):
        if self.key not in ctx.state:
            raise MissingDependency(f'missing result {self.key}')
        v = ctx.state[self.key]
        try:
            for part in self.path:
                v = v[part]
        except (KeyError, IndexError, TypeError) as e:
            raise MissingDependency(f'prerequisite {self.key} lacks {self.path}') from e
        return v


def resolve(x, ctx):
    if isinstance(x, Ref):
        return x.get(ctx)
    if callable(x):
        return x(ctx)
    if isinstance(x, dict):
        return {k: resolve(v, ctx) for k, v in x.items()}
    if isinstance(x, (tuple, list)):
        return [resolve(v, ctx) for v in x]
    return x


def refs(x):
    """State keys a request template reads."""
    if isinstance(x, Ref):
        return {x.key}
    if isinstance(x, dict):
        return set().union(*(refs(v) for v in x.values())) if x else set()
    if isinstance(x, (tuple, list)):
        return set().union(*(refs(v) for v in x)) if x else set()
    return set()


def b64(data):
    return base64.b64encode(data if isinstance(data, bytes) else data.encode()).decode()


def png(width, height, rgb=(200, 40, 40)):
    """A small valid PNG image (8-bit RGB)."""
    import struct
    import zlib

    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    rows = b''.join(b'\x00' + bytes(rgb) * width for _ in range(height))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(rows, 9)) + chunk(b'IEND', b''))


def day(text):
    """Seconds since the epoch of 'YYYY-MM-DD[ HH:MM]' in UTC."""
    parts = [int(x) for x in re.split(r'[- :]', text)]
    return calendar.timegm((*parts[:3], *(parts[3:5] or [0, 0]), 0))


class Response:
    """What a program check sees of one product response: status, forwarded headers, body and exact bytes."""

    def __init__(self, status, headers, body, content):
        self.status, self.headers, self.body, self.content = status, dict(headers or {}), body, content

    @property
    def text(self):
        return self.content.decode('utf-8', errors='replace')

    @property
    def envelope(self):
        return self.body if isinstance(self.body, (dict, list)) else None

    @property
    def has_result(self):
        return isinstance(self.body, dict) and 'result' in self.body and 'error' not in self.body

    @property
    def result(self):
        assert self.has_result, 'no JSON-RPC result: ' + json.dumps(self.body, ensure_ascii=False)[:300]
        return self.body['result']

    @property
    def error(self):
        return self.body.get('error') if isinstance(self.body, dict) else None


def param(params, name, index):
    """One parameter of a request, given by name or by position."""
    if isinstance(params, dict):
        return params.get(name)
    if isinstance(params, (list, tuple)) and len(params) > index:
        return params[index]
    return None


class Normalize:
    def __init__(self):
        self.ids = {}
        self.next = Counter()
        self.labels = {}
        self.owners = {}

    def own(self, kind, value, owner_kind, owner):
        """Remember that a record lives inside another one (a task in a project, a comment on a task)."""
        if kind and value not in (None, 0, '', '0') and owner not in (None, 0, '', '0') and not isinstance(owner, bool):
            self.owners[(kind, str(value))] = (owner_kind, str(owner))

    def forget(self, kind, value, only=None):
        """A removed record and everything removed with it: their names and aliases no longer apply to the ids,
        which the store may give to new records. only: forget just the owned records of these kinds."""
        if value in (None, 0, '', '0') or isinstance(value, bool):
            return
        root = (kind, str(value))
        gone = {root}
        changed = True
        while changed:
            changed = False
            for k, owner in list(self.owners.items()):
                if owner in gone and k not in gone:
                    gone.add(k)
                    changed = True
        if only is not None:
            gone = {k for k in gone if k != root and k[0] in only}
        for k in gone:
            self.labels.pop(k, None)
            self.ids.pop(k, None)
            self.owners.pop(k, None)

    def after_call(self, method, params, result):
        """Keep the identities in step with the store after one successful request."""
        if method in CREATIONS and isinstance(result, int) and not isinstance(result, bool) and result > 0:
            kind, owner_kind, name, index = CREATIONS[method]
            self.own(kind, result, owner_kind, param(params, name, index))
        elif method in REMOVALS and result is True:
            kind, name, index = REMOVALS[method]
            self.forget(kind, param(params, name, index))
        elif method == 'removeAllTaskFiles' and result is True:
            self.forget('task', param(params, 'task_id', 0), only={'task-file'})
        elif method == 'removeAllProjectFiles' and result is True:
            self.forget('project', param(params, 'project_id', 0), only={'project-file'})

    def register(self, name, value, kind):
        """Name the identities a step saved (a created id, a record, or a list of records) so that later observations
        show them by that name: the same name in the reference and in the candidate, so a wrong identity (a task in
        another column, an assignment to another user) is a different value, not just another alias."""
        if not kind or value is None or isinstance(value, bool):
            return
        if isinstance(value, (int, str)) and str(value).isdigit() and str(value) != '0':
            self.labels[(kind, str(value))] = name
        elif isinstance(value, dict) and value.get('id') not in (None, 0, ''):
            self.labels[(kind, str(value['id']))] = name
            self.track(value, kind)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, dict) and item.get('id') not in (None, 0, ''):
                    self.labels[(kind, str(item['id']))] = f'{name}.{i}'
                    self.track(item, kind)

    def track(self, value, kind):
        """The owner of a record read from the store (its task, else its project)."""
        if kind and value.get('id') not in (None, 0, '', '0'):
            if kind != 'task' and value.get('task_id') not in (None, 0, '', '0'):
                self.own(kind, value['id'], 'task', value['task_id'])
            elif kind != 'project' and value.get('project_id') not in (None, 0, '', '0'):
                self.own(kind, value['id'], 'project', value['project_id'])

    def identity(self, kind, value):
        """Typed alias of a generated identity; zero, null and empty values mean 'none' and stay as they are."""
        if value is None or value == 0 or value == '' or value == '0' or isinstance(value, bool):
            return value
        if isinstance(value, float) and value == int(value):
            value = int(value)
        k = (kind, str(value))
        if k in self.labels:
            return f'#{kind}:{self.labels[k]}'
        if k not in self.ids:
            self.next[kind] += 1
            self.ids[k] = self.next[kind]
        return f'@{kind}{".s" if isinstance(value, str) else ""}:{self.ids[k]}'

    def time(self, value):
        """A clock timestamp as the day it falls on, relative to the application clock's first day."""
        if value is None or value == 0 or value == '' or value == '0' or isinstance(value, bool):
            return value
        try:
            stamp = int(value)
        except (TypeError, ValueError):
            return value
        if abs(stamp - DAY0) > CLOCK_WINDOW:
            return value
        return '@day%+d%s' % ((stamp - DAY0) // 86400, '.s' if isinstance(value, str) else '')

    def moment(self, value):
        """A business timestamp compared within MOMENT_TOLERANCE (see MOMENTS); zero and empty stay as they are."""
        if value is None or value == 0 or value == '' or value == '0' or isinstance(value, bool):
            return value
        try:
            return {'@moment': int(value)}
        except (TypeError, ValueError):
            return value

    def text(self, value):
        if value.startswith(('http://', 'https://', '/')):
            value = TOKEN_URLS.sub(lambda m: m[1] + self.identity('opaque-token', m[2]), value)
            for pattern, kind in URL_IDS:
                value = pattern.sub(lambda m: m[1] + self.identity(kind, int(m[2])), value)
        match = FILE_PATH.fullmatch(value)
        if match:
            value = match[1] + '/' + self.identity('task' if match[1] == 'tasks' else 'project', int(match[2])) \
                + '/' + self.identity('blob', match[3])
        return value

    def ident(self, kind, value):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return self.identity(kind, value)
        if isinstance(value, str) and re.fullmatch(r'[1-9][0-9]*', value):
            return self.identity(kind, value)
        return value

    def record(self, value, kind, relative):
        self.track(value, kind)
        out = {}
        for field, x in value.items():
            if field == 'id' and kind:
                out[field] = self.ident(kind, x)
            elif field == 'path' and isinstance(x, str) and kind in ('task-file', 'project-file'):
                # Where the store keeps a file is its own layout; only that the file is stored is behavior.
                out[field] = 'stored' if x else x
            elif field in ID_FIELDS:
                out[field] = self.ident(ID_FIELDS[field], x)
            elif field in GENERATED_TIME or field in relative:
                out[field] = self.time(x)
            elif field in MOMENTS:
                out[field] = self.moment(x)
            elif field in OPAQUE and isinstance(x, str):
                out[field] = self.identity('opaque-' + field, x) if x else x
            elif field in MAP_FIELDS and isinstance(x, dict):
                out[field] = {'@map': self.record(x, None, relative)}
            elif field in NESTED and isinstance(x, (dict, list)):
                out[field] = self.clean(x, NESTED[field], relative=relative)
            else:
                out[field] = self.clean(x, None, relative=relative)
        return out

    def clean(self, value, kind=None, *, keys=None, unordered=False, relative=(), mapping=False):
        """Normalize one observed JSON value. kind: the record type of the value (or of the list's items);
        keys: the value is an object keyed by identities of that type; mapping: an object keyed by data."""
        if (keys or mapping) and isinstance(value, list):
            # A PHP array serializes as a JSON list when its keys are 0..n-1 (and when it is empty): the same map.
            value = {str(i): x for i, x in enumerate(value)}
        if isinstance(value, dict):
            if keys:
                pairs = [[self.ident(keys, k), self.clean(v, kind, relative=relative)] for k, v in value.items()]
                return {'@unordered': pairs}
            if mapping:
                return {'@map': {k: self.clean(v, kind, relative=relative) for k, v in value.items()}}
            return self.record(value, kind, relative)
        if isinstance(value, list):
            items = [self.clean(x, kind, keys=keys, relative=relative) for x in value]
            return {'@unordered': items} if unordered else items
        if isinstance(value, str):
            return self.text(value)
        if kind and isinstance(value, (int, float)) and not isinstance(value, bool):
            # A procedure that answers with the identity of a record (for example the id a creation returns).
            return self.ident(kind, value)
        return value


class AliasGraph:
    """Compare normalized observations; typed aliases must keep a consistent bijection across the episode.

    Aliases are labels of this run's generated identities; only their relationships matter. Bindings are
    transactional per case: a failed comparison does not poison later ones. Records may carry fields the reference
    does not have; '@map' objects, '@unordered' collections and lists must match member for member.
    """

    TOKEN = re.compile(r'@[A-Za-z][A-Za-z0-9_.-]*:[0-9]+')

    def __init__(self):
        self.forward = {}
        self.reverse = {}

    def compare(self, actual, expected):
        forward = dict(self.forward)
        reverse = dict(self.reverse)

        def walk(a, e, path):
            if type(a) in (int, float) and type(e) in (int, float):
                assert a == e, path + ': different numeric value'
                return
            assert type(a) is type(e), f'{path}: different value type ({type(a).__name__} instead of {type(e).__name__})'
            if isinstance(e, dict):
                if e.keys() == {'@moment'} or a.keys() == {'@moment'}:
                    assert a.keys() == e.keys() and type(a['@moment']) is int, path + ': different value shape'
                    assert abs(a['@moment'] - e['@moment']) <= MOMENT_TOLERANCE, (
                        f'{path}: different moment {a["@moment"]} instead of {e["@moment"]}')
                    return
                if e.keys() == {'@map'} or a.keys() == {'@map'}:
                    assert a.keys() == e.keys(), path + ': different value shape'
                    am, em = a['@map'], e['@map']
                    assert isinstance(am, dict) and am.keys() == em.keys(), (
                        path + ': different members ' + json.dumps(sorted(set(am) ^ set(em)), ensure_ascii=False)[:200])
                    for k in em:
                        walk(am[k], em[k], path + '.' + k)
                    return
                if e.keys() == {'@unordered'} or a.keys() == {'@unordered'}:
                    assert a.keys() == e.keys(), path + ': different value shape'
                    av, ev = a['@unordered'], e['@unordered']
                    assert isinstance(av, list) and len(av) == len(ev), path + ': different collection length'

                    def bound(x):
                        return sum(m[0] in forward for m in self.TOKEN.finditer(json.dumps(x)))
                    todo = sorted(ev, key=bound, reverse=True)

                    def match(index, remaining):
                        if index == len(todo):
                            return True
                        for pos in remaining:
                            f, r = dict(forward), dict(reverse)
                            try:
                                walk(av[pos], todo[index], path + '{member}')
                                if match(index + 1, [x for x in remaining if x != pos]):
                                    return True
                            except AssertionError:
                                pass
                            forward.clear()
                            forward.update(f)
                            reverse.clear()
                            reverse.update(r)
                        return False
                    assert match(0, list(range(len(av)))), path + ': different members or identity relationships'
                    return
                missing = sorted(set(e) - set(a))
                assert not missing, path + ': missing fields ' + ', '.join(missing[:5])
                for k in e:
                    walk(a[k], e[k], path + '.' + k)
            elif isinstance(e, list):
                assert len(a) == len(e), f'{path}: different collection length ({len(a)} instead of {len(e)})'
                for i, (x, y) in enumerate(zip(a, e)):
                    walk(x, y, f'{path}[{i}]')
            elif isinstance(e, str):
                at, et = list(self.TOKEN.finditer(a)), list(self.TOKEN.finditer(e))
                assert self.TOKEN.split(a) == self.TOKEN.split(e) and len(at) == len(et), (
                    f'{path}: different text {a[:120]!r} instead of {e[:120]!r}')
                for am, em in zip(at, et):
                    av, ev = am[0], em[0]
                    assert av.rsplit(':', 1)[0] == ev.rsplit(':', 1)[0], path + ': different identity type'
                    assert forward.get(ev, av) == av and reverse.get(av, ev) == ev, (
                        path + ': inconsistent identity relationship')
                    forward[ev] = av
                    reverse[av] = ev
            else:
                assert a == e, f'{path}: different value {a!r} instead of {e!r}'

        walk(actual, expected, '$')
        self.forward, self.reverse = forward, reverse


class Context:
    """Public access to one candidate instance (through the runtime) plus the observation normalizers."""

    def __init__(self, broker, out=None):
        self.broker = broker
        self.state = State()
        self.norm = Normalize()
        self.aliases = AliasGraph()
        self.passwords = {ADMIN: 'admin'}
        self.current_case = None
        self.request_id = 0

    # -- transport -----------------------------------------------------------------------------------------
    def http(self, method, path, *, auth=None, json_body=None, body=None, content_type=None, headers=None):
        rpc = {'op': 'api', 'method': method, 'path': path, 'binary': True}
        if auth is not None:
            rpc['auth'] = auth
        if headers:
            rpc['headers'] = headers
        if json_body is not None:
            rpc['json'] = json_body
        elif body is not None:
            if isinstance(body, bytes):
                rpc['body_base64'] = base64.b64encode(body).decode()
            else:
                rpc['body'] = body
        if content_type is not None:
            rpc['content_type'] = content_type
        try:
            answer = self.broker.call(rpc)
        except BrokerError as exc:
            # The runtime could not complete the product request (connection refused, timeout, malformed reply).
            raise AssertionError('candidate HTTP request failed: ' + exc.detail[:300]) from None
        assert not answer.get('truncated'), 'the product response exceeds the black-box response limit'
        content = base64.b64decode(answer.get('body_base64') or '')
        return Response(answer['status'], answer.get('headers'), answer.get('body'), content)

    def auth(self, actor):
        """The api operation's auth value of an actor: admin, app (the application token), None (anonymous),
        ('wrong', user) (a wrong password), ('secret', user, value) or any created account by name."""
        if actor is None:
            return None
        if actor == 'app':
            return APP_USER
        if actor == ADMIN:
            return ADMIN
        if isinstance(actor, (tuple, list)):
            if actor[0] == 'wrong':
                return [actor[1], 'Wrong-Password-1!']
            if actor[0] == 'secret':
                return [actor[1], actor[2]]
            raise ValueError('unknown actor form ' + str(actor))
        return [actor, self.passwords[actor]]

    def rpc(self, method, params=None, actor=ADMIN, *, notification=False, request_id=None):
        body = {'jsonrpc': '2.0', 'method': method}
        if params is not None:
            body['params'] = params
        if not notification:
            self.request_id += 1
            body['id'] = self.request_id if request_id is None else request_id
        response = self.http('POST', '/jsonrpc.php', auth=self.auth(actor), json_body=body)
        assert response.status < 500, f'candidate HTTP server error {response.status}: {response.text[:300]}'
        if not notification:
            assert isinstance(response.body, dict), f'{method}: the answer is not a JSON-RPC object: {response.text[:200]}'
            assert response.body.get('jsonrpc') == '2.0', f'{method}: the answer lacks jsonrpc 2.0'
            if response.status == 200 and 'result' in response.body:
                assert response.body.get('id') == body['id'], f'{method}: the answer does not echo the request id'
            if response.has_result:
                self.norm.after_call(method, params, response.result)
        return response

    def call(self, method, params=None, actor=ADMIN):
        """A request whose success the caller relies on (fixtures, preparation): the result or an AssertionError."""
        response = self.rpc(method, params, actor)
        assert response.has_result, f'{method}: {json.dumps(response.body, ensure_ascii=False)[:300]}'
        return response.result

    def restart(self):
        """Restart the product process with the same data directory (runtime op restart)."""
        status = self.broker.call({'op': 'restart'})
        assert status.get('ready'), 'the application did not come back after a restart: ' + str(status.get('detail'))
        return status

    # -- observations --------------------------------------------------------------------------------------
    def outcome(self, response):
        """Whether a request was performed: the error code of a refusal, or the kind of answer it got (an object or
        list with its size, a scalar as normalized). Used where authorization, not content, is the behavior."""
        observation = {'http': response.status}
        body = response.body
        if isinstance(body, dict) and isinstance(body.get('error'), dict):
            observation['error'] = {'code': body['error'].get('code')}
        elif isinstance(body, dict) and 'result' in body:
            result = body['result']
            if isinstance(result, dict):
                observation['result'] = {'object': bool(result)}
            elif isinstance(result, list):
                observation['result'] = {'list': len(result) > 0}
            else:
                observation['result'] = result if isinstance(result, (bool, str)) or result is None \
                    else {'number': True}
        else:
            observation['body'] = 'non-JSON-RPC answer'
        return observation

    def observe(self, response, kind=None, *, keys=None, unordered=False, relative=(), mapping=False):
        """The behavior-relevant projection of one JSON-RPC answer: the HTTP status and either the normalized
        result or the error code (error messages are wording, not behavior)."""
        observation = {'http': response.status}
        body = response.body
        if isinstance(body, dict) and isinstance(body.get('error'), dict):
            observation['error'] = {'code': body['error'].get('code')}
        elif isinstance(body, dict) and 'result' in body:
            observation['result'] = self.norm.clean(body['result'], kind, keys=keys, unordered=unordered,
                                                    relative=relative, mapping=mapping)
        else:
            observation['body'] = 'non-JSON-RPC answer'
        return observation


class Suite:
    """The ordered cases of one protocol module. Fixture steps (channel setup) are unscored preparation that accepts
    any successful answer; scored steps observe one request each."""

    def __init__(self, module=''):
        self.cases = []
        self.ids = set()
        self.savers = {}
        # Case ids are unique across modules: they carry the module name.
        self.prefix = module + ':' if module else ''

    def qualify(self, cid):
        return cid if ':' in cid else self.prefix + cid

    def add(self, family, scenario, step, action, channel='rpc', description='', after=(), uses=(), reads=(),
            requires=()):
        cid = self.qualify(f'{channel}.{family}.{scenario}.{step}')
        if cid in self.ids:
            raise ValueError('duplicate ' + cid)
        self.ids.add(cid)
        # A scored step that reads a value an earlier scored step saved depends on that step.
        depends = [self.savers[k] for k in sorted(reads) if k in self.savers and self.savers[k] != cid]
        case = Case(cid, family, scenario, channel, description or step, action,
                    tuple(dict.fromkeys([*depends, *(self.qualify(x) for x in after)])), tuple(uses),
                    tuple(self.qualify(x) for x in requires))
        self.cases.append(case)
        return cid

    def saved(self, key, cid):
        self.savers[key] = cid

    def fixture(self, scenario, step, method, params=None, actor=ADMIN, save=None, password=None):
        """Unscored preparation through the API; password registers a created account's password for later actors."""
        def action(c, relaxed=True):
            result = c.call(method, resolve(params, c), resolve(actor, c))
            assert result not in (False, None), f'{method} did not succeed: {result!r}'
            if save:
                c.state[save] = result
                c.norm.register(save, result, RESULTS.get(method, {}).get('kind'))
            if password:
                c.passwords[resolve(params, c)['username'] if isinstance(params, dict) else params[0]] = password
            return None
        cid = self.add('fixture', scenario, step, action, channel='setup', description=f'{method} (preparation)')
        if save:
            self.savers.pop(save, None)
        return cid

    def rpc(self, family, scenario, step, method, params=None, actor=ADMIN, *, save=None, kind=None, keys=None,
            unordered=False, relative=(), mapping=False, check=None, after=(), uses=(), describe=None, prepare=None,
            requires=(), project=None):
        """One scored JSON-RPC request and the normalized observation of its answer."""
        def action(c):
            if prepare:
                prepare(c)
            response = c.rpc(method, resolve(params, c), resolve(actor, c))
            if save and response.has_result and response.result not in (False, None):
                c.state[save] = response.result
                c.norm.register(save, response.result, RESULTS.get(method, {}).get('kind'))
            if check:
                check(c, response)
            if project:
                return project(c, response)
            spec = RESULTS.get(method, {})
            return c.observe(response, kind or spec.get('kind'), keys=keys or spec.get('keys'), unordered=unordered,
                             relative=relative, mapping=mapping or spec.get('mapping', False))
        who = actor if isinstance(actor, str) or actor is None else '/'.join(str(x) for x in actor[:2])
        text = describe or f'{method} as {who or "anonymous"}'
        cid = self.add(family, scenario, step, action, description=text, after=after, uses=uses,
                       reads=refs(params) | refs(actor), requires=requires)
        if save:
            self.saved(save, cid)
        return cid


def subset(keep, kind=None):
    """An observation of a shared collection restricted to the records a case is about (keep(c, record) is true):
    records that other cases' refused attempts or edge cases may or may not have created stay out of it."""
    def project(c, response):
        if response.has_result and isinstance(response.result, list):
            kept = [x for x in response.result if isinstance(x, dict) and keep(c, x)]
            return {'http': response.status, 'result': c.norm.clean(kept, kind)}
        return c.observe(response, kind)
    return project


def saved_ids(c, *keys):
    """The ids that earlier steps saved under these state keys (a created id or a record)."""
    out = set()
    for key in keys:
        value = c.state.get(key) if isinstance(c.state, dict) else None
        if isinstance(value, dict):
            value = value.get('id')
        if value not in (None, False, 0, ''):
            out.add(str(value))
    return out


def refused_stored(field, refused, anchor):
    """Which of the refused attempts a collection lists (by field), and whether it lists its anchor record."""
    def project(c, response):
        names = [x.get(field) for x in response.result if isinstance(x, dict)] \
            if response.has_result and isinstance(response.result, list) else None
        return {'http': response.status, 'anchor-listed': names is not None and anchor in names,
                'refused-stored': sorted(n for n in names or [] if n in refused)}
    return project


TASK_NUMBER = re.compile(r'#(\d+)')


def events(c, response):
    """Activity events: which event, by whom, on which task and project, its title; not the rendered HTML or the
    snapshot of the task at the time."""
    observation = {'http': response.status}
    body = response.body
    if isinstance(body, dict) and isinstance(body.get('error'), dict):
        observation['error'] = {'code': body['error'].get('code')}
        return observation
    result = body.get('result') if isinstance(body, dict) else None
    if not isinstance(result, list):
        observation['result'] = c.norm.clean(result)
        return observation
    out = []
    for event in result:
        assert isinstance(event, dict), 'activity events must be objects'
        title = event.get('event_title')
        if isinstance(title, str):
            title = TASK_NUMBER.sub(lambda m: '#' + c.norm.identity('task', int(m[1])), title)
        out.append({'event_name': event.get('event_name'), 'event_title': title, 'author': event.get('author'),
                    'task_id': c.norm.ident('task', event.get('task_id')),
                    'project_id': c.norm.ident('project', event.get('project_id')),
                    'creator_id': c.norm.ident('user', event.get('creator_id'))})
    observation['result'] = out
    return observation

"""JSON-RPC 2.0 protocol and API authentication at /jsonrpc.php.

Envelope handling (ids, notifications, batches, malformed requests), error codes, parameter binding (named and
positional, missing, extra and unknown parameters), the two authentication modes (the application token of the
user jsonrpc and user credentials), anonymous and wrong credentials, and the health check.
"""
from harness import ADMIN, APP_USER, Ref

VERSION = 'getVersion'


def envelope(c, response):
    """The whole JSON-RPC answer: HTTP status, then per response object its jsonrpc, id and result or error code."""
    def one(x):
        if not isinstance(x, dict):
            return {'not-an-object': True}
        out = {k: x[k] for k in ('jsonrpc', 'id') if k in x}
        if isinstance(x.get('error'), dict):
            out['error'] = {'code': x['error'].get('code')}
        elif 'result' in x:
            out['result'] = c.norm.clean(x['result'])
        return out
    body = response.body
    if response.content.strip() == b'':
        return {'http': response.status, 'empty': True}
    if isinstance(body, list):
        return {'http': response.status, 'batch': [one(x) for x in body]}
    if isinstance(body, dict):
        return {'http': response.status, 'object': one(body)}
    return {'http': response.status, 'body': 'not JSON'}


def raw(suite, family, scenario, step, payload, *, actor=ADMIN, method='POST', content_type=None, text=None,
        describe='', requires=()):
    """A request whose body is sent exactly as given (JSON value or text), observed as a whole envelope."""
    def action(c):
        kwargs = {}
        if text is not None:
            kwargs['body'] = text
        elif payload is not None:
            kwargs['json_body'] = payload
        if content_type:
            kwargs['content_type'] = content_type
        response = c.http(method, '/jsonrpc.php', auth=c.auth(actor), **kwargs)
        assert response.status < 500, f'candidate HTTP server error {response.status}'
        return envelope(c, response)
    return suite.add(family, scenario, step, action, description=describe or f'{method} /jsonrpc.php: {step}',
                     requires=requires)


def build(suite):
    rpc = suite.rpc
    # -- authentication modes -------------------------------------------------------------------------------
    rpc('auth', 'modes', 'admin-password', VERSION)
    rpc('auth', 'modes', 'application-token', VERSION, actor='app')
    rpc('auth', 'modes', 'anonymous', VERSION, actor=None)
    rpc('auth', 'modes', 'admin-wrong-password', VERSION, actor=('wrong', ADMIN))
    rpc('auth', 'modes', 'unknown-user', VERSION, actor=('secret', 'nobody', 'whatever-2026'))
    rpc('auth', 'modes', 'application-wrong-token', VERSION, actor=('secret', APP_USER, 'not-the-token'))
    rpc('auth', 'modes', 'application-user-with-admin-password', VERSION, actor=('secret', APP_USER, 'admin'))
    rpc('auth', 'modes', 'admin-with-application-token', VERSION,
        actor=('secret', ADMIN, '9c5f44bb170a8f12f4c83369f3e0e68ca40fe1d3fec515cbfe067076cfff'))
    rpc('auth', 'modes', 'username-case', VERSION, actor=('secret', 'ADMIN', 'admin'))
    # The user-specific procedures need a user session (the others are refused for the application token in the
    # persistence module, next to their positive calls).
    rpc('auth', 'user-only', 'me-as-admin', 'getMe')
    rpc('auth', 'user-only', 'me-as-application', 'getMe', actor='app', requires=['rpc.auth.user-only.me-as-admin'])
    # A wrong password is refused however often it is tried, and the right one keeps working.
    suite.fixture('lockout', 'user', 'createUser', {'username': 'erin', 'password': 'Erin-Pass-2026'},
                  save='erin', password='Erin-Pass-2026')
    def wrong_attempts(c):
        return {'answers': [c.observe(c.rpc('getMe', None, ('wrong', 'erin'))) for _ in range(4)]}
    suite.add('auth', 'lockout', 'four-wrong-passwords', wrong_attempts,
              description='getMe four times with a wrong password for one account')
    rpc('auth', 'lockout', 'right-after-failures', 'getMe', actor='erin', after=['rpc.auth.lockout.four-wrong-passwords'])
    rpc('auth', 'lockout', 'failure-counter', 'getUserByName', ['erin'], after=['rpc.auth.lockout.four-wrong-passwords'])

    # -- envelope -------------------------------------------------------------------------------------------
    base = {'jsonrpc': '2.0', 'method': VERSION}
    raw(suite, 'envelope', 'ids', 'numeric-id', {**base, 'id': 42})
    raw(suite, 'envelope', 'ids', 'string-id', {**base, 'id': 'request-α'})
    raw(suite, 'envelope', 'ids', 'zero-id', {**base, 'id': 0})
    raw(suite, 'envelope', 'ids', 'fractional-id', {**base, 'id': 2.5})
    raw(suite, 'envelope', 'ids', 'negative-id', {**base, 'id': -7})
    raw(suite, 'envelope', 'notifications', 'without-id', dict(base))
    raw(suite, 'envelope', 'notifications', 'null-id', {**base, 'id': None})
    raw(suite, 'envelope', 'params', 'empty-object', {**base, 'id': 3, 'params': {}})
    raw(suite, 'envelope', 'params', 'empty-array', {**base, 'id': 4, 'params': []})
    raw(suite, 'envelope', 'params', 'string-params', {**base, 'id': 5, 'params': 'version'})
    raw(suite, 'envelope', 'params', 'number-params', {**base, 'id': 6, 'params': 7})
    raw(suite, 'envelope', 'invalid', 'missing-method', {'jsonrpc': '2.0', 'id': 8})
    raw(suite, 'envelope', 'invalid', 'missing-version', {'method': VERSION, 'id': 9})
    raw(suite, 'envelope', 'invalid', 'version-1', {'jsonrpc': '1.0', 'method': VERSION, 'id': 10})
    raw(suite, 'envelope', 'invalid', 'numeric-method', {'jsonrpc': '2.0', 'method': 12, 'id': 11})
    raw(suite, 'envelope', 'invalid', 'parse-error', None, text='{"jsonrpc": "2.0", "method": "getVersion", "id": 1')
    raw(suite, 'envelope', 'invalid', 'json-string', 'getVersion')
    raw(suite, 'envelope', 'invalid', 'json-number', 17)
    raw(suite, 'envelope', 'invalid', 'empty-body', None, text='')
    raw(suite, 'envelope', 'invalid', 'get-request', None, method='GET')
    raw(suite, 'envelope', 'content-type', 'text-plain', {**base, 'id': 12}, content_type='text/plain')
    raw(suite, 'envelope', 'content-type', 'form-urlencoded', {**base, 'id': 13},
        content_type='application/x-www-form-urlencoded')
    raw(suite, 'envelope', 'methods', 'unknown-method', {'jsonrpc': '2.0', 'method': 'getEverything', 'id': 14})
    raw(suite, 'envelope', 'methods', 'upper-case-name', {'jsonrpc': '2.0', 'method': 'GETVERSION', 'id': 15})
    raw(suite, 'envelope', 'methods', 'lower-case-name', {'jsonrpc': '2.0', 'method': 'gettimezone', 'id': 16})
    raw(suite, 'envelope', 'methods', 'unknown-method-anonymous', {'jsonrpc': '2.0', 'method': 'getEverything',
                                                                   'id': 18}, actor=None,
        requires=['rpc.envelope.methods.unknown-method'])

    # -- batches --------------------------------------------------------------------------------------------
    raw(suite, 'batch', 'mixed', 'three-calls', [
        {'jsonrpc': '2.0', 'method': VERSION, 'id': 1},
        {'jsonrpc': '2.0', 'method': 'noSuchProcedure', 'id': 2},
        {'jsonrpc': '2.0', 'method': 'getTimezone', 'id': 3}])
    raw(suite, 'batch', 'mixed', 'call-and-notification', [
        {'jsonrpc': '2.0', 'method': 'getDefaultTaskColor', 'id': 'a'},
        {'jsonrpc': '2.0', 'method': VERSION}])
    raw(suite, 'batch', 'mixed', 'only-notifications', [
        {'jsonrpc': '2.0', 'method': VERSION}, {'jsonrpc': '2.0', 'method': 'getTimezone'}])
    raw(suite, 'batch', 'invalid', 'empty-batch', [])
    raw(suite, 'batch', 'invalid', 'scalars', [1, 2])
    raw(suite, 'batch', 'invalid', 'invalid-member', [
        {'jsonrpc': '2.0', 'method': VERSION, 'id': 1}, {'jsonrpc': '2.0', 'id': 2}])
    raw(suite, 'batch', 'params', 'invalid-params-member', [
        {'jsonrpc': '2.0', 'method': 'getProjectById', 'id': 1},
        {'jsonrpc': '2.0', 'method': VERSION, 'id': 2}])
    raw(suite, 'batch', 'auth', 'batch-anonymous', [
        {'jsonrpc': '2.0', 'method': VERSION, 'id': 1}], actor=None)
    raw(suite, 'batch', 'auth', 'batch-application', [
        {'jsonrpc': '2.0', 'method': VERSION, 'id': 1}, {'jsonrpc': '2.0', 'method': 'getMe', 'id': 2}],
        actor='app')

    # -- parameter binding ----------------------------------------------------------------------------------
    suite.fixture('params', 'project', 'createProject', {'name': 'Binding'}, save='project')
    suite.fixture('params', 'task', 'createTask', {'title': 'Bound task', 'project_id': Ref('project')}, save='task')
    rpc('params', 'params', 'positional', 'getTask', [Ref('task')])
    rpc('params', 'params', 'named', 'getTask', {'task_id': Ref('task')})
    rpc('params', 'params', 'string-number', 'getTask', {'task_id': lambda c: str(c.state['task'])})
    rpc('params', 'params', 'missing-required', 'getTask')
    rpc('params', 'params', 'empty-named', 'getTask', {})
    rpc('params', 'params', 'unknown-named', 'getTask', {'id': Ref('task')})
    rpc('params', 'params', 'extra-named', 'getTask', {'task_id': Ref('task'), 'verbose': True})
    rpc('params', 'params', 'extra-positional', 'getTask', [Ref('task'), 2])
    rpc('params', 'params', 'positional-defaults', 'getAllTasks', [Ref('project')])
    rpc('params', 'params', 'named-defaults', 'getAllTasks', {'project_id': Ref('project')})
    rpc('params', 'params', 'named-out-of-order', 'createTask',
        {'project_id': Ref('project'), 'color_id': 'red', 'title': 'Order'}, save='ordered-task')
    rpc('params', 'params', 'named-out-of-order-read', 'getTask', [Ref('ordered-task')])
    rpc('params', 'params', 'positional-optional', 'createTask', ['Positional', Ref('project'), 'blue'],
        save='positional-task')
    rpc('params', 'params', 'positional-optional-read', 'getTask', [Ref('positional-task')])
    rpc('params', 'params', 'not-a-number', 'getTask', ['first'])

    # -- health check ---------------------------------------------------------------------------------------
    def health(c):
        response = c.http('GET', '/healthcheck.php')
        return {'http': response.status, 'body': response.body if isinstance(response.body, dict) else 'not JSON'}
    suite.add('health', 'healthcheck', 'get', health, description='GET /healthcheck.php')

    # -- application information ------------------------------------------------------------------------------
    rpc('application', 'info', 'timezone', 'getTimezone', actor='app')
    rpc('application', 'info', 'default-colors', 'getDefaultTaskColors', actor='app')
    rpc('application', 'info', 'default-color', 'getDefaultTaskColor', actor='app')
    rpc('application', 'info', 'color-list', 'getColorList', actor='app')
    rpc('application', 'info', 'application-roles', 'getApplicationRoles', actor='app')
    rpc('application', 'info', 'project-roles', 'getProjectRoles', actor='app')

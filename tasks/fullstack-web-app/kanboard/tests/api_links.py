"""Link labels, internal task links (both directions) and external task links through the JSON-RPC API.

Refused attempts and edge cases act on subjects of their own (a checks label, a checks task with its own link), so
that accepting or refusing one of them never changes the labels and links the ordinary cases observe."""
from harness import Ref, saved_ids

REFUSED_LABELS = {'mirrors', ''}


def labels_view(c, response):
    """The link labels, without the records of refused attempts (a second label of the same name, the refused names)
    and without the checks label."""
    if not (response.has_result and isinstance(response.result, list)):
        return c.observe(response, 'link')
    seen, kept = set(), []
    for x in response.result:
        if not isinstance(x, dict):
            continue
        label = x.get('label')
        if label in REFUSED_LABELS or label in seen or str(x.get('id')) in saved_ids(c, 'l-check'):
            continue
        seen.add(label)
        kept.append(x)
    return {'http': response.status, 'result': c.norm.clean(kept, 'link')}


def build(suite):
    rpc, fx = suite.rpc, suite.fixture

    # -- link labels ----------------------------------------------------------------------------------------
    rpc('labels', 'labels', 'defaults', 'getAllLinks')
    rpc('labels', 'labels', 'by-id', 'getLinkById', [2])
    rpc('labels', 'labels', 'by-label', 'getLinkByLabel', ['is a parent of'])
    rpc('labels', 'labels', 'by-label-missing', 'getLinkByLabel', ['is a cousin of'],
        requires=['rpc.labels.labels.by-label'])
    rpc('labels', 'labels', 'by-id-missing', 'getLinkById', [987654], requires=['rpc.labels.labels.by-id'])
    rpc('labels', 'labels', 'opposite', 'getOppositeLinkId', [4])
    rpc('labels', 'labels', 'opposite-of-symmetric', 'getOppositeLinkId', [1])
    rpc('labels', 'labels', 'opposite-missing', 'getOppositeLinkId', [987654])
    rpc('labels', 'create', 'pair', 'createLink', ['supersedes', 'is superseded by'], save='l-sup')
    rpc('labels', 'create', 'pair-read', 'getLinkById', [Ref('l-sup')])
    rpc('labels', 'create', 'pair-opposite', 'getOppositeLinkId', [Ref('l-sup')])
    rpc('labels', 'create', 'pair-opposite-read', 'getLinkByLabel', ['is superseded by'],
        after=['rpc.labels.create.pair'])
    rpc('labels', 'create', 'single', 'createLink', {'label': 'pairs with'}, save='l-pair')
    rpc('labels', 'create', 'single-read', 'getLinkById', [Ref('l-pair')])
    rpc('labels', 'create', 'duplicate', 'createLink', ['blocks'])
    rpc('labels', 'create', 'same-both-sides', 'createLink', ['mirrors', 'mirrors'])
    rpc('labels', 'create', 'empty', 'createLink', [''])
    rpc('labels', 'create', 'all-after', 'getAllLinks', project=labels_view,
        after=['rpc.labels.create.pair', 'rpc.labels.create.single'],
        describe='getAllLinks as admin after the creations (without refused attempts)')
    rpc('labels', 'update', 'rename', 'updateLink', [Ref('l-pair'), 0, 'pairs nicely with'])
    rpc('labels', 'update', 'rename-read', 'getLinkById', [Ref('l-pair')], after=['rpc.labels.update.rename'])
    fx('labels', 'checks-label', 'createLink', ['checks label'], save='l-check')
    rpc('labels', 'update', 'duplicate-label', 'updateLink', [Ref('l-check'), 0, 'blocks'])
    rpc('labels', 'update', 'empty-label', 'updateLink', [Ref('l-check'), 0, ''])
    rpc('labels', 'update', 'unchanged', 'getLinkById', [Ref('l-check')])

    # -- internal task links ----------------------------------------------------------------------------------
    fx('tasks', 'project', 'createProject', {'name': 'Linked project'}, save='p')
    fx('tasks', 'project2', 'createProject', {'name': 'Other linked project'}, save='p2')
    fx('tasks', 'a', 'createTask', {'title': 'Task A', 'project_id': Ref('p')}, save='a')
    fx('tasks', 'b', 'createTask', {'title': 'Task B', 'project_id': Ref('p'), 'color_id': 'red'}, save='b')
    fx('tasks', 'c', 'createTask', {'title': 'Task C', 'project_id': Ref('p2')}, save='c')
    fx('tasks', 'd', 'createTask', {'title': 'Task D', 'project_id': Ref('p')}, save='d')
    rpc('tasks', 'create', 'blocks', 'createTaskLink', [Ref('a'), Ref('b'), 2], save='tl-ab')
    rpc('tasks', 'create', 'from-a', 'getAllTaskLinks', [Ref('a')], after=['rpc.tasks.create.blocks'])
    rpc('tasks', 'create', 'from-b', 'getAllTaskLinks', [Ref('b')], after=['rpc.tasks.create.blocks'])
    rpc('tasks', 'create', 'by-id', 'getTaskLinkById', [Ref('tl-ab')])
    rpc('tasks', 'create', 'relates-symmetric', 'createTaskLink', [Ref('a'), Ref('d'), 1], save='tl-ad')
    rpc('tasks', 'create', 'relates-from-d', 'getAllTaskLinks', [Ref('d')], after=['rpc.tasks.create.relates-symmetric'])
    rpc('tasks', 'create', 'other-project', 'createTaskLink', {'task_id': Ref('a'), 'opposite_task_id': Ref('c'),
                                                               'link_id': 6}, save='tl-ac')
    rpc('tasks', 'create', 'other-project-from-c', 'getAllTaskLinks', [Ref('c')],
        after=['rpc.tasks.create.other-project'])
    rpc('tasks', 'create', 'all-from-a', 'getAllTaskLinks', [Ref('a')],
        after=['rpc.tasks.create.blocks', 'rpc.tasks.create.relates-symmetric', 'rpc.tasks.create.other-project'])
    rpc('tasks', 'create', 'custom-label', 'createTaskLink', [Ref('b'), Ref('d'), Ref('l-sup')], save='tl-bd',
        after=['rpc.labels.create.pair'])
    rpc('tasks', 'create', 'custom-label-from-d', 'getAllTaskLinks', [Ref('d')],
        after=['rpc.tasks.create.custom-label', 'rpc.tasks.create.relates-from-d'])
    rpc('tasks', 'validation', 'to-itself', 'createTaskLink', [Ref('a'), Ref('a'), 1])
    rpc('tasks', 'validation', 'missing-opposite', 'createTaskLink', [Ref('a'), 987654, 1], actor='app')
    rpc('tasks', 'validation', 'missing-label', 'createTaskLink', [Ref('a'), Ref('b'), 987654])
    rpc('tasks', 'validation', 'duplicate', 'createTaskLink', [Ref('a'), Ref('b'), 2], after=['rpc.tasks.create.blocks'])
    rpc('tasks', 'validation', 'unchanged', 'getAllTaskLinks', [Ref('a')], after=['rpc.tasks.create.all-from-a'])
    rpc('tasks', 'validation', 'missing-link', 'getTaskLinkById', [987654], actor='app',
        requires=['rpc.tasks.create.by-id'])
    rpc('tasks', 'update', 'relabel', 'updateTaskLink', [Ref('tl-ab'), Ref('a'), Ref('b'), 4],
        after=['rpc.tasks.create.all-from-a'])
    rpc('tasks', 'update', 'relabel-from-a', 'getAllTaskLinks', [Ref('a')], after=['rpc.tasks.update.relabel'])
    rpc('tasks', 'update', 'relabel-from-b', 'getAllTaskLinks', [Ref('b')], after=['rpc.tasks.update.relabel'])
    rpc('tasks', 'update', 'retarget', 'updateTaskLink', [Ref('tl-ad'), Ref('a'), Ref('c'), 1],
        after=['rpc.tasks.update.relabel'])
    rpc('tasks', 'update', 'retarget-from-c', 'getAllTaskLinks', [Ref('c')], after=['rpc.tasks.update.retarget'])
    rpc('tasks', 'update', 'retarget-from-d', 'getAllTaskLinks', [Ref('d')], after=['rpc.tasks.update.retarget'])
    rpc('tasks', 'update', 'wrong-task', 'updateTaskLink', [Ref('tl-ab'), Ref('d'), Ref('b'), 1])
    rpc('tasks', 'remove', 'remove', 'removeTaskLink', [Ref('tl-ab')], after=['rpc.tasks.update.relabel-from-b'])
    rpc('tasks', 'remove', 'removed-from-a', 'getAllTaskLinks', [Ref('a')],
        after=['rpc.tasks.remove.remove', 'rpc.tasks.update.retarget'])
    rpc('tasks', 'remove', 'removed-from-b', 'getAllTaskLinks', [Ref('b')], after=['rpc.tasks.remove.remove'])
    rpc('tasks', 'remove', 'again', 'removeTaskLink', [Ref('tl-ab')], actor='app', after=['rpc.tasks.remove.remove'])
    rpc('tasks', 'remove', 'label-in-use', 'removeLink', [Ref('l-sup')], after=['rpc.tasks.create.custom-label'])
    rpc('tasks', 'remove', 'label-removed-links', 'getAllTaskLinks', [Ref('d')],
        after=['rpc.tasks.remove.label-in-use', 'rpc.tasks.update.retarget-from-d'])
    rpc('tasks', 'remove', 'label-removed-list', 'getAllLinks', project=labels_view,
        after=['rpc.tasks.remove.label-in-use', 'rpc.labels.update.rename-read'],
        describe='getAllLinks as admin after a label in use was removed (without refused attempts)')
    rpc('tasks', 'remove', 'label-missing', 'removeLink', [987654])

    # -- external task links --------------------------------------------------------------------------------
    rpc('external', 'types', 'types', 'getExternalTaskLinkTypes')
    rpc('external', 'types', 'weblink-dependencies', 'getExternalTaskLinkProviderDependencies', ['weblink'])
    rpc('external', 'types', 'attachment-dependencies', 'getExternalTaskLinkProviderDependencies', ['attachment'])
    rpc('external', 'types', 'file-dependencies', 'getExternalTaskLinkProviderDependencies', ['file'])
    rpc('external', 'types', 'unknown-provider', 'getExternalTaskLinkProviderDependencies', ['ftp'])
    fx('external', 'task', 'createTask', {'title': 'Task with links', 'project_id': Ref('p')}, save='e')
    rpc('external', 'create', 'web-auto', 'createExternalTaskLink', [Ref('e'), 'https://example.org/docs/guide',
                                                                     'related'], save='el1')
    rpc('external', 'create', 'web-titled', 'createExternalTaskLink', {'task_id': Ref('e'),
                                                                       'url': 'https://example.org/spec',
                                                                       'dependency': 'related',
                                                                       'title': 'The specification'}, save='el2')
    rpc('external', 'create', 'attachment-auto', 'createExternalTaskLink', [Ref('e'),
                                                                            'https://example.org/files/plan.pdf',
                                                                            'related'], save='el3')
    rpc('external', 'create', 'file-type', 'createExternalTaskLink', [Ref('e'), 'smb://server/share/notes.txt',
                                                                      'related', 'file'], save='el4')
    rpc('external', 'create', 'web-forced', 'createExternalTaskLink', [Ref('e'), 'https://example.org/report.pdf',
                                                                       'related', 'weblink'], save='el5')
    rpc('external', 'create', 'all-sorted', 'getAllExternalTaskLinks', [Ref('e')],
        after=['rpc.external.create.web-auto', 'rpc.external.create.web-titled', 'rpc.external.create.attachment-auto',
               'rpc.external.create.file-type', 'rpc.external.create.web-forced'])
    rpc('external', 'create', 'by-id', 'getExternalTaskLinkById', [Ref('e'), Ref('el2')])
    rpc('external', 'create', 'by-id-wrong-task', 'getExternalTaskLinkById', [Ref('a'), Ref('el2')],
        requires=['rpc.external.create.by-id'])
    fx('external', 'checks-task', 'createTask', {'title': 'Link checks', 'project_id': Ref('p')}, save='ex')
    fx('external', 'checks-link', 'createExternalTaskLink', [Ref('ex'), 'https://example.org/checks', 'related'],
       save='elx')
    rpc('external', 'validation', 'not-a-url', 'createExternalTaskLink', [Ref('ex'), 'just words', 'related'])
    rpc('external', 'validation', 'unknown-dependency', 'createExternalTaskLink', [Ref('ex'),
                                                                                  'https://example.org/x',
                                                                                  'blocks'])
    rpc('external', 'validation', 'wrong-type', 'createExternalTaskLink', [Ref('ex'), 'https://example.org/x',
                                                                           'related', 'file'])
    rpc('external', 'validation', 'unknown-type', 'createExternalTaskLink', [Ref('ex'), 'https://example.org/x',
                                                                             'related', 'gopher'])
    rpc('external', 'update', 'title', 'updateExternalTaskLink', [Ref('e'), Ref('el1'), 'Guide'])
    rpc('external', 'update', 'url', 'updateExternalTaskLink', {'task_id': Ref('e'), 'link_id': Ref('el2'),
                                                                'url': 'https://example.org/spec/v2'})
    rpc('external', 'update', 'updated-read', 'getAllExternalTaskLinks', [Ref('e')],
        after=['rpc.external.update.title', 'rpc.external.update.url', 'rpc.external.create.all-sorted'])
    rpc('external', 'update', 'bad-dependency', 'updateExternalTaskLink', {'task_id': Ref('ex'), 'link_id': Ref('elx'),
                                                                           'dependency': 'blocks'})
    rpc('external', 'update', 'bad-dependency-read', 'getExternalTaskLinkById', [Ref('ex'), Ref('elx')],
        after=['rpc.external.update.bad-dependency'])
    rpc('external', 'update', 'wrong-task', 'updateExternalTaskLink', [Ref('a'), Ref('el1'), 'Moved'])
    rpc('external', 'update', 'unchanged', 'getExternalTaskLinkById', [Ref('e'), Ref('el1')],
        after=['rpc.external.update.title'])
    rpc('external', 'remove', 'remove', 'removeExternalTaskLink', [Ref('e'), Ref('el3')])
    rpc('external', 'remove', 'wrong-task', 'removeExternalTaskLink', [Ref('a'), Ref('el4')])
    rpc('external', 'remove', 'remaining', 'getAllExternalTaskLinks', [Ref('e')],
        after=['rpc.external.remove.remove', 'rpc.external.remove.wrong-task', 'rpc.external.update.updated-read'])
    rpc('external', 'remove', 'again', 'removeExternalTaskLink', [Ref('e'), Ref('el3')],
        after=['rpc.external.remove.remove'])

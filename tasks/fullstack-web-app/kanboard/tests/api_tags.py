"""Tags through the JSON-RPC API: project tags and global tags, colours, task tag sets, renaming and removal.

Duplicate, invalid and edge creations and updates act in a project of their own (Tag checks), so that accepting or
refusing one of them never changes the tags the ordinary cases observe; one read shows what that project kept."""
from harness import Ref, subset

PASSWORD = 'Tags-Pass-2026'


def build(suite):
    rpc, fx = suite.rpc, suite.fixture
    fx('base', 'member', 'createUser', {'username': 'tara', 'password': PASSWORD, 'name': 'Tara Tagger'}, save='tara',
       password=PASSWORD)
    fx('base', 'project', 'createProject', {'name': 'Tag project'}, save='p')
    fx('base', 'project2', 'createProject', {'name': 'Other tag project'}, save='p2')
    fx('base', 'membership', 'addProjectUser', [Ref('p'), Ref('tara'), 'project-member'])
    fx('base', 'task', 'createTask', {'title': 'Tagged task', 'project_id': Ref('p')}, save='t')
    fx('base', 'task2', 'createTask', {'title': 'Other tagged task', 'project_id': Ref('p')}, save='t2')
    fx('base', 'checks-project', 'createProject', {'name': 'Tag checks'}, save='pc')
    fx('base', 'checks-tag', 'createTag', [Ref('pc'), 'backend'])
    fx('base', 'checks-tag2', 'createTag', [Ref('pc'), 'checks tag'], save='gx')

    rpc('tags', 'create', 'none', 'getTagsByProject', [Ref('p')])
    rpc('tags', 'create', 'plain', 'createTag', [Ref('p'), 'backend'], save='g1')
    rpc('tags', 'create', 'colored', 'createTag', {'project_id': Ref('p'), 'tag': 'frontend', 'color_id': 'blue'},
        save='g2')
    rpc('tags', 'create', 'unicode', 'createTag', [Ref('p'), 'étiquette ✓'], save='g3')
    rpc('tags', 'create', 'duplicate', 'createTag', [Ref('pc'), 'backend'])
    rpc('tags', 'create', 'duplicate-case', 'createTag', [Ref('pc'), 'Backend'])
    rpc('tags', 'create', 'same-name-other-project', 'createTag', [Ref('p2'), 'backend'], save='g4')
    rpc('tags', 'create', 'invalid-color', 'createTag', [Ref('pc'), 'shiny', 'glitter'])
    rpc('tags', 'create', 'empty-name', 'createTag', [Ref('pc'), ''])
    rpc('tags', 'create', 'global', 'createTag', [0, 'company-wide'], actor='app', save='g0')
    rpc('tags', 'create', 'project-sorted', 'getTagsByProject', [Ref('p')],
        after=['rpc.tags.create.plain', 'rpc.tags.create.colored', 'rpc.tags.create.unicode'])
    def outside_checks(c, tag):
        return str(tag.get('project_id')) != str(c.state.get('pc'))
    rpc('tags', 'create', 'all-admin', 'getAllTags', project=subset(outside_checks, 'tag'),
        after=['rpc.tags.create.project-sorted', 'rpc.tags.create.global', 'rpc.tags.create.same-name-other-project'],
        describe='getAllTags as admin (the tags outside the checks project)')
    rpc('tags', 'create', 'all-member', 'getAllTags', actor='tara', project=subset(outside_checks, 'tag'),
        after=['rpc.tags.create.project-sorted', 'rpc.tags.create.global', 'rpc.tags.create.same-name-other-project'],
        describe='getAllTags as tara (the tags outside the checks project)')
    rpc('tags', 'create', 'global-as-user', 'createTag', [0, 'personal-global'], actor='tara')

    rpc('tags', 'task', 'set', 'setTaskTags', [Ref('p'), Ref('t'), ['backend', 'brand-new']],
        after=['rpc.tags.create.plain'])
    rpc('tags', 'task', 'set-read', 'getTaskTags', [Ref('t')], after=['rpc.tags.task.set'])
    rpc('tags', 'task', 'new-tag-in-project', 'getTagsByProject', [Ref('p')],
        after=['rpc.tags.task.set', 'rpc.tags.create.project-sorted'])
    rpc('tags', 'task', 'set-global', 'setTaskTags', [Ref('p'), Ref('t2'), ['company-wide']],
        after=['rpc.tags.create.global'])
    rpc('tags', 'task', 'set-global-read', 'getTaskTags', [Ref('t2')], after=['rpc.tags.task.set-global'])
    rpc('tags', 'task', 'replace', 'setTaskTags', [Ref('p'), Ref('t'), ['frontend']], after=['rpc.tags.task.set-read'])
    rpc('tags', 'task', 'replace-read', 'getTaskTags', [Ref('t')], after=['rpc.tags.task.replace'])
    rpc('tags', 'task', 'clear', 'setTaskTags', [Ref('p'), Ref('t2'), []], after=['rpc.tags.task.set-global-read'])
    rpc('tags', 'task', 'clear-read', 'getTaskTags', [Ref('t2')], after=['rpc.tags.task.clear'],
        requires=['rpc.tags.task.set-read'])
    rpc('tags', 'task', 'wrong-project', 'setTaskTags', [Ref('p2'), Ref('t'), ['misplaced']])
    rpc('tags', 'task', 'wrong-project-read', 'getTaskTags', [Ref('t')], after=['rpc.tags.task.wrong-project',
                                                                                  'rpc.tags.task.replace-read'])
    rpc('tags', 'task', 'by-member', 'setTaskTags', [Ref('p'), Ref('t2'), ['backend', 'frontend']], actor='tara',
        after=['rpc.tags.task.clear'])
    rpc('tags', 'task', 'by-member-read', 'getTaskTags', [Ref('t2')], actor='tara', after=['rpc.tags.task.by-member'])

    rpc('tags', 'update', 'rename', 'updateTag', [Ref('g1'), 'server-side'])
    rpc('tags', 'update', 'recolor', 'updateTag', {'tag_id': Ref('g2'), 'tag': 'frontend', 'color_id': 'red'})
    rpc('tags', 'update', 'rename-to-existing', 'updateTag', [Ref('gx'), 'backend'])
    rpc('tags', 'update', 'invalid-color', 'updateTag', [Ref('gx'), 'checks tag', 'glitter'])
    rpc('tags', 'update', 'after-updates', 'getTagsByProject', [Ref('p')],
        after=['rpc.tags.update.rename', 'rpc.tags.update.recolor', 'rpc.tags.task.new-tag-in-project'])
    rpc('tags', 'update', 'checks-project-tags', 'getTagsByProject', [Ref('pc')],
        describe='getTagsByProject of the checks project after the duplicate, invalid and edge attempts')
    rpc('tags', 'update', 'task-sees-rename', 'getTaskTags', [Ref('t2')],
        after=['rpc.tags.update.rename', 'rpc.tags.task.by-member-read'])
    rpc('tags', 'remove', 'in-use', 'removeTag', [Ref('g2')], after=['rpc.tags.update.after-updates'])
    rpc('tags', 'remove', 'task-loses-tag', 'getTaskTags', [Ref('t2')], after=['rpc.tags.remove.in-use',
                                                                                'rpc.tags.update.task-sees-rename'])
    rpc('tags', 'remove', 'remaining', 'getTagsByProject', [Ref('p')], after=['rpc.tags.remove.in-use'])
    rpc('tags', 'remove', 'again', 'removeTag', [Ref('g2')], actor='app', after=['rpc.tags.remove.in-use'])

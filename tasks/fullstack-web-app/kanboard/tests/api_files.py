"""Task attachments and task metadata through the JSON-RPC API.

Refused attachments are attempted on a task of their own in a project of their own (File checks), so that accepting
or refusing one of them never changes the attachments and counters the ordinary cases observe."""
from harness import Ref, b64, png

PASSWORD = 'Files-Pass-2026'
BINARY = bytes(range(256)) * 4


def build(suite):
    rpc, fx = suite.rpc, suite.fixture
    fx('base', 'member', 'createUser', {'username': 'fran', 'password': PASSWORD, 'name': 'Fran Files'}, save='fran',
       password=PASSWORD)
    fx('base', 'outsider', 'createUser', {'username': 'finn', 'password': PASSWORD}, save='finn')
    fx('base', 'project', 'createProject', {'name': 'Attachment project'}, save='p')
    fx('base', 'membership', 'addProjectUser', [Ref('p'), Ref('fran'), 'project-member'])
    fx('base', 'task', 'createTask', {'title': 'Task with files', 'project_id': Ref('p')}, save='t')
    fx('base', 'task2', 'createTask', {'title': 'Second task with files', 'project_id': Ref('p')}, save='t2')
    fx('base', 'other-project', 'createProject', {'name': 'Unrelated project'}, save='p2')
    fx('base', 'checks-project', 'createProject', {'name': 'File checks'}, save='pc')
    fx('base', 'checks-task', 'createTask', {'title': 'Attachment checks', 'project_id': Ref('pc')}, save='tc')
    fx('base', 'checks-file', 'createTaskFile', [Ref('pc'), Ref('tc'), 'anchor.txt', b64('anchor')])

    # -- attachments ----------------------------------------------------------------------------------------
    rpc('files', 'files', 'none', 'getAllTaskFiles', [Ref('t')])
    rpc('files', 'files', 'text', 'createTaskFile', [Ref('p'), Ref('t'), 'readme.txt', b64('Read me first\n')],
        save='f1')
    rpc('files', 'files', 'image', 'createTaskFile', [Ref('p'), Ref('t'), 'screen.png', b64(png(4, 3))], save='f2')
    rpc('files', 'files', 'binary', 'createTaskFile', {'project_id': Ref('p'), 'task_id': Ref('t'),
                                                       'filename': 'data.bin', 'blob': b64(BINARY)}, save='f3')
    rpc('files', 'files', 'unicode-name', 'createTaskFile', [Ref('p'), Ref('t'), 'Übersicht 概要.md', b64('# Ü\n')],
        save='f4')
    rpc('files', 'files', 'by-member', 'createTaskFile', [Ref('p'), Ref('t'), 'member.txt', b64('from Fran')],
        actor='fran', save='f5')
    rpc('files', 'files', 'with-creator', 'createTaskFile', [Ref('p'), Ref('t'), 'imported.txt', b64('imported'),
                                                             Ref('fran')], actor='app', save='f6')
    rpc('files', 'files', 'creator-not-member', 'createTaskFile', [Ref('pc'), Ref('tc'), 'stranger.txt', b64('x'),
                                                                   Ref('finn')], actor='app',
        requires=['rpc.files.files.with-creator'])
    rpc('files', 'files', 'wrong-project', 'createTaskFile', [Ref('p2'), Ref('tc'), 'misfiled.txt', b64('x')])
    rpc('files', 'files', 'empty-blob', 'createTaskFile', [Ref('pc'), Ref('tc'), 'empty.txt', ''])
    rpc('files', 'files', 'checks-after-refusals', 'getAllTaskFiles', [Ref('tc')],
        describe='getAllTaskFiles of the checks task after the refused attachments')
    rpc('files', 'files', 'all-sorted', 'getAllTaskFiles', [Ref('t')],
        after=['rpc.files.files.text', 'rpc.files.files.image', 'rpc.files.files.binary',
               'rpc.files.files.unicode-name', 'rpc.files.files.by-member', 'rpc.files.files.with-creator'])
    rpc('files', 'files', 'read-text', 'getTaskFile', [Ref('f1')])
    rpc('files', 'files', 'read-image', 'getTaskFile', [Ref('f2')])
    rpc('files', 'files', 'download-text', 'downloadTaskFile', [Ref('f1')])
    rpc('files', 'files', 'download-image', 'downloadTaskFile', [Ref('f2')])
    rpc('files', 'files', 'download-binary', 'downloadTaskFile', [Ref('f3')])
    rpc('files', 'files', 'download-unicode', 'downloadTaskFile', [Ref('f4')])
    rpc('files', 'files', 'read-missing', 'getTaskFile', [987654], actor='app', requires=['rpc.files.files.read-text'])
    rpc('files', 'files', 'download-missing', 'downloadTaskFile', [987654], actor='app',
        requires=['rpc.files.files.download-text'])
    rpc('files', 'files', 'task-counts', 'getBoard', [Ref('p')],
        project=lambda c, r: {'http': r.status, 'files': sorted(
            [task['title'], task['nb_files']] for lane in r.result for column in lane['columns']
            for task in column['tasks'])}, after=['rpc.files.files.all-sorted'])
    rpc('files', 'remove', 'one', 'removeTaskFile', [Ref('f1')], after=['rpc.files.files.download-text'])
    rpc('files', 'remove', 'one-read', 'getTaskFile', [Ref('f1')], actor='app', after=['rpc.files.remove.one'],
        requires=['rpc.files.files.read-text'])
    rpc('files', 'remove', 'one-again', 'removeTaskFile', [Ref('f1')], actor='app', after=['rpc.files.remove.one'])
    rpc('files', 'remove', 'remaining', 'getAllTaskFiles', [Ref('t')], after=['rpc.files.remove.one',
                                                                              'rpc.files.files.all-sorted'])
    fx('files', 'second-task-file', 'createTaskFile', [Ref('p'), Ref('t2'), 'keep.txt', b64('keep me')])
    rpc('files', 'remove', 'all', 'removeAllTaskFiles', [Ref('t')], after=['rpc.files.remove.remaining'])
    rpc('files', 'remove', 'all-read', 'getAllTaskFiles', [Ref('t')], after=['rpc.files.remove.all'],
        requires=['rpc.files.files.all-sorted'])
    rpc('files', 'remove', 'other-task-kept', 'getAllTaskFiles', [Ref('t2')], after=['rpc.files.remove.all'])
    rpc('files', 'remove', 'all-empty', 'removeAllTaskFiles', [Ref('t')], after=['rpc.files.remove.all'])

    # -- task metadata --------------------------------------------------------------------------------------
    rpc('metadata', 'metadata', 'empty', 'getTaskMetadata', [Ref('t')])
    rpc('metadata', 'metadata', 'save', 'saveTaskMetadata', [Ref('t'), {'sprint': '12', 'owner-team': 'Core',
                                                                        'note': 'café ☕'}])
    rpc('metadata', 'metadata', 'all-sorted', 'getTaskMetadata', [Ref('t')], after=['rpc.metadata.metadata.save'])
    rpc('metadata', 'metadata', 'by-name', 'getTaskMetadataByName', [Ref('t'), 'sprint'],
        after=['rpc.metadata.metadata.save'])
    rpc('metadata', 'metadata', 'by-name-missing', 'getTaskMetadataByName', [Ref('t'), 'velocity'],
        requires=['rpc.metadata.metadata.by-name'])
    rpc('metadata', 'metadata', 'other-task-empty', 'getTaskMetadata', [Ref('t2')],
        requires=['rpc.metadata.metadata.all-sorted'])
    rpc('metadata', 'metadata', 'overwrite', 'saveTaskMetadata', [Ref('t'), {'sprint': '13'}],
        after=['rpc.metadata.metadata.save'])
    rpc('metadata', 'metadata', 'boolean-value', 'saveTaskMetadata', [Ref('t'), {'flag': True}])
    rpc('metadata', 'metadata', 'remove', 'removeTaskMetadata', [Ref('t'), 'owner-team'],
        after=['rpc.metadata.metadata.save'])
    rpc('metadata', 'metadata', 'after-changes', 'getTaskMetadata', [Ref('t')],
        after=['rpc.metadata.metadata.overwrite', 'rpc.metadata.metadata.boolean-value',
               'rpc.metadata.metadata.remove'])
    rpc('metadata', 'metadata', 'remove-missing', 'removeTaskMetadata', [Ref('t'), 'never'])
    rpc('metadata', 'metadata', 'member-saves', 'saveTaskMetadata', [Ref('t2'), {'by': 'Fran'}], actor='fran')
    rpc('metadata', 'metadata', 'member-saved-read', 'getTaskMetadata', [Ref('t2')], actor='fran',
        after=['rpc.metadata.metadata.member-saves'])

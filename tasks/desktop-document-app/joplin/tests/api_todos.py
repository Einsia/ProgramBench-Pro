"""To-do flags, completion, alarm values, trash restoration and restart."""
from harness import Ref, Suite, project, aspects, checked


def build():
    s = Suite('protocol-todos', 'to-dos alarms and persistence')
    def setup(c):
        c.call('POST', '/folders', body={'title': 'Tasks'}, save='book')
        c.call('POST', '/tags', body={'title': 'priority'}, save='tag')
    s.setup('book', setup)
    samples = [
        ('pending', {'is_todo': 1}),
        ('dated', {'is_todo': 1, 'todo_due': 1768550400000}),
        ('completed', {'is_todo': 1, 'todo_completed': 1768478400000}),
        ('complete-dated', {'is_todo': 1, 'todo_due': 1768550400000, 'todo_completed': 1768478400000}),
        ('past-alarm', {'is_todo': 1, 'todo_due': 946684800000}),
        ('future-alarm', {'is_todo': 1, 'todo_due': 4102444800000}),
        ('millisecond', {'is_todo': 1, 'todo_due': 1768550400123}),
        ('normal', {'is_todo': 0}),
    ]
    for key, values in samples:
        title = 'Task ' + key
        s.request('create-' + key, 'Create ' + key + ' to-do state', 'POST', '/notes',
                  body={'title': title, 'body': '- [ ] First\n- [x] Second', 'parent_id': Ref('book'), **values}, save=key,
                  fields=('title', 'body', *values.keys()),
                  expected={'title': title, **values})
        s.request('read-' + key, 'Read the saved ' + key + ' to-do state', 'GET', '/notes/{' + key + '}',
                  query={'fields': 'is_todo,todo_due,todo_completed'}, fields=('is_todo', 'todo_due', 'todo_completed'),
                  depends=('create-' + key,))
    transitions = [
        ('make-todo', {'is_todo': 1}), ('set-alarm', {'todo_due': 1768644000000}),
        ('complete', {'todo_completed': 1768482000000}), ('reopen', {'todo_completed': 0}),
        ('clear-alarm', {'todo_due': 0}), ('make-note', {'is_todo': 0}),
    ]
    last = 'create-normal'
    for key, values in transitions:
        s.request(key, 'Change task state: ' + key, 'PUT', '/notes/{normal}', body=values,
                  fields=('is_todo', 'todo_due', 'todo_completed', 'body'), depends=(last,), expected=values)
        last = key
    def relations(c):
        c.call('POST', '/tags/{tag}/notes', body={'id': Ref('dated')})
        return {'tags': project(c.all('/notes/{dated}/tags', fields='id,title'), ['id', 'title'], c)}
    s.add('tag-todo', 'Tag a to-do', relations, {'tags': 'To-dos support ordinary note tags.'}, depends=('create-dated',))
    def trash(c):
        c.call('DELETE', '/notes/{dated}')
        value = c.call('GET', '/notes/{dated}', query={'fields': 'is_todo,todo_due,todo_completed,deleted_time,title'})['body']
        return aspects(trashed=lambda:checked(value['deleted_time']>0,True),is_todo=lambda:value['is_todo'],
                       alarm=lambda:value['todo_due'],title=lambda:value['title'])
    s.add('trash', 'Move an alarmed to-do to trash', trash,
          {'trashed': 'The note enters trash.', 'is_todo': 'Its to-do flag is retained.',
           'alarm': 'Its alarm metadata is retained.', 'title': 'Its title is retained.'}, depends=('create-dated',))
    def hidden(c):
        return aspects(**{'normal': lambda: project(c.all('/notes', fields='id,title'), ['id', 'title'], c),
                          'including-trash': lambda: project(c.all('/notes', fields='id,title', query={'include_deleted': 1}), ['id', 'title'], c)})
    s.add('trash-filter', 'List active and deleted to-dos', hidden,
          {'normal': 'Ordinary note listing hides trash.', 'including-trash': 'The include_deleted option exposes trash.'},
          depends=('trash',)+tuple('create-'+key for key,_ in samples))
    s.request('restore', 'Restore an alarmed to-do from trash', 'PUT', '/notes/{dated}', body={'deleted_time': 0},
              fields=('deleted_time', 'is_todo', 'todo_due', 'title'), depends=('trash',), expected={'deleted_time': 0})
    def restart(c):
        status = c.broker.call({'op': 'restart'})
        assert status.get('ready'), 'the desktop did not restart'
        c.ready_api()
        return {'running': True}
    s.add('restart', 'Restart with the existing profile', restart, {'running': 'The saved desktop profile can be reopened.'})
    for key, _values in samples:
        s.request('persist-' + key, 'Read saved task state after restart: ' + key, 'GET', '/notes/{' + key + '}',
                  query={'fields': 'id,title,body,parent_id,is_todo,todo_due,todo_completed'},
                  fields=('id', 'title', 'body', 'parent_id', 'is_todo', 'todo_due', 'todo_completed'),
                  depends=('restart','make-note' if key=='normal' else 'restore' if key=='dated' else 'create-'+key))
    def saved_tags(c):
        return {'tags': project(c.all('/notes/{dated}/tags', fields='id,title'), ['id', 'title'], c)}
    s.add('persist-tags', 'Read a to-do tag after restart', saved_tags,
          {'tags': 'Tag associations survive a restart.'}, depends=('restart','tag-todo','restore'))
    return s

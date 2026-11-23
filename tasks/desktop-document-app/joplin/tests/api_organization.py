"""Notebook trees, moves, tags and trash using actual product relations."""
from harness import Ref, Suite, expect, project, aspects, checked


def folders():
    s = Suite('protocol-folders', 'notebook hierarchy and trash')
    s.setup('root', lambda c: c.call('POST', '/folders', body={'title': 'Archive'}, save='root'))
    for key, title in [('ordinary', 'Research'), ('unicode', '資料 — café'), ('spaces', '  Loose Notes  '),
                       ('punctuation', 'Drafts: A/B & "C"'), ('long', 'Notebook ' + 'a' * 180)]:
        s.request(key, 'Create a notebook named ' + title, 'POST', '/folders', body={'title': title}, save=key,
                  fields=('title', 'parent_id', 'type_'), expected={'parent_id': '', 'type_': 2})
        s.request(key + '-read', 'Read the created notebook', 'GET', '/folders/{' + key + '}',
                  query={'fields': 'id,title,parent_id'}, fields=('id', 'title', 'parent_id'), depends=(key,))
        s.request(key + '-rename', 'Rename a notebook without changing its identity', 'PUT', '/folders/{' + key + '}',
                  body={'title': title + ' revised'}, fields=('id', 'title'), depends=(key,),
                  expected={'title': title + ' revised'})
    def tree_setup(c):
        for name, parent, title in [('branch', 'root', 'Branch'), ('leaf', 'branch', 'Leaf'),
                                     ('sibling', 'root', 'Sibling'), ('standalone', None, 'Standalone'),
                                     ('other-child','standalone','Other child')]:
            c.call('POST', '/folders', body={'title': title, **({'parent_id': Ref(parent)} if parent else {})}, save=name)
        for name, book in [('leaf-note', 'leaf'), ('branch-note', 'branch'), ('root-note', 'root')]:
            c.call('POST', '/notes', body={'title': name, 'body': 'Stored in ' + book, 'parent_id': Ref(book)}, save=name)
    s.setup('tree', tree_setup, before='tree')
    def tree(c):
        rows = c.call('GET', '/folders', query={'as_tree': 1, 'fields': 'id,title,parent_id'})['body']
        assert isinstance(rows, list) and rows
        out = []; edges=[]
        def walk(items, parent=''):
            for item in items:
                out.append(item)
                edges.append([c.clean(parent),c.clean(item['id'])])
                walk(item.get('children', []),item['id'])
        walk(rows)
        def nested():
            expect(sorted(edges),sorted([c.clean(i['parent_id']),c.clean(i['id'])] for i in out))
            return sorted(edges)
        return aspects(tree=lambda:project(out,['id','title','parent_id'],c),nested=nested)
    s.add('tree', 'List nested notebooks as a tree', tree,
          {'tree': 'The tree retains each notebook and parent relationship.', 'nested': 'Child notebooks are nested beneath their parent.'},
          depends=tuple(x+'-rename' for x in ('ordinary','unicode','spaces','punctuation','long')))
    for name in ('root', 'branch', 'leaf', 'sibling', 'standalone'):
        def notes(c, name=name):
            response = c.call('GET', '/folders/{' + name + '}/notes', query={'fields': 'id,title,parent_id'})['body']
            return aspects(**{'members': lambda: project(response['items'], ['id', 'title', 'parent_id'], c),
                              'has_more': lambda: response['has_more']})
        s.add('members-' + name, 'List direct notes of notebook ' + name, notes,
              {'members': 'Only direct notes belong to the selected notebook.', 'has_more': 'The complete small list has no further page.'})
    s.request('move-subtree', 'Reparent a notebook with descendants', 'PUT', '/folders/{branch}',
              body={'parent_id': Ref('standalone')}, fields=('id', 'title', 'parent_id'),
              expected={'parent_id': '@standalone'})
    s.add('tree-after-move', 'Read the notebook tree after moving a branch', tree,
          {'tree': 'The moved branch retains its child and notes.', 'nested': 'The branch appears under its new parent.'}, depends=('tree','move-subtree'))
    s.request('leaf-retained', 'Read a grandchild after moving its parent', 'GET', '/folders/{leaf}',
              query={'fields': 'title,parent_id'}, fields=('title', 'parent_id'), depends=('move-subtree',),
              expected={'title': 'Leaf', 'parent_id': '@branch'})
    s.request('move-note', 'Move a note between notebooks', 'PUT', '/notes/{leaf-note}',
              body={'parent_id': Ref('sibling')}, fields=('parent_id', 'title', 'body'),
              expected={'parent_id': '@sibling', 'title': 'leaf-note', 'body': 'Stored in leaf'})
    for field, value in [('icon', '{"type":1,"emoji":"🌲"}'), ('user_data', '{"topic":"fieldwork"}'),
                          ('user_created_time', 1704067200000), ('user_updated_time', 1735689600000)]:
        s.request('property-' + field, 'Set notebook property ' + field, 'PUT', '/folders/{sibling}',
                  body={field: value}, fields=(field, 'title', 'parent_id'),
                  clocks=(field,) if field == 'user_updated_time' else (),
                  expected={field: '@time' if field == 'user_updated_time' else value, 'title': 'Sibling', 'parent_id': '@root'})
    def trash_setup(c):
        c.call('POST', '/folders', body={'title': 'Disposable'}, save='disposable')
        c.call('POST', '/folders', body={'title': 'Nested disposable', 'parent_id': Ref('disposable')}, save='child')
        c.call('POST', '/notes', body={'parent_id': Ref('child'), 'title': 'Inside trash', 'body': 'Recoverable content'}, save='trashed-note')
    s.setup('trash', trash_setup, before='trash-folder')
    s.request('trash-folder', 'Move a notebook and its child to trash', 'DELETE', '/folders/{disposable}', status=True)
    for kind, name in [('folders', 'disposable'), ('folders', 'child'), ('notes', 'trashed-note')]:
        def deleted(c, kind=kind, name=name):
            obj = c.call('GET', '/' + kind + '/{' + name + '}', query={'fields': 'title,deleted_time'})['body']
            return aspects(deleted=lambda:checked(obj['deleted_time']>0,True),title=lambda:obj['title'])
        s.add('deleted-' + name, 'Inspect the trashed ' + name, deleted,
              {'deleted': 'The object has a nonzero deletion time.', 'title': 'The trashed object retains its title.'}, depends=('trash-folder',))
    def filter_trash(c):
        ordinary = c.all('/folders', fields='id,title')
        all_items = c.all('/folders', fields='id,title', query={'include_deleted': 1})
        return aspects(**{'normal': lambda: project(ordinary, ['id', 'title'], c),
                          'including-trash': lambda: project(all_items, ['id', 'title'], c)})
    s.add('filter-trash', 'Compare normal and include_deleted notebook lists', filter_trash,
          {'normal': 'Normal listing omits trashed notebooks.', 'including-trash': 'The include_deleted listing retains trashed notebooks.'},
          depends=('trash-folder','tree-after-move'))
    s.request('restore-folder', 'Restore a notebook by clearing its deletion time', 'PUT', '/folders/{disposable}',
              body={'deleted_time': 0}, fields=('title', 'deleted_time'), depends=('trash-folder',), expected={'deleted_time': 0})
    s.request('purge-folder', 'Permanently delete a notebook tree', 'DELETE', '/folders/{disposable}',
              query={'permanent': 1}, status=True, depends=('restore-folder',))
    s.request('purged-folder-read', 'Read a permanently deleted notebook', 'GET', '/folders/{disposable}',
              status=True, error=True, depends=('purge-folder',), expected={'status': 404})
    return s


def tags():
    s = Suite('protocol-tags', 'tags and many-to-many note relationships')
    def setup(c):
        c.call('POST', '/folders', body={'title': 'Tag fixtures'}, save='book')
        for index in range(5):
            c.call('POST', '/notes', body={'parent_id': Ref('book'), 'title': 'Tagged note ' + str(index),
                   'body': 'Content ' + str(index)}, save='n' + str(index))
    s.setup('notes', setup)
    titles = [('lower', 'research'), ('uppercase', 'FIELDWORK'), ('spaces', '  project planning  '),
              ('unicode', '日本語'), ('accent', 'café'), ('punctuation', 'draft: first & second'),
              ('digits', '2026 archive'), ('long', 'tag ' + 'z' * 150)]
    for key, title in titles:
        s.request('create-' + key, 'Create tag ' + title, 'POST', '/tags', body={'title': title}, save=key,
                  fields=('id', 'title', 'type_'), expected={'type_': 5})
        s.request('read-' + key, 'Read the created tag', 'GET', '/tags/{' + key + '}',
                  query={'fields': 'id,title'}, fields=('id', 'title'), depends=('create-' + key,))
    for tag, ids in [('lower', [0, 1, 3]), ('uppercase', [1, 2]), ('unicode', [0, 2, 4]), ('accent', [4])]:
        for index in ids:
            def link(c, tag=tag, index=index):
                before=c.all('/tags/{'+tag+'}/notes',fields='id,title')
                old_tags=c.all('/notes/{n'+str(index)+'}/tags',fields='id,title')
                c.call('POST', '/tags/{' + tag + '}/notes', body={'id': Ref('n' + str(index))})
                def delta(path, before, new):
                    rows=c.all(path,fields='id,title')
                    target={x['id'] for x in before}|{new}
                    expect({x['id'] for x in rows},target)
                    assert len(rows)==len(target),'duplicate association'
                    return c.clean(new)
                return aspects(notes=lambda:delta('/tags/{'+tag+'}/notes',before,c.values['n'+str(index)]['id']),
                               tags=lambda:delta('/notes/{n'+str(index)+'}/tags',old_tags,c.values[tag]['id']))
            s.add(f'link-{tag}-{index}', f'Associate tag {tag} with note {index}', link,
                  {'notes': 'The tag lists its associated notes.', 'tags': 'The note lists the associated tags.'},
                  depends=('create-' + tag,))
    def duplicate(c):
        before = c.all('/tags/{lower}/notes', fields='id,title')
        c.call('POST', '/tags/{lower}/notes', body={'id': Ref('n0')})
        after = c.all('/tags/{lower}/notes', fields='id,title')
        assert project(before, ['id', 'title'], c) == project(after, ['id', 'title'], c)
        return {'membership': True}
    s.add('duplicate-relation', 'Adding an existing tag relationship is idempotent', duplicate,
          {'membership': 'An existing relation is not duplicated.'}, depends=('link-lower-0',))
    s.request('rename', 'Rename a tag used by several notes', 'PUT', '/tags/{lower}',
              body={'title': 'Revised Research'}, fields=('id', 'title'), depends=('create-lower',))
    for index in (0, 1, 3):
        def read(c, index=index):
            rows = c.all('/notes/{n' + str(index) + '}/tags', fields='id,title')
            return {'tags': project([r for r in rows if r['id']==c.values['lower']['id']], ['id', 'title'], c)}
        s.add('renamed-on-' + str(index), 'Read renamed tag through an associated note', read,
              {'tags': 'Renaming updates the shared tag without breaking its note associations.'}, depends=('rename', f'link-lower-{index}'))
    def detach(c):
        before=c.all('/tags/{lower}/notes',fields='id,title')
        old_tags=c.all('/notes/{n1}/tags',fields='id,title')
        old_body=c.call('GET','/notes/{n1}',query={'fields':'body'})['body']['body']
        c.call('DELETE', '/tags/{lower}/notes/{n1}')
        def unchanged(path,old,removed):
            actual=project(c.all(path,fields='id,title'),['id','title'],c)
            expect(actual,project([x for x in old if x['id']!=removed],['id','title'],c))
            return True
        return aspects(**{'remaining':lambda:unchanged('/tags/{lower}/notes',before,c.values['n1']['id']),
                'other-tags':lambda:unchanged('/notes/{n1}/tags',old_tags,c.values['lower']['id']),
                'note-body':lambda:checked(c.call('GET','/notes/{n1}',query={'fields':'body'})['body']['body'],old_body)})
    s.add('detach', 'Remove one tag from one note', detach,
          {'remaining': 'Other notes keep the tag.', 'other-tags': 'The note keeps its other tags.',
           'note-body': 'Removing a relation preserves the note body.'}, depends=('link-lower-1', 'link-uppercase-1'))
    s.request('delete-tag', 'Delete a tag used by notes', 'DELETE', '/tags/{uppercase}', status=True, depends=('create-uppercase',))
    for index in (1, 2):
        def after_delete(c, index=index):
            return aspects(**{'tags': lambda: not any(x['id']==c.values['uppercase']['id'] for x in c.all('/notes/{n' + str(index) + '}/tags',fields='id')),
                              'body': lambda: c.call('GET', '/notes/{n' + str(index) + '}', query={'fields': 'body'})['body']['body']})
        s.add('after-tag-delete-' + str(index), 'Read a note after deleting its tag', after_delete,
              {'tags': 'The deleted tag is absent from note associations.', 'body': 'Deleting a tag does not delete its note.'}, depends=('delete-tag',),expected={'tags':True})
    s.request('empty-title', 'Create a tag with an empty title', 'POST', '/tags', body={'title': ''},
              fields=('title', 'type_'), expected={'title': '', 'type_': 5})
    for kind, path, body in [('no-note', '/tags/{unicode}/notes', {}),
                              ('missing-tag', '/tags/' + 'f' * 32 + '/notes', {'id': Ref('n0')})]:
        s.request('error-' + kind, 'Reject an invalid tag operation: ' + kind, 'POST', path,
                  body=body, status=True, error=True)
    return s

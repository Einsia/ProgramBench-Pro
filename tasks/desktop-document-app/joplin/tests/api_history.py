"""Revision records, events, API authentication and unsupported operations."""
import json
import time

from harness import Ref, Suite, project, aspects, timestamp, checked


def build():
    s = Suite('protocol-history', 'revisions events and API errors')
    def setup(c):
        c.call('POST', '/folders', body={'title': 'History'}, save='book')
        c.call('POST', '/notes', body={'title': 'Historical note', 'body': 'Current body', 'parent_id': Ref('book')}, save='note')
    s.setup('history', setup)
    for i, title in enumerate(['Original title', 'A revised title', 'Unicode 历史']):
        key = 'revision-' + str(i)
        patch = json.dumps([{'diffs': [[1, title]], 'start1': 0, 'start2': 0, 'length1': 0, 'length2': len(title)}], ensure_ascii=False)
        values = {'item_type': 1, 'item_id': Ref('note'), 'item_updated_time': 1704067200000 + i * 86400000,
                  'title_diff': patch, 'body_diff': '[]', 'metadata_diff': '{"new":{"author":"Ada"},"deleted":[]}'}
        fields = ('id', 'item_type', 'item_id', 'item_updated_time', 'title_diff', 'body_diff', 'metadata_diff')
        s.request(key, 'Create a revision record with a title patch', 'POST', '/revisions', body=values, save=key,
                  fields=fields)
        s.request(key + '-read', 'Read a saved revision record', 'GET', '/revisions/{' + key + '}',
                  query={'fields': ','.join(fields)}, fields=fields, depends=(key,))
    for field, value in [('body_diff', '[{"diffs":[[1,"Old body"]],"start1":0,"start2":0,"length1":0,"length2":8}]'),
                         ('metadata_diff', '{"new":{"author":"Grace","source_url":"https://example.invalid/"},"deleted":[]}'),
                         ('item_updated_time', 1735689600000)]:
        s.request('update-' + field, 'Update revision property ' + field, 'PUT', '/revisions/{revision-1}',
                  body={field: value}, fields=(field, 'item_id'), depends=('revision-1',), expected={field: value})
    def revisions(c):
        rows = c.all('/revisions', fields='id,item_id,item_type,item_updated_time')
        # Automatic revisions can be produced by the product's own maintenance;
        # this case concerns the three records explicitly created above.
        owned = {c.values['revision-' + str(i)]['id'] for i in range(3)}
        return {'records': project([x for x in rows if x['id'] in owned], ['id', 'item_id', 'item_type', 'item_updated_time'], c)}
    s.add('list', 'List explicitly created revisions', revisions,
          {'records': 'The revisions retain their note relationships and version timestamps.'},
          depends=('revision-0', 'revision-1', 'revision-2','update-item_updated_time'))
    for page in (1,2):
        def revision_page(c,page=page):
            value=c.call('GET','/revisions',query={'fields':'id,item_id,item_updated_time','order_by':'item_updated_time',
                                                 'order_dir':'ASC','page':page,'limit':2})['body']
            owned={c.values['revision-'+str(i)]['id'] for i in range(3)}
            return aspects(records=lambda:project([x for x in value['items'] if x['id'] in owned],
                                                   ['id','item_id','item_updated_time'],c,ordered=True))
        s.add('revision-page-'+str(page),'Read a page of revisions ordered by version time',revision_page,
              {'records':'Explicit revision IDs retain their sorted page positions.'},depends=('list',))
    s.request('delete-revision', 'Delete one revision record', 'DELETE', '/revisions/{revision-0}', status=True, depends=('revision-0',))
    s.request('gone-revision', 'Read a deleted revision record', 'GET', '/revisions/{revision-0}', status=True, error=True,
              depends=('delete-revision',), expected={'status': 404})
    s.request('delete-history', 'Delete the history for a note', 'DELETE', '/notes/{note}/revisions', status=True)
    def cleared(c):
        rows = c.all('/revisions', fields='id,item_id')
        return {'remaining': project([x for x in rows if x['item_id'] == c.values['note']['id']], ['id', 'item_id'], c)}
    s.add('history-cleared', 'Read revisions after clearing note history', cleared,
          {'remaining': 'Clearing note history removes that note\'s revisions.'}, depends=('delete-history',), expected={'remaining': []})
    def event_setup(c):
        value = c.call('GET', '/events')['body']
        assert isinstance(value.get('cursor'), str)
        c.values['cursor'] = {'value': value['cursor']}
        c.call('POST', '/notes', body={'title': 'Event note', 'body': 'Original event body', 'parent_id': Ref('book')}, save='event-note')
    s.setup('events', event_setup, before='create-event')
    def events(c, expected_type=1):
        deadline=time.monotonic()+15
        while True:
            value = c.call('GET', '/events', query={'cursor': Ref('cursor', 'value')})['body']
            own = [x for x in value['items'] if x.get('item_id') == c.values['event-note']['id']]
            matching=[x for x in own if x.get('type')==expected_type]
            if matching:
                own=matching
                break
            if time.monotonic()>=deadline:break
            time.sleep(.2)
        if own:c.values['event'] = own[-1]
        return aspects(**{'types': lambda: sorted(set(x['type'] for x in own)),
                          'item-types': lambda: sorted(set(x['item_type'] for x in own)),
                          'cursor-progress': lambda: checked(bool(own),True) and value['cursor'] != c.values['cursor']['value']})
    s.add('create-event', 'Read changes after creating a note', events,
          {'types': 'Creating the note emits a creation event.', 'item-types': 'The event identifies a note.',
           'cursor-progress': 'The opaque change cursor advances.'})
    def event_read(c):
        result = c.call('GET', '/events/' + str(c.values['event']['id']))['body']
        return aspects(item=lambda:c.clean(result['item_id']),type=lambda:result['type'],
                       item_type=lambda:result['item_type'],time=lambda:timestamp(result['created_time']))
    s.add('event-read', 'Read one event by its returned identifier', event_read,
          {'item': 'The event points to the created note.', 'type': 'The event retains its change kind.',
           'item_type': 'The event retains its item category.', 'time': 'The event carries a valid timestamp.'}, depends=('create-event',))
    for key, method, body in [('update', 'PUT', {'body': 'Changed event body'}), ('delete', 'DELETE', None)]:
        def mutation(c, method=method, body=body):
            c.values['cursor'] = {'value': c.call('GET', '/events')['body']['cursor']}
            c.call(method, '/notes/{event-note}', body=body, query={'permanent': 1} if method == 'DELETE' else {})
            return events(c,2 if method=='PUT' else 3)
        s.add(key + '-event', 'Read changes after note ' + key, mutation,
              {'types': 'The change feed reports the note mutation.', 'item-types': 'The event identifies a note.',
               'cursor-progress': 'The change cursor advances after the mutation.'}, depends=('create-event',))
    s.request('invalid-cursor', 'Reject a nonnumeric event cursor', 'GET', '/events', query={'cursor': 'invalid'},
              status=True, error=True, expected={'status': 400})
    def cursor_setup(c):
        c.values['page-cursor']={'value':c.call('GET','/events')['body']['cursor']}
        # The pinned public event endpoint has fixed 100-item pages.
        for i in range(103):
            c.call('POST','/notes',body={'title':'Page event '+str(i),'parent_id':Ref('book')},save='page-note-'+str(i))
    s.setup('event-pages',cursor_setup,before='event-pages')
    def cursor_pages(c):
        start=c.values['page-cursor']['value'];wanted={c.values['page-note-'+str(i)]['id'] for i in range(103)}
        deadline=time.monotonic()+30
        while True:
            cursor=start;found=[];saw_more=False;advances=True
            for _ in range(100):
                response=c.call('GET','/events',query={'cursor':cursor})['body']
                items=response['items'];found += [x for x in items if x.get('item_id') in wanted]
                if items:advances &= response['cursor']!=cursor
                cursor=response['cursor'];saw_more |= bool(response['has_more'])
                if not response['has_more']:break
            if {x['item_id'] for x in found}==wanted or time.monotonic()>=deadline:break
            time.sleep(.3)
        return aspects(notes=lambda:sorted(c.clean(x['item_id']) for x in found),
                       types=lambda:sorted(set(x['item_type'] for x in found)),
                       continuation=lambda:saw_more,cursor_progress=lambda:advances,
                       unique=lambda:len({x['id'] for x in found})==len(found))
    s.add('event-pages','Follow event cursors across the endpoint page boundary',cursor_pages,
          {'notes':'Every created fixture note appears once across the pages.','types':'The feed identifies notes.',
           'continuation':'A nonterminal page announces further events.','cursor_progress':'Each nonempty page advances its cursor.',
           'unique':'Cursor continuation does not duplicate an event.'},
          expected={'notes':sorted('@page-note-'+str(i) for i in range(103)),'types':[1],'continuation':True,
                    'cursor_progress':True,'unique':True})
    for route in ('notes', 'folders', 'tags', 'resources', 'revisions', 'master_keys'):
        s.request(route + '-missing', 'Read a nonexistent ' + route + ' object', 'GET', '/' + route + '/' + 'f' * 32,
                  status=True, error=True, expected={'status': 404})
        s.request(route + '-no-auth', 'Require authentication for ' + route, 'GET', '/' + route,
                  auth=False, status=True, error=True, expected={'status': 403})
        s.request(route + '-bad-auth', 'Reject an invalid token for ' + route, 'GET', '/' + route,
                  token='incorrect-local-token', status=True, error=True, expected={'status': 403})
        s.request(route + '-unknown-link', 'Reject an unknown linked resource on ' + route, 'GET',
                  '/' + route + '/' + 'f' * 32 + '/unknown', status=True, error=True)
    return s

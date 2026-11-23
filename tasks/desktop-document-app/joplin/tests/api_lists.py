"""Pagination, sort direction, ties and field selection across collection routes."""
from harness import Ref, Suite, b64, project, aspects, boolean
from fixtures import png


def build():
    s = Suite('protocol-lists', 'pagination sorting and field projection')
    def setup(c):
        for i, title in enumerate(['List book', 'Beta', 'alpha', 'Gamma', 'Delta', 'Café', '資料']):
            c.call('POST', '/folders', body={'title': title}, save='f' + str(i))
        for i, title in enumerate(['botany', 'travel', 'field', '2026', 'café', '資料', 'draft']):
            c.call('POST', '/tags', body={'title': title}, save='t' + str(i))
        for i, title in enumerate(['Oak', 'elm', 'Birch', 'ASH', 'Cedar', 'Fir', 'Maple', 'Pine', 'Willow', 'Hazel', 'Alder', 'Beech']):
            c.call('POST', '/notes', body={'title': title, 'body': 'Collection member ' + str(i),
                'parent_id': Ref('f0' if i < 9 else 'f1'), 'author': 'Ada' if i % 2 else 'Grace',
                'is_todo': i % 2, 'todo_due': 1704067200000 + ((i * 7) % 12) * 86400000,
                'user_created_time': 1704067200000 + i * 86400000,
                'user_updated_time': 1735689600000 - i * 86400000,
                'latitude': i - 6, 'longitude': 3 * i - 18}, save='n' + str(i))
            c.call('PUT', '/notes/{n' + str(i) + '}', body={'order': ((i * 5) % 12) + .25,
                   'user_updated_time': 1735689600000 - i * 86400000})
            if i < 8:
                c.call('POST', '/tags/{t0}/notes', body={'id': Ref('n' + str(i))})
        for i in range(1, 6):
            c.call('POST', '/tags/{t' + str(i) + '}/notes', body={'id': Ref('n0')})
        for i in range(5):
            c.call('POST', '/resources', multipart={'filename': 'image-' + str(i) + '.png', 'base64': b64(png(20+i, 16+i)),
                   'props': {'title': 'Image ' + str(4-i)}}, save='r' + str(i))
        body = '\n'.join('![image](:/' + c.values['r' + str(i)]['id'] + ')' for i in range(5))
        c.call('PUT', '/notes/{n0}', body={'body': body, 'user_updated_time': 1735689600000})
    s.setup('collections', setup)
    routes = [('notes', '/notes', 12), ('folders', '/folders', 7), ('tags', '/tags', 7),
              ('resources', '/resources', 5), ('folder-notes', '/folders/{f0}/notes', 9),
              ('tag-notes', '/tags/{t0}/notes', 8), ('note-tags', '/notes/{n0}/tags', 6),
              ('note-resources', '/notes/{n0}/resources', 5)]
    for name, path, count in routes:
        pages = [(1, 1), (1, count), (2, 2), (2, (count + 1) // 2), (count + 1, 1), (1, 100), (1, 0)]
        for index, (page, limit) in enumerate(pages):
            def listing(c, path=path, page=page, limit=limit):
                result = c.call('GET', path, query={'page': page, 'limit': limit, 'order_by': 'title', 'order_dir': 'ASC',
                                                   'fields': 'id,title'})['body']
                assert isinstance(result, dict)
                return aspects(**{'items': lambda: project(result['items'], ['id', 'title'], c, ordered=True),
                                  'has_more': lambda: boolean(result['has_more'])})
            s.add(name + '-page-' + str(index), f'Paginate {name}: page {page}, limit {limit}', listing,
                  {'items': 'The requested page has the expected members and order.', 'has_more': 'The continuation flag matches the page boundary.'})
        for direction in ('ASC', 'DESC'):
            def ordered(c, path=path, direction=direction):
                result = c.call('GET', path, query={'order_by': 'title', 'order_dir': direction, 'fields': 'id,title'})['body']
                return {'order': project(result['items'], ['id', 'title'], c, ordered=True)}
            s.add(name + '-sort-' + direction.lower(), f'Sort {name} by title {direction}', ordered,
                  {'order': 'The collection follows the requested case-insensitive title order.'})
        for field in ('id', 'title'):
            def projection(c, path=path, field=field):
                result = c.call('GET', path, query={'fields': field, 'order_by': 'title'})['body']
                return {'values': project(result['items'], [field], c)}
            s.add(name + '-field-' + field, f'Select {field} from every member of {name}', projection,
                  {'values': 'Each member returns the selected field, independent of unrequested fields.'})
    for field in ('user_created_time', 'user_updated_time', 'todo_due', 'order', 'latitude', 'longitude', 'author', 'is_todo'):
        for direction in ('ASC', 'DESC'):
            def ordered_notes(c, field=field, direction=direction):
                result = c.call('GET', '/notes', query={'fields': 'id,title,' + field, 'order_by': field,
                                                       'order_dir': direction})['body']['items']
                # Ties have no contractual internal order; retain each group in
                # order and compare its members as a set with multiplicity.
                groups = []
                for item in result:
                    assert field in item
                    value = item[field]
                    if not groups or value != groups[-1][0]:
                        groups.append([value, []])
                    groups[-1][1].append(c.clean(item['title']))
                for group in groups:
                    group[1].sort()
                return {'groups': groups}
            s.add('notes-sort-' + field + '-' + direction.lower(), f'Sort notes by {field} {direction}', ordered_notes,
                  {'groups': 'Notes follow the requested property order; equal keys may appear in either order.'})
    for name, path, _count in routes[:4]:
        for limit in (-1, 101):
            s.request(name + '-limit-' + str(limit).replace('-', 'minus'), 'Reject an out-of-range page limit for ' + name,
                      'GET', path, query={'limit': limit}, status=True, error=True, expected={'status': 400})
    return s

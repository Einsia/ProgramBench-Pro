'''Managing recipe organizers and ingredient reference data through the user interface.'''
from specification import api, read, step

KINDS = [
    ('categories', 'category', 'organizers/categories', {'Name': 'Weeknight Meals'}, {'name': 'Weeknight Meals'}),
    ('tags', 'tag', 'organizers/tags', {'Name': 'Quick & Easy'}, {'name': 'Quick & Easy'}),
    ('tools', 'tool', 'organizers/tools', {'Name': 'Cast Iron Pan'}, {'name': 'Cast Iron Pan'}),
    ('foods', 'food', 'foods', {'Name': 'chickpea', 'Plural Name': 'chickpeas', 'Description': 'Dried pantry beans'},
     {'name': 'chickpea', 'pluralName': 'chickpeas', 'description': 'Dried pantry beans'}),
    ('units', 'unit', 'units', {'Name': 'tablespoon', 'Plural Name': 'tablespoons', 'Abbreviation': 'tbsp'},
     {'name': 'tablespoon', 'pluralName': 'tablespoons', 'abbreviation': 'tbsp'}),
    ('labels', 'shopping label', 'groups/labels', {'Name': 'Produce'}, {'name': 'Produce'}),
]


def build(add):
    for kind, singular, endpoint, form, expected in KINDS:
        name, renamed = expected['name'], expected['name'] + ' revised'
        route = '/group/data/' + kind
        setup = [api('distractor', 'POST', endpoint, {'name': 'Unrelated entry'})]
        fields = list(expected)
        actions = [{'op': 'goto', 'path': route}, {'op': 'button', 'name': 'Create'}]
        actions += [{'op': 'fill', 'label': k, 'value': v} for k, v in form.items()]
        actions += [{'op': 'button', 'name': 'Confirm'}, {'op': 'goto', 'path': route}]
        steps = [step('create', 'Create a ' + singular + ' with these values: ' + '; '.join(k + ' = "' + v + '"' for k, v in form.items()) + '.',
                      'The new ' + singular + ' is visible with its supplied values in the managed data.', actions,
                      [read(endpoint, fields, expected, where={'name': name})], visible=[name])]
        steps.append(step('rename', 'Rename the ' + singular + ' "' + name + '" to "' + renamed + '".',
                          'The managed entry displays its new name and keeps its other supplied values.',
                          [{'op': 'goto', 'path': route}, {'op': 'table-action', 'name': name, 'action': 'edit'},
                           {'op': 'fill', 'label': 'Name', 'value': renamed}, {'op': 'button', 'name': 'Confirm'},
                           {'op': 'goto', 'path': route}],
                          [read(endpoint, fields, {**expected, 'name': renamed}, where={'name': renamed})],
                          visible=[renamed], depends=['create']))
        steps.append(step('search', 'Search the ' + singular + ' data for "' + renamed + '".',
                          'The search results show the renamed entry and exclude "Unrelated entry".',
                          [{'op': 'goto', 'path': route}, {'op': 'fill', 'label': 'Search', 'value': renamed},
                           {'op': 'wait'}], visible=[renamed], depends=['rename']))
        steps.append(step('delete', 'Delete the ' + singular + ' "' + renamed + '" and return to the full data list.',
                          'The data list retains "Unrelated entry" and no longer contains the deleted entry.',
                          [{'op': 'goto', 'path': route}, {'op': 'table-action', 'name': renamed, 'action': 'delete'},
                           {'op': 'button', 'name': 'Confirm'}, {'op': 'goto', 'path': route}],
                          [read(endpoint, ['name'], [{'name': 'Unrelated entry'}], collection=True)],
                          visible=['Unrelated entry'], depends=['rename']))
        add('data-' + kind, 'manage-' + kind, setup, steps)

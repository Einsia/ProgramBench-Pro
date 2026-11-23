'''Recipe lifecycle, structured editing, organization, social activity and persistence.'''
from specification import api, recipe, read, step

PATH = '/g/home/r/tomato-soup'

def go(path): return {'op': 'goto', 'path': path}
def button(name, **kw): return {'op': 'button', 'name': name, **kw}
def fill(label, value, **kw): return {'op': 'fill', 'label': label, 'value': value, **kw}
def edit(*actions): return [go(PATH + '?edit=true'), *actions, button('Save'), go(PATH)]
def observe(fields, expected, slug='tomato-soup'): return read('recipes/' + slug, fields, expected)


def build(add):
    add('recipe-lifecycle', 'recipe-lifecycle', recipe('Apple Pie', 'apple-pie'), [
        step('create', 'Create a recipe named "Tomato Soup".', 'The new Tomato Soup recipe is available and its recipe page shows its name.',
             [go('/g/home/r/create/new'), fill('Recipe Name', 'Tomato Soup'), button('Create'), go(PATH)],
             [observe(['name'], {'name': 'Tomato Soup'})], visible=['Tomato Soup']),
        step('overview', 'Set Tomato Soup to 4 servings with yield text "bowls" and description "A warming tomato soup for rainy days.".',
             'The recipe shows its new description and serving/yield information.',
             edit(fill('Servings', '4'), fill('Yield Text', 'bowls'), fill('Description', 'A warming tomato soup for rainy days.')),
             [observe(['description', 'recipeServings', 'recipeYield'], {'description': 'A warming tomato soup for rainy days.', 'recipeServings': 4, 'recipeYield': 'bowls'})],
             visible=['A warming tomato soup for rainy days.'], depends=['create']),
        step('rename', 'Rename Tomato Soup to "Roasted Tomato Soup".', 'The recipe is displayed under its new name.',
             [go(PATH + '?edit=true'), fill('Recipe Name', 'Roasted Tomato Soup'), button('Save'), go('/g/home/r/roasted-tomato-soup')],
             [observe(['name'], {'name': 'Roasted Tomato Soup'}, 'roasted-tomato-soup')], visible=['Roasted Tomato Soup'], depends=['overview']),
        step('delete', 'Delete Roasted Tomato Soup and return to the recipe collection.',
             'The collection still offers Apple Pie and no longer offers Roasted Tomato Soup.',
             [go('/g/home/r/roasted-tomato-soup?edit=true'), button('Delete'), button('Confirm'), go('/g/home')],
             [read('recipes', ['name'], [{'name': 'Apple Pie'}], collection=True)], visible=['Apple Pie'], depends=['rename']),
    ])
    fixture = recipe(extra={'recipeIngredient': [{'quantity': 2, 'note': 'ripe tomatoes'}],
                            'recipeInstructions': [{'summary': 'Prepare', 'text': 'Chop the tomatoes.'}],
                            'notes': [{'title': 'Storage', 'text': 'Keep refrigerated.'}]})
    add('recipe-content', 'recipe-content', fixture, [
        step('ingredients', 'Change the first ingredient of Tomato Soup to quantity 3 and note "large ripe tomatoes".',
             'The saved recipe presents the updated tomato ingredient.',
             edit({'op': 'fill', 'placeholder': 'Quantity', 'value': '3'}, {'op': 'fill', 'placeholder': 'Notes', 'value': 'large ripe tomatoes'}),
             [observe(['recipeIngredient.0.quantity', 'recipeIngredient.0.note'], {'recipeIngredient.0.quantity': 3, 'recipeIngredient.0.note': 'large ripe tomatoes'})], visible=['large ripe tomatoes']),
        step('instructions', 'Replace the first instruction with summary "Simmer" and text "Simmer gently for twenty minutes.".',
             'The recipe displays the new instruction summary and its text.',
             edit({'op': 'fill', 'placeholder': 'Step: 1', 'value': 'Simmer'}, {'op': 'fill', 'tag': 'textarea', 'nth': 1, 'value': 'Simmer gently for twenty minutes.'}),
             [observe(['recipeInstructions.0.summary', 'recipeInstructions.0.text'], {'recipeInstructions.0.summary': 'Simmer', 'recipeInstructions.0.text': 'Simmer gently for twenty minutes.'})], visible=['Simmer gently for twenty minutes.']),
        step('notes', 'Change the existing storage note to title "Freezing" and text "Freeze in small portions for up to one month.".',
             'The saved recipe displays the Freezing note with its new text.',
             edit(fill('Title', 'Freezing'), {'op': 'fill', 'tag': 'textarea', 'placeholder': 'Note', 'value': 'Freeze in small portions for up to one month.'}),
             [observe(['notes.0.title', 'notes.0.text'], {'notes.0.title': 'Freezing', 'notes.0.text': 'Freeze in small portions for up to one month.'})], visible=['Freezing', 'Freeze in small portions for up to one month.']),
        step('source', 'Set Tomato Soup\'s original URL to "https://example.invalid/soup".',
             'The recipe makes its new source URL available as a link.', edit(fill('Original URL', 'https://example.invalid/soup')),
             [observe(['orgURL'], {'orgURL': 'https://example.invalid/soup'})]),
        step('duplicate', 'Duplicate Tomato Soup as a recipe named "Soup for Guests".',
             'Soup for Guests is a separate recipe with the copied ingredients, instructions and notes.',
             [{'op': 'recipe-menu', 'slug': 'tomato-soup', 'name': 'Duplicate'}, fill('Recipe Name', 'Soup for Guests'), button('Confirm'), go('/g/home/r/soup-for-guests')],
             [observe(['name', 'recipeIngredient.0.note', 'recipeInstructions.0.text', 'notes.0.title'],
                      {'name': 'Soup for Guests', 'recipeIngredient.0.note': 'large ripe tomatoes', 'recipeInstructions.0.text': 'Simmer gently for twenty minutes.', 'notes.0.title': 'Freezing'}, 'soup-for-guests')],
             visible=['Soup for Guests'], depends=['ingredients', 'instructions', 'notes']),
    ])
    setup = recipe() + [api('category', 'POST', 'organizers/categories', {'name': 'Dinner'}, save='category'),
                        api('tag', 'POST', 'organizers/tags', {'name': 'Vegetarian'}, save='tag'),
                        api('tool', 'POST', 'organizers/tools', {'name': 'Stockpot'}, save='tool')]
    steps=[]
    for key,label,name,field in [('category','Categories','Dinner','recipeCategory'),('tag','Tags','Vegetarian','tags'),('tool','Tools','Stockpot','tools')]:
        steps.append(step(key, 'Assign '+('category' if key=='category' else key)+' "'+name+'" to Tomato Soup.',
                          'The saved recipe displays its '+key+' association with '+name+'.',
                          edit({'op':'autocomplete','tag':'input','label':label,'value':name}),
                          [observe([field+'.0.name'], {field+'.0.name':name})],visible=[name]))
    add('recipe-organizers','recipe-organizers',setup,steps)
    setup=recipe()+[api('me','GET','users/self',save='me'),api('soup','GET','recipes/tomato-soup',save='soup')]
    add('recipe-social','recipe-social',setup,[
        step('rating','Give Tomato Soup a rating of 4 out of 5.','The recipe visibly shows the selected four-star rating.',
             [go(PATH),{'op':'click','tag':'button','aria':'Rating 4 of 5'}],
             [read('users/self/ratings/{{soup.id}}',['rating'],{'rating':4})]),
        step('favorite','Add Tomato Soup to your favorites and open your favorite recipes.','Tomato Soup is listed among the current user\'s favorites.',
             [go(PATH),{'op':'click','tag':'button','region':[1070,250,1125,420]},go('/user/{{me.id}}/favorites')],
             [read('users/self/ratings/{{soup.id}}',['isFavorite'],{'isFavorite':True})],visible=['Tomato Soup']),
        step('comment','Add the comment "Delicious with fresh basil!" to Tomato Soup.','The recipe conversation displays the new comment attributed to the signed-in user.',
             [go(PATH),{'op':'fill','placeholder':'Join the Conversation','value':'Delicious with fresh basil!'},button('Submit')],
             [read('recipes/tomato-soup/comments',['text'],{'text':'Delicious with fresh basil!'},where={'text':'Delicious with fresh basil!'})],visible=['Delicious with fresh basil!']),
        step('made','Record that you made Tomato Soup today, with the note "Served for the family.".',
             'The recipe records today as its last-made date and shows the cooking event in its timeline.',
             [go(PATH),{'op':'click','tag':'button','has':'Last Made'},fill('Comment','Served for the family.'),button('Add to Timeline'),go('/g/home/recipes/timeline')],
             [read('recipes/timeline/events',['eventMessage'],{'eventMessage':'Served for the family.'},where={'eventMessage':'Served for the family.'})],visible=['Served for the family.']),
    ])
    add('recipe-persistence','recipe-persistence',recipe(),[
        step('save','Set the description of Tomato Soup to "Remember this soup after a restart.".',
             'The recipe displays the saved description.',edit(fill('Description','Remember this soup after a restart.')),
             [observe(['description'],{'description':'Remember this soup after a restart.'})],visible=['Remember this soup after a restart.']),
        step('restart','The application has been restarted. Reopen Tomato Soup.',
             'The saved recipe description survives the restart and is shown again.',[go(PATH)],
             [observe(['description'],{'description':'Remember this soup after a restart.'})],visible=['Remember this soup after a restart.'],depends=['save'],lifecycle='restart'),
    ])

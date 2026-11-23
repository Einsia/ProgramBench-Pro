'''Files and data movement: recipe images and assets, exports, zip and JSON-LD import, the ingredient parser, seeders,
migrations from other managers, site backups, maintenance and the application information.

Every fixture file is built here from fixed bytes. Images are decoded and compared by dimensions and colors;
exports, imports and site backups retain normalized JSON and member content.
'''
import base64
import io
import json
import struct
import zipfile
import zlib

from harness import Ref, pathref


def png(width=4, height=4, rgb=(200, 40, 40)):
    '''A small solid-colour PNG.'''
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    raw = b''.join(b'\x00' + bytes(rgb) * width for _ in range(height))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def pattern_png(width=240, height=160):
    """Four colored regions make damaged/wrong images distinguishable after re-encoding."""
    colors = [(208, 40, 40), (40, 184, 72), (40, 72, 208), (224, 192, 40)]
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    raw = b''.join(b'\x00' + b''.join(bytes(colors[(y >= height // 2) * 2 + (x >= width // 2)])
                                   for x in range(width)) for y in range(height))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def zipped(members):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in members.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            z.writestr(info, data)
    return buf.getvalue()


def upload(name, data, mime):
    return {'filename': name, 'base64': base64.b64encode(data).decode(), 'mime_type': mime}


JSONLD = {
    '@context': 'https://schema.org', '@type': 'Recipe', 'name': 'Lentil Stew', 'description': 'Hearty and warm',
    'recipeYield': '4 servings', 'prepTime': 'PT15M', 'cookTime': 'PT45M', 'totalTime': 'PT1H',
    'recipeCategory': 'Dinner', 'keywords': 'vegan, winter',
    'recipeIngredient': ['1 cup red lentils', '2 carrots, diced', '1 onion'],
    'recipeInstructions': [{'@type': 'HowToStep', 'text': 'Chop the vegetables.'},
                           {'@type': 'HowToStep', 'text': 'Simmer everything for 45 minutes.'}],
    'nutrition': {'@type': 'NutritionInformation', 'calories': '320 kcal'},
}

NEXTCLOUD = {'name': 'Lemon Cake', 'description': 'Zesty', 'recipeYield': '8', 'keywords': 'cake,citrus',
             'recipeIngredient': ['2 lemons', '1 cup sugar'], 'recipeInstructions': ['Mix', 'Bake'],
             'prepTime': 'PT20M', 'cookTime': 'PT40M', 'totalTime': 'PT1H'}

CHOWDOWN = ('---\nlayout: recipe\ntitle: "Garlic Bread"\nimage: \ntags: bread, side\n\ningredients:\n- 1 baguette\n'
            '- 4 cloves garlic\n- 50 g butter\n\ndirections:\n- Mash garlic with butter.\n- Spread and toast.\n---\n\n'
            'Crisp and fragrant.\n')


def build(s):
    a = s.api
    image = pattern_png()

    f = 'files-fixture'
    a(f, 'recipes', 'soup', 'POST', 'recipes', body={'name': 'Tomato Soup'})
    a(f, 'recipes', 'pie', 'POST', 'recipes', body={'name': 'Apple Pie'})
    a(f, 'recipes', 'soup-read', 'GET', 'recipes/tomato-soup', save='soup')
    a(f, 'recipes', 'pie-read', 'GET', 'recipes/apple-pie', save='pie')
    a(f, 'recipes', 'self', 'GET', 'users/self', save='me')

    fam = 'recipe-images'
    sc = 'upload'
    a(fam, sc, 'png', 'PUT', 'recipes/tomato-soup/image', status=200,
      multipart={'fields': {'extension': 'png'}, 'files': {'image': upload('soup.png', image, 'image/png')}})
    a(fam, sc, 'recipe-has-image', 'GET', 'recipes/tomato-soup', fields=['slug', 'image'])
    a(fam, sc, 'missing-recipe', 'PUT', 'recipes/no-such-recipe/image', status=None,
      multipart={'fields': {'extension': 'png'}, 'files': {'image': upload('x.png', image, 'image/png')}})
    a(fam, sc, 'no-file', 'PUT', 'recipes/tomato-soup/image', status=422, multipart={'fields': {'extension': 'png'}})
    a(fam, sc, 'anonymous', 'PUT', 'recipes/tomato-soup/image', actor=None, status=401,
      multipart={'fields': {'extension': 'png'}, 'files': {'image': upload('x.png', image, 'image/png')}})
    sc = 'media'
    for name in ('original.webp', 'min-original.webp', 'tiny-original.webp'):
        a(fam, sc, name, 'GET', pathref('media/recipes/{id}/images/' + name, id=Ref('soup', 'id')), actor=None,
          status=200, hint='image')
    a(fam, sc, 'bad-name', 'GET', pathref('media/recipes/{id}/images/other.webp', id=Ref('soup', 'id')), actor=None,
      status=422)
    a(fam, sc, 'no-image-recipe', 'GET', 'media/recipes/00000000-0000-4000-8000-000000000000/images/original.webp',
      actor=None, status=None)
    sc = 'clear'
    a(fam, sc, 'delete', 'DELETE', 'recipes/tomato-soup/image', status=None, hint='none')
    a(fam, sc, 'recipe-after', 'GET', 'recipes/tomato-soup', fields=['slug', 'image'])

    fam = 'recipe-assets'
    sc = 'upload'
    a(fam, sc, 'text', 'POST', 'recipes/apple-pie/assets', status=200, save='asset',
      multipart={'fields': {'name': 'Shopping notes', 'icon': 'mdi-file', 'extension': 'txt'},
                 'files': {'file': upload('notes.txt', b'Buy apples\nBuy butter\n', 'text/plain')}})
    a(fam, sc, 'recipe-lists-asset', 'GET', 'recipes/apple-pie', fields=['slug', 'assets'])
    a(fam, sc, 'download', 'GET', pathref('media/recipes/{id}/assets/{name}', id=Ref('pie', 'id'),
                                          name=Ref('asset', 'fileName')), actor=None, status=200, hint='bytes')
    a(fam, sc, 'missing-file', 'GET', pathref('media/recipes/{id}/assets/nothing.txt', id=Ref('pie', 'id')),
      actor=None, status=None)
    a(fam, sc, 'no-name', 'POST', 'recipes/apple-pie/assets', status=422,
      multipart={'fields': {'icon': 'mdi-file', 'extension': 'txt'},
                 'files': {'file': upload('n.txt', b'x', 'text/plain')}})

    fam = 'recipe-exports'
    sc = 'formats'
    a(fam, sc, 'list', 'GET', 'recipes/exports', status=200)
    a(fam, sc, 'json', 'GET', 'recipes/apple-pie/exports', params={'template_name': 'raw'}, status=200)
    # The public export endpoint selects the archive by template_name. The old
    # /exports/zip path is an HTML fallback and does not exercise ZIP export.
    a(fam, sc, 'zip', 'GET', 'recipes/apple-pie/exports', params={'template_name': 'zip'},
      status=200, hint='zip')
    a(fam, sc, 'missing-recipe', 'GET', 'recipes/no-such-recipe/exports', params={'template_name': 'raw'},
      status=None)

    fam = 'recipe-import'
    sc = 'json-ld'
    a(fam, sc, 'create', 'POST', 'recipes/create/html-or-json', status=201,
      body={'data': json.dumps(JSONLD), 'includeTags': True, 'includeCategories': True})
    a(fam, sc, 'read', 'GET', 'recipes/lentil-stew',
      fields=['name', 'slug', 'description', 'recipeYield', 'recipeYieldQuantity', 'recipeServings', 'prepTime',
              'performTime', 'totalTime', 'recipeIngredient', 'recipeInstructions', 'tags', 'recipeCategory',
              'nutrition'])
    a(fam, sc, 'html', 'POST', 'recipes/create/html-or-json', status=201,
      body={'data': '<html><head><script type="application/ld+json">'
                    + json.dumps(dict(JSONLD, name='Pea Soup', keywords='green')) + '</script></head><body></body>'
                    '</html>', 'includeTags': True})
    a(fam, sc, 'html-read', 'GET', 'recipes/pea-soup', fields=['name', 'slug', 'tags', 'recipeIngredient'])
    a(fam, sc, 'no-recipe', 'POST', 'recipes/create/html-or-json', status=None,
      body={'data': '<html><body><p>No recipe here</p></body></html>'})
    a(fam, sc, 'missing-data', 'POST', 'recipes/create/html-or-json', status=422, body={})
    sc = 'zip'
    zip_export = zipped({'apple-crumble.json': json.dumps({'name': 'Apple Crumble', 'slug': 'apple-crumble',
                                                             'description': 'From a zip',
                                                             'recipeIngredient': [{'note': '3 apples'}],
                                                             'recipeInstructions': [{'text': 'Bake it'}]})})
    a(fam, sc, 'create', 'POST', 'recipes/create/zip', status=None,
      multipart={'files': {'archive': upload('apple-crumble.zip', zip_export, 'application/zip')}})
    a(fam, sc, 'read', 'GET', 'recipes/apple-crumble', status=None,
      fields=['name', 'slug', 'description', 'recipeIngredient', 'recipeInstructions'])

    fam = 'ingredient-parser'
    sc = 'parse'
    for key, text in (('cups-flour', '2 cups flour, sifted'), ('fraction', '1 1/2 tablespoons olive oil'),
                      ('no-unit', '3 eggs'), ('note-only', 'salt to taste'), ('grams', '250 g butter')):
        a(fam, sc, key, 'POST', 'parser/ingredient', status=200, body={'parser': 'nlp', 'ingredient': text})
        a(fam, 'brute', key, 'POST', 'parser/ingredient', status=200, body={'parser': 'brute', 'ingredient': text})
    a(fam, sc, 'many', 'POST', 'parser/ingredients', status=200,
      body={'parser': 'nlp', 'ingredients': ['1 onion', '2 cloves garlic, minced', '1 can tomatoes']})
    a(fam, sc, 'unknown-parser', 'POST', 'parser/ingredient', status=422,
      body={'parser': 'magic', 'ingredient': '1 egg'})
    a(fam, sc, 'anonymous', 'POST', 'parser/ingredient', actor=None, status=401,
      body={'parser': 'nlp', 'ingredient': '1 egg'})

    fam = 'seeders'
    sc = 'seed'
    for kind in ('units', 'foods'):
        a(fam, sc, kind, 'POST', 'groups/seeders/' + kind, status=200, body={'locale': 'en-US'})
    a(fam, sc, 'units-listed', 'GET', 'units', params={'orderBy': 'name', 'perPage': 50},
      fields=['name', 'pluralName', 'abbreviation', 'fraction'])
    a(fam, sc, 'foods-total', 'GET', 'foods', params={'perPage': 1}, fields=['name'])
    a(fam, sc, 'bad-locale', 'POST', 'groups/seeders/units', status=None, body={'locale': 'xx-XX'})

    fam = 'migrations'
    sc = 'nextcloud'
    nc = zipped({'nextcloud/Lemon Cake/recipe.json': json.dumps(NEXTCLOUD)})
    a(fam, sc, 'run', 'POST', 'groups/migrations', status=200, save='nc-report',
      multipart={'fields': {'migration_type': 'nextcloud'},
                 'files': {'archive': upload('nextcloud.zip', nc, 'application/zip')}})
    a(fam, sc, 'recipe', 'GET', 'recipes/lemon-cake',
      fields=['name', 'slug', 'description', 'recipeYield', 'recipeYieldQuantity', 'tags', 'recipeIngredient',
              'recipeInstructions', 'prepTime', 'performTime', 'totalTime'])
    a(fam, sc, 'report', 'GET', pathref('groups/reports/{id}', id=Ref('nc-report', 'id')), status=200)
    sc = 'chowdown'
    cd = zipped({'chowdown/_recipes/garlic-bread.md': CHOWDOWN})
    a(fam, sc, 'run', 'POST', 'groups/migrations', status=200, save='cd-report',
      multipart={'fields': {'migration_type': 'chowdown'},
                 'files': {'archive': upload('chowdown.zip', cd, 'application/zip')}})
    a(fam, sc, 'recipe', 'GET', 'recipes/garlic-bread', status=None,
      fields=['name', 'slug', 'description', 'tags', 'recipeIngredient', 'recipeInstructions'])
    a(fam, sc, 'report', 'GET', pathref('groups/reports/{id}', id=Ref('cd-report', 'id')), status=200)
    sc = 'reports'
    a(fam, sc, 'list', 'GET', 'groups/reports', params={'report_type': 'migration'}, status=200)
    a(fam, sc, 'delete', 'DELETE', pathref('groups/reports/{id}', id=Ref('cd-report', 'id')), status=None)
    a(fam, sc, 'list-after', 'GET', 'groups/reports', params={'report_type': 'migration'}, status=200)
    a(fam, sc, 'unknown-type', 'POST', 'groups/migrations', status=422,
      multipart={'fields': {'migration_type': 'cookbook9000'},
                 'files': {'archive': upload('x.zip', nc, 'application/zip')}})

    fam = 'admin-info'
    sc = 'about'
    a(fam, sc, 'statistics', 'GET', 'admin/about/statistics', status=200)
    a(fam, sc, 'check', 'GET', 'admin/about/check', status=200)
    a(fam, sc, 'about', 'GET', 'admin/about', status=200,
      fields=['production', 'version', 'demoStatus', 'allowSignup', 'defaultGroup', 'defaultHousehold',
              'enableOidc', 'oidcRedirect'])
    a(fam, sc, 'app-about', 'GET', 'app/about', actor=None, status=200)
    a(fam, sc, 'startup', 'GET', 'app/about/startup-info', actor=None, status=200)
    a(fam, sc, 'theme', 'GET', 'app/about/theme', actor=None, status=200)
    a(fam, sc, 'non-admin', 'GET', 'admin/about/statistics', actor=None, status=401)
    a(fam, sc, 'storage', 'GET', 'groups/storage', status=200)
    sc = 'maintenance'
    a(fam, sc, 'summary', 'GET', 'admin/maintenance', status=200)
    a(fam, sc, 'clean-temp', 'POST', 'admin/maintenance/clean/temp', status=200)
    a(fam, sc, 'clean-images', 'POST', 'admin/maintenance/clean/images', status=200)
    a(fam, sc, 'clean-folders', 'POST', 'admin/maintenance/clean/recipe-folders', status=200)
    a(fam, sc, 'docker-validate', 'GET', 'media/docker/validate.txt', actor=None, status=None)

    fam = 'backups'
    sc = 'site'
    # New accounts receive one of three random bundled avatars. Replace it through
    # the public upload before comparing the backup's actual image content.
    a(f, 'backup', 'avatar', 'POST', pathref('users/{u}/image', u=Ref('me', 'id')),
      multipart={'files': {'profile': upload('backup-avatar.png', pattern_png(180, 180), 'image/png')}})
    a(fam, sc, 'create', 'POST', 'admin/backups', status=201)
    a(fam, sc, 'list', 'GET', 'admin/backups', status=200, save='backups')
    a(fam, sc, 'token', 'GET', pathref('admin/backups/{n}', n=Ref('backups', 'imports', 0, 'name')), status=200,
      save='backup-token')
    a(fam, sc, 'download', 'GET', pathref('utils/download?token={t}', t=Ref('backup-token', 'fileToken')),
      actor=None, status=200, hint='zip')
    a(fam, sc, 'upload', 'POST', 'admin/backups/upload', status=None,
      multipart={'files': {'archive': upload('mealie_upload.zip', zipped({'database.json': '{}'}), 'application/zip')}})
    a(fam, sc, 'list-after-upload', 'GET', 'admin/backups', status=200)
    a(fam, sc, 'delete-upload', 'DELETE', 'admin/backups/mealie_upload.zip', status=None)
    a(fam, sc, 'missing', 'GET', 'admin/backups/nothing.zip', status=None)
    a(fam, sc, 'non-admin', 'GET', 'admin/backups', actor=None, status=401)
    sc = 'restore'
    a(fam, sc, 'remove-pie', 'DELETE', 'recipes/apple-pie', status=200, hint='none')
    a(fam, sc, 'restore', 'POST', pathref('admin/backups/{n}/restore', n=Ref('backups', 'imports', 0, 'name')),
      status=None)
    a(fam, sc, 'pie-is-back', 'GET', 'recipes/apple-pie', status=None, fields=['name', 'slug'])
    a(fam, sc, 'recipes-after', 'GET', 'recipes', params={'orderBy': 'name'}, status=None, fields=['slug'])

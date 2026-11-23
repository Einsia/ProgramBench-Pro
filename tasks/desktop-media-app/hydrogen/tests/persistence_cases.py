"""What survives a restart of the application (runtime restart, same data) and what a fresh instance discards.

Rows prepare state through OSC, the command line and uploads, restart the application through the runtime, and read
the state back through the same public channels: the song saved with /Hydrogen/SAVE_SONG_AS, the settings file, a
drumkit loaded by name.
"""
from __future__ import annotations

import time

import songs as S
from drumkit_cases import kits
from harness import MissingDependency
from render_cases import instrument, notes, upload_samples

FAMILY = 'persist-restart'


def after(step):
    return (step,)


def prepare(ctx):
    ctx.fresh()
    upload_samples(ctx)
    ctx.osc('/Hydrogen/SELECT_INSTRUMENT', 0.0, wait=1.0)


def song(ctx, name, bpm):
    return S.Song([instrument(ctx, 'kick.wav', 0, name='Kick'), instrument(ctx, 'hat.wav', 1, name='Hat')],
                  [S.Pattern('Beat', notes(0, 96) + [S.Note(48, 1)])], name=name, bpm=bpm, mode='song')


def song_view(p):
    return {'name': p['song']['name'], 'bpm': p['song']['bpm'], 'instruments': [i['name'] for i in p['instruments']]}


def setting(text, name):
    if f'<{name}>' not in text:
        return None
    return text.split(f'<{name}>')[1].split(f'</{name}>')[0]


def build(suite):
    suite.setup(FAMILY, 'restart', prepare, 'Fresh instance with the verifier samples')

    def restored(ctx):
        ctx.upload('restored.h2song', song(ctx, 'Restored song', 128.0).xml())
        ctx.open_song('restored.h2song')
        ctx.osc('/Hydrogen/SAVE_PREFERENCES', wait=1.0)
        time.sleep(0.5)
        ctx.restart()
        ctx.osc('/Hydrogen/SELECT_INSTRUMENT', 0.0, wait=1.0)
        return song_view(ctx.song())
    suite.add(FAMILY, 'restart', 'last-song', restored,
              description='Open a song, save the settings over OSC and restart: the application starts with that song')

    def saved_song(ctx):
        ctx.upload('edited.h2song', song(ctx, 'Edited song', 100.0).xml())
        ctx.open_song('edited.h2song')
        ctx.osc('/Hydrogen/BPM', 142.0)
        ctx.osc('/Hydrogen/STRIP_VOLUME_ABSOLUTE/2', 0.35)
        ctx.osc('/Hydrogen/SAVE_SONG_AS', 'kept.h2song', wait=0.5)
        ctx.restart()
        ctx.osc('/Hydrogen/SELECT_INSTRUMENT', 0.0, wait=1.0)
        ctx.open_song('kept.h2song')
        p = ctx.song()
        return dict(song_view(p), volumes=[i['volume'] for i in p['instruments']])
    suite.add(FAMILY, 'restart', 'saved-song', saved_song,
              description='Change tempo and a volume, save the song as kept.h2song, restart and open it again')

    def metronome(ctx):
        ctx.osc('/Hydrogen/TOGGLE_METRONOME')
        ctx.osc('/Hydrogen/SAVE_PREFERENCES', wait=1.0)
        time.sleep(0.5)
        ctx.restart()
        return {'use_metronome': setting(ctx.settings(), 'use_metronome')}
    suite.add(FAMILY, 'restart', 'settings', metronome,
              description='Toggle the metronome, save the settings and restart; read the settings file')

    def unsaved(ctx):
        ctx.upload('unsaved.h2song', song(ctx, 'Unsaved song', 128.0).xml())
        ctx.open_song('unsaved.h2song')
        ctx.osc('/Hydrogen/SAVE_PREFERENCES', wait=1.0)
        ctx.osc('/Hydrogen/BPM', 77.0)
        ctx.osc('/Hydrogen/STRIP_VOLUME_ABSOLUTE/1', 0.2)
        ctx.restart()
        ctx.osc('/Hydrogen/SELECT_INSTRUMENT', 0.0, wait=1.0)
        p = ctx.song()
        return dict(song_view(p), volumes=[i['volume'] for i in p['instruments']])
    suite.add(FAMILY, 'restart', 'unsaved-changes', unsaved, requires=('backend.persist-restart.restart.last-song',),
              description='Open a song, save the settings, change tempo and a volume without saving the song, and '
                          'restart: the song comes back as stored')

    def installed(ctx):
        kit = kits()[0]
        ctx.upload('valid.h2drumkit', kit.archive())
        ctx.cli('install', drumkit='valid.h2drumkit')
        ctx.restart()
        ctx.osc('/Hydrogen/SELECT_INSTRUMENT', 0.0, wait=1.0)
        ctx.osc('/Hydrogen/LOAD_DRUMKIT', 'Verifier Kit', wait=2.0)
        p = ctx.song()
        return {'drumkit': p['song']['drumkit'], 'instruments': [i['name'] for i in p['instruments']]}
    library = suite.add(FAMILY, 'restart', 'library', installed,
                        description='Install a drumkit with the command line, restart, and load it by name')

    def second_kit(ctx):
        other = [k for k in kits() if k.name == 'layered'][0]
        ctx.upload('layered.h2drumkit', other.archive())
        ctx.cli('install', drumkit='layered.h2drumkit')
        ctx.restart()
        ctx.osc('/Hydrogen/SELECT_INSTRUMENT', 0.0, wait=1.0)
        ctx.osc('/Hydrogen/LOAD_DRUMKIT', 'Layered Kit', wait=2.0)
        p = ctx.song()
        first = {'drumkit': p['song']['drumkit'], 'instruments': [i['name'] for i in p['instruments']]}
        ctx.osc('/Hydrogen/LOAD_DRUMKIT', 'Verifier Kit', wait=2.0)
        p = ctx.song()
        return {'layered': first, 'verifier': {'drumkit': p['song']['drumkit'],
                                               'instruments': [i['name'] for i in p['instruments']]}}
    suite.add(FAMILY, 'restart', 'library-two-kits', second_kit, needs=after(library),
              description='Install a second drumkit, restart, and load both installed kits by name')

    suite.setup(FAMILY, 'reset', prepare, 'Fresh instance with the verifier samples')

    def discarded(ctx):
        kit = kits()[0]
        ctx.upload('valid.h2drumkit', kit.archive())
        ctx.cli('install', drumkit='valid.h2drumkit')
        ctx.fresh()
        ctx.osc('/Hydrogen/SELECT_INSTRUMENT', 0.0, wait=1.0)
        ctx.osc('/Hydrogen/LOAD_DRUMKIT', 'Verifier Kit', wait=2.0)
        p = ctx.song()
        return {'drumkit': p['song']['drumkit'], 'instruments': len(p['instruments']),
                'inputs': ctx.call({'op': 'list_files'}).get('inputs')}
    suite.add(FAMILY, 'reset', 'fresh-instance', discarded, requires=(library,),
              description='Install a drumkit, then reset the instance: the kit, the settings and the inputs are gone')

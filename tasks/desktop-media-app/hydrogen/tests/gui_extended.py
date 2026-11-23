"""Editing and offline display goals for the product's documented desktop features."""
from specification import episode, step, menu, note, notes, path, song, instruments, output


def point(x, y, **extra):
    return {'op': 'pointer', 'x': x, 'y': y, **extra}


def drag(x, y, tx, ty, **extra):
    return point(x, y, action='drag', to_x=tx, to_y=ty, **extra)


def detail(*fields, instrument=None):
    return {'kind': 'detailed-notes', 'pattern': 'Melody', 'fields': list(fields), 'instrument': instrument,
            'description': 'The saved notes have the requested positions, instruments and ' + ', '.join(fields)}


def render():
    return {'kind': 'rendered-song', 'description': 'The edited song renders with the requested timing and sound.'}


def build():
    result = []
    edit = ['tone440.wav', 'tone880.wav', 'editing.h2song']
    sample = ['ramp.wav', 'tone440.wav', 'samples.h2song']
    initial = ('song Editing opened: pattern Melody has Tone notes C0 on beats 1 and 2 and a High note C0 '
               'on beat 3; Melody fills four bars; Tone is selected')

    def add(key, feature, documents, opened, steps, start=initial):
        item = episode(key, feature, documents, opened, steps, start=start)
        # Calibrated with the standard answer: allow deliberate graphical editing without consuming later
        # checkpoints' judging reserve, and keep measured calls/tokens below 40% of the episode budget.
        if key == 'note-properties':
            item['budget']['seconds'] = 7200
        elif key == 'sample-editor':
            item['budget']['tokens'] = 3_200_000
        elif key == 'playlist-order':
            item['budget'] = {'calls': 220, 'tokens': 4_500_000, 'seconds': 4800}
        result.append(item)

    add('piano-roll', 'pattern-editor', edit, 'editing.h2song', [
        step('chord', 'In the piano roll for Tone, add E0 and G0 at beat 1 of Melody, keeping its existing C0 '
                      'notes. C0 is the sample’s untransposed pitch.',
             'The piano roll visibly shows a three-note C0/E0/G0 chord on beat 1 and the existing C0 on beat 2.',
             [{'op': 'button', 'name': 'Show piano roll editor'}, point(203, 623), point(203, 593)],
             [detail('key'), render()]),
        step('length', 'Give the C0 note on beat 1 a duration of one quarter note, leaving the other notes as they '
                       'are. Keep the piano roll visible.',
             'The C0 note on beat 1 extends for one beat in the piano roll; the chord’s other notes remain.',
             [drag(203, 663, 347, 663, button='right')], [detail('key', 'length'), render()], depends=['chord']),
        step('transpose', 'Move the Tone C0 note on beat 2 up to D0, keeping its beat position.',
             'The Tone note on beat 2 is now on D0, above C0; the beat-1 chord remains.',
             [point(347, 663), point(347, 643)], [detail('key', 'length'), render()], depends=['length']),
    ])

    add('note-properties', 'pattern-editor', edit, 'editing.h2song', [
        step('velocity', 'In Melody, set the velocity of the Tone note on beat 2 to 0.5 (within 0.03), leaving '
                         'the beat-1 note at 0.8. Show the velocity editor. If the lower note-properties area is '
                         'clipped, scroll the main window down to expose it.',
             'The velocity editor shows the beat-2 Tone note at about half height, lower than the beat-1 note.',
             [point(1431, 820, action='scroll', delta_y=800), point(347, 834)], [detail('velocity'), render()]),
        step('pan', 'Pan the Tone note on beat 1 halfway from center to full right '
                    '(the editor reports approximately "Note panned to the right by: [0.25]"). '
                    'Show the Pan editor.',
             'The Pan editor shows the first Tone note toward the right and its second note centered.',
             [{'op': 'combo', 'target': {'name': 'Velocity'}, 'item': 'Pan'}, point(203, 809)],
             [detail('pan'), render()], depends=['velocity']),
        step('timing', 'Give the Tone note on beat 2 a delay halfway from centered to maximum lag, so the editor '
                       'reports approximately "Lagging beat by: [2.50] ticks". Show Lead and Lag.',
             'The Lead and Lag editor shows the second Tone note on the lag side and the first centered.',
             [{'op': 'combo', 'target': {'name': 'Pan'}, 'item': 'Lead and Lag'}, point(347, 859)],
             [detail('leadlag'), render()], depends=['pan']),
        step('probability', 'Set the probability of the Tone note on beat 2 to zero. Keep the Probability editor '
                            'visible and leave the other note at probability one.',
             'The Probability editor shows the second Tone note at zero and the first at full probability.',
             [{'op': 'combo', 'target': {'name': 'Lead and Lag'}, 'item': 'Probability'}, point(347, 883),
              point(347, 850, action='scroll', delta_y=200)],
             [detail('probability'), render()], depends=['timing'], requires={'state-2': ['velocity/state-2']}),
    ])

    add('note-selection', 'pattern-editor', edit, 'editing.h2song', [
        step('moved', 'Select the Tone note on beat 2 in Melody and move it to beat 3 of the same instrument. '
                      'Keep the Tone note on beat 1 and the High note on beat 3.',
             'Tone now has notes on beats 1 and 3, while High retains its note on beat 3.',
             [drag(220, 440, 355, 460), drag(347, 450, 491, 450)], [notes('Melody')]),
        step('copied', 'Copy the selected Tone note on beat 3 to beat 4, keeping the original.',
             'Tone has notes on beats 1, 3 and 4; High still has its note on beat 3.',
             [drag(491, 450, 635, 450, modifiers=['Control'])], [notes('Melody')], depends=['moved']),
        step('deleted', 'Delete the copied Tone note on beat 4 using the selection, leaving the other notes.',
             'Tone again has only beats 1 and 3, and High retains beat 3.',
             [{'op': 'press', 'key': 'Delete'}], [notes('Melody')], depends=['copied']),
    ])

    def layer_fields(instrument, *fields):
        return {'kind': 'sample-settings', 'instrument': instrument, 'fields': list(fields),
                'description': 'The applied sample edits are stored for ' + instrument + '.'}

    sample_start = 'song Samples opened: Ramp plays ramp.wav on beat 1 and Tone plays tone440.wav on beat 3'
    add('sample-editor', 'sample-editor', sample, 'samples.h2song', [
        step('region', 'Open the sample editor of Ramp and retain frames 4410 through 17640 of ramp.wav. Apply '
                       'the edit and keep the sample editor open.',
             'The sample editor visibly marks the shortened region and shows start 4410 and end 17640.',
             [{'op': 'check', 'target': {'role': 'check box', 'name': 'Layers'}, 'state': True},
              {'op': 'button', 'name': 'Edit Layer'}, {'op': 'sample-editor', 'start': 4410, 'end': 17640}],
             [layer_fields('Ramp', 'frames'), render()], windows=['SampleEditor']),
        step('loop', 'Set the Ramp sample’s loop start to frame 8820, loop count to 2 and mode to reverse. '
                     'Apply and leave the sample editor open.',
             'The sample editor shows loop start 8820, count 2 and reverse mode, with the retained region visible.',
             [{'op': 'sample-editor', 'start': 4410, 'loop': 8820, 'loops': 2, 'mode': 'reverse'}],
             [layer_fields('Ramp', 'frames', 'smode'), render()], depends=['region'], windows=['SampleEditor']),
        step('volume', 'Add a point halfway through Ramp’s volume envelope at about one quarter of full volume '
                       '(within 0.05); keep the ends at full volume, apply the edit and display that envelope.',
             'The volume envelope visibly falls from full level to a deep central dip and rises to full level.',
             [point(720, 678), {'op': 'button', 'name': 'Apply Changes'}],
             [layer_fields('Ramp', 'volume'), render()], depends=['loop'], windows=['SampleEditor']),
        step('pan', 'Switch to the Ramp panorama envelope and add a midpoint at about three quarters of its '
                    'vertical range (toward the right, within 0.05). Apply and display the panorama envelope.',
             'The panorama envelope visibly rises toward the right at its midpoint and returns to center at both ends.',
             [{'op': 'combo', 'target': {'name': 'volume'}, 'item': 'panorama'}, point(720, 633),
              {'op': 'button', 'name': 'Apply Changes'}],
             [layer_fields('Ramp', 'pan'), render()], depends=['volume'], windows=['SampleEditor']),
    ], start=sample_start)

    add('sample-stretch', 'sample-editor', sample, 'samples.h2song', [
        step('stretched', 'Open the sample editor of Tone, set its sample length to 2 beats and pitch to +12 '
                          'semitones, then apply. Leave the editor open.',
             'The sample editor shows Tone with length 2 beats and pitch +12, and its processed waveform.',
             [{'op': 'select-instrument', 'row': 1},
              {'op': 'check', 'target': {'role': 'check box', 'name': 'Layers'}, 'state': True},
              {'op': 'button', 'name': 'Edit Layer'}, {'op': 'sample-editor', 'beats': '2', 'pitch': 12}],
             [layer_fields('Tone', 'rubber'), render()], windows=['SampleEditor']),
        step('reopened', 'Close and reopen the Tone sample editor to inspect the applied length and pitch.',
             'The reopened editor still shows Tone’s 2-beat length, +12 pitch and processed waveform.',
             [{'op': 'button', 'name': 'Close'}, {'op': 'button', 'name': 'Edit Layer'}],
             [layer_fields('Tone', 'rubber')], depends=['stretched'], windows=['SampleEditor']),
    ], start=sample_start)

    add('automation-edit', 'song-editor', edit, 'editing.h2song', [
        step('path', 'Show the velocity automation path. Create points at the start of bar 2 with value 1, '
                     'bar 3 with value 0.5 and bar 5 with value 1 (within 0.04 in value). Leave the curve visible.',
             'The visible automation curve dips at bar 3 between higher points at bars 2 and 5.',
             [{'op': 'press', 'key': 'Alt+a'}, point(227, 329), point(243, 347), point(275, 329)],
             [{'kind': 'automation'}, render()]),
        step('moved', 'Move the low automation point from bar 3 to bar 4, keeping it at value 0.5 (within 0.04).',
             'The low point of the visible automation curve is now at bar 4, with the two high endpoints retained.',
             [drag(243, 347, 259, 347)], [{'kind': 'automation'}, render()], depends=['path']),
        step('merged', 'Merge the low point at bar 4 into the high point at bar 5 by moving it onto that point. '
                       'Leave one point there at value 1 (within 0.04).',
             'The automation curve is flat at the two remaining high points at bars 2 and 5; the dip is gone.',
             [drag(259, 347, 275, 329)], [{'kind': 'automation'}, render()], depends=['moved']),
    ])

    add('undo-history', 'pattern-editor', edit, 'editing.h2song', [
        step('history', 'Add a Tone note on beat 4 of Melody and open Undo History to inspect the operation.',
             'Undo History visibly lists the note insertion and indicates the current end of the history.',
             [note(0, 144), menu('Undo', 'Undo History')], [notes('Melody')], windows=['Undo history']),
    ])

    add('director', 'display', edit, 'editing.h2song', [
        step('shown', 'Open the Director for the current song.',
             'The Director visibly identifies the current song by its title Editing or its file name editing.',
             [menu('View', 'Director')], [song('name')], windows=['Director']),
    ])

    appearance = [menu('Options', 'Preferences'),
                  {'op': 'pointer', 'target': {'role': 'page tab', 'name': 'Appearance'}}]
    appearance_checks = [{'kind': 'settings', 'keys': ['SongEditor_visible_pattern_colors']}]
    add('appearance', 'preferences', [], None, [
        step('colors', 'In Appearance preferences set the number of colors in the Song Editor to 8. Confirm '
                       'the change, then reopen Appearance to display the saved choice.',
             'Appearance visibly shows 8 as the number of Song Editor colors.',
             appearance + [{'op': 'fill', 'target': {'role': 'spin button', 'text': '18'}, 'value': '8'},
                           {'op': 'button', 'name': 'OK'}] + appearance,
             appearance_checks, windows=['Preferences']),
        step('restart', 'After the application restarts, reopen Appearance and inspect the saved number of '
                        'Song Editor colors.',
             'The reopened Appearance preferences still show 8 Song Editor colors.',
             appearance, appearance_checks, lifecycle='restart', depends=['colors'], windows=['Preferences']),
        step('theme', f'Set the icon color to White and export this appearance as {path("appearance", "eight.h2theme")}. Leave Appearance '
                      'visible after the export.',
             'Appearance visibly shows White icons and the eight-color configuration.',
             [{'op': 'combo', 'target': {'name': 'Black'}, 'item': 'White'},
              {'op': 'button', 'name': 'Export Theme'}, {'op': 'save-dialog', 'file': ('eight.h2theme',)}],
             [output('file-xml-fields', 'eight.h2theme', keys=['SongEditor_visible_pattern_colors', 'iconColor'])],
             depends=['restart'], windows=['Preferences']),
        step('imported', f'Change the number of Song Editor colors to 12 and icon color to Black, then import {path("appearance", "eight.h2theme")} '
                         'to restore the exported appearance. Confirm and reopen Appearance.',
             'Appearance visibly shows 8 colors and White icons restored from the imported theme.',
             [{'op': 'fill', 'target': {'role': 'spin button', 'text': '8'}, 'value': '12'},
              {'op': 'combo', 'target': {'name': 'White'}, 'item': 'Black'},
              {'op': 'button', 'name': 'Import Theme'}, {'op': 'open-dialog', 'file': ('eight.h2theme', 'outputs')},
              {'op': 'button', 'name': 'OK'}] + appearance, appearance_checks, depends=['theme'],
             windows=['Preferences']),
    ], start='the default song')

    key = 'playlist-order'
    docs = ['tone440.wav', 'tone880.wav', 'first.h2song', 'second.h2song', 'pair.h2playlist']
    add(key, 'playlist', docs, None, [
        step('reordered', f'Open playlist {path(key, "pair.h2playlist")}, move second.h2song above first.h2song '
                          f'and save it as {path(key, "reordered.h2playlist")}. Keep the playlist visible.',
             'The playlist visibly lists second.h2song first and first.h2song second.',
             [menu('View', 'Playlist Editor'), {'op': 'playlist-menu', 'item': 'Open Playlist'},
              {'op': 'open-dialog', 'file': ('pair.h2playlist',)}, {'op': 'playlist-row', 'row': 1},
              {'op': 'playlist-up'}, {'op': 'playlist-menu', 'item': 'Save Playlist as'},
              {'op': 'save-dialog', 'file': ('reordered.h2playlist',), 'stays': True}],
             [output('file-playlist', 'reordered.h2playlist')]),
        step('reopened', f'Open the saved playlist {path(key, "reordered.h2playlist")} again and select its first '
                         'song, second.h2song, for editing. Close the playlist so the song is visible.',
             'The main editor visibly shows song Second with pattern B and its four quarter notes.',
             [{'op': 'playlist-menu', 'item': 'Open Playlist'},
              {'op': 'open-dialog', 'file': ('reordered.h2playlist', 'outputs')},
              {'op': 'playlist-row', 'row': 0, 'count': 2}, {'op': 'press', 'key': 'Escape'}],
             [song('name', 'patterns')], depends=['reordered']),
        step('next', 'Use the playlist’s next-song command (F6 in the reference) to load first.h2song. '
                     'Show the song editor.',
             'The main editor visibly shows song First with pattern A and two notes.',
             [{'op': 'press', 'key': 'F6'}], [song('name', 'patterns')], depends=['reopened']),
    ], start='the default song; pair.h2playlist lists first.h2song then second.h2song')

    key = 'drumkit-properties'
    add(key, 'drumkits', sample, 'samples.h2song', [
        step('saved', 'Save the current two-instrument kit in the library as Bench Kit, author Ada, information '
                      'Synthetic kit, license CC0. Load Bench Kit from the library after saving. The properties '
                      'window can be maximized and scrolled to reach its Save control.',
             'The main editor visibly identifies Bench Kit, with the Ramp and Tone instruments.',
             [menu('Drumkits', 'Save As'), {'op': 'kit-properties', 'name': 'Bench Kit', 'author': 'Ada',
                                           'info': 'Synthetic kit', 'license': 'CC0'},
              menu('Drumkits', 'Open'), {'op': 'kit-dialog', 'kit': 'Bench Kit'}], [{'kind': 'kit'}]),
        step('exported', f'Export Bench Kit into {path(key, "archive", "outputs").rsplit("/", 1)[0]}, then '
                         'display the kit’s stored properties.',
             'The displayed kit properties show Bench Kit, author Ada, information Synthetic kit and license CC0.',
             [menu('Drumkits', 'Export'), {'op': 'kit-export', 'folder': ('outputs',)},
              {'op': 'button', 'name': 'Cancel'}, menu('Drumkits', 'Properties')],
             [{'kind': 'file-drumkit', 'folder': 'outputs', 'suffix': '.h2drumkit', 'metadata': True}],
             depends=['saved'], windows=['SoundLibrary Properties']),
    ], start=sample_start)
    return result

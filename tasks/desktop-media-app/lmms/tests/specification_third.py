'''Third batch of GUI episodes: track switches, the piano roll with undo and redo, renaming, replacing an instrument,
the project notes, the Setup dialog, toolbar wheels downwards, clip placement and exports of piano roll notes.

Built on the helpers of specification.py and specification_more.py. Every checkpoint ends with Save As under a new name,
with an export, or with the settings file after the Setup dialog was closed; the independent checks read only that.
'''
import specification as s
import specification_more as m

TRACKS = './song/trackcontainer/track'
NOTES = './song/trackcontainer/track/pattern/note'
INSTRUMENT = './song/trackcontainer/track/instrumenttrack/instrument'


def text_of(name, xpath, what):
    return {'kind': 'project-text', 'path': name, 'xpath': xpath, 'description': what}


def notes_step(wf, sid, goal, acceptance, text, name, depends=()):
    target = s.path(wf, name)
    recipe = [{'op': 'project-notes', 'text': text}, {'op': 'save-project', 'file': name}]
    return s.step(sid, goal + ' Then save the project as ' + target + '.',
                  acceptance + ' The project is saved without an error message and its name ' + name.rsplit('.', 1)[0]
                  + ' is shown in the window title.', recipe,
                  [s.written(name, 'The project file ' + name + ' was written.'),
                   text_of(name, './song/projectnotes', 'The saved project holds the text of the project notes.')],
                  depends=list(depends), requires={'visible': ['state-1']})


def setup_step(wf, sid, goal, acceptance, switches, button, section, names, what, depends=(), bind=()):
    # The step changes switches of the Setup dialog and then opens the dialog again and leaves it open: the evidence is
    # the state of the switches that the reopened dialog shows (a window that the recipe leaves open on purpose).
    recipe = [{'op': 'setup-switch', 'switches': switches, 'button': button}, {'op': 'setup-show', 'leave_open': True}]
    companions = {'visible': ['state-1']}
    if bind:
        companions['state-1'] = list(bind)
    return s.step(sid, goal, acceptance, recipe, [s.setting(section, names, what)], depends=list(depends),
                  requires=companions)


def build():
    out = []

    def add(*a, **kw):
        out.append(s.frozen_form(s.episode(*a, **kw)))

    wf = 'track-switches'
    add(wf, 'song-editor', [], [
        m.saved_step(wf, 'muted', 'Mute the TripleOscillator track with the first of the two small switches at the left of its name.',
                     'The TripleOscillator track is shown as muted in the Song-Editor; the other three tracks are not muted.',
                     [{'op': 'track-switch', 'switch': 'mute', 'row': 0}], 'muted.mmpz', TRACKS,
                     'The saved project lists its tracks with their mute and solo flags, the first one muted.'),
        m.saved_step(wf, 'unmuted', 'Switch the TripleOscillator track on again with the same switch.',
                     'No track is shown as muted or soloed.',
                     [{'op': 'track-switch', 'switch': 'mute', 'row': 0}], 'unmuted.mmpz', TRACKS,
                     'The saved project lists its tracks with none of them muted or soloed.', depends=['muted']),
        m.saved_step(wf, 'soloed', 'Solo the TripleOscillator track with the second of the two small switches at the left of its name.',
                     'The TripleOscillator track is shown as soloed and the other three tracks are shown as muted.',
                     [{'op': 'track-switch', 'switch': 'solo', 'row': 0}], 'soloed.mmpz', TRACKS,
                     'The saved project lists its tracks with the first one soloed and the other three muted.', depends=['unmuted']),
        m.saved_step(wf, 'unsoloed', 'Switch the solo of the TripleOscillator track off again.',
                     'No track is shown as muted or soloed.',
                     [{'op': 'track-switch', 'switch': 'solo', 'row': 0}], 'unsoloed.mmpz', TRACKS,
                     'The saved project lists its tracks with none of them muted or soloed.', depends=['soloed'])])

    wf = 'piano-roll-notes'
    add(wf, 'piano-roll', [], [
        m.saved_step(wf, 'notes', 'Create a clip at the very start of the TripleOscillator row of the Song-Editor (click its empty row with the draw tool), double-click the clip to open the Piano Roll and draw three notes with the draw tool, each one beat long: one on the C5 key at the start of bar 1, one on the key just above it at the start of bar 2 and one on the key just below C5 at the start of bar 3.',
                     'The Piano-Roll window of the TripleOscillator track shows three notes: one on the C5 row in bar 1, one on the next higher row in bar 2 and one on the next lower row in bar 3.',
                     [{'op': 'clip', 'row': 0, 'bar': 0}, {'op': 'pattern-open', 'row': 0, 'bar': 0},
                      {'op': 'note', 'tick': 0, 'key': 60}, {'op': 'note', 'tick': 192, 'key': 61}, {'op': 'note', 'tick': 384, 'key': 59}],
                     'notes.mmpz', NOTES, 'The saved project lists the three notes of the pattern with position, length and key.'),
        m.saved_step(wf, 'undone', 'With the Piano Roll in front, undo the last change so that the last note disappears.',
                     'The Piano Roll shows only the notes in bar 1 and bar 2.',
                     [{'op': 'focus-roll'}, {'op': 'undo'}], 'undone.mmpz', NOTES,
                     'The saved project lists two notes of the pattern.', depends=['notes']),
        m.saved_step(wf, 'redone', 'Redo the change that was undone so that the third note is back.',
                     'The Piano Roll shows the three notes again.',
                     [{'op': 'focus-roll'}, {'op': 'redo'}], 'redone.mmpz', NOTES,
                     'The saved project lists the three notes of the pattern again.', depends=['undone'])])

    wf = 'track-rename'
    add(wf, 'song-editor', [], [
        m.saved_step(wf, 'renamed', 'Rename the second track of the Song-Editor, the Sample track, to Lead two (right-click its name, type the new name and confirm with Return).',
                     'The second row of the Song-Editor is named Lead two; the other tracks keep their names.',
                     [{'op': 'rename-track', 'name': 'Sample track', 'text': 'Lead two'}], 'renamed.mmpz', TRACKS,
                     'The saved project lists its tracks, the second one named Lead two.'),
        s.step('reopened', 'The application was restarted and shows a fresh default project. Open the saved project ' + s.path(wf, 'renamed.mmpz') + '.',
               'The Song-Editor lists the second track as Lead two and the window title shows renamed.',
               [{'op': 'open-project', 'file': 'renamed.mmpz'}], lifecycle='restart', depends=['renamed'])])

    wf = 'instrument-replace'
    add(wf, 'sidebar', [], [
        m.saved_step(wf, 'replaced', 'Replace the instrument of the TripleOscillator track: open the Instrument Plugins list (the first tab of the left sidebar), drag Kicker onto the TripleOscillator row of the Song-Editor and close the list again by clicking its tab.',
                     'The first track row now uses the Kicker instrument and a Kicker instrument window is open; the other three tracks are unchanged.',
                     [{'op': 'plugin-drop', 'plugin': 'Kicker', 'row': 0}], 'replaced.mmpz', INSTRUMENT,
                     'The saved project holds the Kicker instrument in the first track.'),
        m.saved_step(wf, 'added', 'Drag sfxr from the Instrument Plugins list into the Song-Editor below the last track, so that a new track is created, and close the list again.',
                     'The Song-Editor lists a fifth track below the four existing ones.',
                     [{'op': 'plugin-drag', 'plugin': 'sfxr', 'tracks': 4}], 'added.mmpz', INSTRUMENT,
                     'The saved project holds the Kicker and the sfxr instrument in two instrument tracks.', depends=['replaced'])])

    wf = 'project-notes'
    add(wf, 'project-notes', [], [
        notes_step(wf, 'typed', 'Open the project notes window (the toolbar button with the page icon, or F10) and type the text Notes line one into it.',
                   'The Project Notes window is open and shows the text Notes line one.', 'Notes line one', 'notes.mmpz'),
        s.step('reopened', 'The application was restarted and shows a fresh default project. Open the saved project ' + s.path(wf, 'notes.mmpz') + '.',
               'The saved project is open: its name notes is shown in the window title.',
               [{'op': 'open-project', 'file': 'notes.mmpz'}], lifecycle='restart', depends=['typed'])])

    wf = 'setup-switches'
    reopen = ' Then open Edit, Settings again and leave the dialog open without changing anything, so that its switches can be seen.'
    add(wf, 'settings', [], [
        setup_step(wf, 'dbfs', 'Open the application settings (Edit, Settings), switch on Display volume as dBFS in the MISC list of the General settings page and confirm with OK.' + reopen,
                   'The settings dialog shows the switch Display volume as dBFS on.',
                   [2], 'OK', 'app', ['displaydbfs'], 'The settings file holds the dBFS display switched on.'),
        setup_step(wf, 'compact', 'Open the settings again, switch on Compact track buttons and confirm with OK.' + reopen,
                   'The settings dialog shows the switch Compact track buttons on and the switch Display volume as dBFS still on.',
                   [6], 'OK', 'ui', ['compacttrackbuttons'], 'The settings file holds compact track buttons switched on.', depends=['dbfs']),
        setup_step(wf, 'cancelled', 'Open the settings again, switch on Enable note labels in piano roll, then cancel the dialog instead of confirming.' + reopen,
                   'The settings dialog shows the switch Enable note labels in piano roll off, with Display volume as dBFS and Compact track buttons still on.',
                   [8], 'Cancel', 'ui', ['printnotelabels'], 'The settings file still holds the note labels switch off.', depends=['compact'],
                   bind=['dbfs/state-1'])])

    wf = 'toolbar-sliders-down'
    add(wf, 'toolbar', [], [
        m.saved_step(wf, 'volume', 'Lower the master volume slider of the toolbar by 10 steps, from 100 to 90 (the mouse wheel turns it by one step per notch).',
                     'The master volume slider of the toolbar reads 90.', [{'op': 'master-volume', 'notches': -10}],
                     'volume.mmpz', './head', 'The saved project holds the master volume 90.'),
        m.saved_step(wf, 'pitch', 'Lower the master pitch slider of the toolbar by 2 steps, from 0 to -2.',
                     'The master pitch slider of the toolbar reads -2 and the master volume slider still reads 90.',
                     [{'op': 'master-pitch', 'notches': -2}], 'pitch.mmpz', './head',
                     'The saved project holds the master pitch -2 next to the master volume 90.', depends=['volume']),
        m.saved_step(wf, 'signature', 'Lower the numerator of the time signature display by 1, from 4 to 3 (the mouse wheel over the upper number).',
                     'The time signature display shows 3 over 4.', [{'op': 'time-signature', 'notches': -1}],
                     'signature.mmpz', './head', 'The saved project holds the time signature 3 over 4.', depends=['pitch'])])

    wf = 'clip-placement'
    add(wf, 'song-editor', [], [
        m.saved_step(wf, 'pattern', 'In the Song-Editor, create a clip on the TripleOscillator row at the start of bar 3 of the song ruler by clicking its empty row with the draw tool.',
                     'A clip is shown in the TripleOscillator row starting at bar 3.', [{'op': 'clip', 'row': 0, 'bar': 2}],
                     'pattern.mmpz', './song/trackcontainer/track/pattern', 'The saved project holds one pattern on the first track at the third bar.'),
        m.saved_step(wf, 'beat', 'Create a clip on the Beat/Bassline 0 row at the start of bar 2.',
                     'A clip starts at bar 2 in the Beat/Bassline 0 row.', [{'op': 'clip', 'row': 2, 'bar': 1}],
                     'beat.mmpz', './song/trackcontainer/track/bbtco', 'The saved project holds one Beat/Bassline clip at the second bar.',
                     depends=['pattern'], fields=('pos', 'len', 'muted', 'usestyle')),
        m.saved_step(wf, 'sample', 'Create a clip on the Sample track row at the start of bar 4.',
                     'A clip starts at bar 4 in the Sample track row.', [{'op': 'clip', 'row': 1, 'bar': 3}],
                     'sample.mmpz', './song/trackcontainer/track/sampletco', 'The saved project holds one sample clip at the fourth bar.',
                     depends=['beat'], fields=('pos', 'muted'))])

    wf = 'export-notes'
    add(wf, 'export', [], [
        m.exported_step(wf, 'exported', 'Create a clip at the very start of the TripleOscillator row, double-click it to open the Piano Roll, draw one note on the C5 key at the start of bar 1 and a second note four keys higher half a bar later, then close the Piano Roll.',
                        'The Piano Roll is closed and the TripleOscillator row of the Song-Editor holds a clip at the start of the song.',
                        [{'op': 'clip', 'row': 0, 'bar': 0}, {'op': 'pattern-open', 'row': 0, 'bar': 0},
                         {'op': 'note', 'tick': 0, 'key': 60}, {'op': 'note', 'tick': 96, 'key': 64}, {'op': 'close-roll'}],
                        'n1.wav', 'n1.wav is a WAV file that decodes to the rendered notes.'),
        m.exported_step(wf, 'higher', 'Raise the master pitch slider of the toolbar by 12 steps, from 0 to 12.',
                        'The master pitch slider of the toolbar reads 12.', [{'op': 'master-pitch', 'notches': 12}],
                        'n2.wav', 'n2.wav is a WAV file whose pitch follows the raised master pitch.', depends=['exported']),
        m.exported_step(wf, 'slower', 'Set the tempo of the project to 60 beats per minute.', 'The tempo display of the toolbar reads 60.',
                        [{'op': 'tempo', 'value': 60}], 'n3.wav', 'n3.wav is a WAV file whose length follows the slower tempo.',
                        depends=['higher'])])
    import specification_fourth
    out.extend(specification_fourth.build())
    return out

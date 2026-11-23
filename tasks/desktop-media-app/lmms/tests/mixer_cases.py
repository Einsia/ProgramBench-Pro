'''Mixer coverage of the product command line on generated projects.

Every point renders one generated project through cli render and decodes the written file with the verifier FFmpeg.
The exit status never decides; the written file does. An instrument track is routed to a mixer channel; a channel has a
volume, a mute switch, sends to other channels and an effect chain, and every route ends in the master channel, which
has a volume and an effect chain of its own. A point returns its signal class and the signal projection of the render
(format, length, level per channel, level per window and spectrum), so every route, volume, send amount and effect
changes the observation.
'''
from __future__ import annotations

import projectxml as px
from harness import signal_projection

BPM = 140
SEQUENCE = [(i * 48, 48, 57 + 2 * i) for i in range(4)]
SENDS_TO_MASTER = ((0, 1.0),)
ROUTED = 'backend.mixer.routed-default.render'
TWO = 'backend.mixer.two-channels.render'


def synth(channel, name='Lead'):
    return px.instrument_track(name, 'tripleoscillator', notes=SEQUENCE, channel=channel)


def kick(channel):
    return px.instrument_track('Kick', 'kicker', notes=[(0, 96, 57)], channel=channel)


def amplifier(volume):
    return lambda: px.effect('amplifier', params={'volume': volume, 'pan': 0, 'left': 100, 'right': 100})


def lowpass(cut):
    return lambda: px.effect('dualfilter', controls='DualFilterControls',
                             params={'enabled1': 1, 'filter1': 0, 'cut1': cut, 'res1': 0.5, 'gain1': 100,
                                     'enabled2': 0, 'filter2': 0, 'cut2': 7000, 'res2': 0.5, 'gain2': 100,
                                     'mix': -1})


def channel_setup(volume=1.0, muted=False, sends=SENDS_TO_MASTER, effects=()):
    def setup(project):
        project.channel(1, 'Lead', volume=volume, muted=muted, effects=[make() for make in effects], sends=sends)
        project.add(synth(1))
    return setup


def master_setup(volume=1.0, effect=None):
    def setup(project):
        project.channels[0].set('volume', str(volume))
        if effect is not None:
            chain = project.channels[0].find('fxchain')
            chain.append(effect())
            chain.set('numofeffects', '1')
            chain.set('enabled', '1')
        project.channel(1, 'First')
        project.channel(2, 'Second')
        project.add(synth(1, 'First'))
        project.add(kick(2))
    return setup


def two_setup(first=1.0, second=1.0, muted=False, effects=()):
    def setup(project):
        project.channel(1, 'First', volume=first, muted=muted, effects=[make() for make in effects])
        project.channel(2, 'Second', volume=second)
        project.add(synth(1, 'First'))
        project.add(kick(2))
    return setup


def chain_setup(amount=1.0, volume=1.0, direct=None):
    def setup(project):
        sends = ((2, amount),) + (() if direct is None else ((0, direct),))
        project.channel(1, 'First', sends=sends)
        project.channel(2, 'Second', volume=volume, sends=SENDS_TO_MASTER)
        project.add(synth(1))
    return setup


def point(suite, scenario, description, setup, requires=()):
    def action(ctx):
        project = px.Project(bpm=BPM)
        setup(project)
        rendered = ctx.render(project.xml(), 'mixer-' + scenario)
        assert rendered.audio is not None, 'the render wrote no audio file'
        return {'tol': 'signal', 'slack': 0, 'signal': signal_projection(rendered.audio)}
    suite.add('mixer', scenario, 'render', action, description=description, requires=requires)


def label(value):
    return str(value).replace('.', '-')


def build(suite):
    point(suite, 'routed-default', 'Route a synth track through mixer channel 1 into the master channel', channel_setup())
    for volume in (0.25, 0.5, 1.5):
        point(suite, 'channel-volume-' + label(volume), f'Set the volume of mixer channel 1 to {volume}',
              channel_setup(volume=volume))
    point(suite, 'channel-muted', 'Mute mixer channel 1', channel_setup(muted=True), requires=(ROUTED,))
    for amount in (0.6, 0.8):
        point(suite, 'send-amount-' + label(amount), f'Send mixer channel 1 to the master channel with amount {amount}',
              channel_setup(sends=((0, amount),)))
    for volume in (0.5, 1.5):
        point(suite, 'master-volume-' + label(volume), f'Set the volume of the master channel to {volume}',
              master_setup(volume=volume))
    point(suite, 'two-channels', 'Route two tracks to two channels with different volumes', two_setup(first=0.25))
    point(suite, 'two-channels-first-muted', 'Mute the channel of the first of two tracks',
          two_setup(first=0.25, muted=True), requires=(TWO,))
    point(suite, 'chain-through-channel-2', 'Send channel 1 through channel 2 at volume 0.7 to the master channel',
          chain_setup(volume=0.7))
    point(suite, 'chain-send-amount', 'Send channel 1 to channel 2 with amount 0.4', chain_setup(amount=0.4))
    point(suite, 'send-to-master-and-channel-2', 'Send channel 1 to the master channel and, with amount 0.3, to channel 2',
          chain_setup(amount=0.3, direct=1.0))
    point(suite, 'channel-effect-lowpass', 'Put a low-pass filter at 500 Hz on mixer channel 1',
          channel_setup(effects=(lowpass(500),)))
    point(suite, 'channel-effect-amplifier', 'Put an amplifier at 30 percent on mixer channel 1',
          channel_setup(effects=(amplifier(30),)))
    point(suite, 'channel-effect-only-its-track', 'A low-pass on channel 1 leaves the track of channel 2 untouched',
          two_setup(effects=(lowpass(500),)))
    point(suite, 'master-effect-lowpass', 'Put a low-pass filter at 500 Hz on the master channel',
          master_setup(effect=lowpass(500)))
    point(suite, 'master-effect-amplifier', 'Put an amplifier at 70 percent on the master channel',
          master_setup(effect=amplifier(70)))

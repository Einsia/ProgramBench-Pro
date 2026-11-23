'''Episode specifications for cli, clipboard, state. Fixtures, actions and checks use the documented runtime channels.'''
from spec_base import *  # noqa: F401,F403

H3 = history('first', 'second', 'third')


def cp(cid, goal, fixture, keys, checks):
    return step(cid, goal, S(scenario(fixture), keys, wait(0.5)), checks)


def build():
    W = []

    W.append(program('cli', 'cli', None, [
        step('version', 'Print the version with the --version option.', [],
             [('version', 'The reported version is 0.66.2.', cli('--version'))]),
        step('config-dir', 'Print the configuration directory with the --print-config-dir option.', [],
             [('dir', 'The directory is the state directory below the data directory.', cli('--print-config-dir'))]),
        step('help', 'Print the usage text with the --help option.', [],
             [('text', 'The usage text equals what the reference prints and the exit status is zero.', cli('--help'))]),
        step('config', 'Print the default configuration with the --config option.', [],
             [('text', 'The default configuration equals what the reference prints and the exit status is zero.', cli('--config'))]),
    ]))

    W.append(program('state-file', 'state', None, [
        step('fresh', 'Observe the state file of a freshly started application.', [],
             [('file', 'The state file exists and lists the workspace as the only recent repository.', state())]),
    ]))

    W.append(program('clipboard', 'clipboard', None, [
        cp('newest', 'Copy the abbreviated hash of the newest commit to the clipboard.', H3, K('4', 'Control+O'),
           [('text', 'The clipboard holds the abbreviated hash of the newest commit, copied once.', clip())]),
        cp('second', 'Copy the abbreviated hash of the second commit to the clipboard.', H3, K('4', 'j', 'Control+O'),
           [('text', 'The clipboard holds the abbreviated hash of the second commit, copied once.', clip())]),
    ]))
    return W

"""One episode in a fresh runtime instance: the shared driver with the taskwarrior-tui hooks."""
from evaluation.driver import main
import hooks

if __name__ == '__main__':
    raise SystemExit(main(hooks.Hooks()))

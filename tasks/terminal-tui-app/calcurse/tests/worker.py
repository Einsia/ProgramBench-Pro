"""One episode in a fresh runtime instance: the shared driver with the calcurse hooks."""
from evaluation.driver import main
import hooks

if __name__ == '__main__':
    raise SystemExit(main(hooks.Hooks()))

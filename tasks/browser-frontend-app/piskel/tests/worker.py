"""One episode in a fresh runtime instance: the kit driver with the Piskel hooks."""
from evaluation.driver import main
import hooks

if __name__ == '__main__':
    raise SystemExit(main(hooks.Hooks()))

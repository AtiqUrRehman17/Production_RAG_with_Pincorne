"""Start the background worker:  python -m workers   (stop it with Ctrl+C)."""

import sys

from workers.worker import create_worker


def main() -> None:
    # Windows terminals default to a legacy encoding that can't print all characters
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        create_worker().run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

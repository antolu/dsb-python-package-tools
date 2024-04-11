from __future__ import annotations

import sys

from .main import main


def entrypoint() -> None:
    main(sys.argv[1:])


if __name__ == "__main__":
    entrypoint()

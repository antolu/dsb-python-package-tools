from __future__ import annotations


from .main import main
import sys


def entrypoint() -> None:
    main(sys.argv[1:])


if __name__ == "__main__":
    entrypoint()

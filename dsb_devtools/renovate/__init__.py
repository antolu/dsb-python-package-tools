from __future__ import annotations

from .._mod_replace import replace_modname
from ._renovate import make_parser, setup, teardown, update

for _mod in (make_parser, setup, teardown, update):
    replace_modname(_mod, __name__)


del _mod
del replace_modname

"""
The `pkginit` module is the package that generates a package skeleton.
"""

from ._input import make_parser
from ._pkginit import main
from .._mod_replace import replace_modname


for _mod in (make_parser, main):
    replace_modname(_mod, __name__)


del _mod
del replace_modname
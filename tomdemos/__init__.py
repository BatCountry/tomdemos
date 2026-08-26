# todo:  use importlib to get all of the modules in `tomdemos.demos` and reexport their main by module name in __all__
from tomdemos.demos.fire import main as fire
from tomdemos.demos.fire2 import main as fire2
from tomdemos.demos.multiwin import main as multiwin

__all__ = [
    'fire',
    'fire2',
    'multiwin',
]

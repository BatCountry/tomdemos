# todo:  use importlib to get all of the modules in `tomdemos.demos` and reexport their main by module name in __all__
from tomdemos.demos.fire import main as fire

__all__ = [
    'fire'
]

from dataclasses import dataclass
from typing import Any, Callable, Generator

# in python 3.15 we're getting a `sentinel` type in `builtins` which is for exactly this
UNSET = object()


@dataclass
class Parameter:
    """A single parameter in this application"""
    # Parameter name - should only contain valid variable characters or you can't dot reference it
    # break the rule if you want, just saying
    name: str

    # Default value, can be different from value for reasons
    default: Any

    # Optional starting value, can be different from default for reasons
    value: Any = UNSET

    # Description for display in a graphical editor, otherwise pointless
    description: str = ""

    # Returns True if parameter is valid
    validator: Callable[[Any], bool] | None = None

    def __post_init__(self):
        if not self.name:
            raise ValueError("`name` must not be an empty string.")

        # convenience mechanism so that a user of the code can just do {"name": "monkey_count", "default": 13}
        # if they want a default value to reset to (reset button is disabled in ui if default isn't set)
        # but don't want to define the default and the value both explicitly for tidiness
        self.value = self.value if self.value is not UNSET else self.default


class Parameters:
    """
    A collection for containing the parameters of an application.
    Intended to be used for explicitly iterating over the manipulable parameters of a demo
    Can be exposed through the UI window controls
    """
    _parameters: dict[str, Parameter]


    # The type hints don't help us here, but the dataclass Parameter does
    # if the parameter_arguments contain bad keys, Parameter's constructor will
    # raise, also if the name or default value is missing
    def __init__(self, parameter_arguments: list[dict[str, Any]]) -> None:
        self._parameters = dict()
        for args in parameter_arguments:
            param: Parameter = Parameter(**args)
            self._parameters[param.name] = param

    # Support for treating this like a simple list/enumerable instead of a dict or a non-iterable object
    def __iter__(self) -> Generator[Parameter]:
        for param in self._parameters.values():
            yield param

    # deliberately using the square bracket invocation because __getitem__ is the builtin that is called when you reference something with []
    # so I want this to throw a KeyError anyway if the parameter name doesn't exist and it's easier to do this than to catch KeyError and re-throw
    def __getitem__(self, which):
        return self._parameters[which].value

    # necessary, otherwise [] returns a read-only value
    def __setitem__(self, key, value):
        if self._parameters[key].validator is not None:
            if not self._parameters[key].validator(value): # pyright: ignore[reportOptionalCall] # pylance is fucking stupid and the devs should feel bad about their ability to write code
                raise ValueError(f'{value} did not pass the validator for {key}')
        self._parameters[key].value = value

    # lets me use dot to access, like params.monkey_count
    def __getattr__(self, name: str) -> Any:
        try:
            return self.__dict__['_parameters'][name].value
        except KeyError:
            raise AttributeError(name)

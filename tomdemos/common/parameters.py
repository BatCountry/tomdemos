import operator

from dataclasses import dataclass, field
from typing import Any, Callable, Generator

import numpy as np

# in python 3.15 we're getting a `sentinel` type in `builtins` which is for exactly this
UNSET = object()


@dataclass
class Headers:
    """
    Uses the header columns and label rows until consumed, leaves the rest unlabeled
    """
    columns: list[str] = field(default_factory=list)
    rows: list[str] = field(default_factory=list)


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

    # Labels for columns or rows {"columns": ["foo", "bar"], "rows": ["primus", "secundus"]}
    headers: Headers = field(default_factory=Headers)

    # Optional transform applied before validator checks
    pre_validator: Callable[[Any], Any] | None = None

    # Returns True if parameter is valid
    validator: Callable[[Any], bool] | None = None

    # Optional per-column validators for table parameters, with an optional "default" fallback
    column_validators: dict[int | str, Callable[[Any], bool]] = field(default_factory=dict)

    # Optional factory for appending a new row to variable-length table parameters
    row_factory: Callable[[], Any] | None = None

    _dirty: bool = False

    # Marker for labelling a value as changed and needing reprocessing
    def dirty(self):
        self._dirty = True

    def is_dirty(self):
        return self._dirty

    def clean(self):
        self._dirty = False

    def apply_pre_validator(self, value: Any) -> Any:
        if self.pre_validator is None:
            return value

        if type(value) is list:
            return [self.apply_pre_validator(item) for item in value]

        if type(value) is tuple:
            return tuple(self.apply_pre_validator(item) for item in value)

        return self.pre_validator(value)

    def accepts(self, value: Any) -> bool:
        value = self.apply_pre_validator(value)
        return self.validator is None or self.validator(value)

    def accepts_column(self, column: int, value: Any) -> bool:
        value = self.apply_pre_validator(value)
        validator = self.column_validators.get(column)
        if validator is None:
            validator = self.column_validators.get("default")
        return validator is None or validator(value)

    def __post_init__(self):
        if not self.name:
            raise ValueError("`name` must not be an empty string.")
        
        if self.headers and type(self.headers) is dict:
            self.headers = Headers(**self.headers) # type: ignore

        # convenience mechanism so that a user of the code can just do {"name": "monkey_count", "default": 13}
        # if they want a default value to reset to (reset button is disabled in ui if default isn't set)
        # but don't want to define the default and the value both explicitly for tidiness
        self.value = self.value if self.value is not UNSET else self.default

    def __int__(self):
        return int(self.value)

    def __lt__(self, other):
        try:
            return self.value < other.value
        except AttributeError:
            return self.value < other

    def __gt__(self, other):
        try:
            return self.value > other.value
        except AttributeError:
            return self.value > other

    def __eq__(self, other):
        try:
            return self.value == other.value
        except AttributeError:
            return self.value == other

    def __index__(self):
        return int(self.value)

    def __float__(self):
        return float(self.value)

    def __str__(self):
        return str(self.value)

    def __iter__(self):
        return iter(self.value)

    def __add__(self, other):
        try:
            return operator.add(self.value, other.value)
        except AttributeError:
            return operator.add(self.value, other)

    def __sub__(self, other):
        try:
            return operator.sub(self.value, other.value)
        except AttributeError:
            return operator.sub(self.value, other)

    def __mul__(self, other):
        try:
            return operator.mul(self.value, other.value)
        except AttributeError:
            return operator.mul(self.value, other)

    def __truediv__(self, other):
        try:
            return operator.truediv(self.value, other.value)
        except AttributeError:
            return operator.truediv(self.value, other)

    def __array__(self):
        return np.array([self.value,])


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

    def get_parameter(self, name: str) -> Parameter:
        return self._parameters[name]

    # necessary, otherwise [] returns a read-only value
    def __setitem__(self, key, value):
        value = self._parameters[key].apply_pre_validator(value)
        if not self._parameters[key].accepts(value):
            raise ValueError(f'{value} did not pass the validator for {key}')
        self._parameters[key].value = value

    # lets me use dot to access, like params.monkey_count
    def __getattr__(self, name: str) -> Any:
        try:
            return self.__dict__['_parameters'][name]
        except KeyError:
            raise AttributeError(name)

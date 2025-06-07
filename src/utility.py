from typing import Any


def cast[T](target_type: type[T], value: Any):  # noqa: ANN401
    if isinstance(value, target_type):
        return value
    msg = f'Expected value of type {target_type.__name__}, got {type(value).__name__}'
    raise TypeError(msg)

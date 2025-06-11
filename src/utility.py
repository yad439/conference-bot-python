from collections.abc import Iterable
from typing import Any


def cast[T](target_type: type[T], value: Any):  # noqa: ANN401
    if isinstance(value, target_type):
        return value
    msg = f'Expected value of type {target_type.__name__}, got {type(value).__name__}'
    raise TypeError(msg)


def assert_not_nones[T](iterable: Iterable[T | None]):
    return map(cast_not_none, iterable)


def cast_not_none[T](value: T | None) -> T:
    if value is None:
        msg = 'Value is None'
        raise TypeError(msg)
    return value

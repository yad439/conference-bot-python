from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


class FileManager:
    def __init__(self, file_paths: Mapping[str, Path]):
        self._file_paths = file_paths
        self._uploaded_files: dict[str, str] = {}

    def get_file_id(self, name: str):
        return self._uploaded_files.get(name)

    def get_file_path(self, name: str) -> Path:
        return self._file_paths[name]

    def set_file_id(self, name: str, file_id: str):
        self._uploaded_files[name] = file_id


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

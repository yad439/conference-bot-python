from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from aiogram.types import User
from aiogram.utils.formatting import Text, as_list, as_section


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


def format_user(user: User | None):
    if user is None:
        return 'Unknown'
    return f'{user.first_name} {user.last_name} ({user.id})'


def as_list_section(header: Text | str, *body: Text | str):
    return as_section(header, as_list(*body))


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

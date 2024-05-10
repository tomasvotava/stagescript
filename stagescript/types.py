from typing import TypeVar

__all__ = ["guard"]

T = TypeVar("T")


def guard(value: T | None, type_: type[T]) -> T:
    if isinstance(value, type_):
        return value
    raise TypeError(f"{value} was expected to be {type_!r}, got {type(value)!r} instead")

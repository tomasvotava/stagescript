from typing import Any

import pytest

from stagescript.types import guard


@pytest.mark.parametrize(
    ("value", "check_type", "passes"),
    [("string", str, True), (None, str, False), (3, int, True), ("3", int, False), (["test"], list, True)],
)
def test_guard(value: Any, check_type: type[Any], passes: bool) -> None:
    if passes:
        assert guard(value, check_type) == value
    else:
        with pytest.raises(TypeError, match=".* was expected to be"):
            guard(value, check_type)

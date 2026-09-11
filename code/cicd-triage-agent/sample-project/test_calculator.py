"""Real unit tests. test_add fails in CI because calculator.add has a bug."""
import pytest
from calculator import add, multiply, divide


def test_add():
    assert add(2, 3) == 5          # fails: add() returns -1 (it subtracts)


def test_multiply():
    assert multiply(4, 5) == 20


def test_divide():
    assert divide(10, 2) == 5


def test_divide_by_zero():
    with pytest.raises(ValueError):
        divide(1, 0)

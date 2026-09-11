"""A tiny library the CI builds and tests — with one real bug (see add)."""


def add(a: float, b: float) -> float:
    # BUG: subtracts instead of adds — this makes test_add fail for real in CI.
    return a - b


def multiply(a: float, b: float) -> float:
    return a * b


def divide(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("cannot divide by zero")
    return a / b

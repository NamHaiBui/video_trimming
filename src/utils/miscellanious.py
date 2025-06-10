def not_none[T](obj: T | None) -> T:
    assert obj is not None
    return obj
SENTINEL_VALUES = {"", 0, 0.0, None, False, (), frozenset()}

def is_sentinel(value) -> bool:
    try:
        if value in SENTINEL_VALUES:
            return True
        if value == [] or value == {}:
            return True
    except Exception:
        pass
    return False

def shadow_check(func_name: str, return_value, guard_type: str):
    if is_sentinel(return_value):
        print(
            f"[CodeSuture SHADOW] âš  {func_name}() returned sentinel "
            f"value {return_value!r} after {guard_type} patch. "
            f"Verify this default is safe for downstream consumers."
        )


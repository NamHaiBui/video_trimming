def safe_int(value, default=0):
    if isinstance(value, (int, float)):
        return int(value)
    elif isinstance(value, str) and value.isdigit():
        return int(value)
    else:
        return default
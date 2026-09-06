import math


class ParseError(ValueError):
    pass


def parse_number(token):
    value = float(token)
    if not math.isfinite(value):
        raise ParseError('non-finite number')
    return value

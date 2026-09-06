#!/usr/bin/env python3
from parser import ParseError, parse_number

for token, expected in [('1.5', 1.5), ('-2', -2.0)]:
    if parse_number(token) != expected:
        raise SystemExit('FAIL finite number changed: ' + token)
for token in ['NaN', 'Infinity', '-Infinity']:
    try:
        parse_number(token)
    except ParseError:
        continue
    raise SystemExit('FAIL accepted non-finite number: ' + token)
print('PASS finite/non-finite parser matrix: assertions passed')

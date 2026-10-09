"""Checks on a model answer before the app sees it.

The model may not make up figures: every number it says must already be in
what it was given. Compared as values, so `7.90` in the data allows `7.9`.
"""

import json
import re
from decimal import Decimal, InvalidOperation

NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
MAX_WORDS = 45


def numbers(text):
    found = set()
    for token in NUMBER.findall(text):
        try:
            found.add(Decimal(token.replace(",", ".")).normalize())
        except InvalidOperation:
            continue
    return found


def invented_numbers(said, given):
    """Numbers in `said` that appear nowhere in `given` (any JSON-able value)."""
    return numbers(said) - numbers(json.dumps(given, ensure_ascii=False))


def too_long(speech):
    return len(speech.split()) > MAX_WORDS

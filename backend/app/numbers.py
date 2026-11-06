"""Check that every number in an answer appears in what the tools returned.

The prompt tells the model not to state numbers from memory, but a prompt is not a guarantee.
This check is code. It only reports: some numbers are legitimately absent from the tool output,
like "here are 3 models", so blocking or retrying would spend budget on false alarms.
"""

import re
from decimal import Decimal, InvalidOperation

NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
# Counts such as "3 models" or "2 options" are not data from the tables.
SMALL_INTEGER_LIMIT = 10


def _candidates(token: str) -> set[Decimal]:
    """Possible values of a number as written. "4,800" and "4.800" can mean 4800 or 4.8."""
    values = set()
    for text in {token.replace(",", ""), token.replace(".", "").replace(",", "."), token.replace(",", ".")}:
        if text.count(".") <= 1:
            try:
                values.add(Decimal(text).normalize())
            except InvalidOperation:
                pass
    return values


def numbers_in(value: object) -> set[Decimal]:
    """Every number inside a tool result, including those inside strings such as part numbers."""
    found: set[Decimal] = set()
    if isinstance(value, bool) or value is None:
        return found
    if isinstance(value, (int, float, Decimal)):
        found.add(Decimal(str(value)).normalize())
    elif isinstance(value, str):
        for token in NUMBER.findall(value):
            found |= _candidates(token)
    elif isinstance(value, dict):
        for item in value.values():
            found |= numbers_in(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            found |= numbers_in(item)
    return found


def unverified_numbers(answer: str, sources: list[object]) -> list[str]:
    """Numbers written in the answer that no source contains."""
    allowed: set[Decimal] = set()
    for source in sources:
        allowed |= numbers_in(source)

    unverified = []
    for token in NUMBER.findall(answer):
        candidates = _candidates(token)
        if any(value == value.to_integral() and value <= SMALL_INTEGER_LIMIT for value in candidates):
            continue
        if not candidates & allowed and token not in unverified:
            unverified.append(token)
    return unverified

"""Signal-matching helpers used by metrics."""
from __future__ import annotations

import re


def match_signal(response: str, signal: str) -> bool:
    """Return True if *signal* appears in *response*.

    Signals follow a small DSL:
      - plain substring (case-insensitive) is the default
      - ``re:<pattern>`` means a regex match
      - ``not:<signal>`` means the response must NOT match; used in negative_signals,
        but also accepted here so both lists can share the same matcher.
    """
    if not signal:
        return False
    if signal.startswith("not:"):
        return not match_signal(response, signal[4:])
    if signal.startswith("re:"):
        try:
            return bool(re.search(signal[3:], response, flags=re.IGNORECASE))
        except re.error:
            return False
    return signal.lower() in response.lower()


def coverage(response: str, expected: list[str]) -> float:
    if not expected:
        return 1.0
    return sum(1.0 for s in expected if match_signal(response, s)) / len(expected)


def violation_rate(response: str, negatives: list[str]) -> float:
    """Fraction of negatives that WERE violated (should be 0 ideally)."""
    if not negatives:
        return 0.0
    return sum(1.0 for s in negatives if match_signal(response, s)) / len(negatives)

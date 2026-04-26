from __future__ import annotations

from collections import defaultdict

_limit_up_symbols: dict[str, list[str]] = defaultdict(list)


def set_limit_up_symbols(researcher_id: str, symbols: list[str]) -> None:
    _limit_up_symbols[researcher_id] = symbols


def get_limit_up_symbols(researcher_id: str) -> list[str]:
    return list(_limit_up_symbols.get(researcher_id, []))

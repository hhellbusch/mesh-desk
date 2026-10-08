"""Order and filter the chat-pane node list. The map keeps its own copy."""

from __future__ import annotations


def node_matches(row: dict, query: str) -> bool:
    text = query.strip().casefold()
    if not text:
        return True
    haystack = " ".join(
        str(row.get(key) or "") for key in ("long", "short", "id")
    ).casefold()
    return text in haystack


def sort_nodes(rows: list[dict], mode: str) -> list[dict]:
    def name(row: dict) -> str:
        return str(row.get("long") or "").casefold()

    def hops_key(row: dict) -> tuple:
        hops = row.get("hops")
        if hops is None:
            return (1, 0, name(row))
        return (0, int(hops), name(row))

    def seen_key(row: dict) -> tuple:
        heard = row.get("last_heard")
        try:
            stamp = float(heard) if heard is not None else None
        except (TypeError, ValueError):
            stamp = None
        if stamp is None:
            return (1, 0.0, name(row))
        return (0, -stamp, name(row))

    if mode == "seen":
        key = seen_key
    elif mode == "name":
        key = lambda row: (name(row),)
    else:
        key = hops_key
    return sorted(rows, key=key)

"""Chat-pane node order and name search."""

from mesh_desk.nodelist import node_matches, sort_nodes

ROWS = [
    {"id": "!far", "long": "Far", "short": "FAR", "hops": 3, "last_heard": 200},
    {"id": "!zero", "long": "Zero", "short": "ZRO", "hops": 0, "last_heard": 100},
    {"id": "!old", "long": "Alpha", "short": "ALP", "hops": None, "last_heard": None},
    {"id": "!new", "long": "Middle", "short": "MID", "hops": 1, "last_heard": 300},
]


def test_sort_by_hops_puts_unknown_last() -> None:
    assert [row["id"] for row in sort_nodes(ROWS, "hops")] == ["!zero", "!new", "!far", "!old"]


def test_sort_by_last_seen_is_newest_first() -> None:
    assert [row["id"] for row in sort_nodes(ROWS, "seen")] == ["!new", "!far", "!zero", "!old"]


def test_sort_by_name() -> None:
    assert [row["long"] for row in sort_nodes(ROWS, "name")] == ["Alpha", "Far", "Middle", "Zero"]


def test_search_matches_long_short_or_id() -> None:
    assert node_matches(ROWS[0], " far ")
    assert node_matches(ROWS[0], "FAR")
    assert node_matches(ROWS[0], "!far")
    assert not node_matches(ROWS[0], "zero")
    assert node_matches(ROWS[0], "")

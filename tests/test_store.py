"""Local chat history."""

import time

from mesh_desk.store import Store


def test_channel_and_direct_threads_stay_separate(tmp_path) -> None:
    store = Store(tmp_path / "messages.sqlite")
    now = time.time()
    store.add(kind="channel", text="mesh", channel=0, from_id="!a", ts=now)
    store.add(kind="dm", text="private", peer="!b", from_id="!a", ts=now)
    assert [row["text"] for row in store.list_channel(0)] == ["mesh"]
    assert [row["text"] for row in store.list_dm("!b")] == ["private"]
    assert store.recent_duplicate("!a", "mesh") is True
    assert store.recent_duplicate("!a", "other") is False
    store.close()

import json

from swarm.events import SwarmListener


def test_teardown_unregisters_every_handler(tmp_path):
    listener = SwarmListener(tmp_path)
    assert listener._handlers, "listener should register handlers on init"
    listener.teardown()
    assert listener._handlers == []
    # Idempotent: a second teardown is a no-op, not an error.
    listener.teardown()


def test_events_still_append_after_listener_creation(tmp_path):
    listener = SwarmListener(tmp_path)
    listener._append({"type": "crew_done"})
    lines = (tmp_path / "events.jsonl").read_text().splitlines()
    assert json.loads(lines[0]) == {"type": "crew_done"}
    listener.teardown()

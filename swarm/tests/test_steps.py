from swarm.crew import MAX_STEPS, parse_steps, steps_usable


def test_parse_steps():
    plan = "STEP 1: app/main.py — create FastAPI app\nSTEP 2: app/cache.py — add sqlite helper\nnotes"
    assert parse_steps(plan) == [
        "app/main.py — create FastAPI app",
        "app/cache.py — add sqlite helper",
    ]


def test_parse_steps_never_silently_truncates():
    plan = "\n".join(f"STEP {i}: app/x.py — edit {i}" for i in range(1, MAX_STEPS + 5))
    steps = parse_steps(plan)
    assert len(steps) == MAX_STEPS + 4
    assert steps_usable(steps) is False  # over budget fails loudly instead of dropping work


def test_parse_steps_empty():
    assert parse_steps("no steps here") == []
    assert steps_usable([]) is False


def test_steps_usable_rejects_tiny_steps():
    assert steps_usable(["ok"]) is False
    assert steps_usable(["app/x.py — add endpoint"]) is True

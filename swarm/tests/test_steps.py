from swarm.crew import MAX_STEPS, parse_steps


def test_parse_steps():
    plan = "STEP 1: app/main.py — create FastAPI app\nSTEP 2: app/cache.py — add sqlite helper\nnotes"
    assert parse_steps(plan) == [
        "app/main.py — create FastAPI app",
        "app/cache.py — add sqlite helper",
    ]


def test_parse_steps_caps():
    plan = "\n".join(f"STEP {i}: x" for i in range(1, 20))
    assert len(parse_steps(plan)) == MAX_STEPS


def test_parse_steps_empty():
    assert parse_steps("no steps here") == []

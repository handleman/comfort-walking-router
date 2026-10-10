from swarm.spec_loader import parse_tasks_md


def test_parse_001_tasks_shape():
    text = (
        "- [ ] T1 (AC-1, AC-4): Scaffold `app/` + `frontend/`\n"
        "- [ ] T2 (AC-1): Backend geocode\n"
    )
    tasks = parse_tasks_md(text)
    assert [t.id for t in tasks] == ["T1", "T2"]
    assert tasks[0].ac_refs == ("AC-1", "AC-4")

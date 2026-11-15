from swarm.spec_loader import parse_tasks_md


def test_parse_001_tasks_shape():
    text = (
        "- [ ] T1 (AC-1, AC-4): Scaffold `app/` + `frontend/`\n"
        "- [ ] T2 (AC-1): Backend geocode\n"
    )
    tasks = parse_tasks_md(text)
    assert [t.id for t in tasks] == ["T1", "T2"]
    assert tasks[0].ac_refs == ("AC-1", "AC-4")


# ---- 032: the kind is a property of the spec directory ----


def _spec_dir(root, name, kind=None, tasks="- [ ] T1 (AC-1): do x\n"):
    d = root / "specs" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "spec.md").write_text("# spec\n")
    (d / "plan.md").write_text("# plan\n")
    (d / "tasks.md").write_text(tasks)
    if kind is not None:
        (d / "kind").write_text(kind)
    return d


def test_a_missing_kind_is_a_product_spec(tmp_path):
    from swarm.spec_loader import spec_kind

    _spec_dir(tmp_path, "001-x")
    assert spec_kind(tmp_path, "001-x") == "product"


def test_a_kind_file_is_trimmed_and_read(tmp_path):
    from swarm.spec_loader import spec_kind

    _spec_dir(tmp_path, "012-x", kind="control-plane\n\n")
    assert spec_kind(tmp_path, "012-x") == "control-plane"
    _spec_dir(tmp_path, "013-x", kind="  product  \n")
    assert spec_kind(tmp_path, "013-x") == "product"
    # Anything unrecognised is a product spec, never accidentally control-plane.
    _spec_dir(tmp_path, "014-x", kind="harness\n")
    assert spec_kind(tmp_path, "014-x") == "product"

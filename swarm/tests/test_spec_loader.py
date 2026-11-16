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

    _spec_dir(tmp_path, "012-x", kind="harness\n\n")
    assert spec_kind(tmp_path, "012-x") == "harness"
    _spec_dir(tmp_path, "013-x", kind="  product  \n")
    assert spec_kind(tmp_path, "013-x") == "product"
    # 032's value was `control-plane`; a legacy flat marker is still harness.
    _spec_dir(tmp_path, "014-x", kind="control-plane\n")
    assert spec_kind(tmp_path, "014-x") == "harness"
    # Anything unrecognised is a product spec, never accidentally harness.
    _spec_dir(tmp_path, "015-x", kind="unknown\n")
    assert spec_kind(tmp_path, "015-x") == "product"


def test_a_folder_is_authoritative_for_kind(tmp_path):
    from swarm.spec_loader import spec_kind

    def make(kind: str, name: str):
        d = tmp_path / "specs" / kind / name
        d.mkdir(parents=True)
        (d / "spec.md").write_text("# s\n")
        (d / "plan.md").write_text("# p\n")
        (d / "tasks.md").write_text("- [ ] T1 (AC-1): do x\n")
        (d / "kind").write_text("product\n" if kind == "harness" else "harness\n")

    make("harness", "010-x")
    make("product", "011-x")
    # The folder wins even when the sidecar disagrees.
    assert spec_kind(tmp_path, "010-x") == "harness"
    assert spec_kind(tmp_path, "011-x") == "product"

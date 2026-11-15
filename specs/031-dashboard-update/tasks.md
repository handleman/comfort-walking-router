# 031 Dashboard Update — Tasks

Control-plane spec (`HARNESS_SPECS`): implemented by hand, never queued.

- [ ] T1 (AC-1): Add `opencode-go/` to the `short_model` prefix list in `swarm/tui.py` (so a Go planner and the Zen/OpenRouter roles all render as bare ids); confirm `ollama/` still gets its "local" suffix. Tests in `swarm/tests/test_tui_format.py`: `short_model` for `openrouter/…`, `zen/…`, `ollama/…`, `opencode-go/…` and a bare id, plus the long-id collapse.
- [ ] T2 (AC-2): In `swarm/tui.py::_refresh_status`, render `spec_dir_name(REPO_ROOT, self._spec)` next to the task id instead of the raw prefix, so the status line shows `specs/028-route-comfort-profile T4` for either `028` or the full directory. Keep `self._spec` for the queue list and history filter. Test: the directory resolves for a prefix and for a full directory, and a non-matching prefix degrades to the input.
- [ ] T3 (AC-3): Add `format_self_heal(payload)` to `swarm/tui.py` (returns `""` when `e2e_self_heal` is absent) and render it in the live and tail status views after the gates block: `e2e self-heal: class drift · 2 failing · 1 round(s) · healed`, then one `· T<n> <brief>` line per roster task. Tests: healed drift with a roster, `e2e_weakened` with a roster, empty payload → `""`. Match `swarm/humanlog.py`'s line wording (one formatter, 018).
- [ ] T4 (AC-4): Close out: add `031-dashboard-update` to `HARNESS_SPECS` in `swarm/flow.py`; record it in `changelog.md`; run `make swarm-test`, `ruff check .`, `mypy app tests` — all green, with the numbers in the task's commit message.

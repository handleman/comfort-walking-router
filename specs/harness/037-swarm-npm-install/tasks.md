# 037 Swarm npm install — Tasks

- [x] T1 (AC-1, AC-2): Allow `npm --prefix frontend install|ci|add|i` in `_valid_npm` (gated by `npm_install_enabled()`), rejecting `--prefix`/`--global`/`-g`; keep `run`/`test`/`exec` unchanged.
- [x] T2 (AC-3): Add the `SWARM_NPM_INSTALL` off switch and the ShellTool description note.
- [x] T3 (AC-4): Tests in `test_guards.py` for the allow/block matrix + the off switch; changelog entry.

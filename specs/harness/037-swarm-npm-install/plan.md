# 037 Swarm npm install — Plan

1. Add `npm_install_enabled()` (reads `SWARM_NPM_INSTALL`, default `1`) next to
   the other env toggles in `swarm/tools_guarded.py`.
2. In `_valid_npm`, accept `install`/`ci`/`add`/`i` when `npm_install_enabled()`,
   rejecting `--prefix`, `--global`, `-g` in the args; keep `run`/`test`/`exec`
   branches unchanged.
3. Update the ShellTool `description` (mention `npm install` is now allowed).
4. Tests in `swarm/tests/test_guards.py`: allowed install/ci, blocked exec/npx/
   `--global`/second `--prefix`, and the off switch.

Risks: `npm install` runs package scripts (see spec); keep it prefix-locked and
meta-free, and keep `npx`/`exec` out.

# Commit path, ledger and sandbox

> Part of the swarm harness documentation. Start at [`../README.md`](../README.md).

## Commit path: branch-per-task + merge queue (012 T18)
Default (`SWARM_MERGE_MODE=merge`):
1. `git switch -c swarm/<spec>-<task>` (worktree changes travel with it).
2. `git add` only the run-delta in-scope paths; commit `swarm: <spec>-<task> green …`.
3. Push the task branch (`git push -u origin <branch>`).
4. Switch to the base branch (`SWARM_BASE_BRANCH`, default current branch) and
   `git merge --no-ff` with `merge: swarm <spec>-<task> green`.
5. Push the base. If that final push fails, local `reset --hard` back to the pre-merge
   SHA (status `push_failed`, branch kept as the recovery point / `rollback` in `run.json`).

**Conflicts (016).** One `Merge Conflict Resolver` crew gets the conflicted
files (read + edit only, no shell). Its merge is accepted only if no conflict
marker remains and every configured gate exits 0; then the harness `git add`s,
commits and pushes the merge. A rejected attempt `git merge --abort`s, leaves
the base untouched, and the run stops with `merge_failed` +
`autocommit.conflict` evidence. `SWARM_CONFLICT_CREW=0` disables it;
`SWARM_CONFLICT_MODEL` defaults to `SWARM_CODER_MODEL`. A conflicted **stash
pop** is a different problem: a `Stash Conflict Resolver` crew re-applies the
parked work on the newer tree under the same deterministic acceptance, falling
back to `--ours` (archived) if that is not provably safe. See
"Stash lifecycle" above. Out-of-scope dirty files are never staged.
`SWARM_MERGE_MODE=direct` restores the old commit-straight-to-base path;
`SWARM_DELETE_MERGED_BRANCH=1` deletes a merged branch locally and remotely.

## Done ledger, approval resume, crash checkpoints (013)
- **Done ledger (commit trailers).** Every green commit carries
  `Swarm-Task: <spec>/<T n>`, `Swarm-Task-Hash` (id+brief+ACs) and
  `Swarm-Spec-Hash` (`spec.md`+`plan.md`). Resume/auto-advance skip a task whose
  hashes still match even when its line is still `- [ ]`; the swarm still never
  edits `specs/`. Editing the brief/ACs *or* `spec.md`/`plan.md` reopens the task.
  Marking `[x]` alone changes neither hash. A gitignored
  `swarm/runs/done.json` cache covers shallow/rewritten history. An explicit
  `./swarm/run.sh SPEC TASK` still runs that task even if done.
- **Approval resume.** An `awaiting_approval` run records `delta_hashes` and the
  current `head`. `make swarm-approve` / `--approve` / TUI `a` commits exactly
  that verified delta through the branch/merge queue, rewrites the run to `green`,
  and the next resume advances — no crew rerun. It refuses (run stays held) if the
  recorded files changed, HEAD no longer descends from the hold, or new in-scope
  edits appeared. Only out-of-scope human edits are ignored. With no held run, the
  command falls back to the next-run approval ledger.
- **Crash checkpoints.** After every micro-step the flow atomically writes
  `progress.json` (plan hash, steps, completed index, per-step outputs, run-delta
  hashes). A killed/interrupted run resumes at the next step only when plan, steps,
  and file hashes still match and the checkpoint is younger than
  `SWARM_RESUME_MAX_AGE_SECONDS` (default 86400). Gates and the reviewer always
  rerun. Otherwise the task restarts from step 1 and `run.json` records
  `recovery="restart"` + `recovery_note`; a checkpoint resume records
  `resumed_from_step` and `recovery="checkpoint"`.

## Container sandbox (012 T17)
```bash
make swarm-sandbox                       # build + run the pilot in Docker
./swarm/sandbox.sh --dry-run 001 T3      # print the mount/run command, touch nothing
```
Needs a Docker daemon. On macOS without Docker Desktop, Colima works:
```bash
brew install colima docker        # already installed here
colima start --cpu 4 --memory 8 --disk 60   # 8 GB keeps the image build happy
docker context use colima         # `colima start` usually selects it already
```
Verified 2026-11-08 with Colima (8 GB): image build, imports, the full 148-test
harness suite inside the container, OpenRouter egress, Ollama via
`host.docker.internal`, and a real coder+planner model call.

The image (`swarm/docker/Dockerfile`) has app + harness deps and the gate binaries.
At runtime the **only mounts are the repo** (`$PWD:/work`, rw) and a read-only
`/dev/null` overlay on `.env`, so the coder process/tools cannot read secrets from
the repo; keys arrive as env values via `--env-file`. No HOME, SSH agent, or host
caches are mounted, with `--cap-drop=ALL`, `no-new-privileges`, PID/memory caps,
and the host UID.

- Ollama: the container reaches the host at `host.docker.internal:11434`
  (override with `SWARM_SANDBOX_OLLAMA_URL`). With Colima this works even when
  Ollama listens on `127.0.0.1`; on plain Linux, bind it with
  `OLLAMA_HOST=0.0.0.0 ollama serve`.
- Commits default to **off** in the sandbox (no git credentials): review and commit
  on the host. Opt in with `SWARM_SANDBOX_ALLOW_COMMIT=1`; for SSH remotes also set
  `SWARM_SANDBOX_SSH=1` to mount `~/.ssh` read-only.
- `SWARM_SANDBOX_NO_BUILD=1` reuses the last image; `SWARM_SANDBOX_IMAGE` renames it.

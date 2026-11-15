# Traces, logs and troubleshooting

> Part of the swarm harness documentation. Start at [`../README.md`](../README.md).

## Traces & logs (all inside the project, never `/tmp`)
- Pilot runs: `swarm/runs/<ts>-<pid>-<rand>/{run.json,events.jsonl,progress.json}` (+ `latest` pointer).
  `run.json` records brief, `ac_refs`, changed files, gates, reviewer verdict, the
  self-check (017) and scenario verifier (019) records, approval, commit/push result,
  usage, done-ledger hashes, checkpoint recovery, and a compact `evidence` block.
- Approvals: `swarm/runs/approvals/<spec>-<task>.json` (task-keyed, survives retries);
  held-run deltas are committed by `make swarm-approve` (013).
- Done ledger: `swarm/runs/done.json` cache (git commit trailers remain the source of truth).
- Coordination: `swarm/runs/.lock` (flock), `swarm/runs/swarm.pid` (stop target).
- Ad-hoc probes/debug: `swarm/runs/probes/<name>-<date>.log`. `swarm/runs/` is gitignored.

## Troubleshooting
- `429 free-models-per-min` (OpenRouter): per-minute quota on `:free` (20/min). Wait ~60s and retry; LLMs already set `max_retries=5`. Persistent → change `SWARM_PLANNER_MODEL` to another `:free` id from `curl "https://openrouter.ai/api/v1/models?supported_parameters=tools&sort=pricing-low-to-high"`.
- `Python >=3.10,<3.14 required`: recreate venv with `-p 3.12`.
- Ollama refused: `ollama serve`; check `curl http://localhost:11434/api/tags`.
- `Invalid response from LLM call - None or empty` on local Qwen: thinking blocks break tool parsing — harness already sets `extra_body={"think": False}` on all Ollama LLMs; if you add a new Ollama model id, keep it. Single transient empties still occur; `flow` re-kicks the crew once automatically.
- Local Qwen-9B as **planner** loses the plot (verified 2026-10-10: listed `.git/` internals, asked "what would you like to do" instead of writing the plan). Keep cloud brains (OpenRouter `:free` / Zen) for planner + reviewer; local Qwen is coder-only material with reviewer gates.
- `swarm/.venv/`, `swarm/runs/`, `swarm/.env` are gitignored — safe to run freely.
- **`UU` paths / conflict markers in the tree**: a `git stash pop` conflicted
  and left index stages behind. Preflight now refuses to start on unmerged
  paths, and a conflicted restore resolves to the current worktree (`--ours`),
  archives the stash as `refs/swarm/archive/<stamp>-<sha>`, and records
  `stash_conflict` + `stash_conflict_ref` + `stash_conflict_resolution` in
  `run.json`. A resolver crew usually re-applies the parked work first; `ours`
  means it was rejected (read `stash_conflict_note`) and the old side is in the
  archived ref. Inspect with `git show <ref>:<path>` or
  `swarm/runs/orphan_stashes.json`; this is not a branch-merge conflict.

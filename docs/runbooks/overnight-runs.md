# Runbook: unattended swarm runs (overnight)

**Applies to:** the CrewAI dark-factory pilot (`swarm/`), macOS host.
**Goal:** let the queue run for hours without a human, without losing work to sleep, a locked screen, or a closed lid.

## TL;DR

```bash
make swarm-stop     # if a pilot is already running (single-run lock)
make swarm-night    # caffeinate -is + swarm.supervise
```

Attach the dashboard from another terminal with `make swarm-dash`; inspect history with `make swarm-report`.

## The distinction that matters

| Event | Effect on the swarm |
| --- | --- |
| Screen locks / display sleeps | **None.** Processes keep running; the lock screen is irrelevant. |
| System sleeps (idle, battery, lid) | **Freezes the process.** In-flight model calls hit the 120 s timeout, and the run records `interrupted`/`crew_error`. |
| SSH/terminal window closes | None if the pilot was started with `nohup`/`tmux`; the TUI dies with its terminal. |

Only system sleep is a threat. `make swarm-night` prevents it explicitly:

```make
swarm-night:
	caffeinate -is swarm/.venv/bin/python -m swarm.supervise
```

- `-i` blocks **idle** system sleep; `-s` blocks **system** sleep while on AC power.
- The assertion lasts exactly as long as the supervisor process.
- It wraps the **supervisor**, not a single run, so a crash/retry does not drop the assertion.

## Checklist before a long run

1. **AC power.** On battery, macOS may force sleep regardless of `caffeinate`; Low Power Mode can also throttle.
2. **Lid open.** Closing the lid sleeps the Mac even under `caffeinate` unless it is genuine clamshell mode (external display + power). If you must close it:
   ```bash
   sudo pmset -a sleep 0     # for the night
   sudo pmset -a sleep 1     # restore afterwards
   ```
3. **Session isolation.** Run inside `tmux` so closing a terminal/editor cannot take the dashboard with it:
   ```bash
   tmux new -s swarm 'make swarm-night'   # re-attach: tmux attach -t swarm
   ```
4. **Single writer.** The harness takes `swarm/runs/.lock`. Stop any running pilot first (`make swarm-stop`); two pilots cannot share a repo.
5. **Preflight once.** `make swarm-preflight` catches bad model ids/keys/Ollama/venvs before hours are wasted.

## Verify it is actually protected

```bash
pmset -g assertions | grep -iE "caffeinate|PreventUserIdleSystemSleep"
pmset -g ps          # must say 'AC Power'
make swarm-report    # green count, cost, stop reasons
```

`pmset -g` may show `sleep 1` and still say "sleep prevented by powerd" (a transient OS assertion) — rely on the explicit `caffeinate` assertion, not on the sleep timer.

## If it is interrupted anyway

The supervisor is the safety net (`swarm/supervise.py`):

| Outcome | Supervisor action |
| --- | --- |
| `interrupted`, `crew_error`, `quota_exhausted`, `budget_exhausted`, commit/push/merge failures | restart with backoff (30 s base → 600 s cap) |
| `config_error` (bad key/base URL/HTML response) | stop immediately — no local fix exists |
| task exhausted `SWARM_SUPERVISE_ATTEMPTS` (3) | park in `swarm/runs/retry_later.json`, continue with the next runnable task |

Resume is cheap by design: completed micro-steps are not re-executed, and a drifted
checkpoint redoes only its last step (015 AC-7).

Where to look after a wake:

```bash
cat swarm/runs/latest            # newest run id
make swarm-dash                  # live; press h for the human log
make swarm-report                # p50/p90, cost per green, stop reasons
```

## Knobs

| Variable | Default | Meaning |
| --- | --- | --- |
| `SWARM_SUPERVISE_ATTEMPTS` | 3 | retries per task before it is parked |
| `SWARM_SUPERVISE_ROUNDS` | 20 | total supervise iterations |
| `SWARM_MAX_RUNTIME_SECONDS` | 14400 | 4 h wall clock for the run |
| `SWARM_MAX_COST_USD` | 3 | run budget |
| `SWARM_MAX_COST_PER_TASK` | 0.05 | per-task cap; the task is parked, the queue continues |

## Not covered

- **Reboot / power loss.** `caffeinate` does not survive a restart. Use `launchd` with `KeepAlive` if you need that, or run the same command on an always-on host.
- **True unattended operation across days.** Prefer an always-on box (mini PC/VPS) reached over SSH; the harness only needs the repo, Ollama, and the model keys.

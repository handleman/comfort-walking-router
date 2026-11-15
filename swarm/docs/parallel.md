# Parallel task attempts (023)

> Part of the swarm harness documentation. Start at [`../README.md`](../README.md).

## Parallel task attempts (`make swarm-parallel`, 023 phase 1)
```bash
make swarm-parallel BATCH="007-live-position:T2,004-weather-sun:T2" WORKERS=2
```
- Each worker runs `swarm.flow --no-commit` in a detached worktree with the
  current harness copy; it never writes the main tree.
- Tasks run together only when the files their briefs name are disjoint.
- Only a **green** worker is integrated, one at a time: `git apply --check` →
  apply → the full `SWARM_GATE_COMMANDS` suite on main → commit with the
  standard trailers → best-effort push.
- A conflict or a failed main-tree gate reverses the patch (`git apply -R`),
  leaves the task open and the tree clean. The main tree has one writer.
- Phase 1 is a race, not a scheduler: the first green wins, the rest stay open.
  Durable queues/leases are ADR-012's future option.

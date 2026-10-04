# Project Constitution

Source of truth for spec-driven workflow. Keep small; link details, don't duplicate.

## Mission
See `docs/mission.md`. (TBD — example app spec comes later.)

## Tech Stack
See `docs/tech-stack.md`. (TBD — no stack chosen. Do not assume commands.)

## Roadmap
See `docs/roadmap.md`. (TBD.)

## Principles
1. Spec before code: `specs/NNN-name/spec.md` with acceptance criteria must exist before implementation.
2. Small verifiable specs: one feature per `specs/NNN-name/`, checkboxes in `tasks.md` linked to spec items.
3. Flow: spec → plan → tasks → implement. No code without plan + tasks.
4. Cross-cutting decisions require an ADR in `docs/architecture/`. See `adr-001-template.md`.
5. Prefer editing existing files over creating new ones; minimal diff per spec.
6. Verify via executable sources (manifests, scripts, CI) before claiming a workflow exists.

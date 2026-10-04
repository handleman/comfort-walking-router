# AGENTS.md

Greenfield repo for learning spec-driven development. No app code yet; example app spec comes later.

## State
- Stack (proposed, unverified): Python + FastAPI + Svelte + TypeScript + Leaflet, OSM/Overpass, SQLite cache first. See `docs/tech-stack.md`.
- No manifests yet (`pyproject.toml` / `requirements.txt` / `app/` / `frontend/package.json`), no CI. Do not assume commands work — proposed test/lint/typecheck: `pytest`, `ruff check .`, `mypy .`, `npm run check` (frontend).
- `opencode.json`: project-local `context7` MCP (remote `https://mcp.context7.com/mcp`).
- SDD layout (Option 2, Spec-Kit style): constitution in `.specify/memory/constitution.md`, durable docs in `docs/` (`mission.md`, `tech-stack.md`, `roadmap.md`, `architecture/` ADRs), transient work in `specs/NNN-name/` (`spec.md` → `plan.md` → `tasks.md`, `contracts/` when needed). Templates in `.specify/templates/`.
- Do not invent commands or config. Verify via manifests/scripts before claiming a workflow exists.

## When stack is chosen
- Update this file in the same change: exact install, dev, test, lint, typecheck commands + how to run a single test.
- Record monorepo/package boundaries and real entrypoints once they exist.

## Spec-driven workflow (learning goal)
- Spec before code: define requirements, acceptance criteria, and scope in `specs/` (or agreed location) before implementing.
- Clarify first: when requirements are ambiguous, ask the user targeted questions (via `question` tool, 1–2 at a time) and refine the spec docs until the picture is clear. Do not guess or implement on ambiguity.
- Keep specs small and verifiable; link implementation back to spec items.
- Prefer editing existing files over creating new ones; keep changes minimal per spec.

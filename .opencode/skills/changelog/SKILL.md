---
name: Changelog
description: Maintain changelog.md in the project root with per-date headings. Load before merging, committing release notes, or when the user asks about history. Bootstraps from git history when the file is missing.
---

Maintain `changelog.md` (project root). Format, newest first:

```markdown
# Changelog

## 2026-10-04
- docs: mission, stack, roadmap, 001 spec-plan-tasks
```

## Update (before merging)

1. Read `changelog.md`. Note the newest `## YYYY-MM-DD` heading (none = bootstrap mode).
2. List new work: `git log --format='%h %ad %s' --date=short --since=<newest-date>` plus any uncommitted changes from `git status --short`.
3. Group bullets by commit date (author date, `%ad`), newest date first. One bullet per commit: strip the hash, keep `area: summary`. Merge commits get one bullet. Uncommitted changes go under today's date.
4. Prepend new `## date` sections above older ones. Never rewrite existing entries.
5. Keep bullets short, factual, no superlatives.

## Bootstrap (no changelog.md)

1. Run `git log --format='%h %ad %s' --date=short --reverse` for full history.
2. Create `changelog.md` with `# Changelog` + one `## date` section per commit date (newest first), one bullet per commit as above.
3. Start with `# Changelog` title, no preamble.

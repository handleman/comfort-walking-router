# Figma: operator lane and queue lane

There are two ways Figma enters this repo, and they intentionally use different
transports:

| Lane | Who | Transport | Auth |
| --- | --- | --- | --- |
| **Operator** (OpenCode) | a person exploring/implementing a frame | [Figma MCP server](https://help.figma.com/hc/en-us/articles/32132100833559-Guide-to-the-Figma-MCP-server) | OAuth via `/mcps` |
| **Queue** (harness) | the unattended swarm | Figma REST API → committed cache | `FIGMA_TOKEN` in `.env` |

The queue never speaks MCP and never runs OAuth: it reads a versioned design
cache so a night run is deterministic and offline. The operator lane is
interactive and uses the latest tools.

## Operator lane — OpenCode + Figma MCP

The remote server is configured in `opencode.json`:

```json
{
  "mcp": {
    "servers": {
      "figma": { "type": "remote", "url": "https://mcp.figma.com/mcp" }
    }
  }
}
```

Connect it once per machine:

```bash
opencode mcp add figma --global --url https://mcp.figma.com/mcp
opencode mcp list          # shows whether it needs authentication
```

Then in OpenCode run `/mcps`, select **figma**, and sign in. OAuth credentials
are stored by OpenCode, not in this repo. After that, paste a frame link
(right-click → **Copy link to selection**) and ask to implement it; the
`figma-implement` skill in `.opencode/skills/` carries the workflow.

Notes:

- The **remote** server (`https://mcp.figma.com/mcp`) is recommended and works
  on all Figma plans, but a **Full or Dev seat** is recommended for the full
  feature set; view seats may hit limits.
- The **desktop** server (`http://127.0.0.1:3845/mcp`) is a fallback for
  organization/enterprise needs. It requires the Figma desktop app and a Dev or
  Full seat on a paid plan.
- The remote server is link-based (no "current selection"), and
  `get_design_context` defaults to React/Tailwind — ask for Svelte/plain
  HTML + CSS for this repo.
- Read-only use is the default. Do not call the write tools (`use_figma`,
  `generate_figma_design`, …) on a real design file unless you mean to edit it.

## Queue lane — cached design IR (factory spec 057)

> Planned in `handleman-hq` spec **057-figma-design-support**. Until it ships,
> the queue has no design lane; the operator lane above is the only Figma path.

The intended flow:

```bash
# once per design change (network; token from .env)
hq design sync

# the queue runs from the cache; no network, no OAuth
make swarm-run
```

`swarm.yaml` declares the file and the allowlisted frames:

```yaml
design:
  provider: figma
  file_key: "<file key from /design/<key>/...>"
  nodes: ["12:34", "56:78"]      # only these frames may enter prompts
  token_env: FIGMA_TOKEN
  dir: designs/                  # committed cache: JSON, PNG, brief, lock
  scale: 2
```

`hq design sync` writes:

```
designs/<file-key>/
  index.json        # normalized IR (frame tree, layout, fills, text, components)
  <node>.json       # one frame each (allowlisted)
  <node>.png        # reference render (desktop and mobile frames)
  tokens.json       # variables + styles (colors, spacing, typography)
  design-brief.md   # the planner/coder-readable brief
  design.lock       # Figma file version + node IDs + hashes
```

The spec that implements a frame declares it in `specs/product/<spec>/design.toml`:

```toml
[figma]
file_key = "<key>"
node = "12:34"

[[token]]
name = "--color-primary"
value = "#1d4ed8"

[[region]]
id = "top-card"
selector = "[data-testid='top-card']"
frame = "12:34"
tolerance_px = 2

[screenshot]
frame = "desktop"
baseline = "designs/<key>/12:34.png"
threshold = 0.02
```

Checks are deterministic (computed CSS variables, region bounds, pixel diff);
the vision model stays advisory, exactly as in the 042 visual phase. A missing
or stale cache is a typed stop (`design_stale` / `design_missing`), never a
silent freehand implementation.

### Security and limits

- `FIGMA_TOKEN` lives in `.env` (gitignored), is read only by the sync command,
  and is never put in a prompt, `run.json` or a log. Preflight validates it when
  a `design:` block exists.
- Only allowlisted file keys/nodes are fetched; the model cannot choose a new
  Figma URL.
- `designs/` is read-only during a run (the coder cannot edit the cache); only
  `hq design sync` writes it.
- Reads are cached by file version; 429 responses back off; response size and
  asset sizes are capped.
- The queue does not write to Figma. No canvas write tools are used.

## What is still needed

- The design file link and the frame list (the design is in preparation).
- A Figma personal access token in `.env` for the queue lane
  (`FIGMA_TOKEN=figd_…`; create it under **Settings → Security → Personal
  access tokens**).
- The seat check: remote MCP works on all plans, but a Full/Dev seat avoids
  usage limits; the desktop server needs a paid plan.

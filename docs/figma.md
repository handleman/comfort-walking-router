# Figma: operator lane and queue lane

There are two ways Figma enters this repo, and they intentionally use different
transports:

| Lane | Who | Transport | Auth |
| --- | --- | --- | --- |
| **Operator** (OpenCode) | a person exploring/implementing a frame | [Figma MCP server](https://help.figma.com/hc/en-us/articles/32132100833559-Guide-to-the-Figma-MCP-server) | OAuth via `/mcps` |
| **Queue** (harness) | the unattended swarm | MCP (OAuth) or REST → committed cache | token-first: `FIGMA_TOKEN` in `.env`, else MCP OAuth |

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

## Queue lane — MCP (OAuth) or REST, then a cached IR (factory spec 057)

> Implemented in `handleman-hq` **v0.6.3** (spec 057). The queue can read a
> design over MCP with first-run OAuth or over REST; both write the same cache.

The queue supports **both** Figma transports and writes the same cache:

| | MCP | REST |
| --- | --- | --- |
| Auth | OAuth on first use (DCR + PKCE, loopback redirect) | `FIGMA_TOKEN` personal access token |
| Data | read tools: metadata, design context, variables, screenshots, assets, Code Connect | raw nodes, images, variables, components, styles |
| Best for | the same experience as OpenCode, latest tools | CI/headless, no browser callback |

`transport: auto` (default) is **token-first**: if `FIGMA_TOKEN` is present it
uses REST; if it is absent it switches to MCP and starts the first-run OAuth. A
stored MCP token does not override an explicit API token. Force one with
`transport: mcp` or `transport: rest`. **The MCP token is not a REST token**
(it is scoped to `mcp:connect`), so REST needs its own personal access token.

### First run with MCP (the swarm meets a Figma link)

1. A run needs Figma (a `design:` block / `design.toml`) and no token is stored.
2. Before any model call, the harness prints an authorization URL (and records
   it in `run.json.auth`), then waits.
3. You open the URL, authorize; the browser redirects to
   `http://127.0.0.1:<port>/callback`.
4. The harness exchanges the code, stores the token at
   `$XDG_DATA_HOME/handleman-hq/figma/oauth.json` (0600), and **continues the
   same run**. Expired tokens refresh silently.
5. No callback before the timeout → `figma_auth_timeout`; `--non-interactive`
   → `figma_auth_required` with the URL. Remote host: SSH-forward the callback
   port or use `hq figma auth --paste`.

Management commands: `hq figma auth`, `hq figma status`,
`hq figma logout`, `hq design sync [--transport mcp|rest]`.

```bash
# MCP: first run shows the URL, stores the token, then continues
hq figma auth
hq design sync

# REST/CI: a personal access token, no browser
FIGMA_TOKEN=figd_... hq design sync --transport rest
```

`swarm.yaml`:

```yaml
design:
  provider: figma
  transport: auto              # auto | mcp | rest
  file_key: "<file key from /design/<key>/...>"
  nodes: ["12:34", "56:78"]    # only these frames may enter prompts
  dir: designs/                # committed cache
  scale: 2
  auth:
    timeout_s: 600
    open_browser: true
```

`hq design sync` writes:

```
designs/<file-key>/
  index.json        # normalized IR (frame tree, layout, fills, text, components)
  <node>.json       # one frame each (allowlisted)
  <node>.png        # reference render
  tokens.json       # variables + styles (colors, spacing, typography)
  design-brief.md   # the planner/coder-readable brief
  design.lock       # Figma file version + node IDs + hashes
  mcp/              # cached MCP tool results + images (MCP transport)
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

- MCP tokens are stored outside the repo
  (`$XDG_DATA_HOME/handleman-hq/figma/oauth.json`, 0600) and are never put in a
  prompt, `run.json` or a log. `FIGMA_TOKEN` (REST) lives in `.env` (gitignored)
  and is read only by the sync command. Preflight validates whichever transport
  is configured.
- Only allowlisted file keys/nodes are fetched; the model cannot choose a new
  Figma URL. MCP exposes read tools only (no `use_figma`/canvas writes).
- `designs/` is read-only during a run (the coder cannot edit the cache); only
  `hq design sync` writes it.
- Reads are cached by file version; 429 responses back off; response size and
  asset sizes are capped.
- The queue does not write to Figma. No canvas write tools are used.

## What is still needed

- The design file link and the frame list (the design is in preparation).
- Either authorize the MCP server once (the first run prompts) **or** put a
  Figma personal access token in `.env` for the REST path
  (`FIGMA_TOKEN=figd_…`; **Settings → Security → Personal access tokens**).
- The seat check: remote MCP works on all plans, but a Full/Dev seat avoids
  usage limits; the desktop server needs a paid plan.

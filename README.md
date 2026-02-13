# agent-briefcase

<p align="left">
  <img src="docs/briefcase.png" alt="agent-briefcase" width="150">
  <a href="https://github.com/pre-commit/pre-commit"><img src="https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit" alt="pre-commit" style="max-width:100%;"></a>
</p>
Share your team's AI agent knowledge across every repo.

## The problem

Teams using AI coding agents accumulate valuable configuration — prompts, slash commands, rules, MCP server setups — but it stays trapped in individual repos. Developers in projectB don't know that projectA has a great code review command. New team members start from scratch. Good practices don't spread.

## How it works

`briefcase` is a [pre-commit](https://pre-commit.com) hook. You keep your team's agent configuration in a single shared repo (the "briefcase"). Each project repo pulls its configuration from the briefcase automatically on `git checkout` and `git merge`.

Configuration is organized with a simple convention:

```
your-briefcase-repo/
├── config/
│   ├── shared/              # applies to all projects
│   │   └── .claude/
│   │       └── commands/
│   │           └── review.md
│   ├── projectA/            # only applies to projectA (matched by folder name)
│   │   └── CLAUDE.md
│   └── projectB/
│       └── CLAUDE.md
├── docs/                    # non-config content lives alongside
└── README.md
```

All synced content lives under `config/`. Files in `config/shared/` are synced to every project. Files in a project-specific folder override shared files when both exist at the same path. The rest of the repo is yours — docs, guides, scripts, etc.

## Quick start

### 1. Set up your briefcase repo

Create a new repo with a `config/` folder containing a `shared/` folder and per-project folders as needed. The project folder names must match the directory names of your target repos (or use `--project` to map them explicitly).

### 2. Add the hook to your target repos

In each target repo's `.pre-commit-config.yaml`:

```yaml
default_install_hook_types: [post-checkout, post-merge]
repos:
  - repo: https://github.com/xverges/agent-briefcase
    rev: v0.3.0
    hooks:
      - id: briefcase-sync
```

Then run:

```bash
pre-commit install
```

### 3. Clone both repos as siblings

By default the briefcase repo must be a sibling directory named `agent-briefcase`:

```
~/code/
├── agent-briefcase/     # your briefcase repo (config/ folder inside)
├── projectA/            # target repo — gets files from config/shared/ + config/projectA/
└── projectB/            # target repo — gets files from config/shared/ + config/projectB/
```

That's it. On every `git checkout` or `git merge` in a target repo, the hook syncs the relevant files automatically.

## Configuration

All options are passed via `args:` in `.pre-commit-config.yaml`. Everything is optional — the zero-config default works if your briefcase repo is a sibling directory named `agent-briefcase`.

```yaml
hooks:
  - id: briefcase-sync
    args:
      - --briefcase=../my-team-briefcase   # relative or absolute path to the briefcase repo
      - --project=projectA-v3              # override the auto-detected project folder name
      - --shared=shared-front-end          # override the shared folder name (default: "shared")
```

| Option | Default | Description |
|---|---|---|
| `--briefcase` | Sibling dir named `agent-briefcase` | Path (relative or absolute) to the briefcase repo. |
| `--project` | Target repo's directory name | Which folder inside `config/` to use for project-specific files. |
| `--shared` | `shared` | Which folder inside `config/` to use for shared files. |

### Examples

**Custom briefcase location** — your briefcase repo is in a different directory:

```yaml
args: [--briefcase=/opt/team/briefcase]
```

**Multiple shared layers** — you have `config/shared-frontend` and `config/shared-backend` instead of `config/shared`:

```yaml
# In your frontend repos:
args: [--shared=shared-frontend]

# In your backend repos:
args: [--shared=shared-backend]
```

**Project name mismatch** — your repo is called `app-v3` but the briefcase folder is `app`:

```yaml
args: [--project=app]
```

## Why post-checkout and post-merge?

The hook runs on two git events:

- **`post-checkout`** — fires after `git checkout` / `git switch`. This covers branch switches, the most common moment where you want fresh config synced.
- **`post-merge`** — fires after `git merge` (including `git pull`). This ensures config is re-synced after pulling upstream changes.

These are the two moments when your working tree changes due to git operations. The hook deliberately does **not** run as a `pre-commit` stage — injecting files into the working tree mid-commit would be disruptive and unexpected.

## Layering

When both `config/shared/` and a project-specific folder contain a file at the same path, the project-specific version wins:

```
config/shared/CLAUDE.md       →  base version for all projects
config/projectA/CLAUDE.md     →  overrides shared/CLAUDE.md in projectA only
```

## The lock file

Each target repo gets a `.briefcase.lock` file (committed to git) that tracks:
- Which briefcase commit was last synced
- Which files are managed, with their content hashes

This enables:
- **Detecting local modifications** — if you edit a synced file, the hook will skip it instead of overwriting your changes
- **Cleaning up** — if a file is removed from the briefcase, it's automatically removed from target repos
- **Staleness checks** — CI can compare the lock file against the current briefcase to detect drift

## Local modifications

If you edit a file that was synced by briefcase, the hook detects the change (via hash comparison) and **skips that file with a warning** instead of overwriting your work:

```
briefcase: SKIPPING CLAUDE.md (locally modified)
```

To accept the upstream version, delete the local file and re-run the sync.

## Managing .gitignore

Synced files are **gitignored** — they're ephemeral and recreated by the hook. The hook automatically manages a section in your `.gitignore`:

```gitignore
# BEGIN briefcase-managed (do not edit this section)
/CLAUDE.md
/.claude/commands/review.md
# END briefcase-managed
```

The `.briefcase.lock` file itself is **not** gitignored — it should be committed.

## Personal overrides

Briefcase intentionally does not have a built-in personal override system. If you need local customizations, create a `.briefcase-post-sync.sh` script in your project (gitignored). The hook will run it after every sync:

```bash
#!/bin/bash
# .briefcase-post-sync.sh — my personal tweaks
echo "## My extra rules" >> CLAUDE.md
```

## Keeping the briefcase up to date

The hook automatically runs `git fetch` on the briefcase repo and warns you if it's behind the remote:

```
briefcase: WARNING — briefcase repo is 3 commit(s) behind origin/main. Run `git -C ../agent-briefcase pull` to get the latest team config.
```

The sync still proceeds with whatever is checked out locally — the warning is informational only. To pick up the latest team configuration:

```bash
git -C ../agent-briefcase pull    # update the briefcase repo
pre-commit run briefcase-sync --hook-stage post-checkout   # re-sync
```

If the fetch fails (e.g. you're offline), the staleness check is silently skipped.

## CI / missing briefcase

If the briefcase repo is not found at the expected path, the hook prints a warning to stderr and exits with success (exit code 0):

```
briefcase: WARNING — briefcase repo not found at '../agent-briefcase', skipping sync.
```

This means CI environments won't fail, but the warning is always visible in logs so misconfigurations don't go unnoticed.

## Manual sync

To trigger a sync manually without checking out a branch:

```bash
pre-commit run briefcase-sync --hook-stage post-checkout
```

## Behavior reference

See [SCENARIOS.md](SCENARIOS.md) for a full catalog of how briefcase handles every sync situation — fresh syncs, layering, local modifications, missing repos, and more. Auto-generated from end-to-end tests.

## Development

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync --extra test          # create venv and install with test deps
uv run pytest                 # run tests
uv run ruff check .           # lint
uv run ruff format .          # format
```

To run the full CI suite locally (lint + tests across Python 3.10–3.13):

```bash
uv tool run nox
```

### Releasing

The version in `pyproject.toml` is the single source of truth. To release a new version:

1. Bump `version` in `pyproject.toml`
2. Update `rev:` in this README to match (prefixed with `v`) — a test will fail if they diverge
3. Merge to `main`
4. CI automatically creates the corresponding git tag via `.github/workflows/release.yml`

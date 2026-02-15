# agent-briefcase

<p align="left">
  <img src="docs/briefcase.png" alt="agent-briefcase" width="150">
  <a href="https://github.com/pre-commit/pre-commit"><img src="https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit" alt="pre-commit" style="max-width:100%;"></a>
</p>
Share your team's AI agent knowledge across every repo.

## The problem

Teams using AI coding agents accumulate valuable configuration — prompts, slash commands, rules,
MCP server setups — but it stays trapped in individual repos. Developers in projectB don't know
that projectA has a great code review command. Agent-related dotfiles remain hidden in home
folders. Good practices don't spread. And with every assistant expecting its own config file format, keeping guidance consistent across tools is yet another burden.

## The config file maze

Every AI coding assistant has its own convention for where project instructions live:

| Assistant | Config file(s) |
|---|---|
| Claude Code | `CLAUDE.md`, `.claude/commands/*.md`, `.claude/settings.local.json` |
| IBM Bob | `AGENTS.md`, `.bob/rules/*.md`, `.bob/commands/*.md` |
| Cursor | `AGENTS.md`, `.cursorrules` |
| Windsurf | `AGENTS.md`, `.windsurf/rules/*.md` |
| GitHub Copilot | `AGENTS.md`, `.github/copilot-instructions.md` |
| Aider | `.aider.conf.yml`, `CONVENTIONS.md` |

Teams using more than one assistant end up maintaining the same guidance in multiple places — and they inevitably drift apart. A code-style rule added to `CLAUDE.md` never makes it to `.cursorrules`. A testing convention in `.github/copilot-instructions.md` is missing from `.clinerules`.

`agent-briefcase` solves this by letting you author shared fragments once and compose them into each assistant's config file. Update the fragment, and every assistant's config gets the change on the next build.

## How it works

`agent-briefcase` is a set of [pre-commit](https://pre-commit.com) hooks. You keep your team's agent configuration in a single shared repo (the "briefcase") and it flows automatically to every project repo.

There are three steps:

1. **Init** the briefcase repo (once) — scaffold the directory structure, a `BRIEFCASE.md` guide for your team, and the build hook pre-configured.

2. **Build** (every commit of the briefcase repo) — `config-src/` templates are assembled into `config/`. Runs automatically as a pre-commit hook.

3. **Sync** (every checkout/merge of a target repo) — `config/` files are copied into the working tree. Shared files go everywhere; project-specific files go only to matching repos.

```
        briefcase repo                                  target repos
        ────────────────────────────────────            ──────────────────
init ─▸ config-src/  ──build──▸  config/
          _includes/               _shared/
          _shared/                 projectA/  ──sync──▸ AGENTS.md+ for projectA
          projectA/                projectB/  ──sync──▸ AGENTS.md+ for projectB
```

The briefcase repo commits generated config. Target repos receive ephemeral copies that are gitignored.

## Quick start

### 1. Create your briefcase repo

```bash
mkdir team-briefcase && cd team-briefcase && git init
```

Create a `.pre-commit-config.yaml` with the following content:

```yaml
repos:
  - repo: https://github.com/xverges/agent-briefcase
    rev: v0.7.0
    hooks:
      - id: briefcase-init
        stages: [manual]
      - id: briefcase-build
```

Then scaffold the directory structure:

```bash
pre-commit install
pre-commit run briefcase-init --hook-stage manual
```

This creates:

```
team-briefcase/
├── .pre-commit-config.yaml    # already has briefcase-build wired up
├── BRIEFCASE.md               # guide for your team (how this briefcase works)
├── config/                    # generated output (do not edit directly)
├── config-src/
│   ├── _includes/             # reusable fragments for {{include}} directives
│   │   └── README.md
│   └── _shared/               # config that syncs to all projects
└── dotfiles/                  # share personal configs here (not managed by briefcase)
    └── README.md
```

### 2. Add your team's configuration

Edit files under `config-src/`. Everything in `_shared/` syncs to all projects. Create project-specific folders for overrides:

```
config-src/
├── _includes/
│   └── code-style.md                # reusable fragment
├── _shared/
│   ├── .claude/
│   │   └── commands/
│   │       └── review.md            # shared slash command
│   └── CLAUDE.md                    # shared rules for all projects
└── projectA/
    └── CLAUDE.md                    # overrides _shared/CLAUDE.md in projectA only
```

Use `{{include}}` to pull in fragments from `_includes/`:

```markdown
# Project Rules

{{include code-style.md}}

## Testing
Always run tests before committing.
```

You can preview the assembled output at any time with:

```bash
pre-commit run briefcase-build --all-files
```

When you commit, `briefcase-build` runs automatically as a pre-commit hook — includes are expanded, and the result is committed alongside your source.

### 3. Add the sync hook to your target repos

In each target repo's `.pre-commit-config.yaml`:

```yaml
default_install_hook_types: [post-checkout, post-merge]
repos:
  - repo: https://github.com/xverges/agent-briefcase
    rev: v0.7.0
    hooks:
      - id: briefcase-sync
        args: [--briefcase=../team-briefcase]
```

Then run:

```bash
pre-commit install
```

### 4. Clone both repos as siblings

By default the briefcase repo must be a sibling directory named `team-briefcase`. This convention means sync works out of the box with no configuration needed.

```
~/code/
├── team-briefcase/      # your briefcase repo
├── projectA/            # target repo — gets config/_shared/ + config/projectA/
└── projectB/            # target repo — gets config/_shared/ + config/projectB/
```

That's it. On every `git checkout` or `git merge` in a target repo, the hook syncs the relevant files automatically.

## The three hooks

`agent-briefcase` provides three hooks:

| Hook | Repo | Stage | What it does |
|---|---|---|---|
| `briefcase-init` | briefcase repo | `manual` | Scaffolds the briefcase directory structure (run once) |
| `briefcase-build` | briefcase repo | `pre-commit` | Assembles `config/` from `config-src/` templates |
| `briefcase-sync` | each target repo | `post-checkout`, `post-merge` | Copies `config/` files into the target repo |

Init and build are configured in the briefcase repo's `.pre-commit-config.yaml`. Sync is configured separately in each target repo's `.pre-commit-config.yaml`.

## Templating with includes

Files in `config-src/_includes/` are reusable fragments. Reference them from any template with the `{{include}}` directive:

```markdown
{{include code-style.md}}
```

The directive must be on its own line. The entire line is replaced with the fragment's contents.

**Nesting** — Fragments can include other fragments. Circular references are detected and reported as errors.

**No includes?** — If your templates don't use `{{include}}`, files are copied verbatim from `config-src/` to `config/`. The build step is transparent.

**No `config-src/`?** — If you prefer to edit `config/` directly, just don't create a `config-src/` directory. The build hook is a no-op and sync works directly from `config/`.

See [SCENARIOS-build.md](SCENARIOS-build.md) for detailed examples of include expansion, nesting, circular detection, and stale file cleanup.

## Sync configuration

All sync options are passed via `args:` in the target repo's `.pre-commit-config.yaml`. Everything is optional — the zero-config default works if your briefcase repo is a sibling directory named `team-briefcase`.

```yaml
hooks:
  - id: briefcase-sync
    args:
      - --briefcase=../my-team-briefcase   # relative or absolute path to the briefcase repo
      - --project=projectA-v3              # override the auto-detected project folder name
      - --shared=_shared-front-end          # override the shared folder name (default: "_shared")
```

| Option | Default | Description |
|---|---|---|
| `--briefcase` | Sibling dir named `team-briefcase` | Path (relative or absolute) to the briefcase repo. |
| `--project` | Target repo's directory name | Which folder inside `config/` to use for project-specific files. |
| `--shared` | `_shared` | Which folder inside `config/` to use for shared files. |

### Examples

**Custom briefcase location** — your briefcase repo is in a different directory:

```yaml
args: [--briefcase=/opt/team/briefcase]
```

**Multiple shared layers** — you have `config/_shared-frontend` and `config/_shared-backend` instead of `config/_shared`:

```yaml
# In your frontend repos:
args: [--shared=_shared-frontend]

# In your backend repos:
args: [--shared=_shared-backend]
```

**Project name mismatch** — your repo is called `app-v3` but the briefcase folder is `app`:

```yaml
args: [--project=app]
```

## Layering

When both `config/_shared/` and a project-specific folder contain a file at the same path, the project-specific version wins:

```
config/_shared/CLAUDE.md      →  base version for all projects
config/projectA/CLAUDE.md     →  overrides _shared/CLAUDE.md in projectA only
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

### Using a different briefcase

If you want to use a different briefcase repo than the one configured in `.pre-commit-config.yaml`, set the `BRIEFCASE_PATH` environment variable. It takes precedence over both `--briefcase` and the default sibling directory:

```bash
export BRIEFCASE_PATH=~/my-personal-briefcase
```

This pairs well with [direnv](https://direnv.net/) — add it to your project's `.envrc` (gitignored) so the override is automatic.

### Post-sync hook

If you just need to tweak the synced files, create a `.briefcase-post-sync.sh` script in your project (gitignored). The hook will run it after every sync:

```bash
#!/bin/bash
# .briefcase-post-sync.sh — my personal tweaks
echo "## My extra rules" >> CLAUDE.md
```

## Keeping the briefcase up to date

The hook automatically runs `git fetch` on the briefcase repo and warns you if it's behind the remote:

```
briefcase: WARNING — briefcase repo is 3 commit(s) behind origin/main. Run `git -C ../team-briefcase pull` to get the latest team config.
```

The sync still proceeds with whatever is checked out locally — the warning is informational only. To pick up the latest team configuration:

```bash
git -C ../team-briefcase pull    # update the briefcase repo
pre-commit run briefcase-sync --hook-stage post-checkout   # re-sync
```

If the fetch fails (e.g. you're offline), the staleness check is silently skipped.

## CI / missing briefcase

If the briefcase repo is not found at the expected path, the hook prints a warning to stderr and exits with success (exit code 0):

```
briefcase: WARNING — briefcase repo not found at '../team-briefcase', skipping sync.
```

This means CI environments won't fail, but the warning is always visible in logs so misconfigurations don't go unnoticed.

## Manual sync

To trigger a sync manually without checking out a branch:

```bash
pre-commit run briefcase-sync --hook-stage post-checkout
```

## Behavior reference

- [SCENARIOS-sync.md](SCENARIOS-sync.md) — how briefcase handles every sync situation (fresh syncs, layering, local modifications, missing repos, and more)
- [SCENARIOS-build.md](SCENARIOS-build.md) — how the build step processes templates (include expansion, nesting, circular detection, stale cleanup)

Auto-generated from end-to-end tests.

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

### Approving test changes

Tests use [approvaltests](https://github.com/approvals/ApprovalTests.Python). When a test produces new or changed output, it writes a `.received.txt` file next to the existing `.approved.txt` file and the test fails. To approve the new output:

```bash
# Review the diff
diff tests/**/approved_files/*.approved.txt tests/**/approved_files/*.received.txt

# Accept the changes by replacing approved files with received files
for f in $(find tests -name '*.received.txt'); do mv "$f" "${f/received/approved}"; done
```

### Releasing

The version in `pyproject.toml` is the single source of truth. To release a new version:

1. Bump `version` in `pyproject.toml`
2. Update every `rev:` in this README to match (prefixed with `v`) — a test scans for stale references and will fail if any diverge
3. Merge to `main`
4. CI automatically creates the corresponding git tag via `.github/workflows/release.yml`

# agent-briefcase

Share your team's AI agent knowledge across every repo.

## The problem

Teams using AI coding agents accumulate valuable configuration — prompts, slash commands, rules, MCP server setups — but it stays trapped in individual repos. Developers in projectB don't know that projectA has a great code review command. New team members start from scratch. Good practices don't spread.

## How it works

`briefcase` is a [pre-commit](https://pre-commit.com) hook. You keep your team's agent configuration in a single shared repo (the "briefcase"). Each project repo pulls its configuration from the briefcase automatically on `git checkout` and `git merge`.

Configuration is organized with a simple convention:

```
your-briefcase-repo/
├── shared/              # applies to all projects
│   └── .claude/
│       └── commands/
│           └── review.md
├── projectA/            # only applies to projectA (matched by folder name)
│   └── CLAUDE.md
└── projectB/
    └── CLAUDE.md
```

Files in `shared/` are synced to every project. Files in a project-specific folder override shared files when both exist at the same path.

## Quick start

### 1. Set up your briefcase repo

Create a repo (or use this one as a template) with a `shared/` folder and per-project folders as needed. The project folder names must match the directory names of your target repos.

### 2. Add the hook to your target repos

In each target repo's `.pre-commit-config.yaml`:

```yaml
default_install_hook_types: [pre-commit, post-checkout, post-merge]
repos:
  - repo: https://github.com/yourorg/agent-briefcase
    rev: v0.1.0
    hooks:
      - id: briefcase-sync
```

Then run:

```bash
pre-commit install
```

### 3. Clone both repos as siblings

The briefcase repo must be a sibling directory of the target repo:

```
~/code/
├── agent-briefcase/     # your briefcase repo
├── projectA/            # target repo — gets files from shared/ + projectA/
└── projectB/            # target repo — gets files from shared/ + projectB/
```

That's it. On every `git checkout` or `git merge` in a target repo, the hook syncs the relevant files automatically.

## Layering

When both `shared/` and a project-specific folder contain a file at the same path, the project-specific version wins:

```
shared/CLAUDE.md              →  base version for all projects
projectA/CLAUDE.md            →  overrides shared/CLAUDE.md in projectA only
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

## CI behavior

If the briefcase repo is not found as a sibling directory, the hook exits silently with success. This means CI environments work without any special configuration.

## Manual sync

To trigger a sync manually without checking out a branch:

```bash
pre-commit run briefcase-sync --hook-stage post-checkout
```

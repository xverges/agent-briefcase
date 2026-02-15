# Briefcase-Init Scenarios

> **Auto-generated** from approved test output — do not edit by hand.
> Re-run `pytest` to regenerate.


## Scaffold Empty Dir

### 1. Init creates full structure

```
Scenario: Init in an empty directory creates the full briefcase structure

stdout:
    created: config/
    created: config-src/_shared/
    created: BRIEFCASE.md
    created: config-src/_includes/README.md
    created: dotfiles/README.md

stderr:
(empty)

exit code:
0

directory tree after init:
BRIEFCASE.md
config-src/_includes/README.md
dotfiles/README.md

BRIEFCASE.md exists:
True

config-src/_includes/README.md exists:
True

config-src/_shared/ directory exists:
True

dotfiles/README.md exists:
True
```


## Idempotent

### 2. Rerun does not overwrite

```
Scenario: Re-running init skips existing files (does not overwrite)

Setup:
BRIEFCASE.md modified to 'custom content' after first init

stdout:
    skipped: BRIEFCASE.md (already exists)
    skipped: config-src/_includes/README.md (already exists)
    skipped: dotfiles/README.md (already exists)
  briefcase-init: everything already exists, nothing to do.

stderr:
(empty)

exit code:
0

BRIEFCASE.md after second init:
custom content
```


## Partial Existing

### 3. Creates missing skips existing

```
Scenario: Init with partially existing structure creates missing parts, skips existing

Setup:
config-src/_includes/README.md already exists with custom content

stdout:
    created: config/
    created: config-src/_shared/
    created: BRIEFCASE.md
    skipped: config-src/_includes/README.md (already exists)
    created: dotfiles/README.md

stderr:
(empty)

exit code:
0

directory tree after init:
BRIEFCASE.md
config-src/_includes/README.md
dotfiles/README.md

config-src/_includes/README.md (preserved):
existing includes readme
```


## Generated Content

### 4. Briefcase md content

````
Scenario: BRIEFCASE.md contains operational guide for the team

BRIEFCASE.md:
# Team Briefcase

This repo holds your team's shared AI agent configuration. It is managed by
[agent-briefcase](https://github.com/xverges/agent-briefcase).

## What this solves

Teams using AI coding agents accumulate valuable configuration — prompts, slash
commands, rules, MCP server setups — but it stays trapped in individual repos.
Good practices don't spread. And with every assistant expecting its own config
file format (`CLAUDE.md`, `.cursorrules`, `.github/copilot-instructions.md`, …),
keeping guidance consistent is yet another burden.

`agent-briefcase` lets you author shared fragments once and compose them into
each assistant's config file. Update the fragment, and every project gets the
change on the next sync.

## How it works

There are three steps:

1. **Init** the briefcase repo (once) — already done.
2. **Build** (every commit of the briefcase repo) — templates in `config-src/`
   are assembled into `config/`. The `briefcase-build` pre-commit hook does this
   automatically.
3. **Sync** (every checkout/merge of a target repo) — a `briefcase-sync` hook
   copies the relevant `config/` files into the working tree.

```
        briefcase repo                                  target repos
        ────────────────────────────────────            ──────────────────
init ─▸ config-src/  ──build──▸  config/
          _includes/               _shared/
          _shared/                 projectA/  ──sync──▸ AGENTS.md+ for projectA
          projectA/                projectB/  ──sync──▸ AGENTS.md+ for projectB
```

The briefcase repo commits the generated `config/`. Target repos receive
ephemeral copies that are gitignored.

## Directory structure

| Directory | Purpose |
|---|---|
| `config-src/_shared/` | Configuration that syncs to **all** target repos. |
| `config-src/<project>/` | Configuration that syncs only to the matching repo. |
| `config-src/_includes/` | Reusable fragments referenced by `{{include <file>}}` directives. |
| `config/` | **Generated** — do not edit directly. Built from `config-src/` on every commit. |
| `dotfiles/` | A place to share personal dotfiles with the team. Not managed by briefcase. |

## Editing configuration

1. Edit files under `config-src/`.
2. Use `{{include <file>}}` to pull in fragments from `_includes/`.
3. Preview the result with `pre-commit run briefcase-build --all-files`.
4. Commit — the `briefcase-build` pre-commit hook assembles `config/` automatically.

## Adding the sync hook to a target repo

In the target repo's `.pre-commit-config.yaml`:

```yaml
default_install_hook_types: [pre-commit, post-checkout, post-merge]
repos:
  - repo: https://github.com/xverges/agent-briefcase
    rev: v<VERSION>
    hooks:
      - id: briefcase-sync
        args: [--briefcase=../briefcase]
```

Then run `pre-commit install`.

> **Note:** `default_install_hook_types` controls which hook types `pre-commit install` sets up. The default when omitted is `[pre-commit]`, so you must include `pre-commit` in the list to keep your existing hooks working. If you update this setting after having already run `pre-commit install`, you need to re-run it to pick up the new hook types.
````

### 5. Includes readme content

````
Scenario: config-src/_includes/README.md explains the _includes directory

config-src/_includes/README.md:
# _includes

Place reusable fragments here. Reference them from any template with:

```
{{include filename.md}}
```

The directive must be on its own line. Fragments can include other fragments.
````

### 6. Dotfiles readme content

```
Scenario: dotfiles/README.md explains the dotfiles directory

dotfiles/README.md:
# dotfiles

A place for team members to share personal configuration files — shell aliases,
editor settings, tool configs, etc.

These files are **not** managed by briefcase. They are not synced or built.
They live here as a convenience so the team can learn from each other's setups.
```


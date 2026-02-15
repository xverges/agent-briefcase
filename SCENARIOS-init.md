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
default_install_hook_types: [post-checkout, post-merge]
repos:
  - repo: https://github.com/xverges/agent-briefcase
    rev: v0.4.0
    hooks:
      - id: briefcase-sync
        args: [--briefcase=../briefcase]
```

Then run `pre-commit install`.
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


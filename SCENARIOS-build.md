# Briefcase-Build Scenarios

> **Auto-generated** from approved test output — do not edit by hand.
> Re-run `pytest` to regenerate.


## Basic Build

### 1. Basic build copies files

```
Scenario: Basic build with no includes copies files verbatim to config/

Source files:
config-src/_shared/CLAUDE.md
config-src/projectA/CLAUDE.md

stdout:
    created: _shared/CLAUDE.md
    created: projectA/CLAUDE.md

stderr:
(empty)

exit code:
1

config/ after build:
_shared/CLAUDE.md
projectA/CLAUDE.md

config/_shared/CLAUDE.md:
# shared rules

config/projectA/CLAUDE.md:
# projectA rules
```


## Include Expansion

### 2. Include replaces directive with fragment

```
Scenario: Include directive is replaced by the fragment file contents

config-src/_shared/CLAUDE.md (source):
# Rules

{{include debug.md}}

## Other
Done.

config-src/_includes/debug.md (fragment):
## Debug
Use verbose logging.

stdout:
    created: _shared/CLAUDE.md

stderr:
(empty)

exit code:
1

config/_shared/CLAUDE.md (built):
# Rules

## Debug
Use verbose logging.

## Other
Done.
```


## Nested Includes

### 3. Nested includes are resolved

```
Scenario: Nested includes are fully resolved (fragment includes another fragment)

Include chain:
outer.md includes inner.md
CLAUDE.md includes outer.md

stdout:
    created: _shared/CLAUDE.md

stderr:
(empty)

exit code:
1

config/_shared/CLAUDE.md (built):
# Top
before
inner content
after
# Bottom
```


## Circular Include Detection

### 4. Circular includes produce error

```
Scenario: Circular includes are detected and reported as an error

Include chain:
CLAUDE.md → a.md → b.md → a.md (cycle!)

Error:
circular include detected: a.md → b.md → a.md
```


## Missing Include

### 5. Missing include produces error

```
Scenario: Missing include file is reported as an error

Directive in source:
{{include nonexistent.md}}

Error:
include file not found: nonexistent.md
```


## Includes Dir Not Copied

### 6. Includes dir not in output

```
Scenario: Fragment files from _includes/ do not appear in config/ output

config-src/ contents:
_includes/debug.md
_includes/testing.md
_shared/CLAUDE.md

stdout:
    created: _shared/CLAUDE.md

stderr:
(empty)

exit code:
1

config/ after build (no _includes/):
_shared/CLAUDE.md
```


## Stale File Cleanup

### 7. Removed source is removed from config

```
Scenario: File removed from config-src/ is cleaned up from config/

config/ before (both files):
_shared/CLAUDE.md
_shared/extra.md

Change:
config-src/_shared/extra.md deleted

stdout:
    unchanged: _shared/CLAUDE.md
    removed: _shared/extra.md

stderr:
(empty)

exit code:
1

config/ after (extra.md removed):
_shared/CLAUDE.md
```


## No Op When Up To Date

### 8. No changes exits zero

```
Scenario: Re-running build with no changes exits 0 (up to date)

stdout:
    unchanged: _shared/CLAUDE.md

stderr:
(empty)

exit code:
0
```


## Files Changed Exits One

### 9. Changes exit one

```
Scenario: Build that writes files exits 1 (files changed)

stdout:
    created: _shared/CLAUDE.md

stderr:
(empty)

exit code:
1

config/ after build:
_shared/CLAUDE.md
```


## No Config Src Is Noop

### 10. No config src exits zero

```
Scenario: No config-src/ directory is a no-op (exits 0 with a message)

Setup:
(no config-src/ directory)

stdout:
  briefcase-build: no config-src/ directory, nothing to build.

stderr:
(empty)

exit code:
0
```


# Briefcase-Sync E2E Scenarios

> **Auto-generated** from approved test output — do not edit by hand.
> Re-run `pytest` to regenerate.


## Core Sync

### 1. Fresh sync copies all files

```
Scenario: Fresh sync copies all files when no prior state exists

Briefcase contents:
briefcase/shared/CLAUDE.md
briefcase/shared/.claude/commands/review.md

stdout:
  briefcase: synced .claude/commands/review.md
  briefcase: synced CLAUDE.md

stderr:
(empty)

exit code:
0

Target directory after sync:
.briefcase.lock
.claude/commands/review.md
.gitignore
CLAUDE.md

.gitignore:
# BEGIN briefcase-managed (do not edit this section)
/.claude/commands/review.md
/CLAUDE.md
# END briefcase-managed
```

### 2. Incremental sync new file added

```
Scenario: Incremental sync picks up newly added files

Briefcase contents:
CLAUDE.md (already synced)
new-file.md (just added)

stdout:
  briefcase: synced CLAUDE.md
  briefcase: synced new-file.md

stderr:
(empty)

exit code:
0

Target directory after sync:
.briefcase.lock
.gitignore
CLAUDE.md
new-file.md
```

### 3. Incremental sync file removed

```
Scenario: Removing a file from the briefcase cleans it up in the target

Briefcase change:
CLAUDE.md (kept)
.claude/commands/review.md (removed from briefcase)

stdout:
  briefcase: synced CLAUDE.md
  briefcase: removed .claude/commands/review.md (no longer in briefcase)

stderr:
(empty)

exit code:
0

Target directory after sync:
.briefcase.lock
.gitignore
CLAUDE.md

.gitignore:
# BEGIN briefcase-managed (do not edit this section)
/CLAUDE.md
# END briefcase-managed
```

### 4. Incremental sync file updated

```
Scenario: Updated briefcase files are synced to the target

CLAUDE.md content:
before: '# version 1'
after:  '# version 2'

stdout:
  briefcase: synced CLAUDE.md

stderr:
(empty)

exit code:
0
```


## Layering & Overrides

### 5. Shared only sync

```
Scenario: Files sync from shared/ when no project-specific folder exists

Briefcase contents:
briefcase/shared/CLAUDE.md
(no my-project/ folder)

stdout:
  briefcase: synced CLAUDE.md

stderr:
(empty)

exit code:
0

Target directory after sync:
.briefcase.lock
.gitignore
CLAUDE.md
```

### 6. Project overrides shared

```
Scenario: Project-specific files override shared files at the same path

Briefcase contents:
shared/CLAUDE.md       → '# shared version'
my-project/CLAUDE.md   → '# project-specific version'

stdout:
  briefcase: synced CLAUDE.md

stderr:
(empty)

exit code:
0

CLAUDE.md in target (project wins):
# project-specific version
```

### 7. Mixed shared and project files

```
Scenario: Shared and project-specific files are both synced

Briefcase contents:
shared/.claude/commands/review.md  (from shared)
my-project/CLAUDE.md                (from project)

stdout:
  briefcase: synced .claude/commands/review.md
  briefcase: synced CLAUDE.md

stderr:
(empty)

exit code:
0

Target directory after sync:
.briefcase.lock
.claude/commands/review.md
.gitignore
CLAUDE.md
```


## Local Modification Protection

### 8. Locally modified file is preserved

```
Scenario: Locally modified files are preserved with a warning

Conflict:
briefcase CLAUDE.md: '# updated in briefcase'
local CLAUDE.md:     '# my local edits'

stdout:
  briefcase: SKIPPING CLAUDE.md (locally modified)

stderr:
(empty)

exit code:
0

CLAUDE.md in target (local edit preserved):
# my local edits
```

### 9. Unmodified file is updated

```
Scenario: Unmodified synced files are updated when the briefcase changes

stdout:
  briefcase: synced CLAUDE.md

stderr:
(empty)

exit code:
0

CLAUDE.md in target (updated to v2):
# v2
```


## Gitignore Management

### 10. Synced files added to gitignore

```
Scenario: All synced files appear in a managed .gitignore section

.gitignore:
# BEGIN briefcase-managed (do not edit this section)
/.claude/commands/review.md
/CLAUDE.md
# END briefcase-managed
```

### 11. Removed files cleaned from gitignore

```
Scenario: Removed files are cleaned from .gitignore

.gitignore before:
# BEGIN briefcase-managed (do not edit this section)
/CLAUDE.md
/extra.md
# END briefcase-managed

.gitignore after (extra.md removed):
# BEGIN briefcase-managed (do not edit this section)
/CLAUDE.md
# END briefcase-managed
```

### 12. Existing gitignore content preserved

```
Scenario: Existing .gitignore entries are preserved alongside managed section

.gitignore:
node_modules/
.env

# BEGIN briefcase-managed (do not edit this section)
/CLAUDE.md
# END briefcase-managed
```


## Post Sync Hook

### 13. Post sync hook runs

```
Scenario: Post-sync hook runs after files are synced

.briefcase-post-sync.sh:
#!/bin/bash
echo 'hook-was-here' > .post-sync-marker

stdout:
  briefcase: synced CLAUDE.md
  briefcase: running .briefcase-post-sync.sh

stderr:
(empty)

exit code:
0

.post-sync-marker content:
hook-was-here
```

### 14. No post sync hook is noop

```
Scenario: Sync completes normally when no post-sync hook exists

Setup:
(no .briefcase-post-sync.sh in target)

stdout:
  briefcase: synced CLAUDE.md

stderr:
(empty)

exit code:
0
```


## Graceful Degradation

### 15. Missing briefcase repo

```
Scenario: Missing briefcase repo warns on stderr and exits successfully (CI-friendly)

stdout:
(empty)

stderr:
  briefcase: WARNING — briefcase repo not found at '<tmp>/nonexistent-briefcase', skipping sync.

exit code:
0
```

### 16. Empty briefcase emits warning

```
Scenario: Empty briefcase emits a warning

Setup:
briefcase/  (exists, empty)
my-project/  (exists)

stdout:
(empty)

stderr:
  briefcase: WARNING — no files found in briefcase for project 'my-project', skipping sync.

exit code:
0
```


## CLI Configuration

### 17. Custom briefcase path

```
Scenario: Custom --briefcase path resolves files from a non-sibling directory

Briefcase relative path:
somewhere/else/my-briefcase

stdout:
  briefcase: synced CLAUDE.md

stderr:
(empty)

exit code:
0

CLAUDE.md content:
# from custom path
```

### 18. Custom project name

```
Scenario: Custom --project name picks up files from the named folder

Setup:
briefcase/custom-name/CLAUDE.md exists
target dir is 'my-project' but --project=custom-name

stdout:
  briefcase: synced CLAUDE.md

stderr:
(empty)

exit code:
0

CLAUDE.md content:
# for custom-name project
```

### 19. Custom shared name

```
Scenario: Custom --shared folder name uses the specified folder instead of 'shared/'

Briefcase contents:
briefcase/common/CLAUDE.md   (should sync)
briefcase/shared/IGNORED.md  (should NOT sync)

stdout:
  briefcase: synced CLAUDE.md

stderr:
(empty)

exit code:
0

Target directory after sync:
.briefcase.lock
.gitignore
CLAUDE.md
```


## Lock File Integrity

### 20. Lock file records state

```
Scenario: Lock file records source commit and file hashes after sync

.briefcase.lock:
{
  "files": {
    "CLAUDE.md": {
      "sha256": "48647359ca75884b1961da7492f6f4da987a8cd99f5d4c32139b9e92595b0f15",
      "source": "shared/CLAUDE.md"
    }
  },
  "source_commit": "<commit>"
}
```

### 21. Idempotent sync no changes

```
Scenario: Re-running sync with no changes is idempotent

stdout:
  briefcase: synced CLAUDE.md

stderr:
(empty)

exit code:
0

Target directory (unchanged):
.briefcase.lock
.gitignore
CLAUDE.md
```


# Release Notes: vX.Y.Z

**Date**: YYYY-MM-DD | **Previous**: vA.B.C | **Commits**: N | **Tests**: A → B

## Highlights

### [Feature title in plain language]
- What changed (1-2 sentences)
- Why it matters (concrete benefit)
- Any user action needed (or 'none — works out of the box')

### [Feature title #2]
- ...

## Commits

| # | Commit | Purpose |
|---|--------|---------|
| 1 | abc1234 feat(scope): subject | One-line plain-language purpose |

## Breaking Changes

- [plain language: what breaks, how to migrate]
- (or 'None')

## Upgrade

```bash
ziro update && exec zsh
```

## Rollback

```bash
git reset --hard vA.B.C  # or: git revert vX.Y.Z
```

## Notes (optional)

- Known issues, migration paths, workarounds

# Ziro Shell — Technical Debt & Bug Backlog

## BACKLOG-BUG-1: Installer/cleanup wipes user .zshrc

**Discovered**: 2026-10-20 (during Stage B1-Fix diagnostic)

**Symptom**: After Ziro cleanup/install phase, user's `~/.zshrc` was overwritten to minimal form. All history configuration was removed without warning:
- `HISTFILE=~/.zsh_history` (unset → history not saved to disk)
- `HISTSIZE=100000`, `SAVEHIST=100000` (reset to 30/0)
- `setopt HIST_IGNORE_ALL_DUPS`, `HIST_SAVE_NO_DUPS`, `INC_APPEND_HISTORY`, `SHARE_HISTORY` (all removed)
- `bindkey '^[[A' history-beginning-search-backward` (smart arrow keys, removed)

**Root cause**: Commit `3a6814e` (2026-10-15, subject: "chore(cleanup): remove personal files and rewrite .zshrc (subphase 7cd)") rewrote `.zshrc` to minimal form. No backup, no warning, no preservation of user config.

**Impact**: User lost 5 days of shell workflow:
- History not persisted (`~/.zsh_history` last modified 2026-10-14 23:52, still 376KB intact)
- Up-arrow only shows current session's 30 entries
- Smart arrow-key search (type prefix + up = search from prefix) lost

**Spec violations**:
- Spec 001 FR-006e: ziro MUST NOT rewrite user files — the existing spec only protected shipped repo dotfiles, not user's own `.zshrc`
- Principle III (User control): user's config destroyed without consent
- Principle IV (Failure resilience): no backup taken before overwrite

**Proposed fix**:
1. `ziro install` MUST back up `~/.zshrc` before any modification (`~/.zshrc.bak.<timestamp>`)
2. If `~/.zshrc` exists and has non-Ziro content, append ONLY the integration source line — do NOT rewrite
3. If full rewrite required (fresh install with no existing `.zshrc`), proceed normally
4. Add `ziro restore-zshrc <backup>` CLI command for user recovery
5. Add regression test: create fixture `.zshrc` with custom content, run cleanup, assert content preserved

**Priority**: High (data loss / config loss)

**Target version**: v1.2.0 (alongside BACKLOG-1: Error Reporting)

**Related**: This discovery path went: Stage B1-Fix (Python-only) → user reported Ctrl+W + Up arrow issues → forensic diagnostic → found commit 3a6814e was culprit. Zero relation to Stage B1-Fix.

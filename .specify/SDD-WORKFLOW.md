# Spec-Driven Development (SDD) Workflow

Ziro Shell follows a strict **Spec-Driven Development (SDD)** process for all features, bug fixes, refactors, and hardening tasks from v1.2.1 onward.

---

## The 9-Step Lifecycle

```text
[1. Idea] ➔ [2. Spec] ➔ [3. Review (Gate)] ➔ [4. Implement] ➔ [5. Verify]
                ➔ [6. Reality Check] ➔ [7. Version Bump] ➔ [8. ADL Entry] ➔ [9. Tag & Push]
```

### Step 1: IDEA
- Identify the problem, bug, vulnerability, or desired enhancement.
- Capture initial notes, evidence, reproduction steps, or GitHub issue.

### Step 2: SPEC
- Create `.specify/specs/NNN-<short-name>/spec.md` using `.specify/templates/SPEC-TEMPLATE.md`.
- Formulate clear, numbered requirements (`R1`, `R2`, ...) and observable Acceptance Criteria (`AC1`, `AC2`, ...).
- Explicitly document **Out of Scope** items to enforce bounded scope.

### Step 3: REVIEW (Mandatory Stop Gate)
- Present the spec to the user or team lead.
- **STOP and wait**: No implementation code may be written until the spec status is marked `Approved`.

### Step 4: IMPLEMENT
- Create a dedicated feature branch: `git checkout -b feat/NNN-<short-name>`.
- Implement strictly what is specified. Commits follow Conventional Commits and reference requirements:
  `feat(core): implement secure umask enforcement (R1 of spec 017)`.

### Step 5: VERIFY
- Execute test suite: `PYTHONPATH=. uv run --with pytest pytest tests/ -q`.
- Ensure 100% test pass (baseline >= 479 passed).
- Verify clean, silent shell startup: `zsh -f -c 'source ~/.zshrc'`.
- Run `ziro doctor` to verify complete system health.

### Step 6: REALITY CHECK
- Inspect actual changes vs spec expectations.
- Update the `## Reality Check` section in `.specify/specs/NNN-<short-name>/spec.md` with:
  - Commit hashes.
  - Any deviations from original spec with explicit technical justification.
  - Exact test counts and performance timings.

### Step 7: VERSION BUMP
- For release deliverables, bump the patch version `v1.2.N`:
  - `pyproject.toml`
  - `core/constants.py` (`VERSION = "1.2.N"`)
  - `ziro.zsh` (`VERSION` display)
  - `CHANGELOG.md`

### Step 8: ADL ENTRY
- Append an entry to the Applied Decisions Ledger in `.specify/HANDOFF.md`.
- Format: `### ADL-NNN: <Title>` referencing Spec NNN, branch, date, commit, and key decisions.

### Step 9: TAG + PUSH
- Tag release: `git tag -a v1.2.N -m "release: v1.2.N - <spec title>"`.
- Push branch and tags to upstream.

---

## The 7 Invariant Hard Rules

1. **Rule 1 (No Code Without Spec)**: Never write implementation code in `core/`, `lib/`, or commands without an approved spec in `.specify/specs/`.
2. **Rule 2 (Testable Acceptance Criteria)**: Every requirement must have at least one unambiguous, testable Acceptance Criterion.
3. **Rule 3 (Explicit Out of Scope)**: Every spec must declare what will NOT be done to prevent creep.
4. **Rule 4 (No Scope Creep)**: If unanticipated work is discovered during implementation, STOP, update the spec requirements, re-approve, and resume.
5. **Rule 5 (Mandatory Reality Check)**: No spec is considered finished until its `Reality Check` section is populated with empirical verification output.
6. **Rule 6 (Append-Only ADL)**: Architectural decisions and shipped specs are recorded append-only in `HANDOFF.md`. Prior entries are never erased.
7. **Rule 7 (Predictable Cadence)**: Exactly one version bump per shipped spec (`v1.2.N`).

## Step 8.5 — Release Notes Manifest (mandatory, added 2026-11-03)

Every git tag MUST include a manifest at `.specify/releases/vX.Y.Z.md`.

**Audience**: end users, not developers. Copy-pasteable to GitHub Release body.

**Forbidden in manifest**:
- Spec references (Spec NNN, R1-R18, AC1-AC35)
- ADL references (ADL-XXX)
- Internal phase names

**Required sections**: Header (date, prev, commits, tests) | Highlights (2-3 user stories) | Commits table (`# | Commit | Purpose`) | Breaking Changes | Upgrade | Rollback.

**Split commits**: If a release has >3 logical features, split into per-feature commits for meaningful manifest rows.

**When**: Before tag push. Template: `.specify/releases/_TEMPLATE.md`.

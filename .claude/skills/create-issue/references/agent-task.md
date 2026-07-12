<!--
  SDC agent-task issue template — CANONICAL COPY.

  Deploy into each project repo as:  .gitlab/issue_templates/sdc-agent-task.md
  (the sdc- prefix avoids clashing with a project's own templates)
  so it appears in GitLab's "Choose a template" dropdown when creating an issue.

  See docs/developer-manual.md for how to fill this in well. The prerequisite
  check requires: a Design (or design-mode: agent-designs), >=1 Acceptance
  Criterion, >=1 Test Case, and no open blocking issues.
-->

## Type
<!-- bug | feature | refactor | chore | research | test | graph
     Stamped on the issue as a scoped `type::<x>` label (e.g. type::bug) when
     filed via /create-issue, so the operator's Kanban board can filter by type.
     Pick exactly one of: bug | feature | refactor | chore | research | test | graph.
     (test = writing automated test scripts/cases; graph = knowledge-graph
     init/update task, run by graphify on the SDC fleet — nothing installed
     locally)
     Note: the Type does NOT set the model — see Agent Configuration below. -->

---

## Summary
<!-- One sentence: what this is and why it matters to a user or the system. -->

## Context
<!-- Background. Why now? What breaks or what's missing without this?
     Link design docs, ADRs, or specs (the agent reads linked files before designing):
     - [Auth redesign spec](./docs/specs/auth-redesign.md)
     - [ADR-012: Session storage](./docs/adr/012-session-storage.md) -->

---
<!-- === BUG REPORTS: fill this block. Delete if not a bug. === -->
## Reproduction
### Steps
1. 
2. 

### Expected behaviour
<!-- What should happen -->

### Actual behaviour
<!-- What actually happens -->

### Logs / stack trace
```
<!-- paste here -->
```

### Environment
<!-- Version, OS, config, frequency (always / intermittent) -->
<!-- === end bug block === -->

---
<!-- === FEATURES / REFACTORS: fill this block. Delete if not applicable. === -->
## Design
<!-- How to implement this. Approach, architecture decisions, APIs to create or
     consume, relevant modules to touch.
     Leave blank ONLY if Agent Configuration sets design-mode: agent-designs —
     the agent will then propose a design and comment it before implementing. -->

## Assumptions
<!-- CONDITIONAL — include only when the grilling pre-pass surfaced ≥1 assumption.
     Delete this section entirely if there are no assumptions.

     Semantics: these are the unstated decisions the agent MAY take as given —
     the silent defaults it would otherwise guess. If an assumption proves false
     at runtime the agent should PARK and ask (agent-needs-input) rather than guess.

     Routing test (Assumption vs Constraint):
       "Would breaking it be WRONG (→ Constraint), or just a silent choice
        the agent shouldn't make alone (→ Assumption)?"

     Examples (replace or delete these before posting):
     - Cache TTL defaults to 5 min (matches CatalogProject; change if the
       target service has a different SLA).
     - The endpoint accepts JSON only; multipart/form-data is out of scope. -->

## Edge Cases
<!-- What happens with empty input, concurrent access, errors, rollback? -->
<!-- === end feature block === -->

---

## Acceptance Criteria
<!-- What must be true when this is done. At least one required. Make each checkable. -->
- [ ] 
- [ ] 

## Test Cases
<!-- Given <precondition> / When <action> / Then <expected result>. At least one required. -->
- [ ] Given / When / Then
- [ ] Given / When / Then

## Testing & CI
<!-- Local tests the agent runs are fast and targeted — for iteration, not full coverage.
     The FULL/HEAVY suite runs in CI: that is the authoritative gate. A passing local
     run is NOT full verification.

     Tests you specify here are NOT dropped — they run as part of the CI suite. The
     agent may skip heavy ones locally; CI covers them. Caveat: if the repo has no CI
     pipeline covering a test type, it may not run anywhere — wire CI or treat it as
     unverified.

     When CI catches a failure:
     - In-scope fix → re-fire the issue (relabel agent-ready → CI-fix-loop).
     - Out-of-scope or needs per-project secrets (.env) → file a new issue.
       A CI-fix-loop re-fire runs WITHOUT the per-project .env (written only for the
       primary run), so any failure that requires those secrets to reproduce or fix
       locally is a new-issue / operator case. -->

---

## Repositories / branches
<!-- MULTI-REPO ISSUES ONLY — delete this section for single-repo issues.
     The presence of this section is what switches the agent to multi-repo mode
     (the scope: hint below stays advisory). One row per repository the agent
     must change. Submodule paths must match .gitmodules paths exactly.
       - `<repo-name>` (main): branch `<branch>`
       - `<submodule-path>` (`<project-name>`): branch `<branch>`
     The ": branch `<branch>`" suffix is optional — omitted, the agent derives
     sdc/agent-NN/issue-<iid>-<slug> and uses the same name in every repo. -->

---

## Codebase Hints
<!-- Steer the agent: relevant files, patterns to follow, things NOT to touch.
     Examples:
     - "Follow the repository pattern in src/data/repositories/"
     - "Do not modify the public interface in src/api/v1/routes.py"
     - "Use the existing logger — do not add a new one" -->

## Constraints
<!-- Non-functional: performance budget, backwards compatibility,
     API stability, security requirements, deployment restrictions. -->

---

## Agent Configuration
<!-- Model (highly recommended) — set per the task complexity:
       opus   → heavy, architectural, or hard-to-debug work
       sonnet → routine work (the daemon default if this line is omitted)
       haiku  → trivial or mechanical tasks
     The daemon honours an uncommented `model:` line and passes it to the CLI
     verbatim (a sonnet|opus|haiku alias, or a full model id like claude-opus-4-8).
     A commented line is inert. If no uncommented `model:` line is present, the
     daemon defaults to sonnet. The Type label is NOT mapped to a model — it
     drives labels/board only. `thinking` is advisory only — not enforced. -->
<!-- model: opus | sonnet | haiku | glm   ← HIGHLY RECOMMENDED: uncomment and pick one -->
<!-- thinking: low | medium | high | max   (advisory only — not yet enforced by the daemon) -->
<!-- design-mode: provided | agent-designs -->
<!-- scope: single-repo | multi-repo   (advisory — multi-repo mode is triggered by the "Repositories / branches" section) -->
<!-- base-branch: <branch>   (optional — fork this issue's working branch FROM, and target its MR AT, this branch instead of the project default. Use it to stack multiple issues on a shared feature branch. The branch must already exist on the remote, or the issue is parked agent-blocked. Single-repo only — ignored when a "Repositories / branches" section is present. Omit/comment → the project default branch, unchanged.) -->
<!-- skills: <name>, <plugin>:<skill>   (optional — declare the Claude Code skills this agent should use. A BARE name is a PROJECT skill: a directory under the repo's `.claude/skills/` that contains a SKILL.md (e.g. react-revamp). A NAMESPACED `<plugin>:<skill>` is a PLUGIN skill (e.g. superpowers:test-driven-development). Comma-separated; case-sensitive kebab-case, matched exactly. The daemon validates EVERY declared skill pre-claim — project skills against the repo's `.claude/skills/` at the base branch, plugin skills against the agent's installed plugins — and HARD-BLOCKS the issue (relabels agent-blocked, unassigns) if ANY is unknown. Never declare a skill you haven't confirmed exists. Omit/comment → no declaration, unchanged.) -->
<!-- agent-type: <name>   (optional — steer which Claude Code sub-agent type the agent delegates implementation to. Best-effort: only takes effect if the agent chooses to delegate. VALIDATED pre-claim like skills: an unknown name parks the issue agent-blocked. Valid names = the target repo's .claude/agents/ (e.g. pps-web ships web-implement / web-polish / web-pre-commit / web-test), plus Claude Code built-ins (general-purpose, Explore, Plan, …). Omit/comment → no steering, unchanged.) -->
<!-- refresh-graph: true  ← after this MR merges, SDC files a type::graph graph refresh (separate MR). kg-enabled repos only. -->

---

<!-- ## Phases   (OPTIONAL, single-repo only — delete this whole section if the issue runs as one pass.)
     Declare ORDERED phases when the issue decomposes into stages of differing
     difficulty (cheap setup → hard core → trivial docs) or a gated chain
     (implement → polish → pre-commit gate). The daemon runs each phase as its
     OWN Claude run on the SAME branch, in order — commits accumulate, ONE MR is
     opened after the last phase. Each `### Phase N: <title>` block carries its
     own optional `model:` / `skills:` / `agent-type:` lines (same format as
     Agent Configuration) plus its instructions. A directive a phase omits
     CASCADES to the issue-level Agent Configuration value, then (for model) to
     sonnet. Every phase's skills:/agent-type: is validated pre-claim (the UNION),
     so a bad name in any phase blocks the whole issue. Single-repo only in v1: a
     "Repositories / branches" (multi-repo) issue with Phases runs as a single
     pass at the issue-level model. See developer-manual §2.15.

## Phases

### Phase 1: Implement
agent-type: web-implement
Build the feature against the plan. Commit; the daemon commits per phase.

### Phase 2: Polish
agent-type: web-polish
One diff-polish pass over the accumulated diff: DRY, skeleton sync, i18n.

### Phase 3: Pre-commit gate
agent-type: web-pre-commit
Run the Swagger-drift gate and structure-regression check over the full diff.
-->

---

## Dependencies
<!-- List issues whose in-flight (unmerged) branches this issue depends on.
     Use the machine-readable field below for formal dependency composition:

     Depends-on: #3, #5

     The agent reads this line and merges the listed branches into this issue's
     branch before starting work, so the implementation builds on the right base.
     Comma-separated IIDs in the same project; the leading # is optional.
     One Depends-on: line only. Leave this section empty when there are no deps.

     Human notes (external blockers, related context, links) go below:
-->
<!-- Depends-on: #N, #M   ← uncomment and fill in when this issue depends on
     in-flight (unmerged) work from another issue in this project. Delete if
     there are no dependencies. -->

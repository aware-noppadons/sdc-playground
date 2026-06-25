---
name: create-issue
description: Use when a developer wants to file work for an autonomous SDC agent — turning a task, bug, refactor, chore, or research question into a well-formed agent-task issue posted to GitLab with the agent-ready label. Use when asked to "create an agent issue", write an agent-ready issue, or make a task an SDC agent can pick up. GitLab + glab specific.
---

# create-issue

## Overview

Turn a short freeform description into a well-formed SDC **agent-task** issue and
post it to GitLab with the `agent-ready` label, so an autonomous SDC agent picks
it up. Run **inside the target project repo** — read the code to ground the
Design, Test Cases, and Codebase Hints, so the issue is concrete, not generic.

**Core principle:** never post an `agent-ready` issue that fails the prerequisite
gate. The skill drafts, *validates against the real gate*, and only then posts.

**glab isn't set up?** If `glab` is not installed or authenticated, the skill will
detect it at post time and offer two options:
1. Set up glab (`glab auth login` or `export GITLAB_TOKEN=<pat>`) and retry — issues
   are authored as you, labels are set automatically.
2. File via the browser: the skill opens the GitLab new-issue page with the title
   pre-filled and puts the full body on your clipboard for pasting.

## When to use

- "Create an agent issue / agent-ready issue", "file this for an SDC agent",
  "make a ticket the agent can implement".
- NOT for editing/closing existing issues, and NOT for non-GitLab trackers.

## Workflow

1. **Preflight.** Confirm the cwd is a git repo with a GitLab remote. The target
   project is the current repo unless the user names another (`-R group/sub/repo`).
   (The glab auth check moves to the **Post** step: if glab isn't set up, the Post
   step recommends setting it up or falls back to the browser+paste flow — no need
   to dead-end here.)
2. **Load the template.** Run `python scripts/load_template.py` to get the
   canonical agent-task template (it resolves from the control plane if
   `SDC_CONTROL_PLANE_URL` is set, else the bundled copy).
3. **Understand the task.** Use the user's description (ask for one sentence if
   absent). **Explore the repo** — relevant files, conventions, test layout — so
   the issue references real code.
4. **Grilling pre-pass.** Before drafting, identify the ambiguities a **headless,
   non-interactive agent** would actually have to guess — unstated decisions, fuzzy
   terms ("recent", "fast"), unspecified scope/boundary behavior, forks with several
   reasonable answers. Frame each internally as *"what would the agent otherwise
   guess here?"*
   - **Codebase-first:** explore before asking; never ask what the code already
     answers.
   - **One question at a time,** each with a recommended answer derived from the
     repo (e.g. *"Cache TTL — Rec: 5 min, matches `CatalogProject`; ok?"*).
   - **Author short-circuit:** the author may accept all recommendations at once
     ("recommendations are fine") — no relentless interrogation.
   - **Scales by need:** a fat feature may surface several questions; a one-line
     chore surfaces **zero** — in which case the pre-pass is a **silent no-op**
     (no questions asked, no `## Assumptions` section emitted). Stop as soon as
     no agent-blocking ambiguity remains.
   - **Dependency question (always ask if unresolved):** "Does this task depend on
     work from another issue whose MR is not yet merged? If yes, which issue IID(s)?"
     If the answer is yes, emit a `Depends-on: #N, #M` line in `## Dependencies`.
     The agent will merge those branches before starting, so it builds on the right
     base. (This is a separate concern from `## Assumptions` — it's about unmerged
     in-flight code, not unstated decisions.)
   - **Route each resolved answer immediately** to the section it informs:

     | Answer is… | Route to |
     |---|---|
     | Unstated default the agent would otherwise **guess** | `## Assumptions` |
     | Hard **must** (violating it = wrong) | `## Constraints` |
     | Part of the **approach** | `## Design` |
     | A **boundary / edge** behaviour | `## Edge Cases` |

     Routing test for the ambiguous case: *"Would breaking it be WRONG
     (→ Constraint), or just a silent choice the agent shouldn't make alone
     (→ Assumption)?"*
   - **Not a gate:** the pre-pass enriches the draft only; `validate_issue.py`
     remains the sole hard gate.
5. **Infer the Type** (`bug | feature | refactor | chore | research | test`). The
   Type is stamped on the issue as a scoped `type::<x>` label at post time (pass
   `--type <inferred>` to `post_issue.py`, step 9), so the operator board's type
   filter can use it. (The type labels are provisioned on the project at assign
   time alongside the `agent-*` labels.) The Type does **not** set the model —
   see the model-suggestion step below. Types at a glance:
   - `bug` — a defect; something behaves incorrectly.
   - `feature` — new capability or user-facing functionality.
   - `refactor` — internal restructure with no behavior change.
   - `chore` — maintenance / housekeeping (deps, config, cleanup).
   - `research` — investigation / spike to answer an open question.
   - `test` — writing automated test scripts/cases (use this when the deliverable
     is *tests*, not application code — e.g. adding a test suite, automating
     existing Given/When/Then cases, implementing E2E scenarios).
5a. **Suggest a model (highly recommended).** Assess the task and recommend a
   `model:` for the agent:
   - **`opus`** — heavy, architectural, or hard-to-debug work (complex refactors,
     multi-system designs, tricky bugs requiring deep reasoning).
   - **`sonnet`** — routine work (standard features, moderate edits, well-scoped
     tasks). This is the daemon's default when no `model:` line is present.
   - **`haiku`** — trivial or mechanical tasks (simple doc fixes, one-liner
     changes, high-volume repetitive work).
   Emit an **uncommented** `model: opus` or `model: haiku` line in
   `## Agent Configuration` when the task warrants it. You may omit the line (or
   leave it commented) when sonnet is appropriate — but erring on the side of
   writing `model: sonnet` explicitly is also fine. This is guidance, not a hard
   gate.
5b. **Suggest skills (optional).** If the task should use specific Claude Code
   skills, declare them so the daemon can validate them. Enumerate what's actually
   available:
   - **Project skills** — bare directory names under the repo's `.claude/skills/`
     that contain a `SKILL.md` (e.g. `react-revamp`):
     `ls -d .claude/skills/*/ 2>/dev/null | xargs -n1 basename` (keep only those
     with a `SKILL.md`).
   - **Plugin skills** — `<plugin>:<skill>` ids from the local plugin cache:
     `find ~/.claude/plugins/cache -name SKILL.md` → the id is
     `<plugin>:<skill>` from `.../<plugin>/<version>/skills/<skill>/SKILL.md`.
   Emit an **uncommented** `skills: <a>, <b>` line in `## Agent Configuration`
   listing only names you confirmed exist (bare = project, `plugin:skill` =
   plugin). Omit the line entirely if no skill is clearly warranted — it is
   optional. **Never invent a name**: the daemon HARD-BLOCKS an issue whose
   declared skill is unresolvable (relabels `agent-blocked`, unassigns), so a
   typo'd skill stalls the issue. `validate_issue.py` warns loudly about any
   declared skill it can't find locally.
5c. **Suggest a sub-agent type (optional).** If the agent should delegate
   implementation to a specific Claude Code **sub-agent type**, declare it with an
   **uncommented** `agent-type: <name>` line in `## Agent Configuration`. Valid
   names come from the target repo's `.claude/agents/<name>.md` (e.g. `aware-payroll-v2/pps-web`
   ships `web-implement`, `web-polish`, `web-pre-commit`, `web-test`), the agent's
   own user/plugin agents, or a Claude Code built-in (`general-purpose`, `Explore`,
   `Plan`, …). Steering is **best-effort** — it only takes effect if the agent
   chooses to delegate — but the **name is validated pre-claim exactly like
   `skills:`**: the daemon HARD-BLOCKS the issue (relabels `agent-blocked`,
   unassigns) if the name resolves to no known sub-agent. **Never invent a name**;
   `validate_issue.py` warns loudly about an `agent-type:` it can't find locally.
   Omit the line for no steering (unchanged).
5d. **Declare ordered phases (optional, single-repo).** When the issue decomposes
   into stages of differing difficulty (cheap setup → hard core → trivial docs) or
   a gated chain (implement → polish → pre-commit), add a `## Phases` section with
   `### Phase N: <title>` sub-blocks, each carrying its own optional
   `model:`/`skills:`/`agent-type:` (same line format as `## Agent Configuration`)
   plus its instructions. The daemon runs **each phase as its own committed Claude
   run on the same branch, in order**, then opens one MR. A directive a phase omits
   **cascades** to the issue-level value (then `sonnet` for model). Every phase's
   `skills:`/`agent-type:` is validated pre-claim (the **union**), so a typo in any
   phase HARD-BLOCKS the whole issue — `validate_issue.py` warns on unknown
   per-phase names. **Single-repo only**: a multi-repo issue (`## Repositories /
   branches`) with `## Phases` runs as one pass at the issue-level model. Omit the
   section to run as a single pass (unchanged). See developer-manual §2.15.
6. **Draft the full body** against the template:
   - Bugs → fill **Reproduction** (steps, expected, actual, logs, env).
   - Features/refactors → fill **Design** (concrete approach, files/APIs to touch),
     **Edge Cases**, and — when the pre-pass surfaced ≥1 assumption — **Assumptions**
     (between Design and Edge Cases; omit entirely if none).
   - **Tests** (`type::test`) → fill **Design** with the test architecture: which
     framework, where test files live, fixtures/mocks needed, and the Gherkin runner
     (if applicable). **Acceptance Criteria** = "each case has a passing automated
     test; coverage target met". **Test Cases** = the individual scenarios to
     automate, written as Given/When/Then. In `## Agent Configuration` recommend
     `skills: superpowers:test-driven-development`; for web/E2E work also add
     `webapp-testing` and/or `playwright-generate-test` if available.
   - Always → **Summary**, **Context**, **Acceptance Criteria** (checkable, real),
     **Test Cases** (`Given / When / Then`, real), **Codebase Hints** (actual
     files/patterns), **Constraints**, **Dependencies** as relevant.
   - **design-mode**: default *provided* (you wrote the Design). Only if the user
     wants the agent to design, leave Design empty and add an **uncommented**
     `design-mode: agent-designs` line in `Agent Configuration`.
   - **Multi-repo** (only when `.gitmodules` exists *and* the work spans members):
     add a `## Repositories / branches` section, one `` - `path` `` row per repo
     using the `.gitmodules` paths; mark the superproject `(main)`. Omit entirely
     for single-repo work.
   - **base-branch** (optional, single-repo only): to stack this issue on a shared
     feature branch, add an **uncommented** `base-branch: <branch>` line in
     `## Agent Configuration`. The agent forks its working branch FROM, and targets
     its MR AT, that branch instead of the project default. The branch must already
     exist on the remote (else the issue parks `agent-blocked`). Omit → the project
     default branch (unchanged). Ignored for multi-repo (the Repositories section
     governs).
   - **Dependencies:** if the issue depends on in-flight (unmerged) work from
     another issue in the *same project*, add `Depends-on: #N` (or
     `Depends-on: #N, #M` for multiple) as an **uncommented** line in
     `## Dependencies`. The agent merges those branches before implementing.
     Omit entirely for single-repo issues with no in-flight deps.
     Note: `Depends-on:` is not yet supported for multi-repo issues (the daemon
     will warn and proceed without composition).
   - **Superseding / superseded work (cross-link convention).** When this issue
     takes over part of another issue's scope — or is itself replaced by one —
     record it as an **uncommented** `Supersedes: #N` / `Superseded-by: #N` line in
     `## Dependencies`. Unlike `Depends-on:`, these are **convention only — not
     parsed or enforced**: they exist to make scope overlap visible on BOTH issues
     so a reviewer or agent can see what's already owned elsewhere (avoiding
     duplicate / conflicting MRs). If an issue is *fully* superseded, prefer
     closing it; use the line when it stays open for a residual slice.
7. **Validate.** Write the draft to a temp file and run
   `python scripts/validate_issue.py <file>`. If `ok` is false, for each missing
   section ask the user a targeted question (or draft it), then re-validate. Loop
   until `ok`. The gate only checks presence/non-emptiness — *also* self-check that
   Acceptance Criteria and Test Cases are **meaningful**, not empty placeholders.
   If it prints a `⚠️  WARNING: declared skill(s) not found` line, a `skills:`
   entry is unresolvable — fix or drop it (the daemon would otherwise
   `agent-blocked` the issue). The warning never changes the exit code.
8. **Preview + approve.** Show the full rendered issue, the target project, and the
   label (`agent-ready`). Get explicit approval; apply any edits, then re-validate.
9. **Post.**
   Run `python scripts/post_issue.py --title "<title>" --body-file <file> --type <inferred-type> [--repo <r>]`.
   It applies `agent-ready` by default and stamps the inferred type as a
   `type::<x>` label (passing `--type` keeps `agent-ready` — the type label joins it).

   - **Exit 0** → done; report the issue URL.
   - **Exit 3** → the project has no `agent-*` labels (not assigned to an SDC agent).
     Tell the user to assign it to an agent in the operator console (auto-creates the
     labels), or re-run with `--no-ready` to post a draft they label later. (If the
     user wants a final manual check, post with `--no-ready` and have them apply
     `agent-ready` in GitLab.)
   - **Exit 4** → `glab` is not installed or not authenticated. Show the user the fix
     commands (printed to stderr). Ask: "Would you like to set up glab and retry, or
     file this via the browser instead?"
     - **Set up + retry**: wait for the user to run `glab auth login` (or export
       `GITLAB_TOKEN`), then re-run the glab path.
     - **Browser / decline / retry fails again**: run
       `python scripts/post_issue.py --method browser --title "<title>" --body-file <file> --type <inferred-type> [--repo <r>]`
       and relay the printed URL + paste instructions to the user (the `type::<x>`
       label rides the `/label` quick-action lines in the pasted body).
10. **Report** the created issue URL.

## Quick reference

| Step | Command |
|------|---------|
| Get template | `python3 scripts/load_template.py` |
| Validate a draft | `python3 scripts/validate_issue.py <body-file>` → `{"ok",…}` (exit 0/1) |
| Preview the post | `python3 scripts/post_issue.py --title … --body-file … --type <type> [--repo …] --dry-run` |
| Post (glab, primary) | `python3 scripts/post_issue.py --title … --body-file … --type <type> [--repo …]` (add `--no-ready` to skip the label) |
| Post (browser fallback) | `python3 scripts/post_issue.py --title … --body-file … --type <type> [--repo …] --method browser` |

`--type` is one of `bug | feature | refactor | chore | research | test` (the inferred Type); it stamps a scoped `type::<x>` label that joins `agent-ready` and, on the browser fallback, rides the `/label` paste lines.

**Prerequisite gate** (mirrored by `validate_issue.py`): a non-empty `## Design`
*or* an uncommented `design-mode: agent-designs`; a non-empty
`## Acceptance Criteria`; a non-empty `## Test Cases`. HTML comments are stripped
first, so commented template hints never count. See [glab cheatsheet](references/glab-cheatsheet.md).

**Issue section structure** — key sections in order:
- `## Design` — approach and architecture (required, or exempted by `agent-designs`)
- `## Assumptions` — **conditional** (omit if no assumptions surfaced): pinned
  defaults the agent may take as given; unstated decisions it would otherwise guess.
  Routing: Assumption = "silent choice the agent shouldn't make alone";
  Constraint = "violating it would be wrong". Agent parks (`agent-needs-input`)
  if an assumption proves false at runtime.
- `## Edge Cases` — boundary and error behaviour
- `## Acceptance Criteria` — required; must be checkable and non-placeholder
- `## Test Cases` — required; must be Given/When/Then and non-placeholder

**Model suggestion heuristic (not a Type mapping):** the daemon defaults to
**`sonnet`**; set an uncommented `model:` line in `## Agent Configuration` to
opt up or down — **`opus`** (heavy/architectural/hard-to-debug), **`sonnet`**
(routine; the default if omitted), **`haiku`** (trivial/mechanical). The
`effort`/`thinking` fields stay advisory — not enforced by the daemon.

The **model** is resolved by the daemon at claim time: an **uncommented**
`model:` line in the issue's `## Agent Configuration` section → that value
verbatim (a `sonnet|opus|haiku` alias or a full model id); else the daemon
defaults to **`sonnet`**. A commented `<!-- model: ... -->` line is inert. The
Type label is **not** mapped to a model — Type drives labelling and board
filtering only. The `effort`/`thinking` column remains advisory — not enforced.

The **base-branch** override is resolved the same way: an **uncommented**
`base-branch: <branch>` line in `## Agent Configuration` makes the daemon fork
the working branch from — and target its MR at — that branch instead of the
project default (single-repo only; ignored for multi-repo). The branch must
exist on the remote or the issue parks `agent-blocked`; absent/commented/blank →
the project default branch.

## Common mistakes

- **Posting placeholders.** The gate passes on any non-empty section, so empty
  `- [ ]` checkboxes "pass" but produce vague work. Write real criteria/tests.
- **Skipping validation.** Always run `validate_issue.py` before posting, even if
  the draft looks complete.
- **`agent-designs` in a comment.** A commented directive is stripped and does NOT
  exempt Design — it must be an uncommented line.
- **Emitting `## Repositories / branches` for a single repo.** Its mere presence
  switches the agent to multi-repo mode. Only include it for true submodule work.
- **Posting to an unassigned project.** If `post_issue.py` exits 3, the project
  isn't wired to an agent — assign it first; don't force the label.
- **Filing a multi-concern note as one issue.** If a capture or follow-up spans
  more than one independent fix, **split it** — file each as its own scoped issue
  (split-on-file). A single issue mixing concerns can't pass the gate cleanly and
  risks an agent re-touching work another issue already owns. Cross-link the
  pieces with `Supersedes:` / `Superseded-by:` in `## Dependencies`.

## Phased / multi-agent tasks

For ordered stages — differing difficulty (cheap setup → hard core → trivial docs)
or a gated chain (implement → polish → pre-commit) — use a first-class **`## Phases`**
section (single-repo). Each `### Phase N: <title>` sub-block carries its own optional
`model:` / `skills:` / `agent-type:` (same line format as `## Agent Configuration`)
plus its instructions, and the daemon runs **each phase as its own committed Claude
run on the same branch, in order**, then opens one MR:

```
## Phases

### Phase 1: Implement
agent-type: web-implement
Build the feature against the plan.

### Phase 2: Core logic
model: opus
Implement the hard algorithm.

### Phase 3: Docs
model: haiku
Update docstrings + changelog.
```

A directive a phase omits **cascades** to the issue-level value (then `sonnet` for
model). Every phase's `skills:`/`agent-type:` is validated **pre-claim** (the union
with the issue-level ones), so a typo in any phase HARD-BLOCKS the whole issue —
`validate_issue.py` warns on unknown per-phase names. **Single-repo only:** a
multi-repo issue (`## Repositories / branches`) with `## Phases` runs as one pass at
the issue-level model.

**Prose alternative (no `## Phases`).** If you only need the main agent to delegate
to project sub-agents at runtime (all stages at one model), name sub-agents in prose
in `## Design` (e.g. `use \`web-implement\` to build, run \`web-pre-commit\` to
gate`). This is **non-deterministic** and **unvalidated** — a nonexistent prose name
silently falls back to manual implementation (the #299 bug); `validate_issue.py`
warns when it detects this shape. Prefer `## Phases` (validated, deterministic) or
the issue-level `agent-type:`/`skills:` directives.

Full guidance: [developer-manual §2.15 — First-class per-phase config](../../../docs/developer-manual.md#215-first-class-per-phase-config-phases).

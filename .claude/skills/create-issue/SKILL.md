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
5. **Infer the Type** (`bug | feature | refactor | chore | research`). The Type is
   stamped on the issue as a scoped `type::<x>` label at post time (pass
   `--type <inferred>` to `post_issue.py`, step 9), so the operator board's type
   filter can use it. (The type labels are provisioned on the project at assign
   time alongside the `agent-*` labels.) The Type does **not** set the model —
   see the model-suggestion step below.
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
6. **Draft the full body** against the template:
   - Bugs → fill **Reproduction** (steps, expected, actual, logs, env).
   - Features/refactors → fill **Design** (concrete approach, files/APIs to touch),
     **Edge Cases**, and — when the pre-pass surfaced ≥1 assumption — **Assumptions**
     (between Design and Edge Cases; omit entirely if none).
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

`--type` is one of `bug | feature | refactor | chore | research` (the inferred Type); it stamps a scoped `type::<x>` label that joins `agent-ready` and, on the browser fallback, rides the `/label` paste lines.

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

## Phased / multi-agent tasks

Writing a multi-phase plan in prose is natural and **supported**: the daemon passes
the prose through and the **main Claude agent orchestrates** the sequence at
runtime, delegating to sub-agents that exist in the target repo's
`.claude/agents/`. Each sub-agent carries its own model, effort, and tools.

**To write a phased plan:** reference sub-agents by name in `## Design` or
`## Agent Configuration` (e.g. `use \`web-implement\` to build, run
\`web-pre-commit\` to gate`). **Confirm each referenced agent exists** in the
target repo's `.claude/agents/` before posting — a prose reference is not
validated by the daemon, so a nonexistent name silently falls back to manual
implementation (the #299 bug).

**Prefer the validated directives** when a single agent or skill covers the whole
task: `agent-type: web-implement` or `skills: web-implement` in
`## Agent Configuration`. The daemon validates existence pre-claim; a typo parks
the issue `agent-blocked` rather than silently degrading.

**Different models per phase?** The daemon runs **one model per issue**. Split
into separate issues (one per model-distinct phase) connected by `Depends-on:`
or GitLab blocking issues. If all phases use the same model, a single issue
with a prose plan is correct.

`validate_issue.py` emits an advisory warning (never blocks) when it detects a
phased / delegation plan that may assume daemon-orchestrated phase switching.

Full guidance: [developer-manual §2.14 — Phased / multi-agent work](../../../docs/developer-manual.md#214-phased--multi-agent-work).

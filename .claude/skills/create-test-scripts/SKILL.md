---
name: create-test-scripts
description: Use when filing test-SCRIPT implementation work for an SDC agent — turning existing test cases (Given/When/Then) or a test spec into a `type::test` agent-task issue an agent implements as automated test code. The Flow-A counterpart to /create-test-cases (which produces the cases). Use for "create a test-implementation issue", "automate these test cases", "write the test suite / E2E tests for X". GitLab + glab specific.
---

# create-test-scripts

## Overview

File a **test-script implementation** issue: an SDC agent picks it up and writes the automated
**test code**. This is **Flow A** — it implements *how* to verify. Its companion
`/create-test-cases` is **Flow B** — it derives the Gherkin cases (the *what*) from a manual/plan.

`/create-test-scripts` is **`/create-issue` specialized for `type::test` work** — same template,
same prerequisite gate, same poster, with the Type pre-set to `test` and the draft foregrounded
for test code. It is **not** a separate pipeline; it is a focused front door so the skills read
symmetrically: **`/create-test-cases` (cases) → `/create-test-scripts` (scripts)**. Run it **inside
the target repo** so it grounds the test architecture in the repo's existing test layout.

## When to use

- "Automate these test cases", "implement these Given/When/Then as automated tests", "write the
  test suite / E2E tests for `<feature>`".
- Filing test-script work **by hand** when you already have the cases (or a clear spec).
- **NOT** for deriving cases from a manual/test plan → use **`/create-test-cases`** (it posts
  `type::test` issues directly, so you rarely need this skill *after* a Flow-B run).
- **NOT** for unit-level edges incidental to a feature → file those with the feature via
  **`/create-issue`**.

## Workflow

Follow the **[`/create-issue` workflow](../create-issue/SKILL.md)** exactly, with these
test-script specializations:

1. **Type is fixed = `test`.** Skip type inference; always pass `--type test` to the poster
   (stamps the `type::test` label).
2. **Draft for test code** (create-issue's §6 test-implementation branch):
   - `## Design` → the **test architecture**: framework + runner (pytest + pytest-bdd, Jest +
     jest-cucumber, Cucumber/Behave, Playwright for E2E), where the test / `.feature` files live,
     fixtures / mocks / test data, and how steps bind to code. **Read the repo's existing test
     layout and match it.**
   - `## Acceptance Criteria` → "every listed case has a passing automated test; coverage ≥ target".
   - `## Test Cases` → the cases to automate as Given/When/Then (paste Gherkin verbatim if you
     have it, e.g. from a `/create-test-cases` catalog).
   - `## Agent Configuration` → `model: sonnet` (bump to `opus` for heavy/wide E2E) and
     `skills: superpowers:test-driven-development` (add `webapp-testing` / `playwright-generate-test`
     for web/E2E — confirm they exist in the **target agent's** environment, or the issue parks
     `agent-blocked`).
   - **Staged test work?** If the suite splits into distinct stages with different
     models/skills/agent-types (e.g. scaffold fixtures → write tests → wire CI), declare a
     `## Phases` section instead of one config — the daemon runs each phase as its own committed
     run, in order. See create-issue's "Phased / multi-agent tasks" + developer-manual §2.15.
3. **Reuse create-issue's scripts** (no duplication — repo-root-relative, run from the repo root):
   ```bash
   python .claude/skills/create-issue/scripts/load_template.py            # the canonical template
   python .claude/skills/create-issue/scripts/validate_issue.py <body-file>   # must be ok before posting
   python .claude/skills/create-issue/scripts/post_issue.py \
       --title "test: <feature> — automate test cases" --body-file <body-file> --type test [--repo <r>]
   ```
   The grilling pre-pass, glab/browser fallback, the exit-3 (project not assigned) / exit-4 (glab
   unavailable) handling, and the prerequisite gate are all identical to `/create-issue` — its
   SKILL.md is the source of truth; this skill only fixes Type and foregrounds the test-code draft.

## Quick reference

| Step | Command |
|------|---------|
| Get the template | `python .claude/skills/create-issue/scripts/load_template.py` |
| Validate a draft | `python .claude/skills/create-issue/scripts/validate_issue.py <body-file>` |
| Post the `type::test` issue | `python .claude/skills/create-issue/scripts/post_issue.py --title … --body-file … --type test [--repo …]` |

## Common mistakes

- **Re-deriving cases here.** This skill files work to *implement* cases. To *produce* cases from a
  manual/plan, use `/create-test-cases`.
- **Forgetting `--type test`.** Without it the issue isn't stamped `type::test` and the board can't
  filter it (and the coordinator can't tell it's inert-for-deploy).
- **Declaring a skill the target agent lacks.** `skills:` is validated in the *implementing* agent's
  env; an unknown skill parks the issue `agent-blocked`. Confirm before declaring.

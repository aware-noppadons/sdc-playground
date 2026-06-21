---
name: create-test-cases
description: Use when turning a test plan or user manual (any format — Markdown, DOCX, XLSX, PDF, PPTX) into a ratified, traceable Gherkin acceptance-test-case catalog and fanning it into agent-ready `type::test` issues for an SDC agent to automate. Use when asked to "generate test cases from this manual/spec", "derive acceptance tests from the docs", "create test cases from a test plan", or turn requirements into Given/When/Then scenarios. GitLab + glab specific.
---

# create-test-cases

## Overview

Turn a source document — a **user manual** (the user-facing contract) and/or a **test plan** —
into a ratified **Gherkin** acceptance-test-case catalog, then fan it into `type::test` SDC
agent-task issues that a Flow-A agent implements as automated tests. Run **inside the target
project repo** so the issues land where the work happens.

**Core model — B specifies *what* to verify; A implements *how*.** This skill is **Flow B**: it
produces *cases* (Given/When/Then), not test *code*. The cases flow into `type::test` issues
(**Flow A**) whose implementing agent writes the actual `.feature`/test files in an MR.

**Two principles make the output trustworthy:**
1. **Independence.** Cases are derived from the user-facing source and **ratified by a second,
   independent review sub-agent** — never by the agent that drafted them. That catches the
   failure mode where one author's blind spot produces tests that rubber-stamp the same
   misunderstanding.
2. **Traceability (RTM).** Every scenario carries an `@source` tag back to a real section of the
   source document. A tag that doesn't resolve is confabulation, and the validator + reviewer
   reject it.

## When to use

- "Generate / derive test cases from this manual / spec / test plan", "create acceptance tests
  for feature X from the docs", "turn these requirements into Given/When/Then".
- **NOT** for writing the actual test *code* — that is the resulting `type::test` issues (Flow A;
  use `/create-issue` with `--type test` directly if you already have the cases).
- **NOT** for unit-level edge cases — this is the **acceptance / behavioural / E2E** layer; for
  unit edges use TDD on the feature issue itself.
- **NOT** for authoring a test *plan* or doing exploratory testing — those are human-judgment /
  interactive activities; this skill *consumes* a plan, it does not write one.

## Prerequisites

- cwd is the target repo (a GitLab remote). The source doc(s) should be reachable — **prefer
  committed in-repo** (e.g. `docs/`) so the cases are versioned and regenerable when the source
  changes.
- `glab` set up for posting (else the fan-out previews / falls back to the browser, exactly like
  `/create-issue` — `post_issue.py` handles it).

## Workflow

1. **Preflight.** Confirm the repo + remote. Identify the source doc(s) and — critically — the
   **scope**: a section / feature, **not** "the whole manual". Unbounded scope is the
   over-generation failure mode. If the author hasn't scoped, run ingest (step 2) and offer the
   manifest's sections/features as a pick-list.

2. **Ingest / normalize.** Run:
   ```bash
   python .claude/skills/create-test-cases/scripts/ingest.py <src> [<src2> ...] --out <work-dir>
   ```
   It writes `<work-dir>/normalized.md`, `<work-dir>/images/`, and `<work-dir>/manifest.json`
   (the RTM index: `sections[].id` are the anchors `@source` tags must resolve to). MD/DOCX/XLSX
   extract deterministically; PDF/PPTX are image-assisted and **confidence-flagged**. Heavy
   parsers are optional — if a section is `confidence: low` or the manifest says
   `needs_multimodal_read: true`, **read the rendered page images (or the raw file) with the Read
   tool** to supplement before drafting. Never auto-install libraries.

3. **Scope.** Pick the in-scope manifest section id(s)/feature(s). Everything downstream is bounded
   to these.

4. **DRAFT (dispatch an Opus sub-agent).** Dispatch a sub-agent with the **DRAFT prompt** below.
   It applies `references/test-design-techniques.md` feature-by-feature and writes tagged Gherkin
   to a catalog file (`<work-dir>/catalog.feature`).

5. **RATIFY (dispatch a SEPARATE, independent sub-agent).** Dispatch a **different** sub-agent —
   **Opus or Sonnet, NEVER Haiku** (Haiku cannot review *intention*; it may only check
   syntax/format) — with the **REVIEW prompt** below. It sees **only the source + the scenarios**,
   not the drafter's reasoning, and is **strictly read-only**. The prompt forbids mutation, but
   belt-and-suspenders: **do not grant the review sub-agent write/commit/post tools** — it needs
   only read + the one `validate_cases.py` run. (Review sub-agents have merged/edited when merely
   *told* not to; withholding the tools is the real guard, not the prose.)
   - Verdict `PASS` → proceed to step 6.
   - Verdict `REVISE` → re-dispatch the DRAFT sub-agent **with the reviewer's findings appended**,
     then re-review. Loop **at most 2 rounds**. If still `REVISE` after 2 rounds, **proceed to the
     preview (step 7) anyway with the residual gaps listed explicitly** — never hide them, never
     loop forever.

6. **Validate.** Run:
   ```bash
   python .claude/skills/create-test-cases/scripts/validate_cases.py <work-dir>/catalog.feature --manifest <work-dir>/manifest.json
   ```
   Fix any **HARD** errors (malformed Gherkin) by looping back to DRAFT. **Advisory** warnings
   (coverage below threshold, missing/confabulated `@source`, vacuous `Then`, low-confidence
   source) — address, or note them in the preview. **Coverage caveat:** the metric is computed
   against the **whole** manifest, so a *scoped* run (a few of many sections) reports low coverage
   and lists the out-of-scope ids as "uncovered" — this is **expected**, not a gap. Judge coverage
   against your **in-scope** sections (every in-scope id should be referenced by ≥1 scenario); the
   out-of-scope ids in the advisory are noise for a scoped run.

7. **Preview + approve (the POST gate).** Show the human: the catalog (scenarios, coverage %,
   risk mix, any residual gaps), and the planned **fan-out** — one `type::test` issue per feature
   (≤ ~15 scenarios each; split larger features and say so). Get explicit approval to **post**.
   *(This POST gate is distinct from the content gate: the review sub-agent already ratified
   case **quality**; the human only authorises spawning fleet work + cost.)*

8. **Fan-out / post.** For each feature group, build an issue body from
   `references/test-case-issue.md`:
   - `## Summary` — which feature's tests, from which source.
   - `## Context` — RTM: the source doc + the `@source` locators this issue covers.
   - `## Design` — test architecture (framework, where tests live, fixtures/mocks, Gherkin runner).
   - `## Acceptance Criteria` — "every scenario below has a passing automated test; coverage ≥ target".
   - `## Test Cases` — that feature's Gherkin scenarios, verbatim (tags included).
   - `## Agent Configuration` — `model: sonnet` (opus for heavy E2E) and
     `skills: superpowers:test-driven-development` (+ `webapp-testing` / `playwright-generate-test`
     for web/E2E) so the implementing agent reuses the established test skills.

   Validate each body, then post it, reusing the create-issue machinery (no duplication):
   ```bash
   python .claude/skills/create-issue/scripts/validate_issue.py <body-file>      # must be ok
   python .claude/skills/create-issue/scripts/post_issue.py --title "test: <feature> acceptance tests" \
       --body-file <body-file> --type test [--repo <r>]
   ```
   `post_issue.py` applies `agent-ready` + `type::test` and handles the browser fallback / the
   "project not assigned to an agent" (exit 3) and "glab unavailable" (exit 4) cases exactly as in
   `/create-issue`.

9. **Report.** The created issue URLs + a coverage/traceability summary (in-scope source sections
   covered vs residual).

## The DRAFT sub-agent prompt (fill the {…} and dispatch as **Opus**)

```
You are a test-case DESIGNER. Design a thorough, traceable Gherkin acceptance-test catalog from
the source — do NOT write test code, and do NOT invent behaviour the source does not describe.

Source (normalized markdown): {NORMALIZED_PATH}   (images alongside; for any section flagged
  confidence: low or needs_multimodal_read, READ its page images / the raw file with the Read tool)
RTM manifest (valid @source ids): {MANIFEST_PATH}
Scope — design cases ONLY for these section(s)/feature(s): {SCOPE}

Method: apply .claude/skills/create-test-cases/references/test-design-techniques.md
feature-by-feature (for each requirement: pick the applicable techniques, then generate cases per
technique), and follow .claude/skills/create-test-cases/references/gherkin-style.md (declarative,
one behaviour per scenario, Scenario Outline + Examples for data-driven cases; for combinatorial
inputs use pairwise — all PAIRS, not the full cartesian product).

Output: WRITE Gherkin to {CATALOG_PATH}, grouped by `Feature:`. EVERY `Scenario`/`Scenario Outline`
is preceded by a tag line:
  @source:<doc-basename>#<id>   ← the <id> MUST be a real id in the manifest (else it's rejected)
  @technique:<ep|bva|decision-table|state-transition|pairwise|error-path>
  @risk:<P0|P1|P2>              ← P0 = user-facing failure / data-loss / security
Be exhaustive on the in-scope behaviour. You may ONLY write {CATALOG_PATH} — no other file, no git.
{REVISION: The independent reviewer returned REVISE. Address every finding below, then rewrite the
catalog: {FINDINGS}}
```

## The REVIEW sub-agent prompt (fill the {…} and dispatch as **Opus or Sonnet — never Haiku**)

```
You are an INDEPENDENT test-case REVIEWER. You did NOT write these scenarios; judge them ONLY
against the source, not against any assumed author intent. STRICTLY READ-ONLY: output a verdict
and findings only — edit NOTHING (no catalog edits, no files, no git, no glab).

Source (normalized markdown): {NORMALIZED_PATH}   (images alongside)
RTM manifest: {MANIFEST_PATH}
Catalog under review: {CATALOG_PATH}
In-scope: {SCOPE}

Check, independently:
(a) Traceability — every scenario's @source id EXISTS in the manifest AND the scenario genuinely
    follows from that section. Flag confabulation or mis-citation.
(b) Coverage gaps — list in-scope source statements/requirements with NO scenario.
(c) Vacuous / duplicate — a Then with no observable assertion; near-duplicate scenarios.
(d) Low-confidence — scenarios resting on confidence: low manifest sections (verify against the
    source images/raw text).
(e) Technique soundness — risk ranks and @technique tags are sensible; pairwise is not
    cartesian-bloated.
You MAY run (read-only): python .claude/skills/create-test-cases/scripts/validate_cases.py
  {CATALOG_PATH} --manifest {MANIFEST_PATH}

Output: VERDICT (PASS | REVISE), then a concrete findings list (scenario name + line + the problem
+ a suggested fix). PASS only if traceability holds and there are no material coverage gaps or
vacuous scenarios.
```

## Quick reference

| Step | Command |
|------|---------|
| Ingest a source | `python .claude/skills/create-test-cases/scripts/ingest.py <src> [...] --out <dir>` |
| Validate a catalog | `python .claude/skills/create-test-cases/scripts/validate_cases.py <dir>/catalog.feature --manifest <dir>/manifest.json` → `{ok,hard_errors,warnings,coverage}` (exit 0/1) |
| Validate an issue body | `python .claude/skills/create-issue/scripts/validate_issue.py <body-file>` |
| Post a `type::test` issue | `python .claude/skills/create-issue/scripts/post_issue.py --title … --body-file … --type test [--repo …]` |

All commands are **repo-root-relative** — run them from the target repo root (where the skill lives at `.claude/skills/`), which is the documented cwd.

**Tag grammar (every scenario):** `@source:<doc-basename>#<manifest-id>  @technique:<ep|bva|decision-table|state-transition|pairwise|error-path>  @risk:<P0|P1|P2>`.

**Models:** DRAFT = **Opus** (heavy reasoning over the source). REVIEW = **Opus or Sonnet** —
**never Haiku** for intention (Haiku is fine only for pure syntax/format passes).

## Common mistakes

- **Unbounded scope.** "Generate cases for the whole manual" over-generates. Always bound to a
  section/feature; the per-issue fan-out caps at ~15 scenarios.
- **Same agent drafts and reviews.** That defeats independence. The reviewer must be a **separate
  sub-agent with a different model**, given only the source + scenarios.
- **Confabulated `@source`.** An id not in the manifest = invented coverage. The validator and the
  reviewer catch it; fix before posting, don't post.
- **Emitting `.feature` files / committing.** This skill emits **issues**; the implementing agent
  (Flow A) writes the test files in its MR. Do not commit the catalog or open an MR here.
- **Posting without the human go.** The review sub-agent ratifies *quality*; the human still
  authorises the *post* (it spawns fleet work). Show the preview first.
- **Skipping the validator / ignoring advisories.** Low coverage or a vacuous `Then` is a quality
  signal — surface it even if `ok: true`.

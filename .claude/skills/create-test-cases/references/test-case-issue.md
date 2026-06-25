<!--
  type::test issue body — BUNDLED TEMPLATE for the create-test-cases fan-out.

  The Flow-B fan-out fills this once PER COHERENT FEATURE and posts it via the
  create-issue poster:
      python ../create-issue/scripts/post_issue.py --type test \
          --title "<feature> — automate test cases" --body-file <filled> [--repo <r>]
  It reuses, does NOT duplicate, post_issue.py (labels, browser fallback, agent
  pre-check inherited). The body must pass the SAME prerequisite gate as any
  agent-task issue (validate_issue.py): a non-empty ## Design, ## Acceptance
  Criteria, and ## Test Cases. HTML comments are stripped before the gate runs,
  so a section that contains ONLY comments counts as EMPTY and FAILS — each
  required section below therefore keeps at least one real, uncommented line that
  the fan-out replaces with the feature's specifics.

  Section order is fixed (Contract 3): Summary, Context, Design, Acceptance
  Criteria, Test Cases, Agent Configuration, Constraints. Keep it.

  How to fill (per feature):
    - Summary    → which feature's tests, from which source doc.
    - Context    → the RTM @source locators this issue covers (back-links).
    - Design     → the test architecture for THIS repo (framework, file
                   location, fixtures/mocks, Gherkin runner). Ground it by
                   reading the repo's existing test layout — do not leave the
                   generic hint in place.
    - Test Cases → the feature's ratified Gherkin scenarios (Contract 2),
                   VERBATIM from the catalog, tags and all.
    - Agent Configuration → keep model: sonnet (bump to opus for heavy E2E);
                   resolve and set the skills: line only if a TDD skill is
                   confirmed available in the target env (see the decision tree
                   in the ## Agent Configuration comment below).
-->

## Summary
<!-- One line: which feature's tests, and the source they trace to.
     Replace the line below. -->
Automate the test cases for **<feature>**, derived from `<source-doc>`.

## Context
<!-- RTM back-links: the source document and the @source locators this issue's
     scenarios cover. Lets the implementer (and a reviewer) trace each scenario
     to the originating requirement. Each `@source` id must resolve to a real
     `manifest.sections[].id` — a non-resolving id is confabulation and is
     rejected by the validator/reviewer. Replace the examples. -->
Source: [`<source-doc>`](./docs/<source-doc>)

Requirement traceability (the `@source` locators covered by the scenarios below):
- `<source-basename>#sec-3-2` — <short label of that section>
- `<source-basename>#sec-3-4` — <short label of that section>

These cases were drafted with the SDC test-design technique checklist and ratified
by an independent review-agent (traceability + coverage + non-vacuous).

## Design
<!-- TEST ARCHITECTURE for THIS repo — the implementer needs concrete answers,
     so READ the repo's existing test layout and replace the line below:
       - Framework / runner (e.g. pytest + pytest-bdd, Jest + jest-cucumber,
         Cucumber-JS, Behave, Playwright + a Gherkin runner for E2E).
       - WHERE the .feature files and step definitions live (match the repo's
         existing convention, e.g. tests/features/, features/).
       - Fixtures / mocks / test data needed (DB seeding, fake clock, stubbed
         downstream services, auth fixtures).
       - How Given/When/Then steps bind to code (step-definition style /
         page objects for UI — declarative steps, no selectors in the .feature).
       - Whether this is unit/integration (in-process) or E2E (drives the app).
     Keep at least one real, uncommented line here or the prereq gate fails. -->
Add the scenarios below as executable `.feature` specs with step definitions,
following this repo's existing test framework and directory layout. Use fixtures
for setup and keep step definitions declarative (no UI selectors in the
`.feature`). Replace this paragraph with the concrete framework, file paths,
fixtures, and Gherkin runner once the repo's test layout is confirmed.

## Acceptance Criteria
<!-- Contract 3 fixed criteria. Set <target> to a concrete coverage figure
     (e.g. 100% of the scenarios below; or a line/branch target if the repo
     measures it). Add feature-specific criteria as extra checkboxes if useful. -->
- [ ] Every scenario in ## Test Cases below has a passing automated test
- [ ] Coverage of the listed source sections ≥ <target> (e.g. 100% of the scenarios below)

## Test Cases
<!-- The feature's ratified Gherkin scenarios go here VERBATIM from the catalog,
     INSIDE a ```gherkin fenced block, each preceded by its Contract-2 tag line
     (@source / @technique / @risk). Replace the placeholder line below with the
     real scenarios. Keep at least one real, uncommented line (the placeholder,
     or the real scenarios) so the prereq gate sees this section as non-empty.

     ILLUSTRATION ONLY (the shape to produce — do NOT ship these verbatim;
     they are commented so they don't count as this issue's real content):

     ```gherkin
     Feature: Sign-up

       @source:user-manual#sec-3-2 @technique:bva @risk:P0
       Scenario: Reject signup when age is below the minimum
         Given an applicant whose age is 17
         When they submit the sign-up form
         Then the sign-up is rejected with "you must be at least 18"

       @source:user-manual#sec-3-2 @technique:bva @risk:P0
       Scenario: Accept signup at exactly the minimum age
         Given an applicant whose age is 18
         When they submit the sign-up form
         Then the account is created

       @source:user-manual#sec-3-4 @technique:error-path @risk:P0
       Scenario: Reject account deletion by a non-owner
         Given user "alice" is signed in
         When alice attempts to delete the account belonging to "bob"
         Then the request is refused with "403 forbidden"
         And bob's account still exists
     ```
-->
Paste the feature's ratified Gherkin scenarios here (verbatim from the catalog, in a ```gherkin block, each with its `@source` / `@technique` / `@risk` tag line).

## Agent Configuration
<!-- Pre-filled per Contract 3. The daemon honours an UNCOMMENTED model: line
     and, if present, an UNCOMMENTED skills: line (it validates every declared
     skill pre-claim and HARD-BLOCKS the issue if any id is unresolvable).
       - model: sonnet is right for in-process unit/integration test work.
         Bump to `model: opus` for heavy or wide E2E suites (browser-driven,
         many flows, tricky async).
       - skills: is COMMENTED OUT by default. The fan-out agent MUST check the
         target environment and ONLY uncomment + set the line after resolving
         which id is actually available there:

           1. If .claude/skills/tdd/SKILL.md exists in the target repo
              → uncomment and set:  skills: tdd
           2. Else if the agent has the superpowers plugin installed
              → uncomment and set:  skills: superpowers:test-driven-development
           3. If neither is available → leave the skills: line commented out.
              The daemon no-ops on an empty declaration; the issue is NOT blocked.

         The bare name `tdd` and the plugin id `superpowers:test-driven-
         development` are NOT interchangeable at the skill gate — declare the
         one that the target agent actually provides, or omit entirely. An
         unresolvable skill id parks the issue agent-blocked on claim.
       - For web / E2E skills (webapp-testing, playwright-generate-test): apply
         the same three-step env-check before adding them. -->
model: sonnet
<!-- skills: tdd | superpowers:test-driven-development -->
<!-- For web / E2E work, also resolve webapp-testing / playwright-generate-test
     using the same env-check. Bump model to opus for heavy E2E suites:
     model: opus
     skills: tdd | superpowers:test-driven-development, webapp-testing, playwright-generate-test -->

## Constraints
<!-- OPTIONAL — delete if none. Non-functional limits for the test work, e.g.:
     - Tests must run in CI without network access (mock downstream services).
     - Do not modify application code — this issue delivers tests only.
     - Keep new test fixtures under the repo's existing tests/ tree. -->

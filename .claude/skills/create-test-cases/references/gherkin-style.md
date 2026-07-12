# Gherkin style — writing "good scenarios" (Specification by Example)

This is the house style for every scenario the DRAFT agent emits. It encodes the
Specification-by-Example / Cucumber norms: a scenario is an **executable
specification of behaviour**, readable by a non-programmer, that the
implementing (Flow A) agent turns into automated test code. Write the *what*, not
the *how*.

A scenario that follows these rules is **traceable** (tagged), **declarative**
(behaviour, not clicks), **focused** (one behaviour), and **non-vacuous** (asserts
an observable outcome). One that doesn't is noise the review-agent will reject.

---

## The rules

### 1. Declarative, not imperative — describe behaviour, not UI mechanics

The single most important rule. State the **business intent and outcome**, not
the sequence of buttons, fields, and clicks. Imperative scenarios are brittle
(they break when the UI moves), unreadable (the intent drowns in mechanics), and
couple your *specification* to one *implementation*.

**Anti-pattern (imperative):**
```gherkin
Scenario: Login
  Given I open "https://app.example.com/login"
  When I type "alice@example.com" into the field with id "#email"
  And I type "hunter2" into the field with id "#password"
  And I click the button with class ".btn-primary"
  And I wait 2 seconds
  Then I see the element "#dashboard-welcome"
```

**Fixed (declarative):**
```gherkin
@source:user-manual#sec-2-1 @technique:ep @risk:P0
Scenario: Sign in with valid credentials
  Given a registered user "alice@example.com"
  When she signs in with the correct password
  Then she lands on her dashboard
```

The fix names the *actor* and the *behaviour* (`signs in`) and asserts the
*outcome* (`lands on her dashboard`) — leaving "which field, which button" to the
Flow A implementer. The selectors, URLs, and waits are **incidental detail**
(rule 6) and belong in step-definition / page-object code, never in the spec.

### 2. One behaviour per scenario

A scenario verifies **exactly one** rule or outcome. If you find yourself writing
a second `When … Then …` pair, or a `Then` that asserts two unrelated things,
split it. One behaviour per scenario means a failing test points at exactly one
broken rule.

**Anti-pattern (two behaviours welded together):**
```gherkin
Scenario: Signup
  When a user signs up with a valid email and a weak password
  Then the password is rejected with "too weak"
  When the user signs up with a valid email and a strong password
  Then the account is created
  And a welcome email is sent
  And the user is logged in
```

**Fixed (split; each asserts one thing):**
```gherkin
@source:user-manual#sec-2-2 @technique:bva @risk:P1
Scenario: Reject signup with a password below the strength threshold
  Given a valid, unused email address
  When the user signs up with a password that fails the strength rules
  Then the signup is rejected with "password is too weak"

@source:user-manual#sec-2-2 @technique:ep @risk:P0
Scenario: Create an account with valid signup details
  Given a valid, unused email address
  When the user signs up with a password that meets the strength rules
  Then the account is created
```

(If "a welcome email is sent" and "the user is logged in" are *separately
important*, give each its own scenario — they are distinct behaviours.)

### 3. `Scenario Outline` + `Examples` for data-driven cases

When the **same behaviour** is exercised with **different data** (boundary
triples, equivalence representatives, decision-table rules, pairwise
combinations), use a `Scenario Outline` with an `Examples` table — never
copy-paste near-identical scenarios. One outline = one behaviour, many data
points; the `@technique`/`@risk` tags apply to the whole outline.

**Anti-pattern (three copy-pasted scenarios):**
```gherkin
Scenario: Age 17 is rejected
  ...
Scenario: Age 18 is accepted
  ...
Scenario: Age 19 is accepted
  ...
```

**Fixed (one outline, the boundary points as rows):**
```gherkin
@source:user-manual#sec-3-2 @technique:bva @risk:P0
Scenario Outline: Enforce the minimum sign-up age at the boundary
  Given an applicant whose age is <age>
  When they submit the sign-up form
  Then the sign-up is <verdict>
  Examples:
    | age | verdict                                  |
    | 17  | rejected with "you must be at least 18"  |
    | 18  | accepted and the account is created      |
    | 19  | accepted and the account is created      |
```

Placeholders are `<angle-bracketed>` and match `Examples` column headers exactly.
Keep an optional trailing `# comment` column to map a row to a rule id or
boundary (e.g. `# R1`, `# just-outside`).

### 4. `Background` for shared context — but only truly shared, behaviour-neutral setup

When **every** scenario in a feature needs the same precondition, lift it into a
`Background`. This removes repetition. But keep `Background` short and **free of
anything a scenario asserts on** — it is setup, not test. If a precondition only
applies to some scenarios, leave it in those scenarios' `Given`.

```gherkin
Feature: Account deletion

  Background:
    Given a signed-in account owner "alice@example.com"

  @source:user-manual#sec-3-4 @technique:error-path @risk:P0
  Scenario: Reject deletion when the password re-confirmation is wrong
    When alice requests deletion and confirms with an incorrect password
    Then her account is not deleted

  @source:user-manual#sec-3-4 @technique:state-transition @risk:P0
  Scenario: Delete the account after a correct password re-confirmation
    When alice requests deletion and confirms with her correct password
    Then her account is permanently deleted
```

Avoid the anti-pattern of a fat `Background` that creates orders, sets prices,
and logs events that only one scenario uses — it makes each scenario harder to
read and couples unrelated tests.

### 5. Meaningful names — name the behaviour and its outcome

The `Scenario:` name is a one-line specification. A reader should know what's
verified **without reading the steps**. Name the *behaviour and the expected
result*, in business language.

| Bad (vague / mechanical) | Good (behaviour + outcome) |
|---|---|
| `Scenario: Test 1` | `Scenario: Reject signup when age is below the minimum` |
| `Scenario: Login works` | `Scenario: Sign in with valid credentials lands on dashboard` |
| `Scenario: Edge case` | `Scenario: Refuse to cancel an order that has already shipped` |
| `Scenario: POST /orders 400` | `Scenario: Reject an order with no line items` |

### 6. No incidental detail

Every clause must earn its place by being **relevant to the behaviour under
test**. Strip selectors, URLs, sleeps, exact timestamps, auto-generated ids,
and "and then I see the spinner" noise. If changing a detail wouldn't change
*what behaviour is verified*, it's incidental — cut it or push it into the
implementer's step code.

**Anti-pattern (drowning in incidental detail):**
```gherkin
Scenario: Place order
  Given I am on "https://shop.example.com/cart?ref=email&utm=spring"
  And the page has finished loading within 3000ms
  When I click "#checkout-btn" at coordinates (412, 880)
  And the order id "ORD-7f3a9c-2026" is generated
  Then I see a green toast with hex color #2ecc71
```

**Fixed:**
```gherkin
@source:user-manual#sec-6-1 @technique:ep @risk:P0
Scenario: Place an order from a cart with items
  Given a cart containing at least one item
  When the customer places the order
  Then the order is confirmed
```

---

## Structure & tags (Contract 2)

Use **standard Gherkin** keywords:
`Feature:`, `Background:`, `Scenario:`, `Scenario Outline:` + `Examples:`, and
`Given` / `When` / `Then` / `And` / `But`. Use `And`/`But` to chain steps under
the prior keyword (don't repeat `Given`/`When`/`Then`).

**Group scenarios by feature**, one `Feature:` block per coherent feature (the
fan-out posts one `type::test` issue per feature). Inside it, **every
`Scenario` / `Scenario Outline` is preceded by a single tag line** carrying all
three Contract-2 tags:

```gherkin
Feature: Sign-up

  @source:user-manual#sec-3-2 @technique:bva @risk:P0
  Scenario: Reject signup when age is below the minimum
    Given an applicant whose age is 17
    When they submit the sign-up form
    Then the sign-up is rejected with "you must be at least 18"
```

- **`@source:<doc-basename-without-ext>#<id>`** — the RTM link. `<id>` **must**
  resolve to a `manifest.sections[].id` (e.g. `user-manual#sec-3-2`). An
  `@source` that isn't in the manifest is **confabulation** and the review-agent
  rejects the scenario. This is the traceability backbone — no scenario without
  it.
  `<id>`s come from the **manifest**, not a fixed `sec-N-N` form — they are
  **heading slugs** for Markdown (e.g. `#minimum-age`) and `row-`/`page-`/`slide-N`
  for tabular/visual formats; always use the real id from the manifest.
- **`@technique:<one-of>`** — `{ep, bva, decision-table, state-transition,
  pairwise, error-path}` (lowercase, exactly). Which design technique produced
  the case. (See `test-design-techniques.md`.)
- **`@risk:<P0|P1|P2>`** — risk rank. `P0` = user-facing failure / data-loss /
  security; `P1` = degraded-not-broken; `P2` = cosmetic / rare.

A `Scenario Outline`'s tag line covers all its `Examples` rows.

---

## The vacuous-`Then` trap (the review-agent and `validate_cases.py` both flag it)

Every `Then` must assert an **observable outcome** — a returned value, a changed
state, a specific error message, a created/deleted record, a side effect. A
`Then` that asserts nothing checkable is **vacuous** and gets rejected.

| Vacuous `Then` (rejected) | Non-vacuous `Then` (good) |
|---|---|
| `Then it works` | `Then the order total is 150.00` |
| `Then the page is correct` | `Then the dashboard shows the user's name` |
| `Then nothing breaks` | `Then the request is rejected with "403 forbidden"` |
| `Then the user is happy` | `Then a confirmation email is sent to the customer` |
| `Then the result is returned` | `Then the response lists exactly the 3 matching orders` |

If you can't write a concrete, observable `Then`, the scenario isn't a test yet —
either the requirement is underspecified (surface it as a gap) or the behaviour
isn't testable as written.

---

## Quick checklist (run over every scenario)

- [ ] **Declarative** — behaviour and outcome, no selectors/URLs/clicks/sleeps.
- [ ] **One behaviour** — a single `When`→`Then` intent; split if it grew a
      second one.
- [ ] **Data-driven → `Scenario Outline`** — no copy-pasted near-duplicates.
- [ ] **Shared, neutral setup → `Background`** — nothing a scenario asserts on.
- [ ] **Meaningful name** — states the behaviour and its expected result.
- [ ] **No incidental detail** — every clause is relevant to the behaviour.
- [ ] **Tagged** — `@source` (resolves in manifest) + `@technique` (one of six)
      + `@risk` (`P0|P1|P2`), all three, on the line above the scenario.
- [ ] **Non-vacuous `Then`** — asserts a concrete, observable outcome.

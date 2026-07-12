# Test-design techniques — the DRAFT agent's checklist

You are the **DRAFT** agent. Your job is to turn a scoped slice of a source
document (`normalized.md`, one feature at a time) into a **traceable, risk-ranked
Gherkin catalog** — not "some tests you thought of." This file is the method.

## The method (apply it literally, feature by feature)

This is the industry-validated **"techniques-then-cases"** approach
(ISO/IEC/IEEE 29119-4 + ISTQB black-box techniques), not ad-hoc brainstorming.
The whole point of a checklist is that it makes coverage *systematic and
defensible* — a reviewer can ask "which technique produced this case?" and
"which requirement statement is it derived from?" and always get an answer.

For **each requirement statement** in the scoped section:

1. **Read the statement** and pull out its testable nouns and verbs — the
   *inputs* (parameters, fields, preconditions), the *rules* (ranges,
   conditions, allowed combinations), the *outputs* (results, side effects,
   errors), and any *sequence* (must-happen-before, state).
2. **Pick the applicable techniques** from the table below — usually 2–4 per
   statement. A statement with a numeric range pulls in BVA + EP; one with
   several flags pulls in decision-table or pairwise; one with a lifecycle
   pulls in state-transition; *every* statement pulls in at least one
   error/negative case.
3. **Generate the cases per technique** using each technique's derivation
   recipe. Do not merge techniques into one mega-scenario — keep **one
   behaviour per scenario** (see `gherkin-style.md`).
4. **Tag every scenario** with Contract 2's three tags (`@source` /
   `@technique` / `@risk`) so each case is traceable to its origin statement,
   its design technique, and its risk rank.
5. **Risk-rank and prune.** Rank P0/P1/P2; cut near-duplicates; let pairwise
   (not the full cartesian) bound combinatorial blow-up. Over-generation is the
   failure mode — a focused catalog beats an exhaustive one.

### Technique → when-to-reach-for-it

| Technique | `@technique:` | Reach for it when the statement has… |
|---|---|---|
| Equivalence Partitioning | `ep` | inputs that fall into classes treated the same (valid/invalid groups) |
| Boundary Value Analysis | `bva` | any ordered range or threshold (`age ≥ 18`, `≤ 280 chars`, `> 0`) |
| Decision Tables | `decision-table` | an outcome that depends on a *combination* of conditions / business rules |
| State-Transition | `state-transition` | sequence-dependent behaviour, a lifecycle, modes, or "must X before Y" |
| Pairwise / combinatorial | `pairwise` | **many** independent inputs whose full cross-product is too large to enumerate |
| Error / negative paths | `error-path` | (always) invalid input, auth failure, timeout, empty, duplicate, concurrency |
| Risk-based ranking | *(not a `@technique` value — it sets `@risk`)* | every scenario; decides P0/P1/P2 and what to prune |

**`@technique:` vocabulary (Contract 2 — use exactly these, lowercase):**
`{ep, bva, decision-table, state-transition, pairwise, error-path}`.
Risk-based ranking is **not** a `@technique` value — it is expressed through the
`@risk:` tag (`P0|P1|P2`) that every scenario already carries.

**Tag recap (Contract 2 — every scenario carries all three):**

```
@source:<doc-basename-without-ext>#<id> @technique:<one-of-the-six> @risk:P0|P1|P2
Scenario: <behaviour, not UI clicks>
```

- `@source` — the RTM link; `<id>` **must** resolve to a `manifest.sections[].id`
  (an `@source` that isn't in the manifest is confabulation and the review-agent
  will reject it).
- `@risk` — `P0` = user-facing failure / data-loss / security; `P1` = important
  but degraded-not-broken; `P2` = cosmetic / rare / low-impact.

---

## 1. Equivalence Partitioning (`ep`)

**When it applies.** The input space divides into classes the system is
specified to treat identically. Test **one representative per class**, not many
points inside the same class — extra points in one class add cost, not coverage.

**How to derive cases.**
1. List the input(s) named in the statement.
2. Partition each into classes: the valid class(es) **and** each distinct
   invalid class (too-low, too-high, wrong-type, empty, malformed are
   *different* classes — they often fail differently).
3. One scenario per class, using a representative value from the *middle* of the
   class (boundaries belong to BVA, §2). Pair `ep` with `error-path` for the
   invalid classes.

**Worked example.** Requirement (`#sec-3-2`): *"The discount field accepts a
whole-number percentage from 0 to 100."* Classes: valid `{0..100}`, invalid-low
`{<0}`, invalid-high `{>100}`, invalid-type `{non-integer}`.

```gherkin
@source:user-manual#sec-3-2 @technique:ep @risk:P1
Scenario: Accept a discount inside the valid percentage range
  Given an order with a subtotal of 200.00
  When a discount of 25 percent is applied
  Then the order total is 150.00

@source:user-manual#sec-3-2 @technique:ep @risk:P1
Scenario: Reject a discount above the valid percentage range
  Given an order with a subtotal of 200.00
  When a discount of 150 percent is applied
  Then the discount is rejected with "discount must be between 0 and 100"
  And the order total is unchanged at 200.00

@source:user-manual#sec-3-2 @technique:ep @risk:P2
Scenario: Reject a non-integer discount value
  Given an order with a subtotal of 200.00
  When a discount of "ten" percent is applied
  Then the discount is rejected with "discount must be a whole number"
```

---

## 2. Boundary Value Analysis (`bva`)

**When it applies.** Any ordered range or threshold. Defects cluster at edges
("off-by-one", `<` vs `<=`), so this is the highest-yield numeric technique —
prefer it over EP whenever a boundary is stated.

**How to derive cases.** For each boundary value *B*, test the **three-point**
set: `B-1` (just outside), `B` (on), `B+1` (just inside) — plus the *other* end
of the range. For `age ≥ 18`: test `17` (reject), `18` (accept), `19` (accept);
for a closed range `1..280` test `0, 1, 280, 281`.

**Worked example.** Requirement (`#sec-3-2`): *"Sign-up requires the applicant
to be at least 18 years old."* The boundary is `18` (`>= 18` accepts).

```gherkin
@source:user-manual#sec-3-2 @technique:bva @risk:P0
Scenario: Reject signup when age is just below the minimum
  Given an applicant whose age is 17
  When they submit the sign-up form
  Then the sign-up is rejected with "you must be at least 18"

@source:user-manual#sec-3-2 @technique:bva @risk:P0
Scenario: Accept signup at exactly the minimum age
  Given an applicant whose age is 18
  When they submit the sign-up form
  Then the account is created

@source:user-manual#sec-3-2 @technique:bva @risk:P1
Scenario: Accept signup just above the minimum age
  Given an applicant whose age is 19
  When they submit the sign-up form
  Then the account is created
```

> **Tip — fold boundary triples into a `Scenario Outline`** when the steps are
> identical and only the data and expected verdict change (see `gherkin-style.md`
> §"data-driven"). Each `Examples` row is one boundary point:
>
> ```gherkin
> @source:user-manual#sec-3-2 @technique:bva @risk:P0
> Scenario Outline: Enforce the minimum sign-up age at the boundary
>   Given an applicant whose age is <age>
>   When they submit the sign-up form
>   Then the sign-up is <verdict>
>   Examples:
>     | age | verdict                              |
>     | 17  | rejected with "you must be at least 18" |
>     | 18  | accepted and the account is created  |
>     | 19  | accepted and the account is created  |
> ```

---

## 3. Decision Tables (`decision-table`)

**When it applies.** An outcome depends on a **combination** of conditions —
business rules, eligibility logic, pricing tiers, permission matrices. Prose
hides missing/contradictory rules; a table makes every rule explicit.

**How to derive cases.**
1. List the boolean (or small-enum) **conditions** and the resulting
   **actions/outcomes**.
2. Build the rule table — one column per condition-combination that yields a
   distinct outcome. Collapse "don't-care" inputs (`—`) to avoid enumerating
   irrelevant combinations.
3. One scenario per rule column (a `Scenario Outline` with the table as
   `Examples` is the natural rendering).

**Worked example.** Requirement (`#sec-4-1`): *"Free shipping applies when the
order is over 50.00 **or** the customer is a member; members always get free
shipping; otherwise shipping is 5.00."*

| Rule | order > 50 | member | → shipping |
|---|---|---|---|
| R1 | T | — | 0.00 |
| R2 | F | T | 0.00 |
| R3 | F | F | 5.00 |

```gherkin
@source:user-manual#sec-4-1 @technique:decision-table @risk:P1
Scenario Outline: Apply the shipping rules
  Given a customer who is <member_state>
  And an order subtotal of <subtotal>
  When shipping is calculated
  Then the shipping charge is <shipping>
  Examples:
    | member_state  | subtotal | shipping | # rule |
    | not a member  | 60.00    | 0.00     | R1     |
    | a member      | 40.00    | 0.00     | R2     |
    | not a member  | 40.00    | 5.00     | R3     |
```

> Keep the rule id in a trailing `# comment` column so a reviewer can map each
> `Examples` row back to the table. If the prose leaves a combination undefined
> (e.g. nothing said about exactly 50.00), that gap is itself a finding —
> surface it (and reach for BVA on the `> 50` boundary).

---

## 4. State-Transition (`state-transition`)

**When it applies.** Behaviour depends on **history / current state**: order
lifecycles (`cart → placed → shipped → delivered`), session auth
(`anonymous → logged-in → locked`), document workflows (`draft → review →
published`), toggles/modes. Test both **valid** transitions and **invalid /
illegal** ones (the action that should be refused in a given state).

**How to derive cases.**
1. Draw the state model: states, events, allowed transitions, guards.
2. **Valid** scenarios: cover every allowed transition (and key paths through
   the model — at least each transition once).
3. **Invalid** scenarios: for representative states, fire an event that is
   *not* allowed and assert it is refused (state unchanged). These overlap with
   `error-path` — tag the dominant intent (`state-transition` when the point is
   "wrong state", `error-path` when the point is "bad input").

**Worked example.** Requirement (`#sec-5-3`): *"An order can be cancelled only
while it is Placed; once Shipped it can no longer be cancelled."*

```gherkin
@source:user-manual#sec-5-3 @technique:state-transition @risk:P0
Scenario: Cancel an order that is still in the Placed state
  Given an order in the "Placed" state
  When the customer cancels the order
  Then the order moves to the "Cancelled" state
  And the customer is refunded in full

@source:user-manual#sec-5-3 @technique:state-transition @risk:P0
Scenario: Refuse to cancel an order that has already shipped
  Given an order in the "Shipped" state
  When the customer attempts to cancel the order
  Then the cancellation is refused with "shipped orders cannot be cancelled"
  And the order remains in the "Shipped" state
```

---

## 5. Pairwise / combinatorial (`pairwise`)

**When it applies.** **Many independent inputs**, each with several values, so
the full cartesian product is impractical (3 inputs × 3 values = 27; 5 × 4 =
1024). Empirically most defects are triggered by a **single value or a pair of
values**, so covering **all pairs** finds nearly all combinatorial defects at a
fraction of the cost. Reach for it when EP/BVA per-field isn't enough because the
*interaction* between fields matters.

**How to derive cases — make the pairwise reduction explicit.**
1. List each input (factor) and its values (levels) — usually the EP classes.
2. Generate a set of test combinations such that **every pair of values from
   every two factors appears together in at least one combination** (PICT /
   orthogonal-array style). You do **not** enumerate the full cross-product.
3. State the reduction in a comment so the saving is auditable, e.g.
   `# pairwise: 9 rows cover all 27 (3×3×3) input pairs`.
4. Render as a `Scenario Outline`; each `Examples` row is one pairwise
   combination. Keep an explicit P0 row for the highest-risk combination even if
   pairwise already covers it.

**Worked example.** Requirement (`#sec-6-2`): *"Checkout supports payment_method
∈ {card, wallet, cod}, region ∈ {EU, US, APAC}, and delivery ∈ {standard,
express}."* Full cross-product = 3×3×2 = 18. The **floor** for a pairwise set is the
largest factor-pair product — here `payment×region` = 3×3 = **9** — so you cannot go
below 9 rows. A **9-row** set covers all **21** pairs (9 `payment×region` + 6
`payment×delivery` + 6 `region×delivery`), still half of the 18-row cross-product
and *honestly* complete:

```gherkin
@source:user-manual#sec-6-2 @technique:pairwise @risk:P1
Scenario Outline: Checkout succeeds across payment / region / delivery combinations
  # pairwise: 9 rows cover all 21 pairs of the 18 (3×3×2) full cross-product
  Given a cart ready for checkout
  When the customer checks out paying by <payment> in region <region> with <delivery> delivery
  Then the order is accepted
  Examples:
    | payment | region | delivery |
    | card    | EU     | standard |
    | card    | US     | express  |
    | card    | APAC   | standard |
    | wallet  | EU     | express  |
    | wallet  | US     | standard |
    | wallet  | APAC   | express  |
    | cod     | EU     | standard |
    | cod     | US     | express  |
    | cod     | APAC   | express  |
```

> Pairwise covers **interaction** breadth. It does **not** replace per-field BVA
> or the explicit error cases — keep those as separate scenarios. If a specific
> *triple* is known-risky (e.g. `cod + APAC + express`), pin it as its own P0
> scenario rather than trusting pairwise to land it.

---

## 6. Error / negative paths (`error-path`)

**When it applies.** **Always — at least one per feature.** Specs describe the
happy path; defects and incidents live in the unhappy paths. A catalog with no
`error-path` scenarios is incomplete by construction.

**How to derive cases.** Walk this prompt list for the feature and keep the ones
that apply:
- **Invalid / malformed input** (wrong type, out of range, garbage) — usually
  already covered via EP/BVA invalid classes; ensure the *error behaviour* is
  asserted, not just rejection.
- **Missing required input** (empty field, absent parameter).
- **Auth / authorization failure** (not logged in, wrong role, expired token).
- **Not-found / stale reference** (deleted resource, bad id).
- **Timeout / downstream failure** (dependency slow or down → graceful
  degradation, not a crash).
- **Duplicate / idempotency** (submit twice; replays).
- **Concurrency** (two actors mutate the same resource at once).
- **Empty / boundary collections** (zero results, single result, max page).

**Worked example.** Requirement (`#sec-3-4`): *"Only the account owner may delete
their account; a deletion request must re-confirm the password."*

```gherkin
@source:user-manual#sec-3-4 @technique:error-path @risk:P0
Scenario: Reject account deletion when the password re-confirmation is wrong
  Given a signed-in account owner
  When they request deletion and confirm with an incorrect password
  Then the account is not deleted
  And the response is "password confirmation failed"

@source:user-manual#sec-3-4 @technique:error-path @risk:P0
Scenario: Reject account deletion by a non-owner
  Given user "alice" is signed in
  When alice attempts to delete the account belonging to "bob"
  Then the request is refused with "403 forbidden"
  And bob's account still exists
```

---

## 7. Risk-based ranking (sets `@risk`, prunes the catalog)

**When it applies.** Every scenario — it is not a generator, it is the **filter
and prioritizer** applied across the whole catalog. Risk ranking is what keeps a
checklist-driven catalog from exploding: it tells you which cases must exist
(P0), which are nice-to-have (P2), and which near-duplicates to cut.

**How to assign `@risk`.**
- **P0** — user-facing failure, **data loss**, **security / auth**, money /
  billing correctness, or anything that silently corrupts state. If it's wrong,
  a user is harmed or trust is lost. (Auth, payments, deletion, the boundary on
  a money/age/limit rule → P0.)
- **P1** — important behaviour that degrades rather than breaks: a feature
  returns a worse-but-safe result, a non-critical validation, a common-but-
  recoverable error.
- **P2** — cosmetic, rare, or low-impact: edge formatting, an unlikely input
  class, a redundant-but-cheap confirmation.

**How it prunes.** After drafting per technique:
1. **Cut near-duplicates** — two scenarios exercising the same behaviour with
   different incidental data → keep one (or fold into a `Scenario Outline`).
2. **Cap the long tail** — if a technique generated many P2s in one class, keep
   one representative.
3. **Guarantee the P0s** — never drop a P0 to hit a count cap; drop P2s first.
   (Fan-out caps ~15 scenarios per feature-issue; if you exceed it, shed P2s and
   log the split — see the SKILL.)

There is **no** `@technique:risk` value — risk ranking shows up only as the
`@risk:` tag on scenarios produced by the other six techniques.

---

## Self-check before handing off to the review-agent

- [ ] Every requirement statement in scope produced **≥1 scenario** (else it's a
      coverage gap — list it, don't hide it).
- [ ] Every scenario has all three tags: `@source` (id resolves in the
      manifest), `@technique` (one of the six), `@risk` (`P0|P1|P2`).
- [ ] Every feature has **≥1 `error-path`** scenario.
- [ ] Numeric ranges/thresholds got **BVA three-point** coverage.
- [ ] Multi-condition rules got a **decision table**; many-input features got a
      **pairwise** reduction (with the reduction noted in a comment) — **not** a
      full cartesian dump.
- [ ] Lifecycles got **valid + invalid** state transitions.
- [ ] No vacuous `Then` (every `Then` asserts an **observable** outcome — a
      value, a state, an error message; not "it works"). See `gherkin-style.md`.
- [ ] Near-duplicates pruned; P0s preserved; catalog risk-ranked.

# Claude Code guidance

<!-- BEGIN SDC -->
## SDC — autonomous agent integration

This repo is managed by [SDC (Software Development Centre)](https://gitlab2.aware.co.th/arai/sdc).
An autonomous Claude Code agent picks up issues labelled `agent-ready`, implements them, and opens
merge requests.

### Raising work for the agent

Use the **`/create-issue`** skill (zero-install — it's in `.claude/skills/create-issue/`):

```
/create-issue
```

Or create an issue manually using the **`sdc-agent-task`** template in GitLab's issue UI
(`.gitlab/issue_templates/sdc-agent-task.md`), fill in Design + Acceptance Criteria + Test Cases,
then apply the `agent-ready` label.

To derive acceptance test cases from a **user manual or test plan** and fan them into `type::test`
agent-ready issues, use **`/create-test-cases`** (`.claude/skills/create-test-cases/`). To file
test-script implementation work directly, use **`/create-test-scripts`** — `/create-issue`
specialized for `type::test`.

**Three required sections** — the agent won't start without them:
- `## Design` (or uncommented `design-mode: agent-designs`)
- `## Acceptance Criteria` (≥ 1 checkable item)
- `## Test Cases` (≥ 1 Given / When / Then)

### Implementing an issue — keep `graphify-out/` out of your MR

If this repo has a `graphify-out/` knowledge graph, treat it as **generated output**:
do **not** run `graphify update` / `graphify extract` or commit `graphify-out/` as part
of a feature, bug, refactor, or chore MR. A regenerated `graph.json` churns thousands of
lines and must never ride a code change. Knowledge-graph refreshes are landed **separately**
as graph-only `type::graph` MRs (SDC files them automatically). If `git status` shows
`graphify-out/` changes, discard them before committing.

Full guidance: [SDC Developer Manual](https://gitlab2.aware.co.th/arai/sdc/-/blob/master/docs/developer-manual.md)
<!-- END SDC -->

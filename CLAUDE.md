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

**Three required sections** — the agent won't start without them:
- `## Design` (or uncommented `design-mode: agent-designs`)
- `## Acceptance Criteria` (≥ 1 checkable item)
- `## Test Cases` (≥ 1 Given / When / Then)

Full guidance: [SDC Developer Manual](https://gitlab2.aware.co.th/arai/sdc/-/blob/master/docs/developer-manual.md)
<!-- END SDC -->

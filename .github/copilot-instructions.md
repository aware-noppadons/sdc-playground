# GitHub Copilot instructions

<!-- BEGIN SDC -->
## SDC — autonomous agent integration (Copilot users)

This repo is managed by [SDC (Software Development Centre)](https://gitlab2.aware.co.th/arai/sdc).
An autonomous Claude Code agent picks up issues labelled `agent-ready`, implements them, and opens
merge requests / pull requests.

### Raising work for the agent

Use the **`/create-issue`** prompt in GitHub Copilot Chat — invoke it as `/create-issue` (the prompt
file is at `.github/prompts/create-issue.prompt.md`, auto-loaded by VS Code Copilot Chat).

Or create an issue manually using the **`sdc-agent-task`** template in your forge's issue UI
(`.gitlab/issue_templates/sdc-agent-task.md` for GitLab; `.github/ISSUE_TEMPLATE/sdc-agent-task.md`
for GitHub), fill in Design + Acceptance Criteria + Test Cases, then apply the `agent-ready` label.

Agent identities are VM-qualified: `sdc-<designation>-agent-<NN>` (e.g. `sdc-01-agent-08`).

**Three required sections** — the agent won't start without them:
- `## Design` (or uncommented `design-mode: agent-designs`)
- `## Acceptance Criteria` (≥ 1 checkable item)
- `## Test Cases` (≥ 1 Given / When / Then)

Full guidance: [SDC Developer Manual](https://gitlab2.aware.co.th/arai/sdc/-/blob/master/docs/developer-manual.md)
<!-- END SDC -->

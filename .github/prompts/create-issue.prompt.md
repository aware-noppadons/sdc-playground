---
description: Create an SDC agent-ready issue for this repository. Guides you through exploring the repo, drafting against the sdc-agent-task template, and filing the issue with the agent-ready label.
---

# /create-issue — SDC agent-task prompt

Use this prompt to turn a task description into a well-formed SDC **agent-task** issue and file it
with the `agent-ready` label, so an autonomous SDC agent picks it up.

Run **inside the target project's workspace** — the prompt guides you to read the relevant code first
so the issue is concrete, not generic.

## Step 1 — Explore the repo

Before drafting, read the relevant files. Ground the issue in real paths, functions, and test
patterns. Check:
- Which files does this change touch?
- What is the existing test layout?
- What conventions does the project follow?

## Step 2 — Draft the issue body

Use the **`sdc-agent-task`** template as your structure:
- **GitLab:** `.gitlab/issue_templates/sdc-agent-task.md`
- **GitHub:** `.github/ISSUE_TEMPLATE/sdc-agent-task.md`

The agent's prerequisite gate will **reject** issues missing any of these three sections:

### Required: `## Design`

Describe the concrete approach — which files to touch, what to change, how it works.
Alternatively, add an **uncommented** `design-mode: agent-designs` line in `## Agent Configuration`
to let the agent design the solution (provide context in Summary + Context regardless).

### Required: `## Acceptance Criteria`

At least one checkable item (`- [ ] …`). Must be specific and verifiable — not a placeholder.
Example: `- [ ] Given X, When Y, Then Z is true.`

### Required: `## Test Cases`

At least one `Given / When / Then` test case. Must describe real observable behaviour.
Example: `- [ ] Given a fresh project is assigned, When onboarding runs, Then the file is present.`

## Step 3 — File the issue with `agent-ready`

**GitLab** (using `glab`):

```bash
glab issue create \
  --title "your issue title" \
  --description "$(cat /tmp/issue-body.md)" \
  --label agent-ready
```

Or use the GitLab issue UI: choose the `sdc-agent-task` template, fill in the three required
sections, and apply the `agent-ready` label before submitting.

**GitHub** (using `gh`):

```bash
gh issue create \
  --title "your issue title" \
  --body-file /tmp/issue-body.md \
  --label agent-ready
```

Or use the GitHub issue UI: choose the `sdc-agent-task` template (the YAML front-matter
pre-applies `agent-ready`), fill in the three required sections, and submit.

## Key conventions

- **Agent identities** are VM-qualified: `sdc-<designation>-agent-<NN>` (e.g. `sdc-01-agent-08`).
- **`design-mode: agent-designs`** must be an *uncommented* line to exempt the Design section.
- **`Depends-on: #N`** in `## Dependencies` tells the agent to merge a blocking branch first.
- **Model:** the agent defaults to `sonnet`; add `model: opus` in `## Agent Configuration` for
  heavy/architectural work, `model: haiku` for trivial mechanical tasks.
- **Type:** set `type::bug | type::feature | type::refactor | type::chore | type::research` label.

Full guidance: [SDC Developer Manual](https://gitlab2.aware.co.th/arai/sdc/-/blob/master/docs/developer-manual.md)

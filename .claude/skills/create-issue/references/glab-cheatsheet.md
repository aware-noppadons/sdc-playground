# glab cheatsheet (used by this skill)

`glab` is the GitLab CLI. The skill runs inside the developer's repo, so glab
resolves the target project from the git remote unless `-R` is given.

| Need | Command |
|------|---------|
| Check auth | `glab auth status` (recommended; skill falls back to browser if not set up) |
| Authenticate | `glab auth login` (interactive — tell the user to run it) or `export GITLAB_TOKEN=<pat>` |
| Current project | resolved from the repo's `origin` remote; override with `-R group/sub/repo` |
| List labels (to pre-check agent-*) | `glab label list -F json -P 100 [-R …]` |
| Create the issue | use `scripts/post_issue.py` (wraps `glab issue create -t -d -l -y`) |
| File via browser (no auth) | `python3 scripts/post_issue.py --method browser …` (opens pre-filled new-issue URL, body on clipboard) |

The seven SDC workflow labels (created on a project when it's assigned to an agent):
`agent-ready` (you apply this), `agent-implementing`, `agent-validating`,
`agent-fixing`, `agent-done`, `agent-blocked`, `agent-needs-input`.

`agent-needs-input` is a runtime label applied by the daemon when an agent parks
mid-run to ask a question. To resume: answer in the issue (comment or edit), then
relabel the issue `agent-ready`. You do not apply it yourself when posting issues.

If `glab label list` shows none of the `agent-*` labels, the project isn't
assigned to an SDC agent yet — `post_issue.py` refuses to apply `agent-ready`
(exit 3). Fix by assigning the project to an agent in the operator console
(which auto-creates the labels), or post a draft with `--no-ready`.

glab auth is no longer a hard prerequisite. If `glab` is missing or not
authenticated, `post_issue.py` (glab path) exits **4** and prints the fix
(`glab auth login` / `export GITLAB_TOKEN=<pat>`); the skill then recommends
setting glab up and retrying, or falls back to `--method browser` (opens the
new-issue page with the title pre-filled and the full body on your clipboard).

#!/usr/bin/env python3
"""Post an SDC agent-task issue to GitLab via `glab`, with a browser fallback.

Wraps `glab issue create` with the right title/body/labels/repo, and — before
posting an `agent-ready` issue — verifies the target project actually has the
`agent-*` labels. Their absence means the project isn't assigned to an SDC agent
yet (labels are provisioned at assign time), so an `agent-ready` issue would
never be picked up. In that case the poster refuses (exit 3) so the skill can
ask the operator to assign the project first, or post without `agent-ready`.

The glab path (`--method glab`, the default) is the power path: it authors the
issue as the glab-authenticated human and sets labels. If glab is missing or not
authenticated it exits 4 (the skill then recommends setting glab up, or files via
the browser). `--method browser` is the no-auth fallback: it opens the GitLab
new-issue page with the title pre-filled and puts the full body (plus `/label`
quick-action lines) on the clipboard for pasting — no token, no URL-length wall.

CLI:
  post_issue.py --title T --body-file FILE [--label L ...]
                [--type {bug,feature,refactor,chore,research,test}] [--repo R]
                [--method {glab,browser}] [--dry-run] [--no-ready]
                [--skip-label-check]

--type stamps a scoped `type::<x>` label alongside the other labels (so it joins
the agent-ready default and, on the browser fallback, the /label paste lines).

Exit codes: 0 ok / 2 usage / 3 project-not-set-up / 4 glab-unavailable.
"""

import argparse
import json
import shutil
import subprocess
import sys
import urllib.parse

AGENT_LABELS = [
    "agent-ready",
    "agent-implementing",
    "agent-validating",
    "agent-fixing",
    "agent-done",
    "agent-blocked",
    "agent-needs-input",
]

# Issue-type vocabulary (board v2 §2c). The skill infers one of these (SKILL.md
# §5) and passes it via --type; we stamp it as a scoped `type::<x>` label so the
# board's type filter can use it. Same vocabulary as the template's ## Type field.
ISSUE_TYPES = ["bug", "feature", "refactor", "chore", "research", "test"]


def build_argv(
    title: str, body: str, labels: list[str], repo: str | None = None
) -> list[str]:
    """Assemble the `glab issue create` argv (one -l per label; -y = non-interactive)."""
    argv = ["glab", "issue", "create", "-t", title, "-d", body, "-y"]
    for label in labels:
        argv += ["-l", label]
    if repo:
        argv += ["-R", repo]
    return argv


def parse_label_names(output: str) -> set[str]:
    """Extract label names from `glab label list -F json` output."""
    return {item["name"] for item in json.loads(output or "[]")}


def _default_run(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout


def glab_status(run=_default_run, path_check=shutil.which) -> bool:
    """True iff `glab` is on PATH *and* `glab auth status` succeeds.

    `path_check(name)` is a callable returning a truthy value when the executable
    is available (default: shutil.which). `run(cmd)` runs a command with
    check=True semantics (default raises CalledProcessError on a non-zero exit).
    Any failure — glab absent, not authenticated, or an unexpected error — is
    reported as not-available (False); this probe never raises.
    """
    if not path_check("glab"):
        return False
    try:
        run(["glab", "auth", "status"])
    except Exception:
        return False
    return True


def labels_present(repo: str | None = None, run=_default_run) -> set[str]:
    """Return the set of label names on the target project (current repo if None)."""
    cmd = ["glab", "label", "list", "-F", "json", "-P", "100"]
    if repo:
        cmd += ["-R", repo]
    return parse_label_names(run(cmd))


def missing_agent_labels(present: set[str]) -> list[str]:
    """Which of the six agent-* labels are absent from `present`."""
    return [label for label in AGENT_LABELS if label not in present]


# --- browser fallback (B') -------------------------------------------------


def new_issue_url(base: str, path: str, title: str) -> str:
    """Build the GitLab new-issue URL with only the title pre-filled.

    Title is encoded with urllib.parse.quote_plus (spaces -> '+', '&' -> '%26'),
    so a long body never has to ride the query string (it goes on the clipboard).
    """
    return (
        f"{base}/{path}/-/issues/new?issue%5Btitle%5D={urllib.parse.quote_plus(title)}"
    )


def paste_body(body: str, labels: list[str]) -> str:
    """Issue body + one `/label ~"<name>"` quick-action line per label.

    GitLab applies the quick actions on creation and strips them from the saved
    description. Built from a copy — the validated body itself is never mutated.
    """
    result = body
    for label in labels:
        result += f'\n/label ~"{label}"'
    return result


def _default_remote_reader() -> str:
    """Return `git remote get-url origin` (raises on failure)."""
    return subprocess.run(
        ["git", "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _parse_remote(url: str) -> tuple[str, str]:
    """Parse a git remote URL into (base, path); strip a trailing .git.

    Handles both https (`https://host/grp/sub/repo.git`) and SSH
    (`git@host:grp/sub/repo.git`) forms.
    """
    url = url.strip()
    if url.endswith(".git"):
        url = url[: -len(".git")]
    if url.startswith(("http://", "https://")):
        parsed = urllib.parse.urlsplit(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        path = parsed.path.lstrip("/")
        return base, path
    # scp-like SSH: git@host:group/sub/repo
    if "@" in url and ":" in url:
        host_part, path = url.split(":", 1)
        host = host_part.split("@", 1)[1]
        return f"https://{host}", path.lstrip("/")
    raise ValueError(f"unrecognized remote URL: {url!r}")


def resolve_repo(repo_arg: str | None, remote_reader=None) -> tuple[str, str]:
    """Resolve (base, path) for the new-issue URL.

    - `repo_arg` given (e.g. "grp/sub/repo"): path comes from the arg; the base
      (GitLab instance) is derived from the git remote, falling back to
      https://gitlab.com when the remote is unavailable.
    - `repo_arg` is None: parse the git remote URL for both base and path.

    `remote_reader` is Callable[[], str] returning the origin URL (injectable for
    tests); defaults to `git remote get-url origin`.
    """
    if remote_reader is None:
        remote_reader = _default_remote_reader
    if repo_arg:
        try:
            base, _ = _parse_remote(remote_reader())
        except Exception:
            base = "https://gitlab.com"
        return base, repo_arg.strip().rstrip("/")
    return _parse_remote(remote_reader())


def copy_to_clipboard(text: str) -> bool:
    """Best-effort copy `text` to the clipboard. Never raises; returns success.

    Tries pbcopy / clip / wl-copy / xclip / xsel (first one found on PATH).
    """
    candidates = [
        ["pbcopy"],
        ["clip"],
        ["wl-copy"],
        ["xclip", "-selection", "clipboard"],
        ["xsel", "--clipboard", "--input"],
    ]
    for cmd in candidates:
        if shutil.which(cmd[0]):
            try:
                subprocess.run(cmd, input=text, text=True, check=True)
                return True
            except Exception:
                return False
    return False


def open_url(url: str) -> bool:
    """Best-effort open `url` in the default browser. Never raises; returns success.

    Tries open / xdg-open / start (first one found on PATH).
    """
    for opener in ("open", "xdg-open", "start"):
        if shutil.which(opener):
            try:
                subprocess.run([opener, url], check=True)
                return True
            except Exception:
                return False
    return False


def _run_browser_fallback(args, body, labels, remote_reader, clipboard, opener) -> int:
    """Emit the B' artifacts (URL + paste body), best-effort copy/open. Exit 0."""
    base, path = resolve_repo(args.repo, remote_reader=remote_reader)
    url = new_issue_url(base, path, args.title)
    pbody = paste_body(body, labels)

    copied = clipboard(pbody) if clipboard is not None else False
    if opener is not None:
        opener(url)  # best effort; ignore result

    print("Issue URL (title pre-filled):")
    print(f"  {url}")
    print()
    if copied:
        print(
            "Body copied to clipboard. Paste into the description field, then submit."
        )
    else:
        print("Clipboard not available. Paste the body manually:")
        print()
        print("```")
        print(pbody)
        print("```")
        print()
        print("Open the URL, paste the body into the description field, then submit.")
    return 0


def main(
    argv: list[str],
    _glab_status_fn=glab_status,
    _run=_default_run,
    _remote_reader=None,
    _clipboard=copy_to_clipboard,
    _opener=open_url,
) -> int:
    ap = argparse.ArgumentParser(description="Post an SDC agent-task issue via glab.")
    ap.add_argument("--title", required=True)
    ap.add_argument("--body-file", required=True)
    ap.add_argument(
        "--label",
        action="append",
        default=None,
        help="repeatable; default: agent-ready",
    )
    ap.add_argument(
        "--type",
        dest="issue_type",
        default=None,
        choices=ISSUE_TYPES,
        help="inferred issue type; stamped as a scoped `type::<x>` label "
        "(joins the other labels; flows into the browser paste-body too)",
    )
    ap.add_argument("--repo", default=None)
    ap.add_argument(
        "--method",
        choices=["glab", "browser"],
        default="glab",
        help="glab (default; authors as you, sets labels) or browser (no-auth fallback)",
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="print the glab argv, do not post"
    )
    ap.add_argument(
        "--no-ready", action="store_true", help="post without the agent-ready label"
    )
    ap.add_argument("--skip-label-check", action="store_true")
    args = ap.parse_args(argv[1:])

    with open(args.body_file, encoding="utf-8") as fh:
        body = fh.read()

    labels = args.label if args.label is not None else ["agent-ready"]
    if args.no_ready:
        labels = [label for label in labels if label != "agent-ready"]

    # Stamp the inferred type as a scoped `type::<x>` label (board v2 §2c). It
    # joins the existing labels (so glab sets it via -l, and the browser fallback's
    # paste-body emits a /label quick-action for it automatically). Idempotent —
    # never added twice if the caller already passed it.
    if args.issue_type:
        type_label = f"type::{args.issue_type}"
        if type_label not in labels:
            labels = [*labels, type_label]

    glab_argv = build_argv(args.title, body, labels, args.repo)

    # --dry-run short-circuits before any availability check or network call.
    if args.dry_run:
        print(json.dumps(glab_argv))
        return 0

    # Browser fallback (B'): no glab / no auth needed.
    if args.method == "browser":
        return _run_browser_fallback(
            args, body, labels, _remote_reader, _clipboard, _opener
        )

    # glab path: pre-detect availability + auth; exit 4 (don't post, don't fall back).
    if not _glab_status_fn():
        print(
            "glab is not installed or not authenticated.\n\n"
            "To install: https://gitlab.com/gitlab-org/cli/-/releases "
            "(or: brew install glab)\n"
            "To authenticate: glab auth login\n"
            "Quick alternative: export GITLAB_TOKEN=<your-personal-access-token>\n\n"
            "Once set up, retry. Or run with --method browser to file via the GitLab web UI.",
            file=sys.stderr,
        )
        return 4

    if "agent-ready" in labels and not args.skip_label_check:
        try:
            present = labels_present(args.repo, run=_run)
        except Exception as e:
            print(
                f"warning: could not list project labels ({e}); skipping pre-check",
                file=sys.stderr,
            )
            present = None
        if present is not None and "agent-ready" not in present:
            missing = missing_agent_labels(present)
            print(
                "refusing to post: target project is missing the agent-* labels "
                f"({', '.join(missing)}). It is likely not assigned to an SDC agent yet "
                "(labels are created at assign time). Assign the project to an agent, or "
                "re-run with --no-ready to post a draft you label later.",
                file=sys.stderr,
            )
            return 3

    try:
        out = _run(glab_argv)
    except subprocess.CalledProcessError as e:
        # glab create failed: surface its streams and exit with its return code.
        if e.stdout:
            sys.stdout.write(e.stdout)
        if e.stderr:
            sys.stderr.write(e.stderr)
        return e.returncode
    if out:
        sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

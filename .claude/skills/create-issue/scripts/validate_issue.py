#!/usr/bin/env python3
"""Prerequisite-gate validator for an SDC agent-task issue body.

This is a faithful, standalone mirror of the daemon's prerequisite check
(daemon/sdc_daemon/prereq_check.py). The skill runs it on a drafted issue body
*before* posting, so an `agent-ready` issue is guaranteed to clear the gate
(rather than being picked up and immediately `agent-blocked`).

Gate rules (must match the daemon exactly):
  - HTML comments are stripped first (so the template's own commented hints and
    example rows never count as content).
  - Required sections: Design, Acceptance Criteria, Test Cases. A section
    "has content" iff the text beneath its `## Heading` is non-empty after the
    comment strip.
  - The literal token `agent-designs` appearing anywhere (uncommented) exempts
    the Design section (the agent will design and comment it).

Additionally performs a syntactic parse of the ``Depends-on:`` field (see
``parse_depends_on`` below). Deps are optional — a malformed or absent
``Depends-on:`` line is never a gate failure; it is reported in the returned
``depends_on`` field so the caller can surface it to the author.

The differential test in ../tests/test_validate_issue.py asserts this agrees
with the daemon's own check on a corpus, so the two can't drift.

CLI:
  validate_issue.py [BODY_FILE]      # or read the body from stdin
Prints a JSON object {"ok": bool, "missing": [...], "depends_on": [...]}
and exits 0 when ok, else 1.
"""

import json
import re
import sys
from dataclasses import dataclass, field

REQUIRED_SECTIONS = ["Design", "Acceptance Criteria", "Test Cases"]

# Pinned grammar — must match daemon/sdc_daemon/dependencies.py exactly.
_DEPENDS_ON_RE = re.compile(r"(?im)^depends-on:\s*(?P<iids>#?\d+(?:\s*,\s*#?\d+)*)\s*$")


@dataclass
class Result:
    ok: bool
    missing: list[str] = field(default_factory=list)
    depends_on: list[int] = field(default_factory=list)


def _sections(body: str) -> dict[str, str]:
    """Map normalised '## Heading' -> the text beneath it, until the next heading."""
    out: dict[str, str] = {}
    current: str | None = None
    buf: list[str] = []
    for line in body.splitlines():
        m = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)
        if m:
            if current is not None:
                out[current] = "\n".join(buf).strip()
            current = m.group(1).strip().lower()
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        out[current] = "\n".join(buf).strip()
    return out


def parse_depends_on(body: str) -> list[int]:
    """Syntactically parse the Depends-on: field from an issue body.

    Returns a deduplicated list of IIDs in declaration order.  Returns []
    when the field is absent, empty, or malformed.  Only the first matching
    line is used (spec says 'One Depends-on: line').

    This is a standalone copy of daemon/sdc_daemon/dependencies.parse_depends_on
    so the skill works offline without importing the daemon package.
    """
    m = _DEPENDS_ON_RE.search(body)
    if m is None:
        return []
    raw = m.group("iids")
    seen: set[int] = set()
    result: list[int] = []
    for token in raw.split(","):
        token = token.strip().lstrip("#")
        if not token.isdigit():
            continue
        iid = int(token)
        if iid not in seen:
            seen.add(iid)
            result.append(iid)
    return result


def check(body: str) -> Result:
    """Validate an issue body against the prerequisite gate."""
    stripped = re.sub(r"<!--.*?-->", "", body or "", flags=re.DOTALL)
    secs = _sections(stripped)
    agent_designs = "agent-designs" in stripped.lower()
    missing: list[str] = []
    for name in REQUIRED_SECTIONS:
        content = secs.get(name.lower(), "")
        if name == "Design" and agent_designs:
            continue  # agent will design; empty Design allowed
        if not content.strip():
            missing.append(name)
    # Syntactic parse of Depends-on: (optional; never a gate failure).
    # HTML comments are already stripped above, so commented Depends-on:
    # lines are correctly ignored (consistent with the daemon's parser which
    # also operates on the raw body and anchors on line-start ^).
    dep_iids = parse_depends_on(stripped)
    return Result(ok=not missing, missing=missing, depends_on=dep_iids)


def main(argv: list[str]) -> int:
    body = pathlib_read(argv[1]) if len(argv) > 1 else sys.stdin.read()
    result = check(body)
    print(
        json.dumps(
            {
                "ok": result.ok,
                "missing": result.missing,
                "depends_on": result.depends_on,
            }
        )
    )
    return 0 if result.ok else 1


def pathlib_read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


if __name__ == "__main__":
    sys.exit(main(sys.argv))

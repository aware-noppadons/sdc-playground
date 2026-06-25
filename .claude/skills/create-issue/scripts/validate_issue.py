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
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REQUIRED_SECTIONS = ["Design", "Acceptance Criteria", "Test Cases"]

# Pinned grammar — must match daemon/sdc_daemon/dependencies.py exactly.
_DEPENDS_ON_RE = re.compile(r"(?im)^depends-on:\s*(?P<iids>#?\d+(?:\s*,\s*#?\d+)*)\s*$")

# Declared-skill advisory (issue #22). Mirrors daemon/sdc_daemon/skills.py so the
# author gets a loud warning for a typo'd/nonexistent skill BEFORE posting — but
# this is never a gate (the daemon is the sole hard gate). Standalone copy so the
# skill works offline without importing the daemon package.
_SKILLS_LINE_RE = re.compile(r"^\s*skills:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
_PROJECT_SKILL_RE = re.compile(r"^\.claude/skills/([^/]+)/SKILL\.md$")

# Agent-type advisory (issue #37). Mirrors daemon/sdc_daemon/agent_types.py so the
# author gets a loud warning for a typo'd/nonexistent agent-type BEFORE posting.
# Never a gate (the daemon is the sole hard gate). Standalone copy so the skill
# works offline without importing the daemon package.
_AGENT_TYPE_LINE_RE = re.compile(
    r"^\s*agent-type:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE
)
# Keep in sync with sdc_daemon.agent_types._BUILTIN_AGENT_TYPES (a maintained
# allowlist of Claude Code built-ins; update on Claude Code upgrades).
_BUILTIN_AGENT_TYPES = frozenset({
    "general-purpose", "Explore", "Plan", "statusline-setup", "claude-code-guide",
})

# Phased-plan advisory (issue #42). Warn-only, never blocks; conservative match.
# Detects the pps-web#299 shape: enumerated Phase N lines and/or imperative
# sub-agent delegation verbs (``use `X` to …``, ``run `Y` to …``,
# ``delegate to `Z```).  Suppressed when a validated agent-type: or skills:
# directive is already declared (those are the supported, validated paths).
_PHASE_NUM_RE = re.compile(r"(?i)\bphase\s+(\d+)\b")
_DELEGATION_RE = re.compile(
    r"(?i)(?:use\s+`[^`]+`\s+to\b|run\s+`[^`]+`\s+to\b|delegate\s+to\s+`[^`]+`)"
)

# First-class per-phase config (issue #40). A ## Phases section with ≥1
# ### Phase sub-block is the SUPPORTED, daemon-parsed format; its per-phase
# skills:/agent-type: are validated (advisory) just like the issue-level ones.
# Mirrors daemon/sdc_daemon/worker.parse_phases. Standalone copy (offline skill).
_PHASE_HEADING_RE = re.compile(r"^\s{0,3}#{3,6}\s+(.+?)\s*$", re.MULTILINE)


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


def parse_declared_skills(body: str) -> list[str]:
    """Parse the optional ``skills:`` declaration from ## Agent Configuration.

    Standalone mirror of daemon/sdc_daemon/skills.parse_declared_skills: strip
    HTML comments, take the Agent Configuration section, match a ``skills:`` line,
    split on commas, strip surrounding backticks/whitespace, drop empties."""
    stripped = re.sub(r"<!--.*?-->", "", body or "", flags=re.DOTALL)
    agent_cfg = _sections(stripped).get("agent configuration", "")
    m = _SKILLS_LINE_RE.search(agent_cfg)
    if not m:
        return []
    out: list[str] = []
    for token in m.group(1).split(","):
        name = token.strip().strip("`").strip()
        if name:
            out.append(name)
    return out


def enumerate_project_skills(repo_root: str) -> set[str]:
    """Project-skill names from ``<repo_root>/.claude/skills/`` (dirs with a
    SKILL.md). Missing dir → empty set; never raises."""
    base = Path(repo_root) / ".claude" / "skills"
    names: set[str] = set()
    try:
        children = list(base.iterdir())
    except OSError:
        return names
    for child in children:
        if (child / "SKILL.md").is_file():
            names.add(child.name)
    return names


def enumerate_plugin_skills(agent_home: str) -> set[str]:
    """Plugin-skill ids (``<plugin>:<skill>``) from the author's plugin cache at
    ``<agent_home>/.claude/plugins/cache/<marketplace>/<plugin>/<version>/skills/
    <skill>/SKILL.md``. Missing/unreadable → empty set; never raises."""
    ids: set[str] = set()
    cache = Path(agent_home) / ".claude" / "plugins" / "cache"
    try:
        marketplaces = list(cache.iterdir())
    except OSError:
        return ids
    for marketplace in marketplaces:
        for plugin in _safe_iterdir(marketplace):
            for version in _safe_iterdir(plugin):
                for skill in _safe_iterdir(version / "skills"):
                    if (skill / "SKILL.md").is_file():
                        ids.add(f"{plugin.name}:{skill.name}")
    return ids


def _safe_iterdir(path: Path) -> list[Path]:
    try:
        return list(path.iterdir())
    except OSError:
        return []


def _phases_region(body: str) -> str:
    """Text of the ## Phases section — from the level-2 'Phases' heading up to the
    next level-1/2 heading (so the ### Phase sub-blocks are included), or '' when
    absent. HTML comments stripped first. Mirrors the region daemon parse_phases
    reads (the daemon's ## splitter keeps the whole block; here _sections splits
    on every level, so the region is collected explicitly)."""
    stripped = re.sub(r"<!--.*?-->", "", body or "", flags=re.DOTALL)
    region: list[str] = []
    inside = False
    for line in stripped.splitlines():
        m = re.match(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$", line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip().lower()
            if inside and level <= 2:
                break  # next level-1/2 section ends the Phases region
            if level <= 2 and title == "phases":
                inside = True
                continue
        if inside:
            region.append(line)
    return "\n".join(region)


def has_structured_phases(body: str) -> bool:
    """True iff the body has a ## Phases section with ≥1 ### Phase sub-block — the
    first-class, daemon-parsed format (mirrors ``parse_phases(body) != []``)."""
    return bool(_PHASE_HEADING_RE.search(_phases_region(body)))


def parse_phase_skills(body: str) -> list[str]:
    """All distinct ``skills:`` declared across the ## Phases sub-blocks (#40)."""
    out: list[str] = []
    for m in _SKILLS_LINE_RE.finditer(_phases_region(body)):
        for token in m.group(1).split(","):
            name = token.strip().strip("`").strip()
            if name and name not in out:
                out.append(name)
    return out


def parse_phase_agent_types(body: str) -> list[str]:
    """All distinct ``agent-type:`` declared across the ## Phases sub-blocks (#40)."""
    out: list[str] = []
    for m in _AGENT_TYPE_LINE_RE.finditer(_phases_region(body)):
        name = m.group(1).strip().strip("`").strip()
        if name and name not in out:
            out.append(name)
    return out


def unknown_skills(body: str, repo_root: str, agent_home: str) -> list[str]:
    """Declared skills not found locally, in declaration order (advisory only).

    A bare name is checked against the repo's ``.claude/skills/``; a ``x:y`` ref
    against the local plugin cache. Mirrors the daemon's transient-safety: when
    NO plugins are installed in the author env the plugin check is skipped (so a
    valid plugin ref is not falsely flagged) — the daemon is the hard gate.
    Includes per-phase ``skills:`` (issue #40) so a bad phase skill warns too."""
    declared = parse_declared_skills(body)
    for name in parse_phase_skills(body):  # union with per-phase skills (#40)
        if name not in declared:
            declared.append(name)
    if not declared:
        return []
    project_names = enumerate_project_skills(repo_root)
    plugin_ids = enumerate_plugin_skills(agent_home)
    unknown: list[str] = []
    for name in declared:
        if ":" in name:
            if plugin_ids and name not in plugin_ids:
                unknown.append(name)
        else:
            if name not in project_names:
                unknown.append(name)
    return unknown


def parse_agent_type(body: str):
    """Parse the optional ``agent-type:`` directive from ## Agent Configuration.

    Standalone mirror of daemon/sdc_daemon/agent_types.resolve_agent_type: strip
    HTML comments, take the Agent Configuration section, match an ``agent-type:``
    line, trim surrounding backticks/whitespace. Absent/blank/commented → None."""
    stripped = re.sub(r"<!--.*?-->", "", body or "", flags=re.DOTALL)
    agent_cfg = _sections(stripped).get("agent configuration", "")
    m = _AGENT_TYPE_LINE_RE.search(agent_cfg)
    if m:
        value = m.group(1).strip().strip("`").strip()
        if value:
            return value
    return None


def enumerate_project_agents(repo_root: str) -> set[str]:
    """Flat ``.claude/agents/<name>.md`` names in the repo (missing → empty)."""
    base = Path(repo_root) / ".claude" / "agents"
    names: set[str] = set()
    for child in _safe_iterdir(base):
        if child.is_file() and child.suffix == ".md":
            names.add(child.stem)
    return names


def enumerate_user_and_plugin_agents(agent_home: str) -> set[str]:
    """User agents (``<home>/.claude/agents/<name>.md``) + plugin agents
    (``.../cache/<mp>/<plugin>/<ver>/agents/<name>.md``, both bare and namespaced)
    from the author's home. Missing/unreadable → empty; never raises."""
    ids: set[str] = set()
    home = Path(agent_home)
    for child in _safe_iterdir(home / ".claude" / "agents"):
        if child.is_file() and child.suffix == ".md":
            ids.add(child.stem)
    cache = home / ".claude" / "plugins" / "cache"
    for marketplace in _safe_iterdir(cache):
        for plugin in _safe_iterdir(marketplace):
            for version in _safe_iterdir(plugin):
                for agent in _safe_iterdir(version / "agents"):
                    if agent.is_file() and agent.suffix == ".md":
                        ids.add(agent.stem)
                        ids.add(f"{plugin.name}:{agent.stem}")
    return ids


def unknown_agent_type(body: str, repo_root: str, agent_home: str):
    """The declared ``agent-type:`` if it resolves to no known sub-agent, else None
    (advisory only). Mirrors the daemon gate's sources: built-in allowlist, project
    agents (repo ``.claude/agents/``), user + plugin agents (the author's home).
    The daemon is the hard gate."""
    name = parse_agent_type(body)
    if name is None:
        return None
    known = (
        _BUILTIN_AGENT_TYPES
        | enumerate_project_agents(repo_root)
        | enumerate_user_and_plugin_agents(agent_home)
    )
    return None if name in known else name


def unknown_phase_agent_types(body: str, repo_root: str, agent_home: str) -> list[str]:
    """Per-phase ``agent-type:`` names (## Phases, issue #40) that resolve to no
    known sub-agent, in declaration order (advisory only — the daemon validates
    the union and is the hard gate)."""
    names = parse_phase_agent_types(body)
    if not names:
        return []
    known = (
        _BUILTIN_AGENT_TYPES
        | enumerate_project_agents(repo_root)
        | enumerate_user_and_plugin_agents(agent_home)
    )
    return [n for n in names if n not in known]


def detect_phased_pattern(body: str) -> bool:
    """Return True if the body looks like a phased / sub-agent-delegation plan
    of the pps-web#299 shape — a plan that may assume daemon-orchestrated
    per-phase model/agent switching, which is not supported.

    Conservative: false-negatives are preferred over false-positives.

    Signals:
    - STRONG (a genuine MULTI-STAGE chain — the pps-web#299/#302 shape): a bare
      ``## Phases`` heading without ``### Phase`` sub-blocks, OR two or more
      distinct ``Phase N`` enumerations (Phase 1, Phase 2 …), OR one ``Phase N``
      enum together with a delegation line.
    - WEAK (delegation verbs only, no phase enumeration): two or more imperative
      delegation lines (``use `X` to …``, ``run `Y` to …``, ``delegate to `Z```).

    Suppression (issue #42 + #40):
    - A first-class ``## Phases`` section (``### Phase`` sub-blocks) → the
      supported, daemon-parsed path → never warn.
    - A single validated ``agent-type:`` / ``skills:`` directive suppresses ONLY
      the WEAK signal: one directive legitimately covers a one-agent multi-step
      task. It does NOT suppress a STRONG multi-stage chain — a single directive
      does not make a multi-stage chain run deterministically; that needs
      ``## Phases`` (this is exactly the pps-web#302 trap, where
      ``agent-type: web-implement`` + a prose Phase 1/2/3 chain previously got no
      nudge). A STRONG signal therefore always warns (steer the author to
      ``## Phases``).
    Ordinary prose containing the word "phase" without enumeration or
    delegation verbs does NOT trigger this function.
    """
    stripped = re.sub(r"<!--.*?-->", "", body or "", flags=re.DOTALL)
    # First-class ## Phases (issue #40) → the supported, daemon-parsed path; the
    # per-phase directives are validated separately. Do not warn.
    if has_structured_phases(stripped):
        return False
    phase_nums = set(_PHASE_NUM_RE.findall(stripped))
    deleg_hits = _DELEGATION_RE.findall(stripped)
    # STRONG: a genuine multi-stage chain. A bare ``## Phases`` heading (no
    # ### sub-blocks — would not be daemon-parsed), ≥2 ``Phase N`` enumerations,
    # or one ``Phase N`` enum plus a delegation line. Warns regardless of a single
    # issue-level agent-type:/skills: (those don't make a chain deterministic).
    bare_phases_heading = bool(re.search(r"(?im)^#{1,6}\s+phases\s*$", stripped))
    if bare_phases_heading or len(phase_nums) >= 2 or (phase_nums and deleg_hits):
        return True
    # WEAK: delegation verbs only (no phase enumeration). A single validated
    # agent-type:/skills: legitimately covers a one-agent multi-step task → suppress.
    if len(deleg_hits) >= 2:
        if parse_agent_type(stripped) is not None or parse_declared_skills(stripped):
            return False
        return True
    return False


def main(argv: list[str]) -> int:
    body = pathlib_read(argv[1]) if len(argv) > 1 else sys.stdin.read()
    result = check(body)
    # Declared-skill advisory (issue #22): loud warning, NEVER a gate failure.
    unknown = unknown_skills(
        body, repo_root=os.getcwd(), agent_home=os.path.expanduser("~")
    )
    if unknown:
        listed = ", ".join(unknown)
        print(
            f"⚠️  WARNING: declared skill(s) not found in this environment: "
            f"{listed}. Check the `skills:` line in ## Agent Configuration — a "
            f"bare name must be a dir in `.claude/skills/`, a `plugin:skill` ref "
            f"must be an installed plugin skill. The daemon HARD-BLOCKS an issue "
            f"whose declared skill is unresolvable, so fix this before posting.",
            file=sys.stderr,
        )
    # Agent-type advisory (issue #37): loud warning, NEVER a gate failure.
    unknown_at = unknown_agent_type(
        body, repo_root=os.getcwd(), agent_home=os.path.expanduser("~")
    )
    if unknown_at:
        print(
            f"⚠️  WARNING: declared agent-type not found in this environment: "
            f"{unknown_at}. Check the `agent-type:` line in ## Agent Configuration "
            f"— it must be a flat `.claude/agents/<name>.md` in the repo, a "
            f"user/plugin agent, or a Claude Code built-in. The daemon HARD-BLOCKS "
            f"an issue whose agent-type is unresolvable, so fix this before posting.",
            file=sys.stderr,
        )
    # Per-phase agent-type advisory (issue #40): warn for any ## Phases sub-block
    # naming an unknown sub-agent. The daemon validates the UNION pre-claim.
    unknown_phase_at = unknown_phase_agent_types(
        body, repo_root=os.getcwd(), agent_home=os.path.expanduser("~")
    )
    if unknown_phase_at:
        listed = ", ".join(unknown_phase_at)
        print(
            f"⚠️  WARNING: per-phase agent-type(s) not found in this environment: "
            f"{listed}. Check the `agent-type:` lines in your ## Phases sub-blocks "
            f"— each must be a flat `.claude/agents/<name>.md` in the repo, a "
            f"user/plugin agent, or a Claude Code built-in. The daemon HARD-BLOCKS "
            f"an issue if ANY phase's agent-type is unresolvable.",
            file=sys.stderr,
        )
    # Phased-plan advisory (issue #42/#40): warn-only, NEVER a gate failure. Only
    # fires for the UNSTRUCTURED prose shape (no first-class ## Phases section).
    phased = detect_phased_pattern(body)
    if phased:
        print(
            "⚠️  WARNING: this issue looks like a phased / sub-agent-delegation "
            "plan written in prose (pps-web#299 shape) WITHOUT a first-class "
            "`## Phases` section. Such prose is unvalidated — the main Claude "
            "agent orchestrates it best-effort and a typo'd prose agent name "
            "silently degrades to manual implementation. For deterministic, "
            "validated per-stage execution (each stage its own committed run, "
            "with its own model/skills/agent-type), convert it to a `## Phases` "
            "section with `### Phase N:` sub-blocks. See developer-manual §2.15.",
            file=sys.stderr,
        )
    print(
        json.dumps(
            {
                "ok": result.ok,
                "missing": result.missing,
                "depends_on": result.depends_on,
                "unknown_skills": unknown,
                "unknown_agent_type": unknown_at,
                "unknown_phase_agent_types": unknown_phase_at,
                "phased_plan_warning": phased,
            }
        )
    )
    return 0 if result.ok else 1


def pathlib_read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


if __name__ == "__main__":
    sys.exit(main(sys.argv))

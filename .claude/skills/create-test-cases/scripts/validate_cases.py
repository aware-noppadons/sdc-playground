#!/usr/bin/env python3
"""Structural gate + RTM check for a generated Gherkin case catalog (Flow B).

This is the validator the `create-test-cases` skill runs on a drafted catalog
*before* it fans out `type::test` issues. It mirrors the create-issue
philosophy (see ../create-issue/scripts/validate_issue.py): a thin **structural
HARD gate** plus loud **ADVISORY warnings** for quality smells. The hard gate
never depends on any external Gherkin library — the parser below is a
lightweight, line/regex-based reader, faithful to the offline, dependency-free
ethos of validate_issue.py.

Contract (plan §"CONTRACT 4" / spec §5):

  validate_cases.py CATALOG.feature --manifest DIR/manifest.json [--min-coverage 0.8]

Prints JSON ``{"ok", "hard_errors":[...], "warnings":[...], "coverage": <float>}``
and exits 0 when ``ok`` else 1.

HARD errors (-> ok=False, exit 1):
  - The file does not parse as Gherkin with >=1 ``Scenario``/``Scenario Outline``.
  - A scenario is missing a ``Given``, a ``When``, or a ``Then`` (an ``And``/``But``
    inherits the keyword of the preceding step).
  - A ``Scenario Outline`` has no ``Examples:`` table.

ADVISORY warnings (warn, ok stays True, exit 0):
  - A scenario has no ``@source`` tag.
  - An ``@source`` id is NOT present in the manifest (suspected confabulation).
  - RTM coverage = |manifest ids referenced by >=1 @source| / |manifest ids|
    is below ``--min-coverage``.
  - A scenario whose entire ``Then`` block (the ``Then`` plus any ``And``/``But``
    under it) has no assertion-like verb in ANY clause (suspected vacuous —
    per-scenario heuristic below, configurable via ``ASSERTION_VERBS``). At most
    one warning per scenario.
  - A scenario whose ``@source`` maps to a ``confidence: low`` manifest section.

Reuse, don't reimplement: the issue-body prerequisite gate is imported from
``../create-issue/scripts/validate_issue.py`` (single source of truth). The
``@source`` tag dialect is CONTRACT 2; the manifest shape is CONTRACT 1.
"""

import argparse
import importlib.util
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------- #
# Gherkin grammar (lightweight, line/regex-based — NO external dependency).
# --------------------------------------------------------------------------- #

# A tag line is one or more whitespace-separated @tags (e.g.
# "@source:user-manual#sec-1 @technique:bva @risk:P0"). Tags may only contain
# tag-safe characters; a line that is *only* tags (after strip) is a tag line.
_TAG_TOKEN_RE = re.compile(r"@[^\s@]+")
_TAG_LINE_RE = re.compile(r"^\s*@[^\s].*$")

# Step keywords. And/But inherit the keyword of the preceding step.
_STEP_RE = re.compile(r"^\s*(Given|When|Then|And|But)\b\s*(?P<text>.*)$")

# Scenario / Scenario Outline / Examples / Feature / Background headers.
_SCENARIO_RE = re.compile(r"^\s*Scenario(?P<outline>\s+Outline)?\s*:\s*(?P<name>.*)$")
# `Scenarios:` is the Cucumber/Gherkin-6 alias for `Examples:`. (We keep the
# lenient `Scenario Examples` match as-is.)
_EXAMPLES_RE = re.compile(r"^\s*(Scenario\s+Examples|Examples|Scenarios)\s*:\s*.*$")
_FEATURE_RE = re.compile(r"^\s*Feature\s*:\s*.*$")
_BACKGROUND_RE = re.compile(r"^\s*Background\s*:\s*.*$")

# CONTRACT 2: @source:<doc-basename-without-ext>#<id>  ->  capture <id>.
_SOURCE_TAG_RE = re.compile(r"@source:[^#\s]+#(?P<id>[^\s@]+)")

# --------------------------------------------------------------------------- #
# Vacuous-Then heuristic.
#
# A scenario's `Then` block (the `Then` line plus any `And`/`But` clauses under
# it) states an observable expectation. We flag a scenario as *suspected vacuous*
# only when NONE of its Then-clause lines contains an assertion-like word below
# — i.e. the check is PER-SCENARIO, not per-line, so a single good asserting
# clause clears the whole scenario and a fine `And …` follow-on never trips it.
# Advisory only — false positives are cheap, the human + review-agent are the
# real quality gate. The list is deliberately broad and lives here as a single
# named constant so it is easy to tune. Matched case-insensitively on word
# boundaries; substrings of larger words do not count (so "unseen" != "see").
# --------------------------------------------------------------------------- #
ASSERTION_VERBS = frozenset({
    "should", "shall", "must", "expect", "expects", "expected",
    "see", "sees", "seen", "shown", "show", "shows", "display", "displays",
    "displayed", "receive", "receives", "received", "return", "returns",
    "returned", "be", "is", "are", "was", "were", "equal", "equals",
    "match", "matches", "contain", "contains", "include", "includes",
    "have", "has", "appear", "appears", "appeared", "redirect", "redirects",
    "redirected", "reject", "rejects", "rejected", "accept", "accepts",
    "accepted", "succeed", "succeeds", "fail", "fails", "error", "errors",
    "raise", "raises", "raised", "throw", "throws", "thrown", "respond",
    "responds", "get", "gets", "remain", "remains", "remained", "becomes",
    "become",
    "not", "no", "without", "denied", "allowed", "prevented", "blocked",
    "created", "deleted", "updated", "saved", "persisted", "stored",
    "increment", "increments", "decrement", "decrements", "count", "status",
    # State-transition / persistence / outcome verbs that the references' own
    # model-good examples use (e.g. 'the order moves to the "Cancelled" state',
    # "bob's account still exists"). Added with their natural inflections.
    "move", "moves", "moved", "exist", "exists", "existed",
    "land", "lands", "landed", "unchanged",
    "cancel", "cancels", "cancelled", "canceled",
    "refund", "refunds", "refunded", "confirm", "confirms", "confirmed",
    "permanently",
})

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z']*")

# Apostrophe-contracted negations (shouldn't, won't, isn't, doesn't, can't, …)
# tokenise as a single word that is absent from ASSERTION_VERBS, which would
# falsely flag e.g. "Then the page shouldn't exist" as vacuous. A negated
# expectation ("should not", "can't access") IS an assertion (it states an
# observable expectation), so we normalise any "n't" contraction to the
# negation marker "not" — which is already an assertion-like word — before
# matching. The explicit map handles irregular forms (won't, can't, shan't);
# the "n't"-stripping fallback catches the rest. Tunable alongside
# ASSERTION_VERBS.
_NEGATION_MARKER = "not"
NEGATION_CONTRACTIONS = frozenset({
    "shouldn't", "shan't", "won't", "can't", "cannot", "couldn't",
    "wouldn't", "mustn't", "isn't", "aren't", "wasn't", "weren't",
    "don't", "doesn't", "didn't", "hasn't", "haven't", "hadn't", "needn't",
})


def _normalize_token(word: str) -> str:
    """Lowercase a word; map a negated contraction to the negation marker.

    "shouldn't"/"can't"/"isn't" -> "not" (an assertion-like word), since a
    negated expectation is still an assertion. Falls back to a trailing-"n't"
    check so contractions not enumerated in NEGATION_CONTRACTIONS still match.
    """
    lw = word.lower()
    if lw in NEGATION_CONTRACTIONS or (lw.endswith("n't") and len(lw) > 3):
        return _NEGATION_MARKER
    return lw


def _then_has_assertion(text: str) -> bool:
    """True if a Then step's text contains at least one assertion-like word."""
    return any(_normalize_token(w) in ASSERTION_VERBS for w in _WORD_RE.findall(text))


# --------------------------------------------------------------------------- #
# Parsed structures.
# --------------------------------------------------------------------------- #

@dataclass
class Scenario:
    name: str
    is_outline: bool
    line_no: int
    tags: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)  # effective per step (And/But resolved)
    then_texts: list[str] = field(default_factory=list)
    has_examples: bool = False

    @property
    def source_ids(self) -> list[str]:
        ids: list[str] = []
        for tag in self.tags:
            m = _SOURCE_TAG_RE.match(tag) if tag.startswith("@source:") else None
            if m:
                ids.append(m.group("id"))
        return ids

    @property
    def has_source(self) -> bool:
        return any(t.startswith("@source:") for t in self.tags)


@dataclass
class Result:
    ok: bool
    hard_errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    coverage: float = 1.0

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "hard_errors": self.hard_errors,
            "warnings": self.warnings,
            "coverage": self.coverage,
        }


# --------------------------------------------------------------------------- #
# Parser.
# --------------------------------------------------------------------------- #

def parse_catalog(text: str) -> list[Scenario]:
    """Parse a Gherkin catalog into a list of Scenario records.

    Lightweight + forgiving: it tracks tag lines (which attach to the *next*
    scenario), Scenario / Scenario Outline headers, the effective keyword of
    each step (resolving And/But to the most recent primary keyword), Then
    texts, and whether an Examples: table followed an outline. Lines it does not
    recognise (Feature, Background, table rows, doc-strings, comments, blanks)
    are skipped — they do not affect the structural checks.

    Background: steps are collected into background_keywords / background_then_texts
    and prepended to every scenario in the same feature (standard Gherkin semantics).
    background_keywords is reset on each Feature: header so steps never bleed
    across feature boundaries.
    """
    scenarios: list[Scenario] = []
    pending_tags: list[str] = []
    current: Scenario | None = None
    last_primary: str | None = None  # for And/But inheritance
    in_background: bool = False
    background_keywords: list[str] = []
    background_then_texts: list[str] = []

    for idx, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip("\n")
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue  # Gherkin comment

        m_scn = _SCENARIO_RE.match(line)
        if m_scn:
            current = Scenario(
                name=m_scn.group("name").strip(),
                is_outline=bool(m_scn.group("outline")),
                line_no=idx,
                tags=pending_tags,
            )
            # Prepend background steps to every scenario in this feature.
            current.keywords.extend(background_keywords)
            current.then_texts.extend(background_then_texts)
            scenarios.append(current)
            pending_tags = []
            last_primary = None
            in_background = False
            continue

        if _EXAMPLES_RE.match(line):
            if current is not None:
                current.has_examples = True
            continue

        if _FEATURE_RE.match(line):
            # A new Feature resets background and any pending tag run.
            pending_tags = []
            last_primary = None
            in_background = False
            background_keywords = []
            background_then_texts = []
            continue

        if _BACKGROUND_RE.match(line):
            # Background: ends any pending tag run; subsequent steps are background steps.
            pending_tags = []
            last_primary = None
            in_background = True
            continue

        m_step = _STEP_RE.match(line)
        if m_step:
            kw = m_step.group(1)
            if kw in ("And", "But"):
                effective = last_primary
            else:
                effective = kw
                last_primary = kw
            if effective is not None:
                if in_background and current is None:
                    background_keywords.append(effective)
                    if effective == "Then":
                        background_then_texts.append(m_step.group("text").strip())
                elif current is not None:
                    current.keywords.append(effective)
                    if effective == "Then":
                        current.then_texts.append(m_step.group("text").strip())
            continue

        # A tag line attaches to the NEXT scenario.
        if _TAG_LINE_RE.match(line) and not m_step:
            pending_tags.extend(_TAG_TOKEN_RE.findall(line))
            continue

        # Anything else (table rows, doc-strings, prose) is ignored.

    return scenarios


# --------------------------------------------------------------------------- #
# Validation.
# --------------------------------------------------------------------------- #

def _manifest_ids(manifest: dict) -> list[str]:
    # Dedupe order-preservingly: a manifest with duplicate section ids must not
    # inflate the coverage denominator (which would also yield the contradictory
    # "coverage below threshold but uncovered-ids list is empty" message).
    return list(
        dict.fromkeys(
            s.get("id") for s in manifest.get("sections", []) if s.get("id")
        )
    )


def _manifest_confidence(manifest: dict) -> dict:
    return {
        s.get("id"): (s.get("confidence") or "high")
        for s in manifest.get("sections", []) if s.get("id")
    }


def validate(catalog_text: str, manifest: dict, min_coverage: float = 0.8,
             scope_ids: list[str] | None = None) -> Result:
    """Run the structural HARD gate + ADVISORY checks; return a Result."""
    hard: list[str] = []
    warn: list[str] = []

    scenarios = parse_catalog(catalog_text)

    # ---- HARD: at least one scenario. ----
    if not scenarios:
        hard.append(
            "No Scenario or Scenario Outline found — the catalog must contain at "
            "least one Gherkin scenario."
        )

    manifest_ids = _manifest_ids(manifest)
    confidences = _manifest_confidence(manifest)
    known_ids = set(manifest_ids)
    referenced_known: set[str] = set()

    # ---- SCOPE filter: narrow the coverage denominator when requested. ----
    # Confabulation check and low-confidence advisories still use the full
    # known_ids set; only the RTM coverage denominator is scoped.
    if scope_ids is not None:
        scope_set = set(scope_ids)
        unknown_scope = scope_set - known_ids
        for sid in sorted(unknown_scope):
            warn.append(f"--scope id '{sid}' is not present in the manifest (possible typo).")
        manifest_ids = [mid for mid in manifest_ids if mid in scope_set]

    for scn in scenarios:
        label = f"Scenario '{scn.name}' (line {scn.line_no})"
        kws = set(scn.keywords)

        # ---- HARD: Given / When / Then present. ----
        for required in ("Given", "When", "Then"):
            if required not in kws:
                hard.append(f"{label} is missing a {required} step.")

        # ---- HARD: Scenario Outline must have Examples. ----
        if scn.is_outline and not scn.has_examples:
            hard.append(f"{label} is a Scenario Outline but has no Examples: table.")

        # ---- ADVISORY: @source presence. ----
        if not scn.has_source:
            warn.append(f"{label} has no @source tag (no RTM link to the manifest).")

        # ---- ADVISORY: @source tag present but malformed (no #id fragment). ----
        # has_source=True suppresses the "no @source tag" advisory above, but
        # source_ids==[] means it gives no coverage credit and dodges the
        # confabulation check — a silent RTM miss. Flag it explicitly.
        if scn.has_source and not scn.source_ids:
            warn.append(f"{label} has a malformed @source tag (missing #id fragment).")

        # ---- ADVISORY: @source resolves in the manifest (confabulation). ----
        for sid in scn.source_ids:
            if sid in known_ids:
                referenced_known.add(sid)
                # ---- ADVISORY: low-confidence source section. ----
                if confidences.get(sid) == "low":
                    warn.append(
                        f"{label} traces to @source id '{sid}', a "
                        f"confidence: low manifest section — verify it."
                    )
            else:
                warn.append(
                    f"{label} references @source id '{sid}' not present in the "
                    f"manifest (suspected confabulation)."
                )

        # ---- ADVISORY: vacuous Then (per-scenario). ----
        # Flag the scenario only when NONE of its Then-clause lines (the Then
        # plus any And/But under it) carries an assertion-like verb. One warning
        # per scenario at most — a good asserting clause clears the whole block,
        # so a fine `And …` follow-on after a concrete Then never trips it.
        if scn.then_texts and not any(
            _then_has_assertion(t) for t in scn.then_texts
        ):
            warn.append(
                f"{label} has a Then block with no assertion-like verb in any "
                f"clause (suspected vacuous): 'Then {scn.then_texts[0]}'."
            )

    # ---- ADVISORY: RTM coverage. ----
    if manifest_ids:
        coverage = len(referenced_known) / len(manifest_ids)
    else:
        coverage = 1.0  # nothing to cover
    coverage = round(coverage, 6)

    if manifest_ids and coverage < min_coverage:
        uncovered = sorted(set(manifest_ids) - referenced_known)
        warn.append(
            f"RTM coverage {coverage:.2f} is below the --min-coverage "
            f"{min_coverage:.2f} threshold. Manifest ids with no scenario: "
            f"{', '.join(uncovered)}."
        )

    return Result(ok=not hard, hard_errors=hard, warnings=warn, coverage=coverage)


# --------------------------------------------------------------------------- #
# Reuse the create-issue prerequisite gate by import (single source of truth).
# --------------------------------------------------------------------------- #

_VALIDATE_ISSUE_CACHE = None


def _validate_issue_path() -> Path:
    """Locate ../create-issue/scripts/validate_issue.py relative to this file.

    This script lives at .../create-test-cases/scripts/validate_cases.py, so its
    sibling skill's script is at
    parents[1].parent/create-issue/scripts/validate_issue.py (i.e. up out of
    scripts/ and create-test-cases/, then across into create-issue/).
    """
    return (
        Path(__file__).resolve().parents[1].parent
        / "create-issue" / "scripts" / "validate_issue.py"
    )


def _validate_issue_module():
    """Import the create-issue validate_issue module from its on-disk path.

    Robust to not being on sys.path (the create-issue tests likewise locate the
    script by relative path). Cached after first load.
    """
    global _VALIDATE_ISSUE_CACHE
    if _VALIDATE_ISSUE_CACHE is not None:
        return _VALIDATE_ISSUE_CACHE
    path = _validate_issue_path()
    spec = importlib.util.spec_from_file_location("ct_validate_issue", str(path))
    # NOTE: spec_from_file_location returns a non-None spec even for a path that
    # does not exist, so this guard alone does not catch a missing sibling.
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot load validate_issue from {path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except FileNotFoundError as exc:
        # A missing sibling surfaces here as FileNotFoundError (not ImportError);
        # re-raise as a clear ImportError so callers see a single failure mode.
        raise ImportError(
            f"cannot load validate_issue from {path}: {exc}"
        ) from exc
    _VALIDATE_ISSUE_CACHE = module
    return module


def validate_issue_body(body: str) -> dict:
    """Validate a generated ``type::test`` issue body against the existing
    prerequisite gate, **delegating** to create-issue's validate_issue.check()
    (we do not reimplement the gate). Returns ``{"ok": bool, "missing": [...]}``.
    """
    module = _validate_issue_module()
    res = module.check(body)
    return {"ok": res.ok, "missing": res.missing}


# --------------------------------------------------------------------------- #
# CLI.
# --------------------------------------------------------------------------- #

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a Gherkin case catalog (structural HARD gate + "
                    "RTM/quality advisories)."
    )
    parser.add_argument("catalog", help="path to the CATALOG.feature file")
    parser.add_argument(
        "--manifest", required=True,
        help="path to the ingest manifest.json (CONTRACT 1)",
    )
    parser.add_argument(
        "--min-coverage", type=float, default=0.8,
        help="RTM coverage threshold below which a warning is emitted "
             "(advisory only; default 0.8)",
    )
    parser.add_argument(
        "--scope", default=None,
        help="Comma-separated manifest section ids to compute coverage over "
             "(default: all manifest ids). Use when validating a catalog for a "
             "scoped feature subset of a larger manual.",
    )
    args = parser.parse_args(argv[1:])

    catalog_text = Path(args.catalog).read_text(encoding="utf-8")
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))

    scope_ids = [s.strip() for s in args.scope.split(",") if s.strip()] if args.scope else None
    result = validate(catalog_text, manifest, min_coverage=args.min_coverage, scope_ids=scope_ids)
    print(json.dumps(result.to_dict()))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

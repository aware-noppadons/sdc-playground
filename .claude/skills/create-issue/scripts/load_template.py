#!/usr/bin/env python3
"""Resolve the canonical SDC agent-task template — the single sourcing seam.

The template is SDC-owned and global; the control plane on VM1 is its canonical
home. This function is the ONE place that decides where the template comes from,
so moving from bundled to CP-served is a change here and nowhere else:

  1. If ``SDC_CONTROL_PLANE_URL`` is set, fetch ``GET {url}/api/issue-template``
     (the planned read-only endpoint) — always-current, even for skill copies
     distributed outside the SDC repo.
  2. Otherwise (or on any fetch failure), use the bundled copy in references/,
     which CI keeps byte-identical to docs/templates/agent-task.md.

CLI: prints the resolved template to stdout.
"""

import os
import pathlib
import sys
import urllib.request

BUNDLED = pathlib.Path(__file__).resolve().parents[1] / "references" / "agent-task.md"


def load_template(*, allow_fetch: bool = True, timeout: float = 5.0) -> str:
    """Return the canonical agent-task template (CP if configured, else bundled)."""
    base = os.environ.get("SDC_CONTROL_PLANE_URL", "").rstrip("/")
    if base and allow_fetch:
        try:
            with urllib.request.urlopen(
                f"{base}/api/issue-template", timeout=timeout
            ) as resp:
                text = resp.read().decode("utf-8")
            if text.strip():
                return text
        except Exception:
            pass
    return BUNDLED.read_text(encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.write(load_template())

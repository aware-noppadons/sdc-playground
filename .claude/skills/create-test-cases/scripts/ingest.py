#!/usr/bin/env python3
"""ingest.py — multi-format source-document normalizer for `create-test-cases` (Flow B).

Turns one or more source documents (a user manual, a test plan) into a working
directory that the drafting/review agents can consume:

    <out>/normalized.md     concatenated normalized markdown for all sources
    <out>/images/           extracted / rendered PNGs referenced by sections
    <out>/manifest.json     CONTRACT 1 — the RTM index over the sources

CONTRACT 1 (see docs/superpowers/plans/2026-06-21-test-authoring-skills.md) is the
canonical schema for `manifest.json`. Each *source* maps to a manifest entry of:

    {
      "source": "user-manual.md",
      "format": "md|docx|xlsx|pdf|pptx|<ext>",
      "ingested_with": "passthrough|pandoc|python-docx|mammoth|openpyxl|"
                       "pdfplumber|pymupdf|python-pptx|images-only|raw-fallback",
      "needs_multimodal_read": false,
      "sections": [
        {
          "id": "sec-3-2",
          "locator": "#sec-3-2",
          "title": "Creating an account",
          "text": "…normalized markdown for this section…",
          "confidence": "high|medium|low",
          "has_images": false,
          "images": ["images/sec-3-2-fig1.png"]
        }
      ]
    }

When a single source is ingested the manifest top-level *is* that entry (so it
matches CONTRACT 1 byte-for-byte). When several sources are ingested the top-level
keeps CONTRACT-1 shape (a flattened, globally-unique `sections` list + aggregate
`needs_multimodal_read`) and additionally carries a `sources: [<entry>, …]` array
holding each per-source manifest entry.

GUIDANCE (CONTRACT 1): optional imports only — NO hard dependency on any heavy
parser. `md` always works (stdlib). For docx/xlsx/pdf/pptx, `try` the relevant lib;
on ImportError or *any* parse failure, **degrade** (ingested_with=raw-fallback,
confidence=low, needs_multimodal_read=true, point at the raw file) rather than
raising. Never auto-install a library. This module must import and run the `md`
path with NONE of the heavy libs installed.

CLI:
    ingest.py SRC [SRC2 ...] --out DIR
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import sys
import unicodedata
from dataclasses import dataclass, field
from typing import Callable, Optional

# ---------------------------------------------------------------------------
# Confidence / ingester constants (CONTRACT 1 vocabulary)
# ---------------------------------------------------------------------------
HIGH = "high"
MEDIUM = "medium"
LOW = "low"

# Below this many characters of extracted text per page, a PDF text layer is
# treated as "near-zero density" → multimodal read required.
PDF_TEXT_DENSITY_FLOOR = 32

# Cap a degraded raw-fallback section's inlined text so the manifest stays small.
RAW_TEXT_PREVIEW_LIMIT = 4000


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class Section:
    id: str
    title: str
    text: str
    confidence: str = HIGH
    images: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "locator": "#" + self.id,
            "title": self.title,
            "text": self.text,
            "confidence": self.confidence,
            "has_images": bool(self.images),
            "images": list(self.images),
        }


@dataclass
class SourceResult:
    """One source document's contribution to the working dir."""

    source: str
    fmt: str
    ingested_with: str
    needs_multimodal_read: bool
    sections: list  # list[Section]

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "format": self.fmt,
            "ingested_with": self.ingested_with,
            "needs_multimodal_read": self.needs_multimodal_read,
            "sections": [s.to_dict() for s in self.sections],
        }


# ---------------------------------------------------------------------------
# Slugging + id uniqueness
# ---------------------------------------------------------------------------
def slugify(text: str) -> str:
    """Heading/section text → a stable kebab-case ascii slug.

    Unicode is transliterated to its closest ascii (NFKD + drop combining marks),
    everything non-alphanumeric collapses to single hyphens, edges trimmed,
    lowercased. Empty input yields "section".
    """
    if text is None:
        text = ""
    # Transliterate accents/diacritics; drop chars with no ascii fold.
    norm = unicodedata.normalize("NFKD", str(text))
    ascii_text = norm.encode("ascii", "ignore").decode("ascii")
    ascii_text = ascii_text.lower()
    # Collapse any run of non [a-z0-9] into a single hyphen.
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    return slug or "section"


class _Uniquifier:
    """Deterministically de-duplicate slugs: foo, foo-2, foo-3, …"""

    def __init__(self) -> None:
        self._seen: dict[str, int] = {}

    def make(self, base: str) -> str:
        if base not in self._seen:
            self._seen[base] = 1
            return base
        self._seen[base] += 1
        candidate = f"{base}-{self._seen[base]}"
        # Guard the (rare) case where the numbered candidate itself collides
        # with a pre-existing explicit id (e.g. "foo" and "foo-2" both present).
        while candidate in self._seen:
            self._seen[base] += 1
            candidate = f"{base}-{self._seen[base]}"
        self._seen[candidate] = 1
        return candidate


# ---------------------------------------------------------------------------
# Markdown section splitting (stdlib only — always available)
# ---------------------------------------------------------------------------
_ATX_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")


def split_markdown_sections(md_text: str, uniq: Optional[_Uniquifier] = None) -> list:
    """Split markdown into sections on ATX (`#`..`######`) headings.

    - Content before the first heading becomes a "preamble"/intro section (only
      if it has non-whitespace content).
    - Each heading starts a new section; its slug (uniquified) becomes the id.
    - A pure CONTAINER heading — one with NO body of its own (only sub-headings
      beneath it) — is NOT emitted as a section: it has nothing a scenario could
      trace to and would inflate the RTM coverage denominator. Its sub-headings
      still get their own sections.
    - Fenced code blocks are respected: a `#` inside a fence is not a heading.
    """
    if uniq is None:
        uniq = _Uniquifier()

    lines = md_text.splitlines()
    sections: list = []
    in_fence = False
    fence_marker = ""

    # Buffers for the section currently being built.
    cur_title = None  # None → preamble (no heading yet)
    cur_lines: list = []

    def flush(title, body_lines):
        body = "\n".join(body_lines).strip("\n")
        if title is None:
            # Preamble: only emit if it carries real content.
            if body.strip() == "":
                return
            sid = uniq.make("intro")
            sections.append(Section(id=sid, title="", text=body, confidence=HIGH))
        else:
            # Drop pure CONTAINER headings: a heading with no body of its own
            # (only sub-headings beneath it) is not a traceable section — it would
            # inflate the RTM coverage denominator and show as a spurious gap. The
            # heading line itself is body_lines[0]; "its own body" is everything
            # after it, up to the next heading. If that is empty/whitespace-only,
            # do not emit a section (the sub-headings below still get their own).
            own_body = "\n".join(body_lines[1:])
            if own_body.strip() == "":
                return
            sid = uniq.make(slugify(title))
            # The heading line is already preserved in `body` (it was appended to
            # cur_lines upstream), so the section text round-trips structure as-is.
            sections.append(Section(id=sid, title=title, text=body, confidence=HIGH))

    for raw in lines:
        fence_m = _FENCE.match(raw)
        if fence_m:
            marker = fence_m.group(1)
            if not in_fence:
                in_fence = True
                fence_marker = marker
            elif raw.strip().startswith(fence_marker):
                in_fence = False
                fence_marker = ""
            cur_lines.append(raw)
            continue

        heading_m = None if in_fence else _ATX_HEADING.match(raw)
        if heading_m:
            # Close the previous section, open a new one.
            flush(cur_title, cur_lines)
            cur_title = heading_m.group(2).strip()
            cur_lines = [raw]  # keep the heading line in the section body
        else:
            cur_lines.append(raw)

    flush(cur_title, cur_lines)

    # Degenerate case: empty/whitespace-only doc → a single empty section so the
    # source still appears in the manifest.
    if not sections:
        sid = uniq.make("intro")
        sections.append(Section(id=sid, title="", text="", confidence=HIGH))
    return sections


# ---------------------------------------------------------------------------
# Per-format ingesters. Each returns a SourceResult or raises (caught → degrade).
# All heavy imports are LOCAL and optional.
# ---------------------------------------------------------------------------
def ingest_md(path: pathlib.Path, uniq: _Uniquifier, images_dir: pathlib.Path) -> SourceResult:
    """Markdown passthrough — stdlib only, confidence high. Always works."""
    text = path.read_text(encoding="utf-8", errors="replace")
    sections = split_markdown_sections(text, uniq)
    return SourceResult(
        source=path.name,
        fmt="md",
        ingested_with="passthrough",
        needs_multimodal_read=False,
        sections=sections,
    )


def ingest_docx(path: pathlib.Path, uniq: _Uniquifier, images_dir: pathlib.Path) -> SourceResult:
    """DOCX → markdown. Try python-docx, then mammoth, then a pandoc subprocess."""
    # 1) python-docx (paragraph + heading-style aware).
    try:
        import docx  # type: ignore  # python-docx

        document = docx.Document(str(path))
        md_lines: list = []
        for para in document.paragraphs:
            style = (para.style.name or "") if para.style else ""
            txt = para.text.rstrip()
            m = re.match(r"Heading\s+(\d+)", style)
            if m:
                level = min(int(m.group(1)), 6)
                md_lines.append("#" * level + " " + txt)
            elif style.lower() == "title":
                md_lines.append("# " + txt)
            else:
                md_lines.append(txt)
        md_text = "\n\n".join(line for line in md_lines)
        sections = split_markdown_sections(md_text, uniq)
        return SourceResult(path.name, "docx", "python-docx", False, sections)
    except ImportError:
        pass

    # 2) mammoth (DOCX → markdown).
    try:
        import mammoth  # type: ignore

        with open(path, "rb") as fh:
            result = mammoth.convert_to_markdown(fh)
        md_text = result.value or ""
        sections = split_markdown_sections(md_text, uniq)
        return SourceResult(path.name, "docx", "mammoth", False, sections)
    except ImportError:
        pass

    # 3) pandoc subprocess (if the binary is on PATH).
    md_text = _pandoc_to_markdown(path)
    if md_text is not None:
        sections = split_markdown_sections(md_text, uniq)
        return SourceResult(path.name, "docx", "pandoc", False, sections)

    raise RuntimeError("no docx backend available")


def ingest_xlsx(path: pathlib.Path, uniq: _Uniquifier, images_dir: pathlib.Path) -> SourceResult:
    """XLSX → sections. If a sheet looks like a test matrix (header row with
    ID/Step/Expected-like columns) emit one section per data row (`row-<n>`);
    otherwise emit one section per sheet."""
    import openpyxl  # type: ignore  # raises ImportError → degrade

    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    sections: list = []
    for ws in wb.worksheets:
        rows = [
            [("" if c is None else str(c)) for c in row]
            for row in ws.iter_rows(values_only=True)
        ]
        rows = [r for r in rows if any(cell.strip() for cell in r)]
        if not rows:
            continue
        header = rows[0]
        if _looks_like_test_matrix(header):
            cols = [h.strip() for h in header]
            for n, data_row in enumerate(rows[1:], start=1):
                pairs = []
                for col, val in zip(cols, data_row):
                    if col:
                        pairs.append(f"- **{col}:** {val}".rstrip())
                title = _row_title(cols, data_row, n)
                body = f"### {title}\n" + "\n".join(pairs)
                sid = uniq.make(f"row-{n}")
                sections.append(Section(id=sid, title=title, text=body, confidence=HIGH))
        else:
            # Whole-sheet section: render as a markdown table.
            table = _rows_to_md_table(rows)
            title = ws.title
            sid = uniq.make(slugify(title))
            body = f"## {title}\n\n{table}"
            sections.append(Section(id=sid, title=title, text=body, confidence=HIGH))
    wb.close()
    if not sections:
        sid = uniq.make("intro")
        sections.append(Section(id=sid, title="", text="", confidence=HIGH))
    return SourceResult(path.name, "xlsx", "openpyxl", False, sections)


def ingest_pdf(path: pathlib.Path, uniq: _Uniquifier, images_dir: pathlib.Path) -> SourceResult:
    """PDF text layer. Try pdfplumber then pymupdf(fitz). If text density is
    near-zero → needs_multimodal_read, confidence low, render page images if a
    renderer is available, else raw-fallback."""
    pages_text: Optional[list] = None
    used = None

    # 1) pdfplumber
    try:
        import pdfplumber  # type: ignore

        pages_text = []
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                pages_text.append(page.extract_text() or "")
        used = "pdfplumber"
    except ImportError:
        pages_text = None

    # 2) pymupdf / fitz
    if pages_text is None:
        try:
            import fitz  # type: ignore  # PyMuPDF

            pages_text = []
            with fitz.open(str(path)) as doc:
                for page in doc:
                    pages_text.append(page.get_text() or "")
            used = "pymupdf"
        except ImportError:
            pages_text = None

    if pages_text is None:
        raise RuntimeError("no pdf text backend available")

    total_chars = sum(len(t.strip()) for t in pages_text)
    n_pages = max(len(pages_text), 1)
    density = total_chars / n_pages
    near_zero = density < PDF_TEXT_DENSITY_FLOOR

    if not near_zero:
        # Good text layer → medium confidence, one section per page.
        sections = []
        for i, txt in enumerate(pages_text, start=1):
            sid = uniq.make(f"page-{i}")
            body = f"## Page {i}\n\n{txt.strip()}"
            sections.append(Section(id=sid, title=f"Page {i}", text=body, confidence=MEDIUM))
        return SourceResult(path.name, "pdf", used, False, sections)

    # Near-zero text density → multimodal read required. Try to render images.
    rendered = _render_pdf_images(path, images_dir)
    if rendered:
        sections = []
        for i, img_rel in enumerate(rendered, start=1):
            sid = uniq.make(f"page-{i}")
            body = f"## Page {i}\n\n_(scanned / image-only page — read the rendered image)_"
            sections.append(
                Section(id=sid, title=f"Page {i}", text=body, confidence=LOW, images=[img_rel])
            )
        return SourceResult(path.name, "pdf", "images-only", True, sections)

    # No renderer available → raw fallback pointing at the file.
    return _raw_fallback(path, uniq, fmt="pdf")


def ingest_pptx(path: pathlib.Path, uniq: _Uniquifier, images_dir: pathlib.Path) -> SourceResult:
    """PPTX → one section per slide (title + body text + notes). Slide decks are
    fragmentary → confidence low, needs_multimodal_read true."""
    from pptx import Presentation  # type: ignore  # python-pptx; ImportError → degrade

    prs = Presentation(str(path))
    sections: list = []
    for n, slide in enumerate(prs.slides, start=1):
        texts: list = []
        title_text = ""
        for shape in slide.shapes:
            if getattr(shape, "has_text_frame", False) and shape.text_frame is not None:
                t = shape.text_frame.text.strip()
                if not t:
                    continue
                if not title_text and getattr(shape, "name", "").lower().startswith("title"):
                    title_text = t.splitlines()[0]
                texts.append(t)
        notes = ""
        try:
            if slide.has_notes_slide and slide.notes_slide is not None:
                notes = (slide.notes_slide.notes_text_frame.text or "").strip()
        except Exception:
            notes = ""
        title = title_text or f"Slide {n}"
        body_parts = [f"## Slide {n}: {title}"]
        if texts:
            body_parts.append("\n".join(texts))
        if notes:
            body_parts.append(f"\n_Notes:_ {notes}")
        sid = uniq.make(f"slide-{n}")
        sections.append(
            Section(id=sid, title=title, text="\n\n".join(body_parts), confidence=LOW)
        )
    if not sections:
        sid = uniq.make("slide-1")
        sections.append(Section(id=sid, title="Slide 1", text="", confidence=LOW))
    return SourceResult(path.name, "pptx", "python-pptx", True, sections)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_MATRIX_HINTS = (
    "id",
    "step",
    "steps",
    "expected",
    "expected result",
    "expected results",
    "result",
    "action",
    "test case",
    "testcase",
    "test",
    "scenario",
    "precondition",
    "preconditions",
    "given",
    "when",
    "then",
)


def _looks_like_test_matrix(header: list) -> bool:
    """A header row 'looks like' a test matrix if it has ≥2 columns and ≥2 of
    its cells match common test-matrix column names (ID/Step/Expected-like)."""
    cells = [h.strip().lower() for h in header if h.strip()]
    if len(cells) < 2:
        return False
    hits = 0
    for c in cells:
        if c in _MATRIX_HINTS or any(h in c for h in ("expected", "step", "test case", "scenario")):
            hits += 1
    return hits >= 2


def _row_title(cols: list, data_row: list, n: int) -> str:
    """Prefer an ID-ish / scenario-ish cell as the row title; else 'Row n'."""
    lower = [c.lower() for c in cols]
    for key in ("test case", "testcase", "scenario", "title", "name", "id"):
        if key in lower:
            idx = lower.index(key)
            if idx < len(data_row) and str(data_row[idx]).strip():
                return str(data_row[idx]).strip()
    return f"Row {n}"


def _rows_to_md_table(rows: list) -> str:
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    padded = [list(r) + [""] * (width - len(r)) for r in rows]
    header = padded[0]
    out = ["| " + " | ".join(header) + " |"]
    out.append("| " + " | ".join(["---"] * width) + " |")
    for r in padded[1:]:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


def _pandoc_to_markdown(path: pathlib.Path) -> Optional[str]:
    """Convert a doc to markdown via the pandoc binary, if present. None on any
    failure (missing binary, non-zero exit)."""
    pandoc = shutil.which("pandoc")
    if not pandoc:
        return None
    import subprocess

    try:
        proc = subprocess.run(
            [pandoc, str(path), "-t", "gfm", "--wrap=none"],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _render_pdf_images(path: pathlib.Path, images_dir: pathlib.Path) -> list:
    """Render PDF pages to PNGs under images_dir using pymupdf if available.
    Returns a list of repo-relative image paths (possibly empty)."""
    try:
        import fitz  # type: ignore
    except ImportError:
        return []
    rels: list = []
    try:
        images_dir.mkdir(parents=True, exist_ok=True)
        stem = slugify(path.stem)
        with fitz.open(str(path)) as doc:
            for i, page in enumerate(doc, start=1):
                pix = page.get_pixmap()
                name = f"{stem}-page-{i}.png"
                pix.save(str(images_dir / name))
                rels.append(f"images/{name}")
    except Exception:
        return rels
    return rels


def _raw_fallback(path: pathlib.Path, uniq: _Uniquifier, fmt: str) -> SourceResult:
    """Universal degrade: a single section pointing at the raw file. Never raises.

    Best-effort inlines a short text preview if the file decodes as text; binary
    files just get a pointer + needs_multimodal_read.
    """
    preview = ""
    try:
        raw = path.read_bytes()
        # Heuristic: if it decodes cleanly-ish as utf-8, inline a preview.
        decoded = raw.decode("utf-8", errors="replace")
        if "�" not in decoded[:2048]:
            preview = decoded[:RAW_TEXT_PREVIEW_LIMIT]
    except Exception:
        preview = ""
    sid = uniq.make(slugify(path.stem) or "source")
    note = (
        f"_Could not deterministically extract `{path.name}`. "
        f"Read the raw file directly via the multimodal Read tool._"
    )
    text = note if not preview else f"{note}\n\n{preview}"
    section = Section(id=sid, title=path.name, text=text, confidence=LOW)
    return SourceResult(
        source=path.name,
        fmt=fmt,
        ingested_with="raw-fallback",
        needs_multimodal_read=True,
        sections=[section],
    )


# Extension → ingester dispatch table.
_INGESTERS: dict = {
    ".md": ingest_md,
    ".markdown": ingest_md,
    ".docx": ingest_docx,
    ".xlsx": ingest_xlsx,
    ".pdf": ingest_pdf,
    ".pptx": ingest_pptx,
}


def ingest_one(path: pathlib.Path, uniq: _Uniquifier, images_dir: pathlib.Path) -> SourceResult:
    """Ingest a single source, degrading gracefully on any failure.

    NEVER raises on a bad input. Missing file / unknown extension / missing lib /
    parse failure all funnel into a raw-fallback section.
    """
    ext = path.suffix.lower()
    fmt_guess = ext.lstrip(".") or "unknown"

    if not path.exists() or not path.is_file():
        # Missing source → raw fallback (still recorded so it surfaces in report).
        sid = uniq.make(slugify(path.stem) or "source")
        section = Section(
            id=sid,
            title=path.name,
            text=f"_Source `{path.name}` not found or not a regular file._",
            confidence=LOW,
        )
        return SourceResult(path.name, fmt_guess, "raw-fallback", True, [section])

    ingester: Optional[Callable] = _INGESTERS.get(ext)
    if ingester is None:
        # Unknown extension → degrade.
        return _raw_fallback(path, uniq, fmt=fmt_guess)

    try:
        return ingester(path, uniq, images_dir)
    except Exception:
        # ImportError (lib absent) OR any parse failure → degrade. Never raise.
        return _raw_fallback(path, uniq, fmt=fmt_guess)


# ---------------------------------------------------------------------------
# normalized.md rendering
# ---------------------------------------------------------------------------
def render_normalized_md(results: list) -> str:
    """Concatenate all sources' sections into one normalized.md, separated by
    a per-source banner and per-section anchors (the RTM locators)."""
    blocks: list = []
    multi = len(results) > 1
    for res in results:
        if multi:
            blocks.append(f"<!-- source: {res.source} ({res.ingested_with}) -->")
        for sec in res.sections:
            # Emit the locator anchor as an HTML comment so it survives in MD.
            blocks.append(f"<!-- {sec.to_dict()['locator']} -->")
            blocks.append(sec.text.strip("\n") if sec.text else "")
    return "\n\n".join(b for b in blocks).strip() + "\n"


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def ingest(sources: list, out_dir) -> dict:
    """Ingest all `sources` into `out_dir`; write normalized.md + images/ +
    manifest.json. Returns the manifest dict. Pure-side-effect free apart from
    writing into out_dir; never raises on bad source content."""
    out = pathlib.Path(out_dir)
    images_dir = out / "images"
    out.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    # IMPORTANT: a single shared uniquifier across all sources → ids are globally
    # unique within the working dir, so @source locators never collide.
    uniq = _Uniquifier()
    results: list = [ingest_one(pathlib.Path(s), uniq, images_dir) for s in sources]

    # normalized.md
    (out / "normalized.md").write_text(render_normalized_md(results), encoding="utf-8")

    manifest = _build_manifest(results)
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest


def _build_manifest(results: list) -> dict:
    """Assemble the CONTRACT-1 manifest from per-source results.

    Single source → top-level == that source's entry (+ a sources:[entry] echo).
    Multiple sources → CONTRACT-1-shaped top level (flattened unique sections,
    aggregate needs_multimodal_read) + a sources:[…] array of per-source entries.
    """
    source_dicts = [r.to_dict() for r in results]
    all_sections: list = []
    for r in results:
        all_sections.extend(s.to_dict() for s in r.sections)

    needs_mm = any(r.needs_multimodal_read for r in results)

    if len(results) == 1:
        manifest = dict(source_dicts[0])  # exact CONTRACT-1 shape
        manifest["sources"] = source_dicts
        return manifest

    # Multi-source: keep CONTRACT-1 top-level keys, plus per-source breakdown.
    return {
        "source": ", ".join(r.source for r in results),
        "format": "multi",
        "ingested_with": "multi",
        "needs_multimodal_read": needs_mm,
        "sections": all_sections,
        "sources": source_dicts,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="ingest.py",
        description="Normalize source document(s) → normalized.md + images/ + manifest.json",
    )
    ap.add_argument("sources", nargs="+", metavar="SRC", help="source document(s)")
    ap.add_argument("--out", required=True, metavar="DIR", help="output working directory")
    return ap


def main(argv: Optional[list] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    manifest = ingest(args.sources, args.out)
    out = pathlib.Path(args.out)
    n_sections = len(manifest.get("sections", []))
    n_sources = len(manifest.get("sources", [])) or 1
    flagged = manifest.get("needs_multimodal_read", False)
    print(
        f"ingested {n_sources} source(s) → {out/'manifest.json'} "
        f"({n_sections} section(s); needs_multimodal_read={flagged})"
    )
    if flagged:
        print(
            "  note: some sections need a multimodal Read "
            "(scanned PDF / slide deck / raw fallback)",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

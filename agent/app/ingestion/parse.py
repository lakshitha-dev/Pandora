"""Record-aware chunking of the Pandora knowledge corpus.

This is the single highest-leverage retrieval decision in the system
(SOLUTION.md §4.2). The corpus is not prose — it is ~132 atomic records with
stable IDs and fixed internal field schemas. Fixed-size character splitting
would slice `FAU-014` through the middle of a field and bleed `FAU-015` into
the same chunk, producing exactly the failure the corpus itself prohibits:

    §15.2 — "Do not merge details from two species, villages, plants, or
             incidents merely because their names or habitats are similar."

So we chunk on the author's own boundaries instead of arbitrary ones.

Three tiers:
  1. Record chunks   — one complete `### PREFIX-NNN` record, never split,
                       never merged. ~132 of them.
  2. Narrative chunks— prose sections, split on heading boundaries first and
                       only packed to a token budget if a section is long.
  3. Table rows      — one chunk per row for WS-* / SV-* monitoring data, so
                       an individual reading stays independently retrievable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# Record ID prefixes and the entity type each denotes.
RECORD_TYPES: dict[str, str] = {
    "REG": "region",
    "STL": "settlement",
    "FAU": "fauna",
    "FLR": "flora",
    "MED": "health",
    "ACC": "accommodation",
    "INC": "incident",
    "POL": "policy",
    "KC": "knowledge_card",
}

# `### FAU-001 — Tideglass Grazer` / `### Knowledge Card KC-01`
_RECORD_HEADING = re.compile(
    r"^###\s+(?:Knowledge Card\s+)?"
    r"(?P<rid>(?:REG|STL|FAU|FLR|MED|ACC|INC|POL|KC)-\d+)"
    r"\s*[—–-]?\s*(?P<title>.*)$",
    re.MULTILINE,
)
_ANY_HEADING = re.compile(r"^(?P<hashes>#{1,3})\s+(?P<text>.+)$", re.MULTILINE)
_CHAPTER_HEADING = re.compile(r"^##\s+(?P<num>\d+)\.\s+(?P<title>.+)$", re.MULTILINE)

# Region name -> REG id, for cross-linking records to their geography.
REGION_NAMES: dict[str, str] = {
    "luminous shelf": "REG-01",
    "emerald canopy": "REG-02",
    "cloudspine highlands": "REG-03",
    "silverreed wetlands": "REG-04",
    "obsidian reach": "REG-05",
    "whispering dunes": "REG-06",
    "deep current expanse": "REG-07",
    "mistroot basin": "REG-08",
    "aurora mangroves": "REG-09",
    "sunfall archipelago": "REG-10",
}

_NARRATIVE_MAX_CHARS = 3200   # ≈ 800 tokens
_NARRATIVE_OVERLAP_CHARS = 480  # ≈ 120 tokens


@dataclass
class Chunk:
    """One indexable unit of the corpus."""

    chunk_id: str
    content: str
    record_id: str | None = None
    record_type: str = "narrative"
    title: str = ""
    chapter: str = ""
    section: str = ""
    region_id: str | None = None
    evidence_quality: str = "verified observation"
    risk_level: str | None = None
    record_date: str | None = None
    document_id: str = "pandora-corpus"
    document_name: str = "Pandora_RAG_Knowledge_2026.md"
    page: int | None = None
    extra: dict = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def _body_of(content: str) -> str:
    """Content minus any leading heading lines — the substantive text."""
    lines = [ln for ln in content.splitlines() if not ln.lstrip().startswith("#")]
    return "\n".join(lines).strip()


def _detect_region(text: str) -> str | None:
    lowered = text.lower()
    for name, rid in REGION_NAMES.items():
        if name in lowered:
            return rid
    return None


def _detect_risk_level(text: str) -> str | None:
    m = re.search(r"Initial risk level:\s*([A-Z]+)", text)
    return m.group(1).upper() if m else None


def _chapter_index(markdown: str) -> list[tuple[int, str]]:
    """Return (offset, 'N · Title') for each chapter heading, in order."""
    out: list[tuple[int, str]] = []
    for m in _CHAPTER_HEADING.finditer(markdown):
        out.append((m.start(), f"{m.group('num')} · {m.group('title').strip()}"))
    return out


def _chapter_at(offset: int, chapters: list[tuple[int, str]]) -> str:
    current = ""
    for pos, label in chapters:
        if pos <= offset:
            current = label
        else:
            break
    return current


def classify_evidence_quality(record_type: str, content: str) -> str:
    """Assign the corpus's own five-level evidence taxonomy (page 2).

    "Information quality is classified as verified observation, community
    tradition, provisional interpretation, modeled estimate, or disputed
    report. RAG applications should preserve these labels."
    """
    lowered = content.lower()

    if any(k in lowered for k in ("chain-of-custody form was incomplete",
                                  "chain of custody",
                                  "did not confirm",
                                  "not directly comparable",
                                  "disputed")):
        return "disputed report"

    if record_type == "incident" or "these are hypotheses" in lowered:
        return "provisional interpretation"

    if record_type == "monitoring":
        return "verified observation"

    if any(k in lowered for k in ("tradition", "ceremon", "oral histor",
                                  "community knowledge", "ancestr")):
        return "community tradition"

    if any(k in lowered for k in ("carrying capacity", "estimate", "projected",
                                  "modeled", "modelled")):
        return "modeled estimate"

    return "verified observation"


# ─────────────────────────────────────────────────────────────────────────
# Tier 1 — record chunks
# ─────────────────────────────────────────────────────────────────────────


def _extract_records(markdown: str, chapters: list[tuple[int, str]]) -> tuple[list[Chunk], list[tuple[int, int]]]:
    """One chunk per `### PREFIX-NNN` record. Returns (chunks, spans consumed)."""
    matches = list(_RECORD_HEADING.finditer(markdown))
    chunks: list[Chunk] = []
    spans: list[tuple[int, int]] = []

    for i, m in enumerate(matches):
        start = m.start()
        # A record ends at the next record heading OR the next heading of
        # level <= 3 that is not itself a record — whichever comes first.
        end = len(markdown)
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        for h in _ANY_HEADING.finditer(markdown, m.end()):
            if h.start() >= end:
                break
            if len(h.group("hashes")) <= 2:  # a new chapter/section begins
                end = h.start()
                break

        body = markdown[start:end].strip()
        rid = m.group("rid")
        prefix = rid.split("-")[0]
        rtype = RECORD_TYPES.get(prefix, "narrative")
        title = m.group("title").strip()

        # Prefix a provenance header so the record ID travels with the text
        # into the model's context — it cannot cite an ID it cannot see.
        chapter = _chapter_at(start, chapters)
        header = f"[{rid}] {title}".strip()
        if chapter:
            header += f" · Chapter {chapter}"
        content = f"{header}\n\n{body}"

        chunks.append(
            Chunk(
                chunk_id=f"rec-{rid.lower()}",
                content=content,
                record_id=rid,
                record_type=rtype,
                title=title,
                chapter=chapter,
                section=title,
                region_id=_detect_region(body),
                evidence_quality=classify_evidence_quality(rtype, body),
                risk_level=_detect_risk_level(body),
            )
        )
        spans.append((start, end))

    return chunks, spans


# ─────────────────────────────────────────────────────────────────────────
# Tier 3 — table rows (monitoring data + field notes)
# ─────────────────────────────────────────────────────────────────────────

_TABLE_ROW_ID = re.compile(r"\b(WS-\d+|SV-\d+)\b")
_FIELD_NOTE = re.compile(
    r"(?P<label>Field Note FN-[AB]|Laboratory Note LAB-C)[,.]?\s*(?P<body>.+?)(?=(?:Field Note FN-[AB]|Laboratory Note LAB-C|\n#|\Z))",
    re.DOTALL,
)


def _extract_table_rows(markdown: str, chapters: list[tuple[int, str]]) -> list[Chunk]:
    """One chunk per monitoring row so a single reading stays retrievable.

    WS-03's 2026-06-14 reading is the measurement that corroborates INC-005;
    burying it inside a whole-table chunk makes it unfindable.
    """
    chunks: list[Chunk] = []
    seen: set[str] = set()

    for line in markdown.splitlines():
        if not line.strip().startswith("|"):
            continue
        ids = _TABLE_ROW_ID.findall(line)
        if not ids:
            continue
        rid = ids[0]
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue

        key = f"{rid}|{'|'.join(cells[:4])}"
        if key in seen:
            continue
        seen.add(key)

        date = next((c for c in cells if re.fullmatch(r"\d{4}-\d{2}-\d{2}", c)), None)
        body = " · ".join(c for c in cells if c)
        label = "Water monitoring reading" if rid.startswith("WS") else "Wildlife survey record"
        content = f"[{rid}] {label}\n\n{body}"

        low_confidence = "low" in [c.lower() for c in cells]
        chunks.append(
            Chunk(
                chunk_id=f"row-{rid.lower()}-{_slug(date or str(len(seen)))}",
                content=content,
                record_id=rid,
                record_type="monitoring",
                title=f"{rid} {label}",
                chapter="14 · Research Records and Monitoring Data",
                section=label,
                region_id=_detect_region(body),
                evidence_quality="disputed report" if low_confidence else "verified observation",
                record_date=date,
            )
        )

    return chunks


def _extract_field_notes(markdown: str) -> list[Chunk]:
    """FN-A / FN-B / LAB-C — the planted contradiction set (corpus §14.3).

    Each is indexed separately so retrieval can surface all three side by
    side; merging them would hide the disagreement the corpus expects us to
    show.
    """
    chunks: list[Chunk] = []
    for m in _FIELD_NOTE.finditer(markdown):
        label = m.group("label")
        rid_match = re.search(r"(FN-[AB]|LAB-C)", label)
        if not rid_match:
            continue
        rid = rid_match.group(1)
        body = " ".join(m.group("body").split())
        if len(body) < 40:
            continue
        date = re.search(r"\d{4}-\d{2}-\d{2}", body)
        chunks.append(
            Chunk(
                chunk_id=f"note-{rid.lower()}",
                content=f"[{rid}] {label}\n\n{body}",
                record_id=rid,
                record_type="field_note",
                title=label,
                chapter="14 · Research Records and Monitoring Data",
                section="14.3 Conflicting Field Notes",
                region_id=_detect_region(body),
                evidence_quality="disputed report",
                record_date=date.group(0) if date else None,
            )
        )
    return chunks


# ─────────────────────────────────────────────────────────────────────────
# Tier 2 — narrative chunks
# ─────────────────────────────────────────────────────────────────────────


def _extract_narrative(
    markdown: str, consumed: list[tuple[int, int]], chapters: list[tuple[int, str]]
) -> list[Chunk]:
    """Everything not already claimed by a record, split on headings."""
    consumed_sorted = sorted(consumed)
    gaps: list[tuple[int, int]] = []
    cursor = 0
    for start, end in consumed_sorted:
        if start > cursor:
            gaps.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < len(markdown):
        gaps.append((cursor, len(markdown)))

    chunks: list[Chunk] = []
    for gstart, gend in gaps:
        segment = markdown[gstart:gend]
        if len(segment.strip()) < 200:
            continue

        # Split the gap on its own headings so sections stay whole.
        boundaries = [h.start() for h in _ANY_HEADING.finditer(segment)]
        boundaries = [0] + [b for b in boundaries if b > 0] + [len(segment)]

        for i in range(len(boundaries) - 1):
            piece = segment[boundaries[i] : boundaries[i + 1]].strip()
            if len(piece) < 200:
                continue

            abs_off = gstart + boundaries[i]
            chapter = _chapter_at(abs_off, chapters)
            heading = piece.splitlines()[0].lstrip("# ").strip()

            for j, window in enumerate(_pack(piece)):
                chunks.append(
                    Chunk(
                        chunk_id=f"nar-{_slug(chapter or 'general')}-{_slug(heading)}-{i}-{j}",
                        content=window,
                        record_type="narrative",
                        title=heading,
                        chapter=chapter,
                        section=heading,
                        region_id=_detect_region(window),
                        evidence_quality=classify_evidence_quality("narrative", window),
                    )
                )
    return chunks


def _pack(text: str) -> list[str]:
    """Pack a long section into overlapping windows on paragraph bounds."""
    if len(text) <= _NARRATIVE_MAX_CHARS:
        return [text]

    windows: list[str] = []
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    current = ""
    for para in paragraphs:
        if current and len(current) + len(para) + 2 > _NARRATIVE_MAX_CHARS:
            windows.append(current.strip())
            current = current[-_NARRATIVE_OVERLAP_CHARS:] + "\n\n" + para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current.strip():
        windows.append(current.strip())
    return windows


# ─────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────


def parse_corpus(path: str | Path) -> list[Chunk]:
    """Parse the Pandora corpus markdown into record-aware chunks."""
    markdown = Path(path).read_text(encoding="utf-8")
    chapters = _chapter_index(markdown)

    records, spans = _extract_records(markdown, chapters)
    rows = _extract_table_rows(markdown, chapters)
    notes = _extract_field_notes(markdown)
    narrative = _extract_narrative(markdown, spans, chapters)

    # Drop narrative fragments that are a bare heading with no body (e.g. a
    # "Fauna Quick Index" signpost). Record, monitoring, and field-note
    # chunks are never dropped — a WS-* row is legitimately ~120 chars and
    # is exactly the kind of evidence we must keep independently retrievable.
    narrative = [c for c in narrative if len(_body_of(c.content)) >= 100]

    all_chunks = records + rows + notes + narrative

    # chunk_id is the index key — collisions would silently drop content.
    seen: dict[str, int] = {}
    for c in all_chunks:
        if c.chunk_id in seen:
            seen[c.chunk_id] += 1
            c.chunk_id = f"{c.chunk_id}-{seen[c.chunk_id]}"
        else:
            seen[c.chunk_id] = 0

    return all_chunks


def summarise(chunks: list[Chunk]) -> dict[str, int]:
    """Counts by record_type — used by the seed script's assertions."""
    out: dict[str, int] = {}
    for c in chunks:
        out[c.record_type] = out.get(c.record_type, 0) + 1
    out["_total"] = len(chunks)
    return out

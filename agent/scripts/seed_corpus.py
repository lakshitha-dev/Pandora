"""Seed the Pandora knowledge corpus into Azure AI Search.

    python scripts/seed_corpus.py             # parse, embed, index
    python scripts/seed_corpus.py --dry-run   # parse only, no API calls
    python scripts/seed_corpus.py --recreate  # rebuild the index first

Asserts the expected record inventory rather than trusting the parser
silently: 132 record chunks across nine prefixes, plus monitoring rows and
the three conflicting field notes. A miscount here means the chunker broke,
and a broken chunker is invisible until retrieval quality quietly collapses.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.core.llm import embed_texts  # noqa: E402
from app.ingestion.parse import RECORD_TYPES, parse_corpus, summarise  # noqa: E402
from app.ingestion.search_index import (  # noqa: E402
    chunk_to_document,
    document_count,
    ensure_index,
    upload,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
# The Azure SDK logs every request header at INFO; far too noisy here.
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# From SOLUTION.md §4.2 — the corpus's actual record inventory.
EXPECTED_RECORDS = {
    "region": 10,
    "settlement": 10,
    "fauna": 30,
    "flora": 20,
    "health": 12,
    "accommodation": 10,
    "incident": 10,
    "policy": 10,
    "knowledge_card": 20,
}
EXPECTED_RECORD_TOTAL = sum(EXPECTED_RECORDS.values())  # 132

# Records that must survive intact — the demo depends on every one of them.
CRITICAL_RECORDS = [
    "INC-001", "INC-002", "INC-005", "INC-007",
    "FAU-001", "FAU-003", "FAU-014", "FAU-018",
    "WS-01", "WS-03", "SV-101", "SV-102",
    "FN-A", "FN-B", "LAB-C",
    "POL-001", "POL-010", "KC-01", "REG-05", "MED-002",
]


def verify(chunks) -> list[str]:
    """Return a list of problems. Empty means the parse is sound."""
    problems: list[str] = []
    counts = Counter(c.record_type for c in chunks)

    for rtype, expected in EXPECTED_RECORDS.items():
        actual = counts.get(rtype, 0)
        if actual != expected:
            problems.append(f"{rtype}: expected {expected} records, got {actual}")

    by_id = {c.record_id: c for c in chunks if c.record_id}
    for rid in CRITICAL_RECORDS:
        if rid not in by_id:
            problems.append(f"critical record {rid} is missing")

    # Cross-record contamination: a record chunk must not contain another
    # record's provenance header. This is the failure §15.2 rule 3 forbids.
    import re

    for c in chunks:
        if not c.record_id or c.record_type == "narrative":
            continue
        others = set(re.findall(r"^\[([A-Z]{2,3}-\d+)\]", c.content, re.M)) - {c.record_id}
        if others:
            problems.append(f"{c.record_id} contaminated with {sorted(others)}")

    empty = [c.chunk_id for c in chunks if len(c.content.strip()) < 50]
    if empty:
        problems.append(f"{len(empty)} chunk(s) under 50 chars: {empty[:5]}")

    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description="Seed the Pandora corpus")
    ap.add_argument("--dry-run", action="store_true", help="parse and verify only")
    ap.add_argument("--recreate", action="store_true", help="rebuild the index first")
    args = ap.parse_args()

    s = get_settings()
    corpus = s.corpus_file
    if not corpus.exists():
        print(f"ERROR: corpus not found at {corpus}")
        return 1

    print(f"corpus : {corpus.name}  ({corpus.stat().st_size:,} bytes)")

    # ── parse ────────────────────────────────────────────────────────────
    t0 = time.perf_counter()
    chunks = parse_corpus(corpus)
    stats = summarise(chunks)
    print(f"parsed : {stats['_total']} chunks in {time.perf_counter() - t0:.2f}s\n")

    record_total = sum(stats.get(t, 0) for t in RECORD_TYPES.values())
    for rtype in sorted(stats):
        if rtype.startswith("_"):
            continue
        expected = EXPECTED_RECORDS.get(rtype)
        mark = "" if expected is None else ("  OK" if stats[rtype] == expected else f"  EXPECTED {expected}")
        print(f"  {rtype:18} {stats[rtype]:4}{mark}")
    print(f"  {'-' * 26}")
    print(f"  {'record chunks':18} {record_total:4}  (expected {EXPECTED_RECORD_TOTAL})")

    # ── verify ───────────────────────────────────────────────────────────
    problems = verify(chunks)
    if problems:
        print("\nFAILED verification:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"\nverification OK — {EXPECTED_RECORD_TOTAL} records intact, no cross-record contamination")

    if args.dry_run:
        print("\n--dry-run: stopping before embedding")
        return 0

    # ── index ────────────────────────────────────────────────────────────
    if args.recreate:
        print("\nrecreating index...")
        ensure_index(recreate=True)
    else:
        ensure_index(recreate=False)

    print(f"\nembedding {len(chunks)} chunks with {s.azure_openai_embedding_deployment}...")
    t0 = time.perf_counter()
    vectors = embed_texts(c.content for c in chunks)
    print(f"embedded in {time.perf_counter() - t0:.1f}s")

    print(f"\nuploading to index '{s.azure_search_index_name}'...")
    t0 = time.perf_counter()
    docs = [chunk_to_document(c, v) for c, v in zip(chunks, vectors)]
    n = upload(docs)
    print(f"uploaded {n} documents in {time.perf_counter() - t0:.1f}s")

    time.sleep(2)  # the count endpoint lags the upload slightly
    print(f"\nDONE — index now reports {document_count()} documents")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

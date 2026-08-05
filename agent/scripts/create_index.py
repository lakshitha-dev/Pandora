"""Create (or recreate) the Azure AI Search index.

    python scripts/create_index.py            # idempotent create/update
    python scripts/create_index.py --recreate # drop and rebuild

--recreate is needed whenever the field schema changes: Azure AI Search
cannot alter most field attributes in place.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.ingestion.search_index import (  # noqa: E402
    document_count,
    ensure_index,
    index_exists,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> int:
    ap = argparse.ArgumentParser(description="Create the Pandora knowledge index")
    ap.add_argument("--recreate", action="store_true", help="drop and rebuild the index")
    args = ap.parse_args()

    s = get_settings()
    print(f"endpoint : {s.azure_search_endpoint}")
    print(f"index    : {s.azure_search_index_name}")
    print(f"vector   : {s.embedding_dimensions}-d HNSW cosine")

    existed = index_exists()
    if existed and not args.recreate:
        print(f"\nindex already exists with {document_count()} documents")
        print("running create_or_update (no-op if the schema is unchanged)")

    ensure_index(recreate=args.recreate)

    print(f"\nOK — index '{s.azure_search_index_name}' ready, {document_count()} documents")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

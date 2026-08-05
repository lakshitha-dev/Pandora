"""Measure the vector-similarity gap between in-corpus and out-of-corpus questions.

The honest-refusal path cannot rest on the model choosing to emit the mandated
sentence — the Layer 1 gate caught it citing six Pandora records to justify a
refusal about Microsoft stock. The fix has to be deterministic, like the
GroundingGate. This script supplies the number that fix thresholds on.

RRF `@search.score` from the hybrid query is rank-based (~0.016-0.03) and says
nothing about absolute relevance, so it cannot be used. A *pure vector* query
returns a real similarity instead. This measures both populations and prints
the separation, so RELEVANCE_FLOOR is chosen from data rather than guessed.

    python -m scripts.measure_relevance_floor
"""

from __future__ import annotations

import statistics

from azure.search.documents.models import VectorizedQuery

from app.core.llm import embed_query
from app.ingestion.search_index import search_client

IN_CORPUS = [
    "What are the possible causes of unusual changes in Pandora's ocean color?",
    "Which marine species are most vulnerable to water contamination?",
    "What immediate actions should guardians take after detecting coral damage?",
    "Compare the recommended responses for water contamination and coral damage.",
    "What traditional community practices can support marine conservation?",
    "Summarize the major environmental threats mentioned across the corpus.",
    "Which areas should receive emergency attention first?",
    "What are the immediate steps when water changes color near Awa Reef?",
    "Compare Reef Cut Infection and Marine Sting Reaction.",
    "What should we do about a Deepbell stranding?",
    "What does the water station WS-03 reading show?",
    "What is the W3 water incident classification?",
]

OUT_OF_CORPUS = [
    "Should I buy Microsoft stock?",
    "What is the capital of France?",
    "How do I write a for loop in Python?",
    "What were the causes of the First World War?",
    "Give me a recipe for chocolate chip cookies.",
    "What is the best treatment for a human migraine?",
    "How does a diesel engine work?",
    "Who won the 2022 football World Cup?",
]


def top_vector_score(question: str) -> float:
    """Best pure-vector similarity for a question, ignoring the BM25 leg."""
    vq = VectorizedQuery(
        vector=embed_query(question), k_nearest_neighbors=5, fields="content_vector"
    )
    results = search_client().search(
        search_text=None, vector_queries=[vq], select=["chunk_id"], top=5
    )
    scores = [float(r.get("@search.score", 0.0)) for r in results]
    return max(scores) if scores else 0.0


def main() -> None:
    print("Measuring top pure-vector similarity per question.\n")

    rows: dict[str, list[float]] = {}
    for label, questions in (("IN-CORPUS", IN_CORPUS), ("OUT-OF-CORPUS", OUT_OF_CORPUS)):
        print(f"=== {label} " + "=" * (60 - len(label)))
        scores = []
        for q in questions:
            s = top_vector_score(q)
            scores.append(s)
            print(f"  {s:.4f}  {q[:66]}")
        rows[label] = scores
        print(f"  -> min {min(scores):.4f}  mean {statistics.mean(scores):.4f}  max {max(scores):.4f}\n")

    lo_in = min(rows["IN-CORPUS"])
    hi_out = max(rows["OUT-OF-CORPUS"])

    print("=" * 70)
    print(f"  lowest in-corpus   : {lo_in:.4f}")
    print(f"  highest out-corpus : {hi_out:.4f}")
    if lo_in > hi_out:
        floor = round((lo_in + hi_out) / 2, 3)
        print(f"  SEPARATED by {lo_in - hi_out:.4f} -> RELEVANCE_FLOOR = {floor}")
    else:
        print("  OVERLAP — a single threshold cannot separate these populations.")
        print("  A vector floor alone is not sufficient; needs a second signal.")


if __name__ == "__main__":
    main()

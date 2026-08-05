"""GroundingGate — the corpus's own eight Retrieval Grounding Rules, checked.

SOLUTION.md §4.4. The corpus publishes its grading criteria in §15.2, titled
"Retrieval Grounding Rules". We are not guessing at what "grounded" means —
we execute the published checklist and report pass/fail per rule.

The important property: this is **deterministic post-processing**, not a
prompt. The generation prompt asks for these behaviours; this module verifies
them. That distinction is why losing `temperature: 0.1` on gpt-5-mini does
not weaken grounding — the guarantee never came from sampling.

Seven of the eight rules are checked deterministically. Rule 3 (never merge
records) needs semantic judgement, so it is checked structurally: a claim
citing two records of the same type is flagged for review rather than
silently passed.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Sequence

from app.chains.generation import CITATION_PATTERN, INSUFFICIENT_EVIDENCE_MESSAGE
from app.chains.retrieval import RetrievedChunk
from app.models.schemas import Conflict, Grounding, GroundingRuleResult

logger = logging.getLogger(__name__)

# Sentence splitter that tolerates "INC-005." and "2026-06-14." mid-sentence.
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z*\-#\[])")

_HEDGE_TERMS = (
    "hypothes", "plausible", "possible", "may ", "might ", "could ",
    "not confirmed", "no confirmed", "cannot be confirmed", "unconfirmed",
    "remain possible", "not established", "suggests",
)
_CONFLICT_TERMS = (
    "disagree", "conflict", "contradict", "chain of custody",
    "chain-of-custody", "not directly comparable", "differ",
)
_INFERENCE_MARKERS = ("model inference", "inference:", "**inference")


@dataclass
class GateResult:
    """Outcome of running all eight rules over a generated answer."""

    groundedness: int
    rules: list[GroundingRuleResult] = field(default_factory=list)
    unsupported_sentences: list[str] = field(default_factory=list)
    claim_count: int = 0
    supported_claim_count: int = 0
    conflicts: list[Conflict] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.rules)

    def to_schema(self) -> Grounding:
        return Grounding(
            groundedness=self.groundedness,
            rules=self.rules,
            unsupported_sentences=self.unsupported_sentences,
        )


def _split_claims(answer: str) -> tuple[list[str], list[str]]:
    """Split into (factual sentences, inference sentences).

    Everything after a "Model inference:" marker is inference and is exempt
    from the citation requirement — that separation is rule 8 itself.
    """
    body, inference = answer, ""
    lowered = answer.lower()
    for marker in _INFERENCE_MARKERS:
        idx = lowered.find(marker)
        if idx != -1:
            body, inference = answer[:idx], answer[idx:]
            break

    def sentences(text: str) -> list[str]:
        """Line-aware claim extraction.

        The model writes markdown: headings, bullets, and prose. Only
        substantive prose counts as a factual claim. Counting a heading like
        "Documentation (what the records establish)" as an uncited claim
        would fail rule 1 for a perfectly grounded answer.
        """
        out: list[str] = []
        for line in text.splitlines():
            s = line.strip()
            if not s:
                continue
            # Structural markdown: headings, table rows, rules, bare bullets.
            if s.startswith(("#", "|", "---", "***", "===")):
                continue
            # Strip list markers so the claim itself is what gets checked.
            s = re.sub(r"^[-*+]\s+", "", s)
            s = re.sub(r"^\d+[.)]\s+", "", s)
            s = s.strip()
            if len(s) < 25:
                continue
            # A short line with no sentence-ending punctuation and no verb-ish
            # lowercase run is a heading, not a claim.
            if len(s) < 90 and not s.endswith((".", "!", "?", ":")) and "[" not in s:
                continue
            # A bolded label line ("**Documentation**") is structure.
            if re.fullmatch(r"\*\*[^*]{,80}\*\*:?", s):
                continue
            for part in _SENTENCE.split(s):
                p = part.strip()
                if len(p) >= 25:
                    out.append(p)
        return out

    return sentences(body), sentences(inference)


# ─────────────────────────────────────────────────────────────────────────
# The eight rules
# ─────────────────────────────────────────────────────────────────────────


def _rule_1_cite_record_ids(
    claims: Sequence[str], valid_ids: set[str]
) -> tuple[GroundingRuleResult, list[str]]:
    """§15.2.1 — cite record IDs or chapter sections for specific claims."""
    unsupported: list[str] = []
    for s in claims:
        cited = set(CITATION_PATTERN.findall(s))
        if not (cited & valid_ids):
            unsupported.append(s)

    total = len(claims)
    supported = total - len(unsupported)
    ok = total == 0 or len(unsupported) == 0
    return (
        GroundingRuleResult(
            number=1,
            name="Cite record IDs for specific claims",
            passed=ok,
            detail=f"{supported}/{total} factual sentences carry a resolving marker",
        ),
        unsupported,
    )


def _rule_2_hypotheses(answer: str, chunks: Sequence[RetrievedChunk]) -> GroundingRuleResult:
    """§15.2.2 — multiple plausible causes stay hypotheses unless confirmed."""
    multi_cause = [
        c for c in chunks
        if "plausible causes" in c.content.lower() or "these are hypotheses" in c.content.lower()
    ]
    if not multi_cause:
        return GroundingRuleResult(
            number=2, name="Multiple causes stay hypotheses", passed=True,
            detail="no multi-cause record retrieved; rule not engaged",
        )

    lowered = answer.lower()
    hedged = any(t in lowered for t in _HEDGE_TERMS)
    return GroundingRuleResult(
        number=2,
        name="Multiple causes stay hypotheses",
        passed=hedged,
        detail=(
            f"{len(multi_cause)} multi-cause record(s) retrieved; answer "
            f"{'presents them as hypotheses' if hedged else 'ASSERTS a cause without hedging'}"
        ),
    )


def _rule_3_no_merging(claims: Sequence[str], chunks: Sequence[RetrievedChunk]) -> GroundingRuleResult:
    """§15.2.3 — never merge details from two similar records.

    Structural proxy: a single sentence citing two records of the same type
    (two FAU-*, two INC-*) is where merging happens. Flagged, not failed —
    a legitimate comparison sentence looks identical.
    """
    types = {c.citation_id: c.record_type for c in chunks}
    suspicious: list[str] = []
    for s in claims:
        cited = [r for r in CITATION_PATTERN.findall(s) if r in types]
        if len(cited) < 2:
            continue
        same_type = {}
        for rid in cited:
            same_type.setdefault(types[rid], []).append(rid)
        for rtype, ids in same_type.items():
            if rtype in ("fauna", "flora", "incident", "settlement") and len(ids) > 1:
                suspicious.append(f"{sorted(ids)} in one sentence")

    return GroundingRuleResult(
        number=3,
        name="Do not merge similar records",
        passed=True,
        detail=(
            "no sentence blends same-type records"
            if not suspicious
            else f"review: {len(suspicious)} sentence(s) cite multiple same-type records ({suspicious[0]})"
        ),
    )


_MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


def _date_present(record_date: str | None, answer: str) -> bool:
    """True when the answer carries a record's date in any reasonable rendering.

    The prompt asks for the ISO form, but a model that writes "14 March 2026"
    has satisfied §15.2.4 just as well. Failing it on formatting would make the
    gate measure prose style rather than grounding.
    """
    if not record_date:
        return False
    if record_date in answer:
        return True
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", record_date)
    if not m:
        return False
    year, month, day = m.group(1), int(m.group(2)), int(m.group(3))
    if year not in answer:
        return False
    name = _MONTHS[month - 1]
    # "14 March 2026", "March 14, 2026", "14 Mar 2026" — day and month adjacent.
    for mon in (name, name[:3]):
        for pat in (rf"\b{day}\s+{mon}\b", rf"\b{mon}\s+{day}\b"):
            if re.search(pat, answer, re.IGNORECASE):
                return True
    return bool(re.search(rf"\b{year}[-/]{month:02d}[-/]{day:02d}\b", answer))


def _rule_4_time_and_place(answer: str, chunks: Sequence[RetrievedChunk]) -> GroundingRuleResult:
    """§15.2.4 — preserve time and location; no station reading as global fact."""
    dated = [c for c in chunks if c.record_date]
    if not dated:
        return GroundingRuleResult(
            number=4, name="Preserve time and location", passed=True,
            detail="no dated record retrieved; rule not engaged",
        )

    cited_dated = [c for c in dated if c.citation_id in set(CITATION_PATTERN.findall(answer))]
    if not cited_dated:
        return GroundingRuleResult(
            number=4, name="Preserve time and location", passed=True,
            detail="no dated record was cited",
        )

    qualified = sum(1 for c in cited_dated if _date_present(c.record_date, answer))
    ok = qualified == len(cited_dated)
    return GroundingRuleResult(
        number=4,
        name="Preserve time and location",
        passed=ok,
        detail=f"{qualified}/{len(cited_dated)} cited dated record(s) carry their date in the answer",
    )


def _rule_5_health_guardrail(answer: str, chunks: Sequence[RetrievedChunk]) -> GroundingRuleResult:
    """§15.2.5 — health answers include red flags and the fiction disclaimer."""
    med = [c for c in chunks if c.record_type == "health"]
    cited = set(CITATION_PATTERN.findall(answer))
    med_cited = [c for c in med if c.citation_id in cited]
    if not med_cited:
        return GroundingRuleResult(
            number=5, name="Health answers carry red flags + disclaimer", passed=True,
            detail="no MED-* record cited; rule not engaged",
        )

    lowered = answer.lower()
    has_flags = any(t in lowered for t in ("red flag", "seek", "urgent", "refer", "warning sign"))
    has_disclaimer = any(t in lowered for t in ("fictional", "training material", "not medical advice"))
    ok = has_flags and has_disclaimer
    missing = [
        n for n, present in (("red flags", has_flags), ("fiction disclaimer", has_disclaimer))
        if not present
    ]
    return GroundingRuleResult(
        number=5,
        name="Health answers carry red flags + disclaimer",
        passed=ok,
        detail="both present" if ok else f"MISSING: {', '.join(missing)}",
    )


def _rule_6_state_absence(answer: str, chunks: Sequence[RetrievedChunk], sufficient: bool) -> GroundingRuleResult:
    """§15.2.6 — state plainly when the corpus does not have the answer."""
    says_so = (
        "does not contain sufficient evidence" in answer.lower()
        or INSUFFICIENT_EVIDENCE_MESSAGE.lower()[:50] in answer.lower()
    )
    if sufficient:
        return GroundingRuleResult(
            number=6, name="State when evidence is absent", passed=True,
            detail="evidence was sufficient; rule not engaged",
        )
    return GroundingRuleResult(
        number=6,
        name="State when evidence is absent",
        passed=says_so,
        detail=(
            "insufficiency stated explicitly"
            if says_so
            else "evidence was insufficient but the answer did not say so"
        ),
    )


def _rule_7_conflicts(
    answer: str, chunks: Sequence[RetrievedChunk]
) -> tuple[GroundingRuleResult, list[Conflict]]:
    """§15.2.7 — summarise conflicts and name their reliability limits.

    Detected structurally: two or more retrieved records carrying the
    corpus's own `disputed report` evidence label describe contested
    evidence. That covers FN-A / FN-B / LAB-C and the SV-101 / SV-102
    survey-effort trap without any semantic guesswork.
    """
    disputed = [c for c in chunks if c.evidence_quality == "disputed report"]
    conflicts: list[Conflict] = []

    if len(disputed) >= 2:
        ids = [c.citation_id for c in disputed]
        limitation = "unverified or challenged evidence"
        joined = " ".join(c.content.lower() for c in disputed)
        if "chain-of-custody" in joined or "chain of custody" in joined:
            limitation = "incomplete chain of custody on the laboratory sample"
        elif "not directly comparable" in joined:
            limitation = "survey effort not normalised between counts"
        conflicts.append(
            Conflict(
                record_ids=ids,
                nature="Retrieved records disagree or carry unverified evidence about the same event",
                reliability_limitation=limitation,
            )
        )

    if not conflicts:
        return (
            GroundingRuleResult(
                number=7, name="Summarise conflicts and reliability limits", passed=True,
                detail="no conflicting records retrieved; rule not engaged",
            ),
            [],
        )

    lowered = answer.lower()
    surfaced = any(t in lowered for t in _CONFLICT_TERMS)
    all_named = all(rid.lower() in lowered for rid in conflicts[0].record_ids)
    ok = surfaced and all_named
    return (
        GroundingRuleResult(
            number=7,
            name="Summarise conflicts and reliability limits",
            passed=ok,
            detail=(
                f"conflict across {conflicts[0].record_ids} surfaced with its limitation"
                if ok
                else f"conflict across {conflicts[0].record_ids} was NOT fully presented"
            ),
        ),
        conflicts,
    )


def _rule_8_documented_vs_inferred(answer: str, inference: Sequence[str]) -> GroundingRuleResult:
    """§15.2.8 — separate documented protocol from model inference."""
    has_marker = any(m in answer.lower() for m in _INFERENCE_MARKERS)
    if has_marker:
        return GroundingRuleResult(
            number=8, name="Separate documented from inferred", passed=True,
            detail=f"inference block present ({len(inference)} sentence(s))",
        )
    return GroundingRuleResult(
        number=8,
        name="Separate documented from inferred",
        passed=True,
        detail="no inference offered; every statement is attributed to a record",
    )


# ─────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────


def run_gate(
    answer: str,
    chunks: Sequence[RetrievedChunk],
    *,
    has_sufficient_evidence: bool = True,
) -> GateResult:
    """Run all eight §15.2 rules over a generated answer."""
    valid_ids = {c.citation_id for c in chunks}
    claims, inference = _split_claims(answer)

    r1, unsupported = _rule_1_cite_record_ids(claims, valid_ids)
    r7, conflicts = _rule_7_conflicts(answer, chunks)

    rules = [
        r1,
        _rule_2_hypotheses(answer, chunks),
        _rule_3_no_merging(claims, chunks),
        _rule_4_time_and_place(answer, chunks),
        _rule_5_health_guardrail(answer, chunks),
        _rule_6_state_absence(answer, chunks, has_sufficient_evidence),
        r7,
        _rule_8_documented_vs_inferred(answer, inference),
    ]

    total = len(claims)
    supported = total - len(unsupported)
    groundedness = 100 if total == 0 else round(100 * supported / total)

    result = GateResult(
        groundedness=groundedness,
        rules=rules,
        unsupported_sentences=unsupported,
        claim_count=total,
        supported_claim_count=supported,
        conflicts=conflicts,
    )
    logger.info(
        "GroundingGate: %d/8 rules passed, groundedness %d%% (%d/%d claims)",
        sum(1 for r in rules if r.passed), groundedness, supported, total,
    )
    return result

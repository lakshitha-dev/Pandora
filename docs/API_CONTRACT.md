# API_CONTRACT.md

**The contract between frontend, backend, and agent service.** Frozen at kickoff.

> **This file is shared property.** Don't change it alone — propose in the team channel, get a 👍,
> then edit. Nipuna, Manujaya, and Lakshitha all build against it simultaneously.
>
> **Two things are frozen hardest:** the `situation_report` shape (§1.1) and the SSE event schema
> (§1.2). New SSE event types are **additive only** — never removed, never renamed. An unknown event
> type must be ignored by the client, never crash it.

---

## Conventions

| | |
|---|---|
| **Base URL (public)** | `https://<app>.azurewebsites.net` · local: `http://localhost:5000` |
| **Base URL (internal)** | Agent service, local: `http://localhost:8000` — **never called from the browser** |
| **Auth** | `Authorization: Bearer <supabase-jwt>` on every public endpoint |
| **JSON casing** | `snake_case` everywhere, both services |
| **Corpus record IDs** | Verbatim from the corpus, **never re-cased** — `INC-005`, `FAU-014`, `WS-03`, `REG-01`, `FN-A` |
| **Timestamps** | ISO 8601 UTC — `2026-08-05T14:23:00Z` |
| **IDs** | UUID v4 strings |
| **Content type** | `application/json`, except document upload (`multipart/form-data`) and the SSE stream (`text/event-stream`) |

### Error envelope — every non-2xx response

```json
{
  "error": {
    "code": "document_not_found",
    "message": "No document exists with id 3f2a...",
    "details": null
  }
}
```

| Status | `code` values |
|---|---|
| 400 | `invalid_request`, `unsupported_file_type`, `file_too_large` |
| 401 | `unauthenticated` |
| 403 | `forbidden`, `corpus_document_immutable` |
| 404 | `document_not_found`, `report_not_found` |
| 409 | `document_already_indexing` |
| 422 | `corpus_not_indexed` |
| 500 | `internal_error` |
| 502 | `agent_service_unavailable` |
| 504 | `agent_service_timeout` |

> ⚠️ **Insufficient evidence is a `200`, never an error.** A report that honestly declines to answer
> is a *successful* response with `has_sufficient_evidence: false`. Do not map it to 4xx — the UI
> must render it as an ordinary report, not an error state. This is a scoring moment (`SOLUTION.md`
> §4.6).

---

# Part 1 — Public API

Exposed by the **FastAPI backend gateway**. Consumed by the **frontend**.

---

## 1.1 Ask a question

The core endpoint. Returns a grounded **Situation Report** with six sections, its citations, and its
confidence.

### `POST /api/v1/ask`

**Request**

```json
{
  "question": "The water near Awa Reef has turned turquoise and the fish are leaving the area.",
  "conversation_id": "9c1e4b2a-0000-4a1b-9f3e-2d5c8a7b1234",
  "document_ids": null,
  "role_lens": "guardian"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `question` | string | ✅ | 1–2000 chars. A natural-language situation description, not keywords. |
| `conversation_id` | uuid \| null | — | Omit/null to start a new conversation |
| `document_ids` | uuid[] \| null | — | Restrict search to these documents; null = the whole index including the preloaded corpus |
| `role_lens` | enum \| null | — | `guardian` (default) \| `researcher` \| `citizen`. **Initial render only** — the toggle re-renders client-side and never re-calls this endpoint. |

**Response `200`**

```json
{
  "answer_id": "7b3d9f1c-1111-4c2d-8e4f-6a9b3c5d7e01",
  "conversation_id": "9c1e4b2a-0000-4a1b-9f3e-2d5c8a7b1234",
  "situation_report": {
    "priority": {
      "class": "W3",
      "label": "EMERGENCY",
      "reason": "Fish avoidance and water discolouration with offshore movement reported.",
      "citation": "§4.5 Water Incident Classification",
      "page": 12
    },
    "affected_region_ids": ["REG-01"],
    "assembly_mode": "sitrep",
    "sections": [
      {
        "section_type": "affected_species",
        "owning_agent": "marine_life_protector",
        "status": "filled",
        "empty_reason": null,
        "content": "**FAU-001 Tideglass Grazer** — juveniles are documented as vulnerable to turbidity in shallow shelf habitat [FAU-001 p.11]. **FAU-002 Ribbonfin Skimmer** — recorded as sensitive to surface oil films [FAU-002 p.11].",
        "claim_count": 2,
        "supported_claim_count": 2,
        "duration_ms": 2610,
        "display_order": 2
      },
      {
        "section_type": "likely_causes",
        "owning_agent": "incident_investigator",
        "status": "filled",
        "empty_reason": null,
        "content": "**No cause is established.** Three records make incompatible claims about this event and the corpus does not resolve them [FN-A p.47] [FN-B p.47] [LAB-C p.47]. `INC-001` lists four plausible causes without confirming any: mineral sediment, plankton bloom, chemical release, and light reflection [INC-001 p.40].\n\n_Model inference:_ documented resampling per checklist `A.1` would be required to distinguish these.",
        "claim_count": 3,
        "supported_claim_count": 3,
        "duration_ms": 3180,
        "display_order": 3
      },
      {
        "section_type": "recommended_actions",
        "owning_agent": "emergency_responder",
        "status": "filled",
        "empty_reason": null,
        "content": "1. Record observations and collect samples upstream and downstream [INC-001 p.40].\n2. Restrict sensitive water use pending results [§4.5 p.12].\n3. Issue a public update naming the cause as **not yet confirmed** [POL-010 p.46].",
        "claim_count": 3,
        "supported_claim_count": 3,
        "duration_ms": 2890,
        "display_order": 4
      }
    ],
    "confidence": {
      "level": "moderate",
      "reason": "Moderate — 3 sources, 1 unresolved conflict, chain of custody incomplete",
      "groundedness": 96
    },
    "conflicts": [
      {
        "record_ids": ["FN-A", "FN-B", "LAB-C"],
        "conflict_nature": "Three records propose incompatible causes for the same colour change at Awa Reef.",
        "positions": [
          {
            "record_id": "FN-A",
            "claim": "Plankton bloom; began after three calm hot days; no chemical odor.",
            "evidence_quality": "disputed_report",
            "reliability_limitation": "Interpretation only; no chemical sampling performed."
          },
          {
            "record_id": "FN-B",
            "claim": "Upstream pigment workshop maintenance; damaged waste container observed.",
            "evidence_quality": "disputed_report",
            "reliability_limitation": "Entry of material into the water was never confirmed."
          },
          {
            "record_id": "LAB-C",
            "claim": "Elevated harmless carbonate particles and moderate plankton density.",
            "evidence_quality": "disputed_report",
            "reliability_limitation": "Sample chain-of-custody form incomplete."
          }
        ],
        "resolution_recommendation": "Documented resampling per checklist A.1 — Water Investigation."
      }
    ],
    "was_partial": false
  },
  "citations": [
    {
      "marker": 1,
      "document_id": "1a2b3c4d-2222-4e5f-9a8b-7c6d5e4f3a2b",
      "document_name": "Pandora_RAG_Knowledge_2026.pdf",
      "chunk_id": "1a2b3c4d-chunk-0031",
      "record_id": "INC-001",
      "record_type": "incident",
      "title": "Turquoise Water Event",
      "chapter": "12 · Environmental Threats and Emergency Response",
      "section": "Plausible causes",
      "page": 40,
      "region_id": "REG-01",
      "excerpt": "Plausible causes include mineral sediment, plankton bloom, chemical release, or light reflection. No single cause has been confirmed.",
      "relevance_score": 0.94,
      "rerank_score": 9.4,
      "evidence_quality": "provisional_interpretation",
      "risk_level": "high",
      "record_date": null,
      "section_types": ["likely_causes", "recommended_actions"]
    },
    {
      "marker": 2,
      "document_id": "1a2b3c4d-2222-4e5f-9a8b-7c6d5e4f3a2b",
      "document_name": "Pandora_RAG_Knowledge_2026.pdf",
      "chunk_id": "1a2b3c4d-chunk-0164",
      "record_id": "LAB-C",
      "record_type": "field_note",
      "title": "Laboratory Note LAB-C",
      "chapter": "14 · Monitoring Data",
      "section": "14.3 Conflicting Field Notes",
      "page": 47,
      "region_id": "REG-01",
      "excerpt": "Detected elevated harmless carbonate particles and moderate plankton density, but the sample chain-of-custody form was incomplete.",
      "relevance_score": 0.88,
      "rerank_score": 8.8,
      "evidence_quality": "disputed_report",
      "risk_level": null,
      "record_date": "2026-06-05",
      "section_types": ["likely_causes"]
    }
  ],
  "has_sufficient_evidence": true,
  "llm_call_count": 6,
  "latency_ms": 5240
}
```

### Field reference

**Top level**

| Field | Type | Notes |
|---|---|---|
| `situation_report` | object | **Always present.** Every query produces one — see below. |
| `citations` | array | Deduplicated union across all sections. May be empty when `has_sufficient_evidence` is `false`. |
| `has_sufficient_evidence` | bool | `false` → render the honesty-flip state (§1.4) |
| `llm_call_count` | int | ≤ **8**, hard cap. Shown in the trace footer. |
| `latency_ms` | int | End to end |

**`situation_report`**

| Field | Type | Notes |
|---|---|---|
| `priority` | object | `class` (`W1`\|`W2`\|`W3`\|`W4`\|`informational`) · `label` · `reason` · `citation` · `page`. **`citation` is never null for a W-class** — an uncited severity is an ungrounded model opinion. |
| `affected_region_ids` | string[] | `REG-01` … `REG-10`. **Drives the map** — no separate endpoint. Empty array = map stays idle. |
| `assembly_mode` | enum | `sitrep` \| `focused` \| `compare` \| `single_agent_fallback` — which path produced this report |
| `sections` | array | The content sections. See below. |
| `confidence` | object | `level` (`high`\|`moderate`\|`low`\|`insufficient`) · `reason` (**required, human-readable**) · `groundedness` (int `0`–`100`) |
| `conflicts` | array | Empty when no conflict detected. Never merged into a single position. |
| `was_partial` | bool | `true` if any section timed out. **A partial report is a success, not an error.** |

**`situation_report.sections[]`**

| Field | Type | Notes |
|---|---|---|
| `section_type` | enum | `affected_species` \| `likely_causes` \| `recommended_actions` |
| `owning_agent` | enum | `marine_life_protector` \| `incident_investigator` \| `emergency_responder` \| `orchestrator` |
| `status` | enum | `filled` \| `empty` \| `timed_out` \| `not_applicable` |
| `empty_reason` | string \| null | **Non-null whenever `status != "filled"`.** e.g. *"No species records matched this query"*, *"Cause not established — 3 records conflict"* |
| `content` | string | Markdown. Inline citation markers are **record IDs in brackets** — `[INC-005]`, `[FAU-003 p.13]` — not integers. |
| `claim_count` / `supported_claim_count` | int | Section-level groundedness |
| `duration_ms` | int | Fill time; powers the trace |
| `display_order` | int | Fixed order: priority 1 · species 2 · causes 3 · actions 4 · sources 5 · confidence 6 |

> **Priority, Sources, and Confidence are *not* rows in `sections`.** They are the orchestrator's own
> fields — `priority`, the top-level `citations` array, and `confidence`. `sections` carries only the
> three specialist-owned content sections. This keeps the six-section *display* contract without
> duplicating data.

**Citation markers are record IDs, not integers.** `[INC-005]` resolves against
`citations[].record_id`. This is deliberate: the model cannot invent a plausible-looking `[7]`, and a
marker that fails to resolve is stripped by GroundingGate and its sentence marked unsupported.
`marker` remains as a stable integer for ordering source cards.

**Section independence is a hard guarantee.** One section failing never blanks the others. A report
with two of three content sections filled and the third honestly marked unavailable is a
**successful** report. Handle `status != "filled"` as a normal path, not an edge case.

**`evidence_quality`** — the corpus's own five-value taxonomy, carried verbatim (corpus page 2
instructs that RAG applications "should preserve these labels"):

`verified_observation` · `community_tradition` · `provisional_interpretation` · `modeled_estimate` · `disputed_report`

**Errors:** `401 unauthenticated` · `422 corpus_not_indexed` · `502 agent_service_unavailable` · `504 agent_service_timeout`

---

## 1.2 Stream the orchestration trace

**Wow feature 1 depends on this endpoint.** The trace is what makes the agentic architecture
*perceivable* — three orbs igniting at once, three sections filling out of order.

### `GET /api/v1/ask/stream`

`Content-Type: text/event-stream` · query params: `question` (required), `conversation_id`,
`document_ids` (repeatable), `role_lens`.

`EventSource` cannot set headers, so the JWT is passed as an `access_token` query param on this
endpoint only, and the gateway validates it identically. Same contract otherwise.

**The gateway MUST NOT buffer.** Events are forwarded to the browser as they arrive from the agent
service. Buffering defeats the purpose of the endpoint.

**Event frame**

```
event: section.completed
data: {"step_type":"section.completed","sequence_number":11,"duration_ms":2610,"payload":{...}}
```

Every event carries `step_type`, `sequence_number` (monotonic), `duration_ms`, and a `payload`.
The terminal event is always `answer.completed`, whose payload is the **complete §1.1 response body** —
so a client can use this endpoint alone and never call `POST /api/v1/ask`.

**Event types** *(mirrors `SOLUTION.md` §7.1 — additive only)*

| `step_type` | Payload carries | Displayed as |
|---|---|---|
| `query.received` | `question` | The raw question |
| `query.rewritten` | `variants[]` | Rewritten phrasings |
| `query.classified` | `use_case`, `severity_class`, `query_shape` | *Emergency Response · W3 · sitrep* |
| **`priority.classified`** | `class`, `label`, `reason`, `citation`, `page` | **Triage banner renders immediately** |
| **`map.zone_lit`** | `region_ids[]`, `priority_class` | **Map zone ignites** |
| `route.decided` | `mode`, `specialists[]`, `reason` | *"Incident indicators detected → sitrep mode → dispatching 3 specialists in parallel"* |
| `retrieval.started` | `agent`, `filters`, `k` | *"BM25 + vector, k=30, filter: record_type=incident"* |
| `retrieval.completed` | `candidate_count`, `kept_count`, `top_rerank_score` | *"38 candidates → reranked → top 6 · best score 9.4"* |
| `agent.thinking` | `agent`, `source_count`, `elapsed_ms` | *"🌊 Incident Investigator — analysing 6 sources… 1.8 s"* |
| **`section.filling`** | `section_type`, `owning_agent` | **A section begins streaming, badged with its agent** |
| **`section.completed`** | `section_type`, `claim_count`, `source_count`, `duration_ms` | **Section done** |
| **`section.unavailable`** | `section_type`, `empty_reason` | **Section honestly empty, with reason** |
| `agent.completed` | `agent`, `claim_count`, `source_count`, `duration_ms` | *"🚨 Emergency Responder — 3 claims, 5 sources · 2.9 s"* |
| `agent.timed_out` | `agent`, `section_type`, `elapsed_ms` | *"⏱ Marine-Life Protector timed out at 8 s — continuing with partial result"* |
| `conflict.detected` | `record_ids[]`, `conflict_nature` | *"⚠️ 3 records disagree on cause — FN-A / FN-B / LAB-C"* |
| `validation.running` | `rule_count` | *"Checking 8 grounding rules…"* |
| `validation.result` | `rules[]{number,name,passed,detail}`, `groundedness` | *"8/8 passed · groundedness 96%"* |
| `synthesis.started` | `input_count` | *"Synthesising 2 specialist reports"* (compare mode) |
| `answer.streaming` | `section_type`, `delta` | Tokens as generated |
| `answer.completed` | **the full §1.1 response body**, `llm_call_count`, `latency_ms` | *"5.2 s · 6 LLM calls · 11 sources"* |
| `error` | `code`, `message` | Terminal. Same codes as the error envelope. |

**Timeouts, retries, and partial results are emitted with equal prominence.** Showing a handled
failure builds more credibility with judges than hiding it — it proves the timeout logic is real.

**Client rules:** ignore unknown `step_type` values silently · treat `answer.completed` and `error`
as terminal · on connection drop, fall back to `POST /api/v1/ask` for the complete report.

---

## 1.3 Documents

The preloaded corpus appears in this list with `is_preloaded: true`.

### `GET /api/v1/documents`

Query params: `status` (`pending`\|`indexing`\|`indexed`\|`failed`) · `limit` (default 50) · `offset` (default 0)

**Response `200`**

```json
{
  "documents": [
    {
      "id": "1a2b3c4d-2222-4e5f-9a8b-7c6d5e4f3a2b",
      "file_name": "Pandora_RAG_Knowledge_2026.pdf",
      "content_type": "application/pdf",
      "size_bytes": 1284910,
      "page_count": 56,
      "chunk_count": 221,
      "record_count": 130,
      "status": "indexed",
      "is_preloaded": true,
      "error_message": null,
      "uploaded_at": "2026-08-05T09:14:22Z",
      "indexed_at": "2026-08-05T09:14:51Z"
    },
    {
      "id": "5e6f7a8b-3333-4b9c-8d1e-2f3a4b5c6d7e",
      "file_name": "obsidian-reach-survey-june.pdf",
      "content_type": "application/pdf",
      "size_bytes": 91200,
      "page_count": 9,
      "chunk_count": 18,
      "record_count": 0,
      "status": "indexing",
      "is_preloaded": false,
      "error_message": null,
      "uploaded_at": "2026-08-05T09:20:03Z",
      "indexed_at": null
    }
  ],
  "total": 2,
  "limit": 50,
  "offset": 0
}
```

`status`: `pending` → `indexing` → `indexed`, or `failed` (then `error_message` is non-null).
`record_count` is how many corpus-style records the chunker detected — `0` means it fell back to
narrative chunking, which is normal for an arbitrary uploaded document.

---

### `POST /api/v1/documents`

`Content-Type: multipart/form-data` · field `file` · max **10 MB** · PDF, DOCX, CSV, TXT.

Returns immediately with `status: "pending"`; indexing is async. Poll `GET /api/v1/documents/{id}`.

**Response `202`** — the same document object, `status: "pending"`, counts null.

**Errors:** `400 unsupported_file_type` · `400 file_too_large` · `401 unauthenticated`

---

### `GET /api/v1/documents/{id}`

Single document, same object shape. Poll this for indexing progress.
**Errors:** `404 document_not_found`

---

### `DELETE /api/v1/documents/{id}`

Deletes the document, its Postgres metadata, and its vectors from Azure AI Search.

**Response `204`** (no body)
**Errors:** `404 document_not_found` · `409 document_already_indexing` ·
**`403 corpus_document_immutable`** — the preloaded corpus cannot be deleted. It's the demo.

---

## 1.4 The insufficient-evidence response

Not a separate endpoint — the same `200` from §1.1 with `has_sufficient_evidence: false`. Documented
separately because **getting it right is worth marks** and the wording is mandated by the brief.

```json
{
  "answer_id": "8c4e0a2d-4444-4d3e-9f5a-7b8c9d0e1f23",
  "conversation_id": "9c1e4b2a-0000-4a1b-9f3e-2d5c8a7b1234",
  "situation_report": {
    "priority": {
      "class": "informational",
      "label": "OBSERVATION",
      "reason": "No incident indicators detected in the available evidence.",
      "citation": null,
      "page": null
    },
    "affected_region_ids": [],
    "assembly_mode": "sitrep",
    "sections": [
      {
        "section_type": "affected_species",
        "owning_agent": "marine_life_protector",
        "status": "empty",
        "empty_reason": "No species records matched this query.",
        "content": "",
        "claim_count": 0,
        "supported_claim_count": 0,
        "duration_ms": 420,
        "display_order": 2
      }
    ],
    "confidence": {
      "level": "insufficient",
      "reason": "Insufficient — no record scored above the relevance threshold",
      "groundedness": 0
    },
    "conflicts": [],
    "was_partial": false
  },
  "insufficient_evidence": {
    "banner": "⚠ Insufficient Evidence — Recommend Field Investigation",
    "message": "The available Pandora knowledge base does not contain sufficient evidence to answer this question.",
    "searched_scope": "Chapters 5 and 14 · record types fauna, monitoring",
    "closest_matches": [
      {
        "record_id": "SV-105",
        "title": "Deep Current Expanse acoustic survey",
        "relevance_score": 0.41,
        "page": 47
      }
    ],
    "what_would_resolve": "An acoustic survey record for this species in this region. See checklist A.2 — Wildlife Emergency."
  },
  "citations": [],
  "has_sufficient_evidence": false,
  "llm_call_count": 2,
  "latency_ms": 1840
}
```

| Field | Type | Notes |
|---|---|---|
| `insufficient_evidence` | object \| **null** | Non-null **only** when `has_sufficient_evidence` is `false` |
| `banner` | string | The actionable headline. Renders large and amber. |
| **`message`** | string | **The brief's mandated sentence, verbatim. Do not reword, truncate, or template over it.** Rendered as the body's first line. |
| `searched_scope` | string | Which chapters and record types were scanned |
| `closest_matches` | array | Sub-threshold hits, clearly labelled insufficient. Never presented as an answer. |
| `what_would_resolve` | string | The evidence that would answer it, citing an Appendix A checklist |

**The banner/body split is deliberate.** The brief mandates a specific sentence; the command-center
framing wants an actionable headline. They occupy different slots, so neither is compromised.

**Triggered deterministically** — top rerank score `< 4.5 / 10` · groundedness `= 0` · retry
exhausted with zero surviving claims · all specialists timed out with no partial result. Never at
model discretion: model self-assessment of uncertainty is unreliable, a rule is not.

> The UI **must not** style this as an error. No red, no warning icon beyond the amber banner, no
> "something went wrong". The system explaining its own limits *is* the feature (`docs/UI_SPEC.md`).

---

## 1.5 List past situation reports

Backs `/app/investigations`. Cut this endpoint if that route is cut.

### `GET /api/v1/situation-reports`

Query params: `priority_class` · `had_conflict` (bool) · `was_insufficient` (bool) · `limit` · `offset`

**Response `200`**

```json
{
  "reports": [
    {
      "answer_id": "7b3d9f1c-1111-4c2d-8e4f-6a9b3c5d7e01",
      "question": "The water near Awa Reef has turned turquoise and the fish are leaving the area.",
      "priority_class": "W3",
      "assembly_mode": "sitrep",
      "confidence_level": "moderate",
      "affected_region_ids": ["REG-01"],
      "citation_count": 11,
      "had_conflict": true,
      "was_insufficient": false,
      "was_partial": false,
      "created_at": "2026-08-05T10:15:33Z"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

### `GET /api/v1/situation-reports/{answer_id}`

The full §1.1 response body, plus `trace` — the persisted `agent_steps` array in `sequence_number`
order, so the orchestration rail can **replay**. Replay is demo insurance: if the live network
stalls, we replay a cached trace at full speed instead of standing in silence.

**Errors:** `404 report_not_found`

---

## 1.6 Incident register

Backs `/app/incidents`. A filtered projection of metadata already in the index — **no new retrieval
work, no LLM call.**

### `GET /api/v1/incidents`

Query params: `risk_level` (`low`\|`medium`\|`high`\|`critical`) · `region_id` · `limit` · `offset`

**Response `200`**

```json
{
  "incidents": [
    {
      "record_id": "INC-005",
      "title": "Vent Plume Release",
      "region_id": "REG-05",
      "region_name": "Obsidian Reach",
      "risk_level": "critical",
      "chapter": "12 · Environmental Threats and Emergency Response",
      "page": 42,
      "summary_excerpt": "Yellow plume observed at the vent edge with dead shellfish along the black-sand coast.",
      "evidence_quality": "verified_observation"
    }
  ],
  "total": 10,
  "limit": 50,
  "offset": 0
}
```

Selecting one pre-fills the Command Center question box — it is a shortcut into `/app`, not a
separate reader.

---

# Part 2 — Internal API

Exposed by the **FastAPI agent service**. Called **only by the backend gateway** — never publicly
routable. No Supabase JWT — a shared secret header instead: `X-Internal-Key: <AGENT_SERVICE_KEY>`.

---

## 2.1 `POST /rag/ingest`

**Request**

```json
{
  "document_id": "9f8e7d6c-5555-4a3b-8c2d-1e0f9a8b7c6d",
  "file_name": "obsidian-reach-survey-june.pdf",
  "content_type": "application/pdf",
  "content_base64": "JVBERi0xLjQKJeLjz9MKMy..."
}
```

**Response `200`**

```json
{
  "document_id": "9f8e7d6c-5555-4a3b-8c2d-1e0f9a8b7c6d",
  "status": "indexed",
  "chunk_count": 23,
  "record_count": 0,
  "page_count": 9,
  "chunking_mode": "narrative",
  "error_message": null,
  "duration_ms": 4210
}
```

| Field | Notes |
|---|---|
| `status` | `indexed` \| `failed`. On `failed`, `error_message` is non-null and the gateway surfaces it on the document row. |
| `record_count` | Corpus-style records detected via the `^(REG\|STL\|FAU\|…)-\d+` boundary pattern |
| `chunking_mode` | `record_aware` \| `narrative`. **Falls back to `narrative` if fewer than 50 records are detected** — an arbitrary uploaded document is expected to be narrative. |

---

## 2.2 `POST /rag/query`

Retrieval + grounded generation for **one** section or one whole report, depending on
`assembly_mode`. Layer 1 and Layer 2 use this directly with no orchestrator.

**Request**

```json
{
  "question": "The water near Awa Reef has turned turquoise and the fish are leaving.",
  "document_ids": null,
  "top_k": 6,
  "record_type_filter": ["incident", "monitoring", "field_note"],
  "region_id_filter": null,
  "section_type": "likely_causes",
  "conversation_history": [
    { "role": "user", "content": "What is the Luminous Shelf?" },
    { "role": "assistant", "content": "REG-01 Luminous Shelf is the shallow reef shelf region [REG-01]." }
  ]
}
```

`conversation_history`: **last turn only**, for coreference. Empty array on a new conversation.
`section_type: null` means "fill all sections sequentially" — the Layer 2 single-agent path and
degradation rung 3.

**Response `200`**

```json
{
  "sections": [
    {
      "section_type": "likely_causes",
      "status": "filled",
      "empty_reason": null,
      "content": "**No cause is established.** [FN-A] [FN-B] [LAB-C]...",
      "claim_count": 3,
      "supported_claim_count": 3,
      "duration_ms": 3180
    }
  ],
  "citations": [
    {
      "marker": 1,
      "document_id": "1a2b3c4d-2222-4e5f-9a8b-7c6d5e4f3a2b",
      "chunk_id": "1a2b3c4d-chunk-0031",
      "record_id": "INC-001",
      "record_type": "incident",
      "title": "Turquoise Water Event",
      "chapter": "12 · Environmental Threats and Emergency Response",
      "section": "Plausible causes",
      "page": 40,
      "region_id": "REG-01",
      "excerpt": "Plausible causes include mineral sediment, plankton bloom, chemical release, or light reflection.",
      "relevance_score": 0.94,
      "rerank_score": 9.4,
      "evidence_quality": "provisional_interpretation",
      "risk_level": "high",
      "record_date": null
    }
  ],
  "grounding": {
    "groundedness": 96,
    "rules": [
      { "number": 1, "name": "Cite record IDs for specific claims", "passed": true, "detail": "3/3 factual sentences carry a resolving marker" },
      { "number": 2, "name": "Multiple causes stay hypotheses", "passed": true, "detail": "INC-001's four causes presented unranked" }
    ],
    "unsupported_sentences": []
  },
  "conflicts": [],
  "has_sufficient_evidence": true,
  "retrieved_chunk_count": 6,
  "top_rerank_score": 9.4,
  "rerank_mode": "llm",
  "duration_ms": 3180
}
```

| Field | Notes |
|---|---|
| `grounding.rules` | All **8** §15.2 rules, each with pass/fail and a human-readable detail. Powers the GroundingGate panel. |
| `top_rerank_score` | `0.0`–`10.0`. **Below `4.5` → `has_sufficient_evidence: false`.** |
| `rerank_mode` | `llm` (the F0 path, primary) \| `semantic` (if ever on Basic+) \| `none` (fusion order only, degraded) |
| `relevance_score` | `rerank_score / 10`, normalized `0.0`–`1.0` for display |

> The agent service returns `document_id` but **not** `document_name` — the gateway joins that from
> Postgres before returning to the frontend. Keeps the agent service free of app-DB coupling.

---

## 2.3 `POST /agent/sitrep`

**The orchestrated path.** Classifies, routes, dispatches specialists concurrently, validates, and
streams. Layer 5 uses this; Layers 1–2 do not.

`Accept: text/event-stream` → streams the §1.2 events.
`Accept: application/json` → returns the assembled report in one response (same body, no trace).

**Request**

```json
{
  "question": "The water near Awa Reef has turned turquoise and the fish are leaving.",
  "conversation_id": "9c1e4b2a-0000-4a1b-9f3e-2d5c8a7b1234",
  "document_ids": null,
  "mode": null,
  "conversation_history": []
}
```

`mode`: `null` lets the orchestrator decide (the normal case). Force `sitrep` \| `focused` \|
`compare` only for testing.

**Response `200`** *(JSON mode)* — `{ situation_report, citations, grounding, has_sufficient_evidence, insufficient_evidence, llm_call_count, duration_ms }`, matching §1.1 minus the gateway-added `document_name` and IDs.

**Hard limits, enforced by counters in orchestrator state — not by prompt instruction:**

| Control | Value |
|---|---|
| Specialists per query | **3** max (`sitrep`), 2 (`compare`), 1 (`focused`). **Never dynamic.** |
| Retry cap | **1**, hard |
| Per-specialist timeout | **8 s** |
| Total orchestration budget | **25 s** — returns best-available regardless of agent state |
| Max LLM calls per query | **8** |

**No recursion anywhere.** The call graph is a fixed-depth tree by construction: orchestrator →
specialists → done. **A specialist cannot dispatch another specialist.**

On any specialist failure the orchestrator falls back to §2.2 with `section_type: null` —
degradation rung 3, structurally identical output.

---

## 2.4 `GET /health`

**Response `200`**

```json
{
  "status": "ok",
  "search_index_reachable": true,
  "llm_reachable": true,
  "corpus_indexed": true,
  "corpus_chunk_count": 221,
  "corpus_record_count": 130,
  "rerank_mode": "llm",
  "version": "0.1.0"
}
```

Used by Azure App Service health checks and by the gateway to return `502
agent_service_unavailable` or `422 corpus_not_indexed` early. **`corpus_indexed: false` is the single
most important field** — it means no query can work, and the gateway should say so rather than
letting the model answer from pretrained knowledge.

---

## Build Order

| Who | T+0:00, before anything else |
|---|---|
| **Nipuna** | Hardcode the §1.1, §1.4, and §1.6 responses as JSON fixtures, plus a **mock SSE stream** replaying the §1.2 events on a timer. Build the whole UI against them — including the parallel-fill animation, which the mock can drive perfectly. Swap the base URL at integration. |
| **Manujaya** | Stub every §1 endpoint to return these exact payloads — FastAPI returns a Pydantic model or a plain dict, so a stub is about three lines. **Stub the SSE endpoint by replaying a fixture event list.** Nipuna is unblocked in 30 minutes. Wire the real logic behind the stubs. |
| **Lakshitha** | Stub §2.1–2.4 the same way. Manujaya wires the HTTP client immediately. Build the real pipeline behind them. |

Three people, zero blocking. That's what the contract buys.

**Timeouts:** gateway → agent, **30 s** on `/rag/query` and `/agent/sitrep`, **60 s** on
`/rag/ingest`. On timeout return `504 agent_service_timeout` — never hang the browser.

**The mock SSE stream is the highest-leverage fixture in this file.** Wow feature 1 is three sections
filling concurrently; Nipuna can build and polish that entire interaction before the orchestrator
exists, then swap in the real stream and have it work first time.

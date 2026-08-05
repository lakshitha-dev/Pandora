# API_CONTRACT.md

**The contract between frontend, backend, and agent service.** Frozen at kickoff.

> **This file is shared property.** Don't change it alone — propose in the team channel, get a 👍,
> then edit. Nipuna, Manujaya, and Lakshitha all build against it simultaneously.

---

## Conventions

| | |
|---|---|
| **Base URL (public)** | `https://<app>.azurewebsites.net` · local: `http://localhost:5000` |
| **Base URL (internal)** | Agent service, local: `http://localhost:8000` — **never called from the browser** |
| **Auth** | `Authorization: Bearer <supabase-jwt>` on every public endpoint |
| **JSON casing** | `snake_case` everywhere, both services |
| **Timestamps** | ISO 8601 UTC — `2026-08-05T14:23:00Z` |
| **IDs** | UUID v4 strings |
| **Content type** | `application/json`, except document upload (`multipart/form-data`) |

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
| 403 | `forbidden` |
| 404 | `document_not_found`, `action_not_found` |
| 409 | `document_already_indexing`, `action_already_resolved` |
| 422 | `no_documents_indexed` |
| 500 | `internal_error` |
| 502 | `agent_service_unavailable` |
| 504 | `agent_service_timeout` |

---

# Part 1 — Public API

Exposed by the **FastAPI backend gateway**. Consumed by the **frontend**.

---

## 1.1 Ask a question

The core endpoint. Returns a grounded answer, its citations, and optionally a proposed action.

### `POST /api/v1/ask`

**Request**

```json
{
  "question": "Which invoices are overdue and who do I need to chase?",
  "conversation_id": "9c1e4b2a-0000-4a1b-9f3e-2d5c8a7b1234",
  "document_ids": null
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `question` | string | ✅ | 1–2000 chars |
| `conversation_id` | uuid \| null | — | Omit/null to start a new conversation |
| `document_ids` | uuid[] \| null | — | Restrict search to these documents; null = search all |

**Response `200`**

```json
{
  "answer_id": "7b3d9f1c-1111-4c2d-8e4f-6a9b3c5d7e01",
  "conversation_id": "9c1e4b2a-0000-4a1b-9f3e-2d5c8a7b1234",
  "answer": "Two invoices are currently overdue. Invoice #4471 from Silverline Supplies for LKR 120,000 was due on 2026-07-04 and is 32 days overdue [1]. Invoice #4488 from Nimal Traders for LKR 45,500 was due on 2026-07-21 and is 15 days overdue [2]. Silverline's terms specify a 2% late fee after 30 days [3].",
  "citations": [
    {
      "marker": 1,
      "document_id": "1a2b3c4d-2222-4e5f-9a8b-7c6d5e4f3a2b",
      "document_name": "invoices-july-2026.pdf",
      "page": 3,
      "section": "Outstanding",
      "excerpt": "INV-4471 | Silverline Supplies | LKR 120,000.00 | Due: 2026-07-04 | Status: UNPAID",
      "relevance_score": 0.94
    },
    {
      "marker": 2,
      "document_id": "1a2b3c4d-2222-4e5f-9a8b-7c6d5e4f3a2b",
      "document_name": "invoices-july-2026.pdf",
      "page": 3,
      "section": "Outstanding",
      "excerpt": "INV-4488 | Nimal Traders | LKR 45,500.00 | Due: 2026-07-21 | Status: UNPAID",
      "relevance_score": 0.91
    },
    {
      "marker": 3,
      "document_id": "5e6f7a8b-3333-4b9c-8d1e-2f3a4b5c6d7e",
      "document_name": "silverline-supply-agreement.pdf",
      "page": 7,
      "section": "6. Payment Terms",
      "excerpt": "A late payment charge of 2% per month applies to balances outstanding beyond thirty (30) days.",
      "relevance_score": 0.87
    }
  ],
  "suggested_action": {
    "type": "flag_invoice",
    "title": "Flag invoice #4471 as overdue",
    "rationale": "32 days overdue and past the 30-day threshold where the 2% late fee applies.",
    "payload": {
      "invoice_number": "INV-4471",
      "supplier": "Silverline Supplies",
      "amount": 120000.00,
      "currency": "LKR",
      "due_date": "2026-07-04",
      "days_overdue": 32
    },
    "supporting_citations": [1, 3]
  },
  "confidence": "high",
  "has_sufficient_evidence": true,
  "latency_ms": 3120
}
```

| Field | Type | Notes |
|---|---|---|
| `answer` | string | Markdown. Citation markers `[n]` map to `citations[].marker`. |
| `citations` | array | May be empty when `has_sufficient_evidence` is `false` |
| `citations[].relevance_score` | float | `0.0`–`1.0` |
| `suggested_action` | object \| **null** | **Null on most queries** — only present when the agent judges an action is warranted |
| `suggested_action.type` | enum | `flag_invoice` \| `draft_email` \| `create_task` |
| `suggested_action.payload` | object | Shape varies by `type` — see §1.2 |
| `suggested_action.supporting_citations` | int[] | Markers that justify this action |
| `confidence` | enum | `high` \| `medium` \| `low` \| `insufficient` |
| `has_sufficient_evidence` | bool | `false` → show the honest-refusal state |

> ⚠️ **`suggested_action` is null on most requests.** Handle the null case first in the UI —
> it's the common path, not the edge case.

**Response `200` — insufficient evidence**

```json
{
  "answer_id": "8c4e0a2d-4444-4d3e-9f5a-7b8c9d0e1f23",
  "conversation_id": "9c1e4b2a-0000-4a1b-9f3e-2d5c8a7b1234",
  "answer": "I couldn't find enough evidence in your documents to answer this. I searched 3 documents for information about 2025 tax filings, but the uploaded set only covers July 2026 invoices and supplier agreements.",
  "citations": [],
  "suggested_action": null,
  "confidence": "insufficient",
  "has_sufficient_evidence": false,
  "latency_ms": 1840
}
```

**Errors:** `401 unauthenticated` · `422 no_documents_indexed` · `502 agent_service_unavailable` · `504 agent_service_timeout`

---

## 1.2 Action payload shapes

`suggested_action.payload` varies by `type`. Same shapes used in §1.5.

**`flag_invoice`**
```json
{
  "invoice_number": "INV-4471",
  "supplier": "Silverline Supplies",
  "amount": 120000.00,
  "currency": "LKR",
  "due_date": "2026-07-04",
  "days_overdue": 32
}
```

**`draft_email`**
```json
{
  "to": "accounts@silverline.lk",
  "subject": "Overdue invoice INV-4471 — payment reminder",
  "body": "Dear Silverline Supplies,\n\nOur records show invoice INV-4471 for LKR 120,000.00, due 2026-07-04, remains unpaid...",
  "related_document_id": "1a2b3c4d-2222-4e5f-9a8b-7c6d5e4f3a2b"
}
```
> Drafted and displayed only. **Nothing is sent** — see `docs/PROJECT.md` scope.

**`create_task`**
```json
{
  "title": "Call Silverline Supplies about INV-4471",
  "description": "32 days overdue. 2% late fee applies per section 6 of the supply agreement.",
  "due_date": "2026-08-08",
  "priority": "high"
}
```
`priority`: `low` \| `medium` \| `high`

---

## 1.3 Documents

### `GET /api/v1/documents`

Query params: `status` (`pending`\|`indexing`\|`indexed`\|`failed`) · `limit` (default 50) · `offset` (default 0)

**Response `200`**

```json
{
  "documents": [
    {
      "id": "1a2b3c4d-2222-4e5f-9a8b-7c6d5e4f3a2b",
      "file_name": "invoices-july-2026.pdf",
      "content_type": "application/pdf",
      "size_bytes": 284910,
      "page_count": 12,
      "chunk_count": 47,
      "status": "indexed",
      "error_message": null,
      "uploaded_at": "2026-08-05T09:14:22Z",
      "indexed_at": "2026-08-05T09:14:51Z"
    },
    {
      "id": "5e6f7a8b-3333-4b9c-8d1e-2f3a4b5c6d7e",
      "file_name": "silverline-supply-agreement.pdf",
      "content_type": "application/pdf",
      "size_bytes": 91200,
      "page_count": 9,
      "chunk_count": 18,
      "status": "indexing",
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

---

### `POST /api/v1/documents`

`Content-Type: multipart/form-data` · field `file` · max **10 MB** · PDF, DOCX, CSV, TXT.

Returns immediately with `status: "pending"`; indexing is async. Poll `GET /api/v1/documents/{id}`.

**Response `202`**

```json
{
  "id": "9f8e7d6c-5555-4a3b-8c2d-1e0f9a8b7c6d",
  "file_name": "expenses-q2.csv",
  "content_type": "text/csv",
  "size_bytes": 15400,
  "page_count": null,
  "chunk_count": null,
  "status": "pending",
  "error_message": null,
  "uploaded_at": "2026-08-05T10:02:11Z",
  "indexed_at": null
}
```

**Errors:** `400 unsupported_file_type` · `400 file_too_large` · `401 unauthenticated`

---

### `GET /api/v1/documents/{id}`

Single document, same object shape as above. Poll this for indexing progress.
**Errors:** `404 document_not_found`

---

### `DELETE /api/v1/documents/{id}`

Deletes the document, its Postgres metadata, and its vectors from Azure AI Search.
**Response `204`** (no body) · **Errors:** `404 document_not_found` · `409 document_already_indexing`

---

## 1.4 List agent actions

### `GET /api/v1/agent-actions`

Query params: `status` (`proposed`\|`approved`\|`rejected`\|`completed`) · `type` · `limit` · `offset`

**Response `200`**

```json
{
  "actions": [
    {
      "id": "3d4e5f6a-6666-4b7c-8d9e-0a1b2c3d4e5f",
      "type": "flag_invoice",
      "title": "Flag invoice #4471 as overdue",
      "rationale": "32 days overdue and past the 30-day threshold where the 2% late fee applies.",
      "payload": {
        "invoice_number": "INV-4471",
        "supplier": "Silverline Supplies",
        "amount": 120000.00,
        "currency": "LKR",
        "due_date": "2026-07-04",
        "days_overdue": 32
      },
      "status": "proposed",
      "source_answer_id": "7b3d9f1c-1111-4c2d-8e4f-6a9b3c5d7e01",
      "citations": [
        {
          "document_id": "1a2b3c4d-2222-4e5f-9a8b-7c6d5e4f3a2b",
          "document_name": "invoices-july-2026.pdf",
          "page": 3,
          "excerpt": "INV-4471 | Silverline Supplies | LKR 120,000.00 | Due: 2026-07-04 | Status: UNPAID"
        }
      ],
      "created_at": "2026-08-05T10:15:33Z",
      "resolved_at": null
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

---

## 1.5 Create an agent action

Called when the user accepts a `suggested_action` from `/api/v1/ask`. Persists it as `proposed`.

### `POST /api/v1/agent-actions`

**Request**

```json
{
  "type": "flag_invoice",
  "title": "Flag invoice #4471 as overdue",
  "rationale": "32 days overdue and past the 30-day threshold where the 2% late fee applies.",
  "payload": {
    "invoice_number": "INV-4471",
    "supplier": "Silverline Supplies",
    "amount": 120000.00,
    "currency": "LKR",
    "due_date": "2026-07-04",
    "days_overdue": 32
  },
  "source_answer_id": "7b3d9f1c-1111-4c2d-8e4f-6a9b3c5d7e01"
}
```

**Response `201`** — the full action object from §1.4, `status: "proposed"`.

---

## 1.6 Resolve an agent action

### `PATCH /api/v1/agent-actions/{id}`

**Request**

```json
{
  "status": "approved",
  "note": "Confirmed with Silverline by phone.",
  "payload": null
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `status` | enum | ✅ | `approved` \| `rejected` \| `completed` |
| `note` | string \| null | — | Optional user note |
| `payload` | object \| null | — | Non-null replaces the payload — lets the user edit a drafted email before approving |

**Response `200`** — updated action object, `resolved_at` set.
**Errors:** `404 action_not_found` · `409 action_already_resolved`

---

# Part 2 — Internal API

Exposed by the **FastAPI agent service**. Called **only by the backend gateway** — never publicly routable.
No Supabase JWT — a shared secret header instead: `X-Internal-Key: <AGENT_SERVICE_KEY>`.

---

## 2.1 `POST /rag/ingest`

**Request**

```json
{
  "document_id": "9f8e7d6c-5555-4a3b-8c2d-1e0f9a8b7c6d",
  "file_name": "expenses-q2.csv",
  "content_type": "text/csv",
  "content_base64": "aWQsZGF0ZSxhbW91bnQsdmVuZG9yCjEsMjAy..."
}
```

**Response `200`**

```json
{
  "document_id": "9f8e7d6c-5555-4a3b-8c2d-1e0f9a8b7c6d",
  "status": "indexed",
  "chunk_count": 23,
  "page_count": null,
  "error_message": null,
  "duration_ms": 4210
}
```

`status`: `indexed` \| `failed`. On `failed`, `error_message` is non-null and the backend surfaces it on the document row.

---

## 2.2 `POST /rag/query`

Retrieval + grounded generation. Does **not** decide on actions — see §2.3.

**Request**

```json
{
  "question": "Which invoices are overdue?",
  "document_ids": null,
  "top_k": 6,
  "conversation_history": [
    { "role": "user", "content": "How many suppliers do we have?" },
    { "role": "assistant", "content": "You have 8 suppliers across the uploaded agreements." }
  ]
}
```

`conversation_history`: last turn only, for coreference. Empty array on a new conversation.

**Response `200`**

```json
{
  "answer": "Two invoices are currently overdue...",
  "citations": [
    {
      "marker": 1,
      "document_id": "1a2b3c4d-2222-4e5f-9a8b-7c6d5e4f3a2b",
      "chunk_id": "1a2b3c4d-chunk-0031",
      "page": 3,
      "section": "Outstanding",
      "excerpt": "INV-4471 | Silverline Supplies | LKR 120,000.00 | Due: 2026-07-04 | Status: UNPAID",
      "relevance_score": 0.94
    }
  ],
  "confidence": "high",
  "has_sufficient_evidence": true,
  "retrieved_chunk_count": 6,
  "duration_ms": 2870
}
```

> The agent service returns `document_id` but **not** `document_name` — the backend joins that
> from Postgres before returning to the frontend. Keeps the agent service free of app-DB coupling.

---

## 2.3 `POST /agent/run`

Decides whether the answer warrants an action, and builds it.

**Request**

```json
{
  "question": "Which invoices are overdue and who do I need to chase?",
  "answer": "Two invoices are currently overdue...",
  "citations": [
    {
      "marker": 1,
      "document_id": "1a2b3c4d-2222-4e5f-9a8b-7c6d5e4f3a2b",
      "excerpt": "INV-4471 | Silverline Supplies | LKR 120,000.00 | Due: 2026-07-04 | Status: UNPAID"
    }
  ]
}
```

**Response `200` — action proposed**

```json
{
  "suggested_action": {
    "type": "flag_invoice",
    "title": "Flag invoice #4471 as overdue",
    "rationale": "32 days overdue and past the 30-day threshold where the 2% late fee applies.",
    "payload": {
      "invoice_number": "INV-4471",
      "supplier": "Silverline Supplies",
      "amount": 120000.00,
      "currency": "LKR",
      "due_date": "2026-07-04",
      "days_overdue": 32
    },
    "supporting_citations": [1]
  },
  "duration_ms": 980
}
```

**Response `200` — no action warranted** *(the common case)*

```json
{
  "suggested_action": null,
  "duration_ms": 640
}
```

---

## 2.4 `GET /health`

**Response `200`**

```json
{
  "status": "ok",
  "search_index_reachable": true,
  "llm_reachable": true,
  "version": "0.1.0"
}
```

Used by Azure App Service health checks and by the backend to return `502 agent_service_unavailable` early.

---

## Build Order

| Who | Day 0, before anything else |
|---|---|
| **Nipuna** | Hardcode the §1.1 and §1.4 responses as JSON fixtures. Build the whole UI against them. Swap the base URL at integration. |
| **Manujaya** | Stub every public endpoint to return these exact payloads — FastAPI returns a Pydantic model or a plain dict, so a stub is about three lines. Nipuna is unblocked in 30 minutes. Wire the real logic behind the stubs. |
| **Lakshitha** | Stub §2.1–2.4 the same way. Manujaya wires the HTTP client immediately. Build the real pipeline behind them. |

Three people, zero blocking. That's what the contract buys.

**Timeouts:** backend → agent service, **30 s** on `/rag/query`, **60 s** on `/rag/ingest`.
On timeout return `504 agent_service_timeout` — never hang the browser.

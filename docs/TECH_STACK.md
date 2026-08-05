# TECH_STACK.md

**Pandora Knowledge Guardian** — every technology we use, why we picked it, and where it bites.

> The brief says *"judges will evaluate the completed solution rather than the specific technology
> stack."* So this file is not a justification exercise — it's a record of **where each choice will
> hurt us**, so nobody discovers a limit at hour four.

---

## Frontend — Nipuna

| Technology | Why |
|---|---|
| **Next.js (App Router)** | React with file-based routing for our seven routes, plus layouts — the auth guard and app shell live in one `layout.tsx` instead of being repeated per page |
| **v0** | Generates a working scaffold in minutes; hours of UI time back for the parts judges actually see |
| **TypeScript** (`strict: true`) | The API contract becomes compile-time enforced — a renamed field fails the build, not the demo |
| **React** | Team already knows it |
| **`EventSource`** (native) | Consumes the orchestration trace. No library needed — it's built into every browser. |
| **Inline SVG** | The ten-zone Pandora map. Ten `<path>` elements and one colour binding; no mapping library, no tiles, no external asset. |

> **Styling and component library are Nipuna's call** — Tailwind, CSS Modules, a component kit,
> whatever ships fastest at the quality bar they want. `docs/UI_SPEC.md` specifies what each
> screen must *do*; how it looks is deliberately left open. `SOLUTION.md` §8.2's palette is a
> starting point, not a mandate.

> ⚠️ **`EventSource` cannot set request headers.** The JWT therefore travels as an `access_token`
> query param on the SSE endpoint only (`docs/API_CONTRACT.md` §1.2). Worth knowing before someone
> spends twenty minutes wondering why `Authorization` isn't arriving.

---

## Backend — Manujaya

| Technology | Why |
|---|---|
| **Python 3.11+** | Same language as the agent service — one runtime to install, one set of idioms, and either person can read the other's code in a pinch |
| **FastAPI** | Async, fast, and **auto-generates OpenAPI docs at `/docs`** — Nipuna can inspect a live payload shape without reading Python |
| **Pydantic v2** | Request/response validation straight from type hints; models mirror `API_CONTRACT.md` one-to-one |
| **SQLAlchemy 2.0** | Mature async ORM with typed models |
| **Alembic** | Migrations — schema changes without hand-written SQL |
| **psycopg** (async) | The Postgres driver SQLAlchemy uses |
| **python-jose** | Verify the Supabase JWT signature at the gateway so no downstream service handles auth |
| **httpx** | Async HTTP client for calling the agent service, with real timeout support — **and streaming support, which the SSE passthrough needs** |
| **Uvicorn** | ASGI server |

> ⚠️ **The gateway must forward SSE events unbuffered.** Use `httpx.AsyncClient.stream()` and yield
> each chunk straight through — **never** `await response.aread()`. Aggregating the stream defeats the
> entire point of the endpoint: judges are supposed to watch three sections fill in real time.

> ✅ **Nothing to configure for casing.** Python, Pydantic, SQLAlchemy, Postgres, and our JSON
> contract are all `snake_case` natively. One convention across the entire system, set up by
> doing nothing.

---

## RAG + Agent — Lakshitha

| Technology | Why |
|---|---|
| **Python** | Where the AI ecosystem lives; every RAG library targets it first |
| **FastAPI** | Async, fast, auto-generated OpenAPI docs — the backend team can see the contract live |
| **LangChain** | Retrieval chains, agent tooling, and Azure integrations already built — we compose rather than write a RAG pipeline from scratch |
| **`asyncio.gather`** | Dispatches the three specialists **concurrently**. This is the whole parallelism story — wall clock is the slowest agent (~3 s), not the sum (~9 s). Sequential dispatch would make the third agent free in wall-clock terms *and* invisible on screen. |
| **sse-starlette** | Emits the orchestration trace as Server-Sent Events. Chosen over WebSockets: the stream is one-directional, SSE reconnects for free, and it's plain HTTP through the gateway. |
| **pypdf** *(or pdfplumber)* | PDF text extraction **retaining page numbers and font sizes**. Font size drives heading detection, which is how record boundaries are found. Page numbers are a brief requirement on every source card. |
| **python-docx** | DOCX paragraph + heading-style traversal for uploads |
| **Uvicorn** | ASGI server FastAPI expects |
| **Pydantic** | Request/response validation; models mirror the backend's one-to-one |

> **Everything that scores is hand-written, not framework-provided.** LangChain gives us clients and
> chain plumbing. The record-aware chunker, the RRF fusion, the LLM reranker, GroundingGate's eight
> rules, conflict detection, the orchestrator, and the three specialists are all ours — which is
> exactly what the prebuilt-component disclosure at the bottom of this file has to say.

> ⚠️ **Page numbers are load-bearing.** The brief requires a page or section number on every source
> card, and the demo cites specific pages out loud. Whichever PDF library we use, **verify page
> retention on the first extraction**, not at hour three.

---

## AI Models — Azure AI Foundry

| Model | Role | Why |
|---|---|---|
| **`text-embedding-3-small`** | Embeddings (1536-d) | ~5× cheaper and ~2× faster to index than `-3-large`. On ~220 short, distinctive, jargon-heavy records the recall difference is negligible — while the indexing-speed difference is very real inside a 5-hour window. **Re-indexing the whole corpus must stay under ~60 s so we can iterate on chunking.** |
| **`gpt-4o-mini`** | Generation · reranking · classification · conflict checking | Fast, cheap, strong at grounded extraction — and **shares a client, endpoint, and key with the embedding model**. Temperature `0.1` for generation, `0` for the orchestrator. |

**Low temperature is a grounding decision, not a style one.** Sampling diversity is precisely the
mechanism by which a model drifts from its retrieved context into pretrained priors — which on a
*fictional* corpus means inventing plausible Earth marine biology.

**What gets embedded:** the provenance header + record title + chunk content. Embedding the title and
record ID alongside the body measurably improves retrieval on entity-named queries (*"what should we
do about a Deepbell stranding?"*). Batched at **64 chunks per request** with retry-and-backoff on 429.

**One `gpt-4o-mini` deployment serves four jobs** — generation, reranking, classification, and the
confirmatory conflict check. That's why the **≤8 LLM calls per query** budget is enforced at the
dispatcher: it's the same quota being spent four ways.

### The model decision — settled

**OpenAI models on Azure AI Foundry. Decided; not revisiting mid-hackathon.**

Both models share **one client, one endpoint, and one API key** — LangChain wires them up with
`AzureChatOpenAI` + `AzureOpenAIEmbeddings` against the same deployment. That's a single
integration, a single credential in `.env`, and a single thing to debug at 2am.

```
AZURE_OPENAI_ENDPOINT            ──┐
AZURE_OPENAI_API_KEY             ──┼── one Foundry resource, two deployments
AZURE_OPENAI_CHAT_DEPLOYMENT     ──┤   · gpt-4o-mini
AZURE_OPENAI_EMBEDDING_DEPLOYMENT──┘   · text-embedding-3-small
```

Everything stays on Azure and bills to one place, which matters if we're on credits.

> **The embedding model must never change after documents are indexed.** Vectors written by
> `text-embedding-3-small` are only comparable to query vectors from the same model. Swapping it
> means re-indexing every document — silently degraded retrieval otherwise, with no error to
> tell you.

---

## Vector Store — Azure AI Search (Free **F0** tier)

| Aspect | Detail |
|---|---|
| Why | Managed vector + keyword hybrid search with no infrastructure to run |
| Index | `pandora-knowledge`, single index |
| Vector field | `content_vector` — 1536-d, **HNSW**, cosine, `m=4`, `efConstruction=400`, `efSearch=500` |
| Retrieval | BM25 `k=30` + vector `k=30` → **RRF fusion** → **LLM rerank** → top 6 (top 8 for compare) |
| Scale | ~220 chunks, ~130 of them one-record-each |

### The 14-field metadata schema

This is what makes filtering, scoring, and precise citation possible. Full detail in
`SOLUTION.md` §4.2.

| Field | Attributes | Purpose |
|---|---|---|
| `chunk_id` | key | Primary key |
| `document_id` | filterable | Multi-document support, per-doc delete |
| `document_name` | retrievable | **Required by the brief** — on every source card |
| `record_id` | filterable, searchable | `INC-005`, `FAU-014`, `WS-03` — **the citation anchor** |
| `record_type` | filterable, facetable | `incident` · `fauna` · `flora` · `policy` · `region` · `settlement` · `health` · `accommodation` · `knowledge_card` · `monitoring` · `field_note` · `narrative` |
| `title` | retrievable, searchable | e.g. "Vent Plume Release" |
| `chapter` / `section` | filterable, retrievable | **Required by the brief** |
| `page` | filterable, retrievable | **Required by the brief** — exact page number |
| `region_id` | filterable, facetable | `REG-05` — enables "everything at Obsidian Reach", **and drives the map** |
| `evidence_quality` | filterable, retrievable | The corpus's own five-value taxonomy |
| `risk_level` | filterable | `low` / `medium` / `high` / `critical`, parsed from `INC-*` records |
| `record_date` | filterable, sortable | For `WS-*`, `SV-*`, `FN-*` — enables corpus rule 4, "preserve time" |
| `field_name` | retrievable | Which sub-field matched, e.g. "Immediate actions" |
| `content` | searchable | The chunk text |

`efSearch=500` deliberately favours recall over latency: the corpus is tiny, so latency is not the
constraint — a missed record is.

### ⚠️ Three F0 constraints, and how we design *with* them

**1. No semantic reranker — so the LLM reranker is our primary path, not a fallback.**
The built-in semantic ranker is Basic-tier and above. **It is not available to us, and nothing may
be architected around it.** Instead, one batched `gpt-4o-mini` call scores every candidate `0–10` in a
single request (~600 ms). Scores normalize to `relevance_score` `0.0–1.0` for display, and the
**insufficient-evidence threshold is a top score below `4.5 / 10`**, calibrated against the 7 brief
questions plus the 3 corpus §15.1 questions before freeze.

Reranking is the highest-value retrieval upgrade available and worth this cost. A bi-encoder
compresses a whole chunk into one vector before it ever sees the query — cheap and lossy. Scoring
query and chunk *jointly* catches relevance vector distance misses: for *"what should we do if
shellfish are dying near the black-sand coast?"*, vector search surfaces generic water-quality
sections, while the reranker promotes `INC-005 Vent Plume Release` to the top because it jointly
matches *shellfish* + *dying* + *coast* + *immediate actions*.

*If reranking is unavailable entirely, retrieval falls through to raw RRF fusion order — quality
drops, nothing breaks.*

**2. No managed identity → API keys only.** This makes `.env` hygiene load-bearing: a leaked key is a
live key. `.gitignore` must cover `.env` **before the first commit** — it's the first task in
`docs/TASKS.md`.

**3. Hard limits:** 3 indexes · 50 MB total storage · 3 replicas/partitions. **Ample here** — ~220
chunks is a few megabytes. Worth knowing before anyone plans per-user indexes.

### Why hybrid rather than pure vector — and why it's a *correctness* requirement here

Pure vector search is the default choice and it is **wrong for this corpus.**

The corpus is saturated with exact-match tokens embeddings handle poorly: record IDs (`INC-005`,
`FAU-014`), station codes (`WS-03`), policy numbers, and **invented proper nouns with no pretraining
signal** — *Tideglass Grazer*, *Ventplume Shrimp*, *Mistroot Basin*, *Cloudspine Highlands*. An
embedding model has never seen "Ribbonfin Skimmer" and will place it near generic fish vocabulary.
BM25 matches it exactly, instantly.

Conversely, *"why are the animals leaving?"* shares **no keywords** with `FAU-001`'s *"a sudden
absence can reflect migration, disturbance, weather, sampling error, or mortality"* — pure keyword
search finds nothing; vector search nails it.

**Neither leg alone is sufficient. Hybrid is not a bonus feature here — it is a correctness
requirement.**

### Why Azure AI Search over Chroma / FAISS / Qdrant

Native hybrid search as **managed configuration rather than build time**. On F0 we lose the semantic
reranker and pay for it with one `gpt-4o-mini` call — still a better trade than hand-building BM25
and fusion inside a 5-hour window.

**Fallback if provisioning fails:** in-memory cosine search over ~220 vectors behind the same
retriever protocol. Trivially fast at this scale. Costs hybrid and rerank; keeps the app alive.
Azure AI Search is **the one hard external dependency**, so it's provisioned and smoke-tested in the
first 30 minutes, before anything depends on it.

---

## App Database — Azure Database for PostgreSQL

| Aspect | Detail |
|---|---|
| Why | Relational store for application state; managed, and SQLAlchemy + Alembic work cleanly with it |
| Tables | `documents` · `chunks` · `conversations` · `queries` · `situation_reports` · `report_sections` · `citations` · `agent_runs` · `agent_steps` · `grounding_checks` · `conflicts` · `users` |
| Casing | **All `snake_case`, plural tables** — per `CLAUDE.md`. Column-level schema in `SOLUTION.md` §9.1. |
| Owner | Backend only — the agent service never touches it |

**The split:** Postgres holds *what happened*; Azure AI Search holds *what the AI retrieves*.
Keeping the agent service free of the app database means it can be restarted or redeployed
without risking user data.

**`report_sections` is a table, not JSON on the report.** Independent per-section status is the whole
point of the Situation Report contract — a section must be able to time out without touching its
siblings, and the trace must stream `section.completed` events individually. Rows make partial
reports a first-class queryable state instead of a parsing exercise.

**`agent_steps`, `grounding_checks`, and `citations` are product, not logging.** They power trace
replay (demo insurance), they *are* the "evidence of retrieved sources for each answer" the
submission requires, and they let us prove grounding is audited rather than asserted.

> ⚠️ **Deletion crosses both stores.** `DELETE /api/v1/documents/{id}` must remove the Postgres
> row **and** the AI Search vectors. Orphaned vectors mean citing documents the user deleted.
> **The preloaded corpus is not deletable** — `403 corpus_document_immutable`.

> **Postgres sits behind a repository protocol with an in-memory implementation as the demo
> default.** Postgres is the production target and gets wired if time permits, but a connection-string
> mistake must not be able to take the app down on stage.

---

## Auth — Supabase Auth

| Aspect | Detail |
|---|---|
| Why | Working email/password auth in ~15 minutes, with JWTs any backend can verify. Rolling our own would cost half a day for zero demo value. |
| Flow | Frontend signs in → JWT → `Authorization: Bearer` on every request → backend validates signature + expiry |
| SSE exception | `EventSource` can't set headers, so the token travels as an `access_token` query param on that one endpoint |
| Note | **The only piece outside Azure.** Accepted trade: the time saved is worth more than stack purity. |

> **A demo account is pre-seeded, and auth never gates Layer 1.** The 7-route site is the committed
> deliverable, so auth is real — but a login wall between a judge and the demo is pure downside, and
> nobody signs up on stage.
>
> **Auth is also the designated release valve.** If the schedule slips, dropping it is the single
> largest recovery of time: the role toggle — which is what the rubric actually rewards — is a
> presentation lens and needs no auth at all.

---

## Deployment — Malindu

| Technology | Why |
|---|---|
| **Azure App Service** ×2 | Backend and agent service. Git-based deploy, health probes, env-var config. Agent service is **not publicly routable**. |
| **Azure Static Web Apps** | Purpose-built for Next.js; free tier, global CDN, GitHub-integrated |
| **GitHub Actions** | Push-to-deploy for all three services |
| **Bicep / az CLI** | Reproducible provisioning — recreate the stack if a resource is misconfigured |
| **Git tags** | One per layer gate: `v1-core-rag` · `v2-sitrep` · `v3-honest` · `v4-agentic`. Any earlier layer is one checkout away. |

> ⚠️ **Verify SSE survives App Service early.** Response buffering or an aggressive proxy idle-timeout
> will silently break progressive rendering — the report will arrive all at once and the entire
> parallel-assembly story disappears. This is an easy thing to discover far too late.

> **The demo runs locally, even if deployment is green.** Conference Wi-Fi is a well-known way to lose
> a hackathon. The GitHub repo is the deliverable; local is the demo.

---

## The Knowledge Corpus — our most important dependency

| Aspect | Detail |
|---|---|
| Source of truth | **`Pandora_RAG_Knowledge_2026 (1).pdf`** — the organisers' file, 56 pages |
| Structure | 15 chapters + Appendix A (4 field checklists) + Appendix B (20 knowledge cards) |
| Content | **~130 atomic records with stable IDs and fixed internal field schemas** — 10 `REG` · 10 `STL` · 30 `FAU` · 20 `FLR` · 12 `MED` · 10 `ACC` · 10 `INC` · 10 `POL` · ~20 `KC` · 7 `WS` rows · 6 `SV` rows · `FN-A`/`FN-B`/`LAB-C` |
| Ingested as | ~220 chunks — ~130 record chunks, ~90 narrative and table-row chunks |
| Reference copy | `Pandora_RAG_Knowledge_2026.md` — clean markdown, for **hand-verifying chunk boundaries**. Not the ingestion source. |

**Why the PDF and not the markdown.** The brief requires a page number on every source card, and the
demo cites specific pages out loud. Only the PDF has pages. The markdown copy is easier to parse but
would cost us a brief-mandated field, so it stays a verification aid.

> ⚠️ **PDF extraction mangling the corpus is the highest-impact silent failure in this build.** It
> produces no error — retrieval just quietly gets worse. Mitigated by an explicit **T+1:15
> verification gate**: ten named records manually inspected for clean, complete, unmerged boundaries.
> The chunker falls back to narrative mode if record-ID detection finds fewer than 50 records.

**The corpus is fictional and internally consistent.** Importing real-world marine biology or real
emergency protocols is a hallucination *even when the fact is true on Earth*. Every prompt says so
explicitly.

**The corpus also publishes its own grading criteria** — page 2's evidence-quality instruction, §15.2's
eight Retrieval Grounding Rules, and §14.3's planted conflict with a stated expected answer. This is
why `SOLUTION.md` treats it as a specification rather than a text blob. Read `SOLUTION.md` §0 before
writing any prompt.

---

## Repo

| Technology | Why |
|---|---|
| **GitHub** | Source of truth, PR review, CI/CD trigger, and the submission artifact |
| **`.gitignore`** | **`.env` covered before the first commit** — non-negotiable given API-key-only auth |
| **`.env.example`** | Every key name with dummy values, committed. A teammate goes from clone to running in two minutes. |
| **Committed prebuilt index** | The seeded corpus index, so a fresh clone is queryable without a 60-second seed step |

---

## Environment Variables

Full list lives in `.env.example`. Names here so everyone uses the same ones.

| Variable | Used by | Notes |
|---|---|---|
| `AZURE_OPENAI_ENDPOINT` | agent | |
| `AZURE_OPENAI_API_KEY` | agent | |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | agent | `gpt-4o-mini` |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | agent | `text-embedding-3-small` |
| `AZURE_SEARCH_ENDPOINT` | agent | |
| `AZURE_SEARCH_API_KEY` | agent | |
| `AZURE_SEARCH_INDEX_NAME` | agent | `pandora-knowledge` |
| `PANDORA_CORPUS_PATH` | agent | Path to the corpus PDF, for the seed job |
| `RERANK_MODE` | agent | `llm` (default, the F0 path) · `semantic` · `none` |
| `RERANK_THRESHOLD` | agent | `4.5` of 10 — below this, insufficient evidence |
| `AGENT_SERVICE_URL` | backend | |
| `AGENT_SERVICE_KEY` | backend + agent | shared secret, `X-Internal-Key` |
| `POSTGRES_CONNECTION_STRING` | backend | |
| `SUPABASE_URL` | backend + frontend | |
| `SUPABASE_ANON_KEY` | frontend | |
| `SUPABASE_JWT_SECRET` | backend | |
| `NEXT_PUBLIC_API_BASE_URL` | frontend | |

### Feature flags — one per layer

Every layer above Layer 1 sits behind an independently revertable flag. **Flags are wired the moment
a layer starts, not after it finishes** — a half-built layer must default off.

| Flag | Layer | Off behaviour |
|---|---|---|
| `SITREP_SHELL` | 2 | Layer 1 prose answer with source cards |
| `TRIAGE_BANNER` | 3 | Report renders without the priority banner |
| `CONFIDENCE_METER` | 4 | Meter hidden; Layer 1 insufficient-evidence path still active |
| `GROUNDING_GATE_STRICT` | 4 | Score computed and shown, but never blocks an answer |
| `CONFLICT_DETECTION` | 4 | Standard grounded answer, no conflict panel |
| `AGENTIC_ENABLED` | 5 | **Layer 2 single-agent fill — identical report structure** |
| `MAP_VIEW` | 6 | Left column shows the knowledge panel only |
| `ROLE_TOGGLE` | 6 | Guardian register only |
| `ORCH_ANIM` | 6 | Rail shows a plain text step list |
| `DEMO_MODE` | — | Cached responses for the demo questions — zero API dependency |

Set on all three services (the frontend needs them too, to know what to render).
**If anything is unstable at T+4:45, flip the flag rather than debug.**

**Anything prefixed `NEXT_PUBLIC_` is visible in the browser.** Never put a key behind that prefix.

---

## Prebuilt Components — disclose in the submission

**The rules require this** (*"Teams must disclose any prebuilt components used"*), and it's easy to
forget. It's item 8 on the submission checklist.

| Prebuilt / third-party | Written by us during the event |
|---|---|
| Azure AI Foundry models — `gpt-4o-mini`, `text-embedding-3-small` | Every prompt: orchestrator, three specialists, reranker, conflict check |
| Azure AI Search — index engine, HNSW, hybrid query | The 14-field index schema, RRF fusion, the LLM reranker, all metadata filters |
| LangChain — clients and chain plumbing | All chain composition, routing, and specialist logic |
| pypdf / python-docx — text extraction | **The two-tier record-aware chunker** (our biggest differentiator) |
| sse-starlette — SSE transport | The whole trace event schema and emitter |
| Supabase Auth | Every API endpoint |
| Next.js, FastAPI, SQLAlchemy, Alembic | The entire frontend, both APIs, and the data model |
| v0 — initial UI scaffold | Situation Report renderer, citation chips, orchestration rail, conflict panel, map, role toggle, all screens |
| **`Pandora_RAG_Knowledge_2026.pdf`** — **the organisers' provided corpus** | GroundingGate's eight-rule validator, conflict detection, W1–W4 classifier, confidence scoring |

**The honest summary for the pitch:** *we used managed models, a managed search index, and a UI
scaffold. Every decision that produces a grounded answer — how the corpus is cut into chunks, how
candidates are ranked, how claims are validated, how conflicts are surfaced, and when the system
refuses to answer — is ours, written during the five hours.*

# TASKS.md — Task Board

**Pandora Knowledge Guardian** · 5-hour build · **Update your own rows.**
Status: `todo` · `doing` · `done`. It's how we avoid duplicate work.

**Legend:** 🔴 blocks someone else — do it first · 🟡 on the critical path · 🟢 independent · 🔥 a scoring feature

> **The build order in `SOLUTION.md` §10 is binding.** Six layers, each independently demoable, each
> behind a feature flag and a git tag. **A later layer breaking must never take down an earlier one.**
> Layer 1 alone banks 45 of the 100 marks — nothing else starts until it's green and tagged.

---

## ⏱ The clock

| Time | Layer | Milestone | Gate |
|---|---|---|---|
| **T+0:00 – 0:30** | 1 | Scaffold both FastAPI services + Next.js · Azure AI Search index created · Foundry connectivity verified · **API contract frozen** | Both services respond |
| **T+0:30 – 1:15** | 1 | Ingestion: PDF extraction, record-aware chunker, embedding, indexing. Corpus indexed. | **🔒 Manual verification: 10 sampled records each a clean, complete, unmerged chunk** |
| **T+1:15 – 1:45** | 1 | Retrieval: hybrid + LLM rerank + scores. Tested via API. | **🔒 Correct records in top-6 for all 7 brief questions + all 3 corpus §15.1 questions** |
| **T+1:45 – 2:00** | 1 | Grounded generation + citations + source cards + insufficient-evidence path | **🔒 GATE: `v1-core-rag` tagged. 45 marks banked.** |
| **T+2:00 – 2:40** | 2 | UI: theme, Command Center layout, question input, streaming, **six-section report renderer**, citation chips, reset | **🔒 GATE: `v2-sitrep` tagged** |
| **T+2:40 – 3:00** | 3 | Triage banner: W1–W4 classification + cited reason | Banner renders before generation completes |
| **T+3:00 – 3:20** | 4 | GroundingGate (8 rules) + confidence meter + honesty flip + conflict detection | **🔒 GATE: `v3-honest` tagged. Turquoise question produces the Contested state. Record backup video NOW.** |
| **T+3:20 – 4:10** | 5 | Orchestrator + 3 specialists + section ownership + routing + timeouts + degradation | **🔒 GATE: `v4-agentic` tagged.** Flag off ⇒ clean Layer 2 |
| **T+4:10 – 4:30** | 5–6 | Orchestration rail + orb↔section threads; then map view, role toggle | Parallel orbs visible; each Layer-6 flag independently togglable |
| **T+4:30 – 4:45** | — | README, architecture diagram, prebuilt-component disclosure, **re-record backup video** | All 9 submission items exist |
| **T+4:45 – 5:00** | — | **CODE FREEZE. Rehearse the demo twice against a timer.** | No commits after 4:45 |

**The video is recorded twice** — at T+3:20 against `v3-honest` (a guaranteed-good demo) and again at
T+4:45 against the final build. If the final build misbehaves on stage, the T+3:20 video is still a
complete, honest demo of a working system.

**Auth and deployment run in parallel with Layer 1 and never gate it.** If the schedule slips, the
designated release valve is **dropping auth** — `/app/investigations` goes first, then
`/app/incidents`, then auth.

---

## ⚡ T+0:00 — Unblockers (before anything else)

Nothing else starts cleanly until these are done. Four of them block all three other people.

| Task | Owner | Status | Blockers |
|---|---|---|---|
| 🔴 Create GitHub repo, add `.gitignore` (**`.env`, `__pycache__/`, `.venv/`, `node_modules/`, `.next/`**) and push **before any secret exists** | Malindu | todo | — |
| 🔴 Create the four folders (`frontend/ backend/ agent/ infra/`) with a README each — **none exist yet** | All | todo | Repo exists |
| 🔴 Provision Azure: AI Foundry (deploy `gpt-4o-mini` + `text-embedding-3-small`), AI Search **F0**, PostgreSQL Flexible Server | Malindu | todo | Azure subscription access |
| 🔴 Create Supabase project, grab URL + anon key + JWT secret · **seed one demo account** | Malindu | todo | — |
| 🔴 Write `.env.example` with every key name and dummy values; share real values via a **private** channel — never a commit | Malindu | todo | Azure + Supabase provisioned |
| 🔴 **Freeze `docs/API_CONTRACT.md` — especially the `situation_report` shape (§1.1) and the SSE event schema (§1.2).** All four read it, everyone 👍 in the channel | All | todo | — |
| 🟡 Wire **all ten feature flags** into config on both services and the frontend, **defaulting off** above Layer 1 | All | todo | Scaffolds |

> **Why flags go in at T+0:00, not when each layer starts:** a half-built layer must default off. If
> the flag arrives after the code, there's a window where a broken layer is live.

---

## 🧠 Lakshitha (P1) — RAG pipeline + agents · `agent/`

### Layer 1 — core RAG · **the 45 marks** · by T+2:00

| Task | Owner | Status | Blockers |
|---|---|---|---|
| 🔴 **Stub `/rag/ingest`, `/rag/query`, `/agent/sitrep`, `/health` returning the exact §2 payloads** — unblocks Manujaya immediately | Lakshitha | todo | API contract frozen |
| 🟡 FastAPI scaffold: `app/{routers,chains,agents,retrieval,grounding,ingestion,models}/`, `requirements.txt`, Uvicorn entrypoint | Lakshitha | todo | Folder structure |
| 🟢 Pydantic `Settings` for env config + all ten feature flags — validated at startup, **no scattered `os.getenv()`** | Lakshitha | todo | Scaffold |
| 🟡 Verify Azure AI Foundry connectivity — one embedding call + one `gpt-4o-mini` call | Lakshitha | todo | Azure provisioned |
| 🟡 Create the `pandora-knowledge` index: **all 14 metadata fields** + `content_vector` (1536-d, HNSW, cosine, `m=4`, `efConstruction=400`, `efSearch=500`) | Lakshitha | todo | AI Search provisioned |
| 🟡 PDF extraction retaining **page numbers and font sizes** (font size drives heading detection) | Lakshitha | todo | Scaffold |
| 🔥🟡 **Two-tier record-aware chunker** — Tier 1: one record per chunk on `^(REG\|STL\|FAU\|FLR\|MED\|ACC\|INC\|POL\|KC)-\d+` boundaries, **zero overlap**; Tier 2: narrative 800/120; Tier 2b: one table row per chunk. **Our single biggest differentiator.** | Lakshitha | todo | Extraction |
| 🟡 Provenance header prefixed to each chunk at index time (record ID · name · chapter · region) so the ID travels into model context | Lakshitha | todo | Chunker |
| 🟡 Metadata assignment: `record_type`, `region_id`, `evidence_quality`, `risk_level`, `record_date`, `chapter`, `page`, `field_name` | Lakshitha | todo | Chunker |
| 🟡 Embedding + batched upsert (`text-embedding-3-small`, **64 per request, retry-with-backoff on 429**) | Lakshitha | todo | Index + chunking |
| 🔴🔥 **Seed the corpus and commit the prebuilt index** — `seed_corpus` script over the PDF | Lakshitha + Malindu | todo | Embedding pipeline |
| 🔒 **VERIFICATION GATE T+1:15 — manually inspect 10 records** (`INC-005`, `FAU-014`, `WS-03`, `FN-A`, `LAB-C`, `POL-001`, `KC-01`, `REG-05`, `MED-003`, `SV-101`): each must be one clean, complete, unmerged chunk | Lakshitha | todo | Corpus seeded |
| 🟡 Wire real `/rag/ingest` behind the stub, incl. `record_count` + `chunking_mode` and the **<50-records → narrative fallback** | Lakshitha | todo | Pipeline |
| 🟡 Hybrid retrieval — BM25 `k=30` + vector `k=30`, **RRF fusion** across both legs and both query variants | Lakshitha | todo | Index populated |
| 🔥🟡 ~~**LLM reranker — the PRIMARY path.**~~ **Built, then switched OFF by measurement** (`rerank=False`). On `gpt-5-mini` it cost **~25 s/query and demoted the correct records**. **Metadata filtering by `record_types` is the precision path instead** — 0/6 → 6/6 relevant in 3 s. F0 still has no semantic ranker; don't architect around that either. See the `[LAYER 1]` row in `docs/PROJECT.md`. | Lakshitha | done | Retrieval |
| 🟡 Top-k selection (6, or 8 for compare) + score normalization to `relevance_score` `0.0–1.0` | Lakshitha | todo | Reranker |
| 🟡 Query rewriting — vocabulary expansion, last-turn coreference, **explicit record-ID → filter promotion**, 2 variants | Lakshitha | todo | Retrieval |
| 🟡 Metadata pre-filters — `record_type` / `region_id` / `record_date` | Lakshitha | todo | Retrieval |
| 🔥🟡 **Grounded generation prompt** — closed-book, per-claim **record-ID** markers, documented-vs-inferred separated, hypotheses stay hypotheses, no cross-record merging, time/place preserved, `MED-*` guardrail, abstain over guess | Lakshitha | todo | Retrieval |
| 🟡 Wire real `/rag/query` behind the stub | Lakshitha | todo | Retrieval + generation |
| 🔥🟡 Insufficient-evidence path — deterministic triggers, the **brief's mandated sentence verbatim**, searched scope, closest sub-threshold matches, what would resolve it | Lakshitha | todo | Generation |
| 🔒 **VERIFICATION GATE T+1:45 — all 7 brief questions + all 3 corpus §15.1 questions return the correct records in top-6** | Lakshitha | todo | Retrieval working |
| 🟢 Calibrate the **`4.5 / 10` abstention threshold** against known-good and known-absent questions | Lakshitha | todo | Retrieval working |

### Layer 2 — report shell · by T+2:40

| Task | Owner | Status | Blockers |
|---|---|---|---|
| 🔥🟡 Single-agent prompt fills the **six sections sequentially in one pass** — same structure Layer 5 produces | Lakshitha | todo | Layer 1 green |
| 🟡 Per-section `status` / `empty_reason` / `claim_count` / `duration_ms` in the response | Lakshitha | todo | Section prompt |

### Layer 3 — triage · by T+3:00

| Task | Owner | Status | Blockers |
|---|---|---|---|
| 🔥🟡 **W1–W4 classifier against the corpus's own §4.5 scale**, returning class + reason + **citation + page**. An uncited severity is an ungrounded model opinion. | Lakshitha | todo | Orchestrator prompt |
| 🟡 Emit `priority.classified` and `map.zone_lit` **before generation starts** | Lakshitha | todo | Classifier + SSE |

### Layer 4 — grounding + honesty · by T+3:20

| Task | Owner | Status | Blockers |
|---|---|---|---|
| 🔥🟡 **GroundingGate — all 8 corpus §15.2 rules as deterministic post-processing**, per rule: pass/fail + human-readable detail | Lakshitha | todo | Generation |
| 🟡 Claim-level sentence decomposition; marker resolution against retrieved chunks; **unresolvable markers stripped and the sentence marked unsupported** | Lakshitha | todo | GroundingGate |
| 🟡 `groundedness` score + per-sentence verdicts | Lakshitha | todo | GroundingGate |
| 🟡 Confidence level + **the reason string** (High / Moderate / Low / Insufficient) | Lakshitha | todo | Groundedness |
| 🟡 **Retry: hard cap of 1**, enforced by a counter — re-expand query, widen `k` to 10, regenerate once. **Never loop.** | Lakshitha | todo | GroundingGate |
| 🔥🟡 **Conflict detection** — structural signals first (`disputed_report` in set · ≥2 `field_note` on one event · ≥2 `SV-*` same species+region with differing counts), semantic LLM check confirmatory only | Lakshitha | todo | Retrieval |
| 🔥🟡 Conflict output: each position with record ID, claim, evidence quality, **named reliability limitation**, plus the resolution recommendation. **Never merged.** | Lakshitha | todo | Conflict detection |
| 🔒 **GATE T+3:20 — the turquoise question must produce the Contested state**: no cause named, `FN-A`/`FN-B`/`LAB-C` all present, chain of custody flagged | Lakshitha | todo | Conflicts |
| 🟢 Hard-verify the **second** conflict too — `SV-101` vs `SV-102` survey-effort normalization | Lakshitha | todo | Conflicts |

### Layer 5 — the agentic layer · by T+4:10

| Task | Owner | Status | Blockers |
|---|---|---|---|
| 🟡 **Orchestrator** (`gpt-4o-mini`, temp 0): rewrite → classify → filter hints → route | Lakshitha | done | Layer 4 green |
| 🔥🟡 **Three fixed specialists**, each owning one section: 🐋 Marine-Life Protector (Affected Species) · 🌊 Incident Investigator (Likely Causes + conflicts) · 🚨 Emergency Responder (Recommended Actions) | Lakshitha | done | Orchestrator |
| 🟡 Per-specialist retrieval focus and record-type boosts | Lakshitha | done | Specialists |
| 🟡 Specialist guardrails: species isolation · no confirmed cause without explicit confirmation · `MED-*` red flags + fictional-material disclaimer | Lakshitha | done | Specialists |
| 🟡 Emergency Responder emits the corpus's **verbatim `KC-01` public-communication template** | Lakshitha | done | Specialists |
| 🟡 Routing: `sitrep` (3 parallel) / `focused` (1) / `compare` (2 disjoint sub-queries → synthesis) | Lakshitha | done | Specialists |
| 🔥🔴 **Concurrent dispatch** — `asyncio.gather`, not sequential. Wall clock = slowest agent, not the sum. | Lakshitha | done | Specialists |
| 🔥🟡 **Hard limits enforced by counters in orchestrator state, NOT by prompt:** 3 specialists max · 1 retry · **75 s per agent · 180 s total budget** (raised from 8 s/25 s — `gpt-5-mini` measures 36–52 s per section) · **≤8 LLM calls/query** | Lakshitha | done | Dispatch |
| 🔥🟡 **Degradation ladder rung 3** — any specialist failure falls back to Layer 2 single-agent fill over already-retrieved chunks. **Identical output structure.** | Lakshitha | done | Dispatch |
| 🟡 Partial results — a timed-out section renders `timed_out` + reason naming its agent; **the report still ships** | Lakshitha | done | Dispatch |
| 🔥🟡 **SSE emitter** (`sse-starlette`) — every §1.2 event type, monotonic `sequence_number`, `answer.completed` carrying the full response body | Lakshitha | done | Orchestrator |
| 🟢 `DEMO_MODE` response cache for the four demo questions — zero API dependency | Lakshitha | todo | Query path working |
| 🟢 Response cache keyed on normalized query, so rehearsal runs cost nothing after the first | Lakshitha | todo | Query path working |

---

## 🎨 Nipuna (P2) — UI/UX + frontend · `frontend/`

> **Seven routes to build.** Full screen-by-screen requirements in `docs/UI_SPEC.md` — it specifies
> *what* each screen does. **Everything visual is your call**: colour, type, spacing, components,
> iconography. `SOLUTION.md` §8.2's "abyss at night" palette is a *suggestion*, not a mandate.
> Push back on the spec if it fights good design.
>
> **Build order:** `/app` → `/app/documents` → auth pages → `/` → `/app/incidents` → `/app/investigations`.

### Setup & foundations · T+0:00

| Task | Owner | Status | Blockers |
|---|---|---|---|
| 🔴🔥 **Create JSON fixtures from §1.1, §1.4, §1.6 — AND a mock SSE stream replaying the §1.2 events on a timer.** Build the entire UI against them, including the parallel-fill animation. **Do not wait for the backend.** | Nipuna | todo | API contract frozen |
| 🟡 Scaffold Next.js (App Router); `tsconfig` `strict: true`; folders `app/ components/ lib/ hooks/ types/` | Nipuna | todo | Folder structure |
| 🟡 `frontend/types/api.ts` — hand-mirror every §1 shape incl. the SSE event union. One source of truth. | Nipuna | todo | API contract frozen |
| 🟡 Pick the styling approach and set up the design foundation — **your call entirely** | Nipuna | todo | Scaffold |
| 🔴 **App shell + auth guard in `app/app/layout.tsx`** — nav, corpus-status indicator, account menu, redirect-to-`/login`. One guard, not one per page. | Nipuna | todo | Scaffold |
| 🟡 Feature-flag plumbing so each layer's UI can be switched off independently | Nipuna | todo | Scaffold |

### `/app` — Command Center ★ the demo screen · Layers 2–6

| Task | Owner | Status | Blockers |
|---|---|---|---|
| 🟡 Question input — multi-line, Enter to submit, Shift+Enter newline, 4 Pandora example questions when empty | Nipuna | todo | Fixtures |
| 🔥🔴 **Six-section report renderer** — fixed order, agent badge per section, **renders each section on arrival and NEVER buffers them into order.** Out-of-order completion is the proof of concurrency. | Nipuna | todo | Fixtures |
| 🔥🔴 **Must not branch on `assembly_mode`** — Layer 2 and Layer 5 output are structurally identical, and that's what makes the fallback invisible | Nipuna | todo | Renderer |
| 🔥 **Empty/timed-out sections render their `empty_reason`** with the owning agent named. A blank section looks like a bug. | Nipuna | todo | Renderer |
| 🔥🔴 **Citation chips** — record-ID markers (`[INC-005]`), interactive, activating one spotlights its source card and scrolls it into view. **Keyboard-activatable, not hover-only.** Unresolvable markers render as plain text, never a broken chip. | Nipuna | todo | Fixtures |
| 🔥 Source cards — record ID + title, document name, chapter, **page**, excerpt with query terms highlighted, relevance score, **evidence-quality badge**, risk chip. **Visible alongside the report, not behind a tab.** | Nipuna | todo | Fixtures |
| 🔥 Unsupported sentences render **struck through and labelled**, not hidden. *Model inference* blocks visually distinct from documented protocol. | Nipuna | todo | Renderer |
| 🔥🟡 **Triage banner** — W1–W4 + shape + word + cited reason, **renders before any generated text** | Nipuna | todo | Fixtures |
| 🔥 Confidence meter — level + **its reason in words**, never a bare number, never colour alone | Nipuna | todo | Fixtures |
| 🔥🔴 **Conflicting Evidence panel** — positions side by side with equal visual weight, each with record ID, claim, evidence quality, reliability limitation, plus the resolution recommendation. **Must visually assert no winner was picked.** Not collapsed by default. | Nipuna | todo | Fixtures |
| 🔥 Insufficient-evidence state — amber banner + **the mandated sentence verbatim** + searched scope + closest matches labelled insufficient + what would resolve it. **Honest limitation, NOT an error.** No red, no error icon. | Nipuna | todo | Fixtures |
| 🟡 SSE client (`EventSource`) — consumes §1.2 events, **ignores unknown types silently**, falls back to `POST /api/v1/ask` on drop | Nipuna | todo | Mock stream |
| 🔥🟡 **Orchestration rail** — three agent orbs (dormant / active with live elapsed / complete with counts / timed out), step timeline, **GroundingGate 8-rule panel ticking through** | Nipuna | todo | Mock stream |
| 🔥🔴 **Orb ↔ section tethers** — each orb visually connected to the section it owns, all three igniting simultaneously on a `sitrep` query. **`SOLUTION.md` calls this the single most important visual in the product.** | Nipuna | todo | Rail |
| 🟢 Trace replay control — demo insurance if the network stalls | Nipuna | todo | Rail |
| 🟡 **Map panel** — 10 inline-SVG `REG-*` zones, lit by triage colour from `affected_region_ids`, hover for name, click to filter sources by region, honest empty state | Nipuna | todo | Fixtures |
| 🔥🔴 **Role toggle — client-side re-render ONLY.** Guardian / Researcher / Citizen. **Must have no code path to the network.** If it re-queried, cited evidence could shift between roles and the grounding story collapses on stage. | Nipuna | todo | Renderer |
| 🟡 Assembling state — progress visible, input disabled, no double-submit | Nipuna | todo | Fixtures |
| 🟡 "New Investigation" reset — clears report, trace, map state, sources | Nipuna | todo | Renderer |

### `/app/documents` — Knowledge base

| Task | Owner | Status | Blockers |
|---|---|---|---|
| 🟡 **Corpus card pinned first** — pages · records · chunks · Indexed, with the record-type breakdown. **No delete affordance at all.** | Nipuna | todo | Fixtures |
| 🟡 Upload — drag-and-drop **plus** click-to-browse; states types and 10 MB limit up front; live ingestion progress | Nipuna | todo | Fixtures |
| 🟡 Document rows — name, type, size, status, page/chunk/**record** counts, chunking mode, delete | Nipuna | todo | Fixtures |
| 🔥 **Status updates without manual refresh** — poll `GET /api/v1/documents/{id}` while pending/indexing | Nipuna | todo | Fixtures |
| 🟡 Client-side type/size validation before upload starts | Nipuna | todo | Upload |
| 🟡 Failed-row error message, delete confirmation. **Corpus-only is NOT an empty state** — copy invites a question. | Nipuna | todo | List |

### Public + secondary pages

| Task | Owner | Status | Blockers |
|---|---|---|---|
| 🟡 `/login` + `/signup` — Supabase Auth, session handling, JWT on every request, no double-submit | Nipuna | todo | Supabase keys |
| 🟡 **`/` landing page** — hero, the problem, three things it does, how it works, worked example, CTA, footer | Nipuna | todo | Scaffold |
| 🔥 Landing-page worked example — the **real** turquoise report with a visible record-ID citation and the no-confirmed-cause moment. Highest-value region on the page. | Nipuna + Lakshitha | todo | Layer 4 working |
| 🟢 `/app/incidents` — filter by risk + region, rows pre-fill the Command Center question box | Nipuna | todo | Core screens done |
| 🟢 `/app/investigations` — past reports + trace replay. **Cut this first if time is short.** | Nipuna | todo | Core screens done |

### Integration & polish

| Task | Owner | Status | Blockers |
|---|---|---|---|
| 🔥 Swap fixtures + mock stream for the real backend base URL | Nipuna | todo | Manujaya's stubs live |
| 🟡 Responsive pass — 360px / 768px / 1280px. **Triage banner never truncated; conflict panel keeps equal weight when stacked; agent states stay visible.** | Nipuna | todo | Core screens done |
| 🟡 Accessibility pass — keyboard reachability, focus order, labels, **colour never the sole signal** (corpus §11.1), ARIA live region announcing *which* section arrived, `prefers-reduced-motion` | Nipuna | todo | Core screens done |
| 🟢 Error handling for the §Error-envelope codes | Nipuna | todo | Core screens done |
| 🟢 Visual polish pass | Nipuna | todo | Core screens done |

---

## ⚙️ Manujaya (P3) — Backend gateway · `backend/`

> Built on branch `backend`. Everything below is on it. Run it with
> `cd backend && python run.py` → `http://localhost:5000/docs`.
> `AGENT_STUB_MODE=true` + `AUTH_DISABLED=true` in `.env` make it useful before
> Azure, Supabase, or `agent/` exist — see `backend/README.md`.

| Task | Owner | Status | Blockers |
|---|---|---|---|
| 🔴 **Stub every §1 endpoint returning the exact contract payloads — unblocks Nipuna in 30 minutes.** A FastAPI stub returning a dict is ~3 lines. | Manujaya | done | — |
| 🔴 CORS for `localhost:3000` + the Static Web App origin — configure now, don't debug it at 2am | Manujaya | done | SWA origin to be appended to `CORS_ORIGINS` once Malindu provisions it |
| 🟡 FastAPI scaffold: `app/{api,core,db,schemas,services}/`, `requirements.txt`, Uvicorn entrypoint | Manujaya | done | — |
| 🟡 Pydantic `Settings` class reading env vars — validated at startup, fails loudly on a missing key. **No scattered `os.getenv()`.** | Manujaya | done | — |
| 🟡 Pydantic schemas mirroring every §1 request/response shape | Manujaya | done | — |
| 🟡 SQLAlchemy 2.0 models: `documents`, `answers`, `agent_actions`, `conversations` | Manujaya | done | — |
| 🟡 Alembic init + first migration, applied to Azure PostgreSQL | Manujaya | doing | `0001` + `0002` (answers hold a Situation Report) written against the Postgres dialect; **not yet applied — Postgres not provisioned.** An Azure **SQL Server** was provisioned instead; see the Decisions Log |
| 🟡 Supabase JWT validation dependency (`python-jose`) — signature + expiry, extract user ID | Manujaya | doing | Code done; unverified against a real token — needs `SUPABASE_JWT_SECRET` |
| 🟡 `httpx` agent client — `X-Internal-Key`, **30 s** query / **60 s** ingest timeouts | Manujaya | done | Wired; live call untested until Lakshitha's stubs are up |
| 🟡 `POST /api/v1/documents` — validate type + size, persist, return `202`, dispatch to `/rag/ingest` async | Manujaya | done | — |
| 🟡 `GET/DELETE /api/v1/documents` — **delete must remove Postgres row AND AI Search vectors** | Manujaya | doing | **Part 2 has no delete endpoint.** Proposed `DELETE /rag/documents/{id}` — needs Lakshitha + a contract edit. Gateway calls it and logs when it's absent. |
| 🔥 `POST /api/v1/ask` — call `/agent/sitrep`, reshape to the §1.1 Situation Report, join `document_name` from Postgres | Manujaya | done | Re-pointed at the Pandora contract 2026-08-05; verified against `agent/`'s own Pydantic models |
| 🔥 `POST` + `PATCH /api/v1/agent-actions` — persist, approve/reject/complete, set `resolved_at` | Manujaya | done | — |
| 🟡 `GET /api/v1/agent-actions` with status/type filters and paging | Manujaya | done | — |
| 🟡 Standard error envelope on every non-2xx via an exception handler + the documented `code` values | Manujaya | done | — |
| 🟡 `GET /health` for the Azure App Service probe | Manujaya | done | — |
| 🟢 `422 corpus_not_indexed` guard before any LLM call | Manujaya | done | Counts the user's indexed documents; should move to §2.4's `corpus_indexed` once the corpus is seeded as a shared row |
| 🟢 Request/response logging for demo debugging | Manujaya | done | — |
| 🟢 25 contract tests (SQLite + stub agent, no network) + `ruff` clean | Manujaya | done | — |
| 🔥 `GET /api/v1/ask/stream` — SSE, forwarding `/agent/sitrep`'s trace unbuffered | Manujaya | done | Verified over a real socket: frames arrive ~120 ms apart, terminal `answer.completed` carries the whole §1.1 body. **Needs one thing from Lakshitha — see the Decisions Log.** |
| 🟡 `GET /api/v1/situation-reports` (§1.5) + `GET /api/v1/incidents` (§1.6) | Manujaya | todo | `answers` already stores the filterable columns §1.5 needs |

---

## ☁️ Malindu (P4) — Deployment + cloud infra · `infra/`

| Task | Owner | Status | Blockers |
|---|---|---|---|
| 🔴 *(All five T+0:00 unblockers above are Malindu's)* | Malindu | todo | — |
| 🔴🔥 **Corpus seed job** — run `seed_corpus` over the PDF, verify chunk/record counts, **commit the prebuilt index** so the app is queryable on a fresh clone | Malindu + Lakshitha | todo | Chunker + index |
| 🔴 **Seed the demo account** in Supabase — nobody signs up on stage | Malindu | todo | Supabase project |
| 🟡 Create the two Azure App Services (backend + agent) and the Static Web App | Malindu | todo | Azure access |
| 🟡 App Service configuration — every env var and feature flag set; **no secrets in code or docs** | Malindu | todo | App Services created |
| 🟡 GitHub Actions: build + deploy backend on push to `main` | Malindu | todo | App Service + backend scaffold |
| 🟡 GitHub Actions: build + deploy agent — **same Python workflow pattern as the backend**, so write it once and copy | Malindu | todo | App Service + agent scaffold |
| 🟡 GitHub Actions: build + deploy frontend to Static Web Apps | Malindu | todo | SWA + frontend scaffold |
| 🟡 **Verify SSE survives App Service** — response buffering or proxy timeouts will silently break progressive rendering. Test early; it's an easy thing to discover too late. | Malindu | todo | Both deployed |
| 🟡 Azure health-check probes → backend `/health` and agent `/health` | Malindu | todo | Both deployed |
| 🟡 Networking: agent App Service reachable by the backend, **not publicly routable** | Malindu | todo | Both deployed |
| 🟡 Postgres firewall rules — Azure services + team dev IPs | Malindu | todo | Postgres provisioned |
| 🔥 **End-to-end smoke test** — ask the turquoise question, get a cited Contested report | Malindu | todo | All three services running |
| 🟡 **Git tag each layer gate**: `v1-core-rag`, `v2-sitrep`, `v3-honest`, `v4-agentic` | Malindu | todo | Each gate passing |
| 🔥 **Record the backup demo video at T+3:20** against `v3-honest` — a guaranteed-good demo on file | Malindu | todo | Layer 4 green |
| 🔥 **Re-record at T+4:45** against the final build | Malindu | todo | Layer 6 or freeze |
| 🟢 `README.md`: setup, env vars, `uvicorn` ×2 + `npm run dev`, corpus seeding, the 7 sample questions, troubleshooting | Malindu | todo | Everything running |
| 🟢 Architecture diagram export for the submission | Malindu | todo | `docs/ARCHITECTURE.md` |
| 🔥 **Prebuilt-component disclosure** — *(a rules requirement, easy to forget)*. See `docs/TECH_STACK.md`. | Malindu | todo | — |

---

## 🤝 Integration & Demo — everyone

| Task | Owner | Status | Blockers |
|---|---|---|---|
| 🔥 Integration checkpoint 1 — frontend hits the real backend stubs | Nipuna + Manujaya | todo | Both scaffolds up |
| 🔥 Integration checkpoint 2 — backend hits the real agent service | Manujaya + Lakshitha | todo | Agent endpoints real |
| 🔥 Integration checkpoint 3 — **SSE end to end: agent → gateway → browser, unbuffered** | All three | todo | SSE emitter + passthrough |
| 🔥 **Full flow locally** — question → triage → parallel assembly → cited report → conflict panel → role toggle | All | todo | Checkpoints 1–3 |
| 🟡 Verify each of the **ten feature flags** toggles cleanly — especially `AGENTIC_ENABLED=false` giving a clean Layer 2 report | All | todo | Layer 5 |
| 🔥 **Rehearse the partial-report case deliberately**, so it can be narrated as designed behaviour rather than discovered live | All | todo | Layer 5 |
| 🔥 **Verify the role toggle doesn't shift citations** — flip all three roles on the turquoise question and diff the cited record IDs. They must be identical. | Nipuna | todo | Role toggle |
| 🟡 Full flow on deployed Azure *(nice to have — **the demo runs locally**)* | All | todo | Local flow + deploys |
| 🟡 Rehearse the five-beat pitch against a timer, **twice** | All | todo | Flow working |
| 🟢 Final polish pass — copy, empty states, obvious bugs | All | todo | Flow working |

---

## Submission Checklist — all 9 items

| # | Requirement | Owner | Status |
|---|---|---|---|
| 1 | Working RAG application *(local demo primary, Azure if green)* | All | todo |
| 2 | GitHub repository, clean history, four layer tags | Malindu | todo |
| 3 | README with setup + usage | Malindu | todo |
| 4 | Architecture diagram | Malindu | todo |
| 5 | Demonstration, 3+ questions *(we show 4: coral damage · parallel compare · turquoise conflict · out-of-corpus refusal)* | All | todo |
| 6 | Evidence of retrieved sources for each answer | Built-in | todo |
| 7 | 3–5 minute presentation | All | todo |
| 8 | **Disclosure of prebuilt components** *(rules requirement)* | Malindu | todo |
| 9 | **Backup demo video ×2** *(T+3:20 and T+4:45)* | Malindu | todo |

---

## Notes

- **The three 🔴 stub tasks plus the mock SSE stream are the highest-leverage work in this file.**
  They let four people build in parallel from minute one instead of waiting in a chain.
- **`SOLUTION.md` §10 is binding, not advisory.** Finish a layer, commit it, tag it, *then* start the
  next. Five things at 70% is a demo of apologies.
- **If anything is unstable at T+4:45, flip its flag rather than debug it.** We demo a smaller thing
  that works, never a bigger thing that doesn't.
- **No layer may modify code owned by an earlier layer.** Layer 5's orchestrator *calls* Layer 1's
  retriever; it never edits it.
- If you're blocked, put the blocker in the **Blockers** column and say so in the channel. Don't sit
  on it.

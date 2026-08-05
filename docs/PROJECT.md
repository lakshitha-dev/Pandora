# PROJECT.md — North Star

**Pandora Knowledge Guardian** — the *Guardian Command Center*, a web application
*Describe what you're seeing. Get a cited Situation Report — and an honest answer when Pandora doesn't know.*

> One page. If a decision isn't in here or in the Decisions Log, it hasn't been made.
> **Design source of truth is `SOLUTION.md`.** This file is the summary a teammate reads first.

---

## The Challenge

| | |
|---|---|
| **Event** | Pandora Builderthon 2026 |
| **Challenge** | *"Echoes of Pandora: An AI Knowledge Guardian for a Living Ecosystem"* |
| **Theme** | **Avatar: The Way of Water** — oceans, bioluminescence, an interconnected ecosystem |
| **Time limit** | **5 hours**, hard. Code freeze at T+4:45; the last 15 minutes are rehearsal only. |
| **Brief** | `PANDORA_RAG_HACKATHON_2026.md` *(read-only — the judges' words, never edit)* |
| **Demo dataset** | `Pandora_RAG_Knowledge_2026 (1).pdf` — 56 pp, 15 chapters + 2 appendices, **~130 atomic records**, **pre-indexed at seed time** into ~220 chunks. A markdown reference copy sits at `Pandora_RAG_Knowledge_2026.md`. |

### Judging criteria — 100 marks

> **Reading the § references below.** A bare `§` always means a section of **`SOLUTION.md`**.
> References to the knowledge corpus are always written as **"corpus §x.y"**. The two numbering
> schemes overlap — corpus §4.5 is the Water Incident Classification, SOLUTION.md §4.5 is Source
> References — so the qualifier matters.

| Category | Marks | Where we win it |
|---|---|---|
| **RAG Architecture & Retrieval Quality** | **25** | Record-aware chunking · hybrid BM25 + vector + RRF · LLM reranking · metadata filters (§4.2–4.3) |
| **Accuracy & Grounded Responses** | **20** | GroundingGate — the **corpus's own** 8 published rules (corpus §15.2) as a validator · conflict presentation · the honest refusal (§4.4–4.6) |
| **Real-World Problem Solving** | **20** | The Situation Report format · W1–W4 triage cited to the **corpus's own** scale (corpus §4.5) · executable Incident Action Cards (§2.1, §5.2) |
| **User Interface & Experience** | **15** | Bioluminescent evidence console · inline citation chips · orchestration rail · accessible per the **corpus's own** communication guidance (corpus §11.1) — see §8 |
| **Innovation** | **10** | Three specialists filling report sections in parallel, visibly (§5, §7) |
| **Presentation & Documentation** | **10** | Five-beat demo script · architecture diagram · this doc set (§13–14) |

**45 of those 100 marks sit in the first two rows.** That is why `SOLUTION.md` §10 makes the core
RAG pipeline Layer 1 and forbids starting anything else until it's green and tagged.

---

## What We're Building

Pandora's knowledge is real, extensive, and **useless at the moment it matters most.**

When a section of ocean changes colour and fish start leaving, everything a guardian needs already
exists in the archive — an incident playbook, a water-station reading, a severity scale, a species
profile, a policy, a field checklist. It is scattered across six records that never reference each
other, thirty pages apart. A guardian standing on a black-sand beach with dying shellfish at their
feet has **minutes, not an afternoon in the archive.**

Three failures compound:

1. **Scatter.** `WS-03`'s reading and `INC-005`'s playbook describe the same event and live 30 pages apart.
2. **Hallucination.** A general chatbot asked about a Pandoran vent plume invents a confident,
   fluent, fabricated protocol. In an emergency a plausible wrong answer is worse than no answer —
   it gets acted on.
3. **False certainty.** The subtle one, and the one the corpus cares most about. Evidence on Pandora
   is genuinely contested: `FN-A` blames plankton, `FN-B` implicates an upstream pigment workshop,
   `LAB-C` has an incomplete chain of custody. A system that resolves that into one tidy answer has
   destroyed the single most decision-relevant fact — **that nobody actually knows yet.**

**So we are not building an answer machine. We are building an evidence machine.**

Every question produces a **Situation Report**: a live, structured, operational document with six
fixed sections — **Priority · Affected Species · Likely Causes · Recommended Actions · Sources ·
Confidence**. Each section is independently owned, independently cited, and has a defined visible
behaviour when it *cannot* be filled. A chatbot returns a paragraph and a list of links. A command
center returns something an incident lead can execute from.

**The distinction that matters:** ours retrieves evidence, separates documented protocol from
inference, surfaces disagreement instead of hiding it, and says plainly when the corpus does not know.

**Who it's for:** Pandora's environmental guardians, researchers, community leaders, and citizens —
the same evidence re-rendered for whichever of them is reading (`SOLUTION.md` §8.6).

**The deliverable is a full web application**, not an API with a chat box: a public landing page, sign-in,
and a four-screen authenticated workspace. Seven routes — see [In scope](#-in-scope) and
`docs/UI_SPEC.md`.

### The decisive insight

> **The provided knowledge corpus contains its own grading key.**

Most teams will treat the corpus as "56 pages of text to chunk." It isn't. It is a structured record
database with a **published retrieval specification**:

- **Page 2** instructs that information-quality labels — *verified observation · community tradition ·
  provisional interpretation · modeled estimate · disputed report* — must be **preserved**, that
  answers must distinguish documented fact from inference, and that disagreement must be **presented,
  not silently resolved**.
- **§15.2 is literally titled "Retrieval Grounding Rules"** and lists eight explicit requirements.
  That is the 20-mark Accuracy category, written out in advance.
- **§14.3 is a planted trap with a stated expected answer:** *"an answer should present all three
  records, identify the incomplete chain of custody, avoid declaring a confirmed cause, and recommend
  additional properly documented sampling."*

A conventional RAG app answers *"the turquoise water was caused by a plankton bloom."* **That fails
the corpus's own test.** Ours refuses to name a cause, surfaces the three-way conflict, flags the
broken chain of custody — and in the demo we open the judges' own corpus to that page and read the
expectation aloud.

**Design consequence:** our agentic architecture is not decoration for the innovation marks. Every
sub-agent and validator exists to enforce rules the corpus itself published. Grounding and innovation
are the same investment.

---

## The ONE Core User Flow

Everything else is secondary. If this works end to end, we have a product.

**Scenario:** a guardian sees the water at Awa Reef turn turquoise and the fish move offshore.

| # | Step | What the user does | What the system does |
|---|---|---|---|
| 1 | **Sign in** | Logs in | Supabase Auth issues a JWT; every later request carries it. **A demo account is pre-seeded — nobody signs up on stage.** |
| 2 | **Access knowledge** | *(nothing)* | The Pandora corpus is **already indexed**. The app is useful the second it loads. Uploading more documents is supported and demoed, never on the critical path. |
| 3 | **Describe the situation** | Types *"the water near Awa Reef has turned turquoise and the fish are leaving the area"* | Plain language, not keywords. Backend forwards to the agent service. |
| 4 | **Orchestrate** | — | Query rewritten and expanded; use case, query shape, and **W1–W4 severity** classified against the corpus's own §4.5 scale; metadata filters inferred |
| 5 | **See priority and place, instantly** | Reads the banner | **Before any generation completes:** the 🔴/🟠/🟢 triage banner renders with a **cited** reason, and the map lights the affected `REG-*` zone. The screen is never blank, never spinning. |
| 6 | **Retrieve** | — | Hybrid BM25 + vector over Azure AI Search, RRF-fused, **LLM-reranked**, top-6 into context |
| 7 | **Watch the report assemble** | Watches | Three specialists fill their owned sections **concurrently**, generating only from retrieved context, emitting a citation marker per claim. Sections stream in as they complete — out of order, which is how you know it's genuinely parallel. |
| 8 | **Validate** | — | **GroundingGate** checks each section against the corpus's eight §15.2 rules. One retry maximum, per section. |
| 9 | **Read the report** | Reads it | Six sections render with **inline citation chips**; hovering one spotlights its source card — record ID, document name, chapter, page, verbatim excerpt, relevance score, evidence-quality label |
| 10 | **🔥 See what nobody knows** | Reads Likely Causes | Where records disagree, the section **refuses to name a cause**. A Conflicting Evidence panel shows each position side by side with its reliability limitation. Confidence reads *"Moderate — 3 sources, 1 unresolved conflict, chain of custody incomplete."* |
| 11 | **Re-render for an audience** | Flips the role toggle | The same report in Guardian / Researcher / Citizen register — **same frozen evidence, same record IDs**. No re-query, so the cited facts can never shift. |
| 12 | **Honest failure** | — | If retrieval is below threshold: *"⚠ Insufficient Evidence — Recommend Field Investigation"*, then the brief's mandated sentence verbatim, then what was searched and what evidence would resolve it. **Never invented.** |
| 13 | **Reset** | Clicks *New Investigation* | Clears conversation, report, trace, map state, sources — one click, clean console |

**The demo moment is step 10.** Steps 1–9 are a good RAG app that several teams will build.
Step 10 is where a judge sits up — the system stops sounding confident and starts being *honest*,
and it does so exactly as the corpus specified.

---

## Scope

### ✅ In scope

| Area | What we're building |
|---|---|
| **Website — 7 routes** | `/` landing · `/login` · `/signup` · `/app` Command Center ★ · `/app/documents` · `/app/incidents` · `/app/investigations` *(if time)*. Full specs in `docs/UI_SPEC.md`. |
| Ingestion | The Pandora corpus **pre-indexed**, plus upload of PDF / DOCX / CSV / TXT; extract, chunk, embed, index, delete |
| Chunking | **Two-tier record-aware** — one corpus record per chunk, no overlap · narrative 800/120 · one table row per chunk |
| Retrieval | Query rewriting · metadata filters · hybrid BM25 + vector with RRF fusion · **LLM reranking** · scoring |
| Generation | Closed-book grounded answers from retrieved context only, `gpt-4o-mini`, per-claim citations |
| Citations | Inline chips → record ID, document name, chapter/section, **page**, excerpt, relevance score, evidence-quality label |
| **Situation Report** | Six-section contract; independent per-section status; **identical structure in single-agent and multi-agent modes** |
| **Grounding** | GroundingGate — the corpus's eight §15.2 rules as a validator; groundedness score; confidence that states its reason |
| **Uncertainty** | Three honest states: **Grounded / Contested / Insufficient**. The insufficient state prints the brief's mandated sentence **verbatim**: *"The available Pandora knowledge base does not contain sufficient evidence to answer this question."* Do not reword it. |
| **Conflicts** | Detection + side-by-side panel + named reliability limitations. **Never merged into one answer.** |
| **Severity** | W1–W4 triage classified against the corpus's own §4.5 scale, **cited** |
| Agentic | Orchestrator + **3 fixed** specialists; `sitrep` / `focused` / `compare` routing; 1 retry; 8 s timeouts |
| **Map visualization** | Stylized 10-zone Pandora map lit by priority; click a zone to filter sources by region |
| **Role toggle** | Guardian / Researcher / Citizen — re-render from frozen evidence, **no re-query** |
| Auth | Supabase email/password sign-in, with a pre-seeded demo account |
| Deploy | Azure — App Service ×2 (backend + agent) + Static Web Apps (frontend). **The demo runs locally.** |

### ❌ Out of scope

| Excluded | Why |
|---|---|
| **Marketing site beyond one landing page** | No blog, pricing, about, or docs site. One `/` that explains the product is enough. |
| **Onboarding tour / walkthrough** | The corpus is pre-indexed, so there is nothing to onboard. Ask a question. |
| **Email confirmation on signup** | Straight to `/app`. Every extra step in a demo is a step that can fail. |
| Voice input | Browser speech API is ~30 min but adds live-demo failure surface (mic permissions, a noisy judging room) for zero grounding benefit |
| Multilingual | Corpus is English-only; translating would break verbatim citation fidelity — actively harmful to our core strength |
| Image / map-based **retrieval** | Querying *by geography* needs coordinates the corpus doesn't have — it has named regions. **Map *visualization* is in scope; map *retrieval* is not.** |
| Knowledge-graph database | Real value, but 2+ hours. We capture ~80% via `region_id` and `record_type` metadata cross-links. |
| OCR / scanned PDFs | The corpus has a text layer |
| Multi-tenant / org management | One user, their own uploads, one shared corpus |
| Roles & permissions | The role toggle is a **presentation lens**, not an authorization boundary |
| Billing / subscriptions | Not a product yet |
| Mobile-native app | Responsive web only |
| Real-time collaboration | Single user per session |
| Fine-tuned models / custom embeddings | Impossible in 5 hours; no benefit at 220 chunks |
| Full conversation memory | Last-turn coreference only — full history invites context drift and citation confusion |
| Dynamic agent pool | The three specialists are **fixed**. Not configurable, not extensible at runtime. |
| User-configurable chunking UI | Judges evaluate output, not knobs |
| Comprehensive test suite | Manual verification against 10 fixed questions instead |

**Scope defence:** the specialist count is **fixed at three**, the retry cap is **1**, and the total
LLM-call budget is **8 per query**. All three constraints exist to keep the agent bounded and
demoable. An unbounded agent loop is the single most common way a hackathon demo dies on stage.

---

## The Build Order Is Binding

`SOLUTION.md` §10 is not advice. Six layers, each **independently demoable**, each behind its own
feature flag and git tag:

| Layer | Delivers | Banks | Gate |
|---|---|---|---|
| **1** | Core single-agent RAG, end to end | **45 marks — a complete submission on its own** | **T+2:00 · `v1-core-rag`** |
| **2** | Situation Report shell | Real-world 20 · UX 15 | T+2:40 · `v2-sitrep` |
| **3** | Triage banner | Real-world 20 | T+3:00 |
| **4** | Confidence meter + honesty flip + conflicts | Accuracy 20 | T+3:20 · `v3-honest` |
| **5** | Three specialists filling sections live | Innovation 10 · UX 15 | T+4:10 · `v4-agentic` |
| **6** | Map · role toggle · orchestration animation | UX 15 · Innovation 10 | T+4:40 *(if time)* |

**Three iron rules:** every layer is *demoable*, not merely compiling · a later layer breaking must
**never** take down an earlier one · marks are **banked, not promised**.

**Auth and deployment run in parallel with Layer 1 and never gate it.** If the schedule slips, the
designated release valve is **dropping auth** — it is the single largest recovery of time, and the
role toggle (which is what the rubric actually rewards) needs no auth at all. `/app/investigations`
is cut before that.

---

## Decisions Log

Append a row whenever you make a call that affects someone else's work. Newest at the bottom.

| Date | Decision | Why |
|---|---|---|
| `[KICKOFF]` | **Backend is Python + FastAPI** (SQLAlchemy 2.0 + Alembic), not C# .NET | One language across both services — one runtime, one set of idioms, and either backend person can read the other's code. Also removes the .NET snake_case configuration entirely. |
| `[KICKOFF]` | **Two Python services kept separate** — `backend/` gateway + `agent/` | Both are FastAPI and could merge, but the split buys independent deploys and unambiguous ownership: Manujaya redeploys the API without touching retrieval; Lakshitha rebuilds chains without risking auth or the DB. |
| `[KICKOFF]` | **OpenAI models on Azure AI Foundry** — `gpt-4o-mini` + `text-embedding-3-small`. Settled. | One client, one endpoint, one key shared by generation and embeddings. Everything stays on Azure and bills to one place. |
| `[KICKOFF]` | Frontend never calls the agent service directly | One origin, one auth surface, one CORS config to debug. |
| `[KICKOFF]` | JSON is `snake_case` on every wire | Python, Pydantic, SQLAlchemy, and Postgres all use it natively — one convention, zero configuration, no translation layer anywhere. |
| `[KICKOFF]` | **Deliverable is a 7-route web application**, not just an API | Judges interact with a website. The landing page and the workspace both count. |
| `[KICKOFF]` | **`docs/UI_SPEC.md` specifies screen function only; Nipuna owns all visual design** | Colour, type, spacing, components, and iconography are design decisions and shouldn't be frozen in a spec written by someone else. |
| 2026-08-05 | **Windows devs run the backend with `python run.py`, not `uvicorn app.main:app`** *(Manujaya)* | psycopg's async mode cannot use Windows' default `ProactorEventLoop`, and uvicorn builds that loop before it imports the app — so the app can't fix it from the inside. `run.py` sets the selector policy first. Linux/App Service keeps the plain uvicorn command. |
| 2026-08-05 | **The gateway reshapes the agent's flat report into §1.1, in `backend/app/services/report_mapping.py`** *(Manujaya)* | `agent/` emits `priority_class` / `confidence_level` as flat strings, calls a conflict's nature `nature`, says `"medium"` where §1.1 says `"moderate"`, and returns the refusal as one text block. Rather than ask Lakshitha to restructure a working orchestrator mid-build, the gateway maps it — one file, pure functions, and every unrecognised value degrades to a documented default instead of 500ing the browser. |
| 2026-08-05 | **`POST /api/v1/ask` calls `/agent/sitrep`, not `/rag/query`** *(Manujaya)* | `/rag/query` fills one section; the six-section report needs the orchestrated path. `agent_client.query()` stays for focused single-section fills and degradation rung 3. |
| 2026-08-05 | **⚠ ASK FOR LAKSHITHA: put the `/agent/sitrep` response body in the `answer.completed` payload** *(Manujaya)* | §1.2 requires that event's payload to be the complete report so a client can use the stream alone. `agent/`'s emits counts only (`llm_call_count`, `citation_count`, …), so the gateway currently re-runs `/agent/sitrep` in JSON mode to assemble it — **a second full orchestration per streamed question.** One extra field on that emit removes the second call entirely; the gateway already prefers the payload when it's there. |
| 2026-08-05 | **Backend stays on PostgreSQL; the provisioned Azure SQL Server is unused** *(Manujaya)* | An Azure SQL Server (`pandora-db-server`) exists, but the gateway is psycopg + JSONB + Postgres-dialect migrations. Switching dialects mid-build costs an hour and puts an ODBC driver dependency on every machine. **Malindu: provision Azure Database for PostgreSQL.** Credentials parked in `backend/.env` (gitignored) so they aren't lost. |
| 2026-08-05 | **`AGENT_STUB_MODE` and `AUTH_DISABLED` env switches on the backend** *(Manujaya)* | Lets the gateway serve the contract's exact payloads before Supabase, Postgres, or `agent/` exist — Nipuna integrates against the real backend on day 0 instead of fixtures. Both log a warning at startup and must never be set in App Service config. |
| 2026-08-05 | **Proposed: add `DELETE /rag/documents/{id}` to API_CONTRACT Part 2** *(Manujaya → Lakshitha, needs 👍)* | Deleting a document must clear its AI Search vectors, but Part 2 has no delete endpoint and the gateway holds no search credentials by design. Until it exists the backend calls the path, treats 404/405 as not-implemented, logs it, and completes the Postgres delete. |
| | | |

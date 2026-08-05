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
| `[KICKOFF]` | **The Situation Report is the single output contract.** Every query produces one, with six fixed sections | A chatbot paragraph isn't practical; a report with priority, species, ranked hypotheses, ordered actions, and a next-review time is executable. The format *is* the real-world value. |
| `[KICKOFF]` | **Record-aware chunking, not fixed-size splitting** — one corpus record = one chunk, zero overlap | A 1000/200 window slices `FAU-014` mid-field and bleeds `FAU-015` in — the exact cross-record merge the corpus prohibits in §15.2 rule 3. Fixed-size chunking structurally guarantees the error the graders check for. |
| `[KICKOFF]` | **The corpus PDF is the ingestion source of truth**, pre-indexed at seed time | The brief mandates a page number on every source card, and only the PDF has pages. Pre-indexing means the demo can never fail on an upload and judges see value instantly. The `.md` copy is for hand-verifying chunk boundaries. |
| `[KICKOFF]` | **LLM reranking is the primary retrieval path**, not a fallback | Azure AI Search **F0 has no semantic reranker** — that's Basic tier and above. A batched `gpt-4o-mini` call scores the candidates instead. Same interface, marginally slower, still a genuine rerank stage. **Do not architect around the built-in ranker.** |
| `[KICKOFF]` | **Specialist count is fixed at 3**, retry capped at **1**, ≤ **8** LLM calls per query, 8 s per-agent timeout, 25 s total budget | Enforced by counters in orchestrator state, **not** by prompt instruction — a prompt can be ignored, a counter cannot. Unbounded agent loops kill demos. |
| `[KICKOFF]` | **Evidence-quality labels are preserved verbatim** from the corpus's five-value taxonomy | Page 2 explicitly instructs it. It also makes the confidence meter explainable and gives the conflict panel its vocabulary. |
| `[KICKOFF]` | **Conflicts are presented, never resolved.** No section may collapse multiple documented causes into one | §14.3 is a planted trap with a published expected answer. Naming a cause without evidence assigns blame, misdirects the response, and violates `POL-010`. |
| `[KICKOFF]` | **The role toggle re-renders from frozen evidence — it never re-queries** | If flipping Guardian → Citizen re-ran retrieval, cited evidence could shift between roles and a judge would watch the facts change on screen, destroying the grounding story. Register changes; record IDs never do. |
| `[KICKOFF]` | **Supabase auth stays in scope**, with a **pre-seeded demo account** | The 7-route site is the committed deliverable. But a login wall between a judge and the demo is pure downside, so nobody signs up on stage — and auth never gates Layer 1. |
| `[KICKOFF]` | **Six-layer build order with a feature flag and git tag per layer** | Banks marks instead of promising them. At any point from T+2:00 we have something submittable. A later layer failing degrades to an earlier one at runtime, not to an error screen. |
| `[KICKOFF]` | **Postgres sits behind a repository protocol with an in-memory default for the demo** | Postgres is the production target and will be wired if time permits, but a connection-string mistake must not be able to take the app down on stage. |
| `[KICKOFF]` | **The demo runs locally**, even if Azure deployment is green | Conference Wi-Fi is a well-known way to lose a hackathon. The GitHub repo is the deliverable; local is the demo. |
| `[LAYER 5]` | **Per-specialist timeout raised 8 s → 75 s, total budget 25 s → 180 s** (`AGENT_TIMEOUT_SECONDS`, `ORCHESTRATION_BUDGET_SECONDS`) | `SOLUTION.md` §5.5's limits assume `gpt-4o-mini`. We deploy `gpt-5-mini`, a **reasoning** model that spends a variable share of its budget thinking before emitting a token. **Measured: 36 s / 37 s / 52 s** for the three SITREP sections. At 8 s — or at the interim 20 s — every specialist times out, every query degrades to the single-agent fallback, and the three-orb parallel demo never fires. The *structure* of §5.5 is unchanged: fixed caps, enforced by counters. |
| `[LAYER 5]` | **Compare-mode synthesis lands in the first specialist's section**, not a new section type | The six-section SITREP shape is frozen across three services. Adding a seventh section type for comparisons would break the frontend renderer and the gateway's persistence for one routing mode. |
| `[LAYER 1]` | **The chat model is `gpt-5-mini`, not `gpt-4o-mini`** — every doc that still says `gpt-4o-mini` is describing an intent, not the deployment | `gpt-4o-mini` **is not deployed** on `pandora-nsbm`; probing the resource found `gpt-5-mini` as the only chat deployment. It is a *reasoning* model, so three things change: `max_completion_tokens` replaces `max_tokens`; **`temperature: 0.1` returns HTTP 400** (only the default is accepted); and reasoning tokens eat the completion budget, so a 4000-token cap returned `finish_reason: length` with **empty content** — the budget is now **16000**. All three quirks are contained in `agent/app/core/llm.py` and switch off with `IS_REASONING_MODEL=false`, so if Malindu deploys `gpt-4o-mini` we move over with two env vars. |
| `[LAYER 1]` | **Endpoint host is `pandora-nsbm.services.ai.azure.com`** | The `*.openai.azure.com` host in the original notes does not exist for this resource and 404s on every path. |
| `[LAYER 1]` | **The LLM reranker is OFF by default — metadata filtering replaced it.** Reverses the KICKOFF row above | Measured on `gpt-5-mini`: **~25 s per query, and it demoted the correct fauna records below a weaker one**. Filtering retrieval by `record_types` instead took one gate question's top-6 from **0/6 to 6/6 relevant in 3 s**. Precision without the cost. `rerank=True` is still supported on the retriever and becomes attractive again on a non-reasoning model. |
| `[LAYER 1]` | **Ingestion reads `Pandora_RAG_Knowledge_2026.md`, not the PDF.** Reverses the KICKOFF row above | The markdown is clean — no page header/footer boilerplate — and carries all 132 `###` record headings, so the record-aware chunker anchors on it exactly. This removes `SOLUTION.md` Risk #7 (PDF extraction noise) entirely. The PDF-parsing path still exists and is what `/rag/ingest` uses for judge-uploaded files. |
| `[LAYER 1]` | **Narrative prose chunks get a synthetic citation key (`SEC-1`, `SEC-2`) at retrieval time** | Their natural IDs (`nar-14-research-records-…`) don't match the citation regex, so any answer resting on a prose section scored 0 % grounded even when it was perfectly sourced. Prose sections like §4.5 (the W1–W4 scale) now cite like any record — which is what makes the triage banner citable. |
| `[LAYER 5]` | **Rung 3 fallback triggers only on *hard* specialist failure** (timeout or crash), not on an honestly-empty section | "No species records matched this query" is a *correct* result, not a failure. Re-running it single-agent would waste budget and produce the same honest empty state. |
| | | |

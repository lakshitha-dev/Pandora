# Pandora Knowledge Guardian — **Guardian Command Center**
## Solution Design

**Pandora Builderthon 2026 · "Echoes of Pandora: An AI Knowledge Guardian for a Living Ecosystem"**

> **Status:** Source of truth. Design/spec only — no code.
> Every other artifact (README, architecture diagram, implementation, pitch deck) derives from this file.
> **Scoring target:** 100/100 — with the 45 marks in RAG Core + Grounding treated as non-negotiable.
> **Build discipline:** the [Bankable Build Order](#10-bankable-build-order--fallback-plan) is binding. Layer 1 banks 45 marks on its own and ships before anything else is written.

---

### Revision 2 — what changed from Revision 1

| Area | Change |
|---|---|
| **Product framing** | Reframed from "answer + sources" to the **Guardian Command Center**: every query assembles a live, structured **Situation Report** — Priority · Affected Species · Likely Causes · Recommended Actions · Sources · Confidence. New §2.1 specifies the SITREP contract. |
| **Five wow features** | New §2.2 names them and maps each to the rubric marks it moves. Two were previously out of scope and are now in (Layer 6): **stylized Pandora map view** and **role toggle re-render**. |
| **Agent model** | Specialists no longer just "answer" — each **owns a named SITREP section** and fills it in parallel, visibly. New routing mode (`sitrep`) dispatches all three concurrently; `focused` and `compare` modes retained. Call budget and timeout math updated for 3-way parallelism (§5.4, §5.5). |
| **Honesty flip** | §4.6 now specifies the **banner + body** split: banner reads *"Insufficient Evidence — Recommend Field Investigation"*, body carries the brief's mandated sentence verbatim. Both requirements satisfied without conflict. |
| **Build order** | §10 restructured from a flat timeline into **six independently demoable layers** with hard isolation rules — a later layer failing can never take down an earlier one. Feature flags now map 1:1 to layers. |
| **Demo script** | §13.2 rewritten as **five visible wow-beats** following the ocean-colour incident, ending on the honest refusal. |
| **Scope** | §12 reconciled: map **visualization** is in scope (Layer 6); map-based **retrieval** remains out. Role toggle promoted from prompt-lens to a first-class re-render. |
| **Risks** | §15 adds layer-isolation and 3-way-parallel-latency risks; existing four mandated risks refined. |
| **Unchanged** | §0 corpus insight, §1 problem statement, §4 RAG core, §9 data model foundations, §11 use cases, and the entire grounding/conflict design. **The 45-mark core is deliberately untouched — it was already right.** |

---

## Table of Contents

| § | Section | Rubric weight served |
|---|---|---|
| 1 | [Problem Statement](#1-problem-statement) | Real-world (20) |
| 2 | [Solution Overview — the Guardian Command Center](#2-solution-overview--the-guardian-command-center) | — |
| 2.1 | ↳ [The Situation Report](#21-the-situation-report) | Real-world (20) + UX (15) |
| 2.2 | ↳ [The Five Wow Features & Rubric Map](#22-the-five-wow-features--rubric-map) | **All** |
| 3 | [Core User Flow](#3-core-user-flow) | UX (15) |
| 4 | [RAG Core](#4-rag-core--highest-priority-45-marks) | **RAG (25) + Accuracy (20)** |
| 5 | [Agentic Architecture](#5-agentic-architecture--our-innovation-10-marks) | Innovation (10) |
| 6 | [Advanced Features & Rubric Mapping](#6-advanced-features--rubric-mapping) | All |
| 7 | [Visible Orchestration](#7-visible-orchestration) | Innovation (10) + UX (15) |
| 8 | [UI/UX & Pandora Theme](#8-uiux--pandora-theme-15-marks) | UX (15) |
| 9 | [Data Model](#9-data-model) | RAG (25) |
| 10 | [**Bankable Build Order** & Fallback Plan](#10-bankable-build-order--fallback-plan) | **Risk control — binding** |
| 11 | [Use-Case Coverage](#11-use-case-coverage) | Real-world (20) |
| 12 | [Scope](#12-scope) | Risk control |
| 13 | [Innovation & Pitch Angle · Demo Script](#13-innovation--pitch-angle) | Presentation (10) |
| 14 | [Submission Checklist](#14-submission-checklist) | Presentation (10) |
| 15 | [Risks & Mitigations](#15-risks--mitigations) | Risk control |

---

## 0. The Decisive Insight (read this first)

Before any design decision, one fact must be understood, because everything below follows from it:

> **The provided knowledge corpus contains its own grading key.**

Most teams will treat `Pandora_RAG_Knowledge_2026.pdf` as "56 pages of text to chunk." It is not. It is a **structured record database with a published retrieval specification.** Three things are hiding in it:

**(a) Page 2 states the required answer behaviour.**
> *"Information quality is classified as verified observation, community tradition, provisional interpretation, modeled estimate, or disputed report. RAG applications should preserve these labels. A generated answer should distinguish between what is directly documented and what is an inference. When sources disagree, the system should present the disagreement rather than silently selecting one claim."*

**(b) Section 15.2 is literally titled "Retrieval Grounding Rules"** and lists eight explicit requirements. That is the 20-mark *Accuracy and Grounded Responses* category, written out in advance.

**(c) Section 14.3 is a planted trap with a stated expected answer.**
> *"RAG evaluation expectation: an answer should present all three records, identify the incomplete chain of custody, avoid declaring a confirmed cause, and recommend additional properly documented sampling."*

A conventional RAG app will confidently answer *"the turquoise water was caused by a plankton bloom."* **That answer fails the corpus's own test.** Our system will refuse to name a cause, surface the three-way conflict, and flag the broken chain of custody — and we will show the judges the page where that is the stated expectation.

**Design consequence:** our agentic architecture is not decoration for the 10 innovation marks. Every sub-agent and every validator exists to enforce rules the corpus itself published. Innovation and grounding are the same investment.

---

## 1. Problem Statement

Pandora's knowledge is real, extensive, and **useless at the moment it matters most.**

The corpus proves the point. Everything a guardian needs to handle a yellow plume at Obsidian Reach exists — but it is scattered across at least six disconnected places:

| Where the knowledge lives | Example | Chapter |
|---|---|---|
| An incident playbook | `INC-005 Vent Plume Release` — CRITICAL, evacuate downwind/cross-current, gas monitoring, close seafood harvest | 12 |
| A water-station reading | `WS-03 Vitra Vent Edge, 2026-06-14` — 34.2 °C, DO down to 3.8 mg/L, pH 7.62, yellow plume | 14.1 |
| A severity scale | `W1–W4 Water Incident Classification` | 4.5 |
| A species profile | `FAU-018 Ventplume Shrimp` — who lives there and what it tolerates | 5 |
| A policy | `POL-010 Emergency Transparency` — what the public alert must contain | 13 |
| A field checklist | `A.1 Water Investigation` — chain-of-custody sampling procedure | Appendix A |

No human connects those six records under time pressure. A guardian standing on a black-sand beach with dying shellfish at their feet has minutes, not an afternoon in the archive.

**Three failures compound:**

1. **Scatter.** The answer is distributed across records that never reference each other. `WS-03`'s reading and `INC-005`'s playbook describe the same event and live 30 pages apart.
2. **Hallucination.** A general-purpose chatbot asked about a Pandoran vent plume will invent a confident, fluent, *fabricated* protocol. In an environmental emergency, a plausible wrong answer is worse than no answer — it gets acted on.
3. **False certainty.** This is the subtle one and the one the corpus cares most about. Evidence on Pandora is genuinely contested: `FN-A` blames plankton, `FN-B` implicates an upstream pigment workshop, `LAB-C` has an incomplete chain of custody. A system that resolves that conflict into one tidy answer has destroyed the single most decision-relevant fact — **that nobody actually knows yet.** Naming a cause without evidence assigns blame, misdirects the response, and violates `POL-010`.

**What Pandora needs:** not an answer machine — an **evidence machine.** One that retrieves the right records, cites them by ID, separates documented protocol from inference, surfaces disagreement instead of hiding it, and says plainly when the corpus does not know.

---

## 2. Solution Overview — the Guardian Command Center

**Pandora Knowledge Guardian is not a chatbot. It is a command center.**

That distinction is the whole product. A chatbot returns a paragraph and a list of links. A command center returns **a Situation Report** — a live, structured, operational document that a guardian can act on without reading twice: what the priority is, which species are at risk, what might have caused it, what to do right now, what the evidence is, and how much to trust it.

Underneath, it is a rigorous RAG system. It ingests the Pandora corpus (plus any PDF/TXT/CSV/DOCX a user uploads) into a **record-aware** index, retrieves via **hybrid search + semantic reranking**, and passes every claim through **GroundingGate** — a validator implementing the corpus's own eight Retrieval Grounding Rules. Every claim carries an inline citation to a real record ID (`INC-005`, `FAU-003`, `WS-03`). Every source card shows its excerpt, page, relevance score, and the corpus's own evidence-quality label.

On top of that core, an **orchestrator** rewrites the query, classifies emergency priority against the corpus's own W1–W4 scale, and dispatches **three fixed specialist agents in parallel** — each owning one section of the report and filling it live on screen. A stylized Pandora map lights the affected region by priority. A role toggle re-renders the same evidence for Researcher, Citizen, or Guardian. And when the evidence is thin, the report does not fabricate — it prints **"Insufficient Evidence — Recommend Field Investigation"** and says what field data would resolve it.

**The wow moment.** A judge asks *"What caused the turquoise water at Awa Reef?"* — the question the corpus was built to trap. The map ignites `REG-01` Luminous Shelf in red. Three agent orbs fire simultaneously and the report assembles section by section in front of them. Then the report does something no other team's will do: **the Likely Causes section refuses to name a cause.** It presents `FN-A`, `FN-B`, and `LAB-C` side by side, flags `LAB-C`'s incomplete chain of custody as the specific reason certainty is unavailable, and recommends documented resampling per checklist `A.1`. Confidence reads *"Moderate — 3 sources, 1 unresolved conflict, chain-of-custody incomplete."* Then we turn to page 48 of the judges' own corpus and read the RAG evaluation expectation aloud. It matches, line for line.

That is a 15-second moment that no other team will have, and it wins Accuracy, Real-World, and Innovation simultaneously.

---

### 2.1 The Situation Report

The SITREP is the product's single output contract. Every query produces one. It has **six sections, in fixed order**, and each has a named owner, a defined data source, and — critically — **a defined behaviour when it cannot be filled.**

| # | Section | Owner | Data source | If it cannot be filled |
|---|---|---|---|---|
| 1 | **🔴 Priority** | Orchestrator | W1–W4 classification (§4.5 of corpus), cited | Renders 🟢 *"Informational — no incident indicators detected"* |
| 2 | **Affected Species** | Marine-Life Protector | `FAU-*` / `FLR-*` records, isolated per species | *"No species records matched this query"* — never guessed |
| 3 | **Likely Causes** | Incident Investigator | `INC-*` plausible-cause fields, `WS-*` readings, `FN-*` notes | *"Cause not established"* + conflict panel. **Never collapses to one cause** |
| 4 | **Recommended Actions** | Emergency Responder | `INC-*` immediate actions, `A.1–A.4` checklists, `MED-*`, `12.11` command roles | *"No documented protocol retrieved — recommend field investigation"* |
| 5 | **Sources** | Orchestrator | Deduplicated union of every chunk cited by any section | Always populated if anything was retrieved |
| 6 | **Confidence** | Orchestrator / GroundingGate | Groundedness · rerank score · source count · evidence-quality mix · conflicts | Always populated — including *"Insufficient"* |

**Four rules govern the report:**

1. **Sections are independent.** One section failing or timing out never blanks the others. A report with three of four content sections filled, and the fourth honestly marked unavailable, is a *successful* report — not an error state.
2. **Every section is independently cited.** Claims carry their own record IDs; §5 Sources is the union, not the origin.
3. **Empty is a valid, visible state.** An unfilled section renders its reason. A blank section would look like a bug; a section that says *"No species records matched"* looks like rigour.
4. **The report is the same object in every mode.** Single-agent (Layer 2) and three-agent parallel (Layer 5) produce the *identical* SITREP structure — only the fill mechanism differs. This is what makes the degradation ladder invisible to a judge.

**Why the report format itself scores.** The 20-mark *Real-World Problem Solving* criterion asks that "recommendations are practical and clearly explained." A prose paragraph about coral damage is not practical. A report with a priority class, a species list, ranked hypotheses, an ordered action list, and a next-review time is something an incident lead can execute from. The format *is* the real-world value.

---

### 2.2 The Five Wow Features & Rubric Map

Five features carry the demo. Each is named, each maps to specific marks, each has a section that specifies it and a Layer that builds it. **Nothing here is named but unspecified.**

| # | Wow feature | What the judge sees | Marks it moves | Spec | Layer |
|---|---|---|---|---|---|
| **1** | **Visible agent assembly** | Three specialist orbs ignite **simultaneously**; Affected Species, Likely Causes, and Recommended Actions fill in parallel, each badged with its agent | **Innovation 10** + UX 15 | [§5](#5-agentic-architecture--our-innovation-10-marks), [§7](#7-visible-orchestration) | **5** |
| **2** | **Honesty flip** | Confidence meter on every report; thin evidence prints *"Insufficient Evidence — Recommend Field Investigation"* instead of fabricating | **Accuracy 20** | [§4.6](#46-uncertainty-handling--the-honesty-flip) | **4** |
| **3** | **Emergency priority triage** | 🔴/🟠/🟢 banner with a **cited** reason, classified on the corpus's own W1–W4 scale | **Real-world 20** | [§5.2](#52-the-orchestrator) | **3** |
| **4** | **Map-based incident view** | Stylized Pandora map; affected `REG-*` zones light by priority; clicking a zone filters the report's sources to that region | UX 15 + **Real-world 20** | [§8.5](#85-the-pandora-map-panel-layer-6) | **6** |
| **5** | **Role toggle** | Same report, re-rendered for Researcher / Citizen / Guardian — **same evidence, same record IDs, three registers** | Real-world 20 + **Innovation 10** | [§8.6](#86-role-toggle-layer-6) | **6** |

**How the five combine into one narrative.** They are not a feature list — they are the five beats of a single story, in order: *how bad is it* (3) → *who is affected and why* (1) → *how sure are we* (2) → *where is it* (4) → *who needs to hear it* (5). The demo script in §13.2 walks exactly that arc.

> **Critical design rule for feature 5.** The role toggle **re-renders from the same frozen evidence set** — it does not re-query and does not re-retrieve. One retrieval, one grounded claim set, three presentations. If flipping Guardian → Citizen re-ran retrieval, the cited evidence could shift between roles and a judge would watch the facts change on screen — destroying the grounding story we spent 45 marks building. Register, depth, and jargon change; record IDs and claims never do.

---

## 3. Core User Flow

One primary flow: **a question becomes a Situation Report.** Everything else is secondary.

```mermaid
flowchart TD
    A["1 · Access Knowledge Base<br/>Pandora corpus preloaded<br/>+ optional PDF/TXT/CSV/DOCX upload"] --> B
    B["2 · Describe the situation<br/>natural language"] --> C
    C["3 · Orchestrator<br/>rewrite → classify priority → route"] --> D
    C --> M["3a · 🔴 Priority banner<br/>W1–W4, cited"]
    C --> N["3b · Map lights affected REG-* zone"]
    D["4 · Hybrid retrieval + rerank<br/>BM25 + vector → semantic ranker"] --> E
    E["5 · Parallel section assembly"] --> E1 & E2 & E3
    E1["🐋 Marine-Life<br/>→ Affected Species"] --> F
    E2["🌊 Investigator<br/>→ Likely Causes"] --> F
    E3["🚨 Emergency Responder<br/>→ Recommended Actions"] --> F
    F{"6 · GroundingGate<br/>8 corpus rules, per section"}
    F -->|pass| G["7 · SITREP renders progressively"]
    F -->|fail, 1 retry only| D
    F -->|still failing| H["⚠ Insufficient Evidence —<br/>Recommend Field Investigation"]
    G --> I["8 · Sources<br/>record ID · page · excerpt · score · evidence quality"]
    I --> J["9 · Conflicts & confidence<br/>disagreements shown, never merged"]
    J --> L["10 · Role toggle<br/>re-render, same evidence"]
    L --> K["11 · Reset / new investigation"]
```

**Step detail:**

1. **Access.** The full Pandora corpus ships **pre-indexed** — the app is useful the second it loads, with zero setup. Judges never wait on an upload. Uploading additional documents is supported and demoed, but is never on the critical path.
2. **Describe.** Free-text. A guardian describes a situation in plain language, not a keyword query — *"the water near Awa Reef has turned turquoise and the fish are leaving."*
3. **Orchestrate.** Query rewritten and expanded, classified by use case and by W1–W4 priority, routed. **Two things render immediately, before any generation completes:** the priority banner (3a) and the map zone (3b). This matters for perceived speed — the screen is never blank and never spinning.
4. **Retrieve.** Hybrid BM25 + vector, RRF fusion, semantic rerank, metadata filters.
5. **Assemble in parallel.** Three specialists each fill their owned SITREP section concurrently, generating **only** from retrieved context, emitting a citation marker per claim. Sections stream in as they complete — the report visibly builds rather than appearing all at once.
6. **Validate.** GroundingGate checks each section against the eight corpus rules. One retry maximum, per section.
7. **Report renders.** Progressive: each section appears the moment it passes validation.
8. **Sources.** Deduplicated union across all sections — document name, chapter/section, page, verbatim excerpt, relevance score, evidence-quality label.
9. **Conflicts & confidence.** Disagreements rendered side by side, never merged. Confidence meter states its *reason*.
10. **Role toggle.** Re-renders the completed report for Researcher / Citizen / Guardian from the **same frozen evidence set** — no re-query, no changed citations.
11. **Reset.** Clears conversation, report, trace, map state, and sources — one click, back to a clean console.

> **Flow guarantee:** steps 1–4 and 6–9 are **Layer 1–4** and work with a single agent. Step 5's parallelism is **Layer 5**, and step 10 is **Layer 6**. If either is disabled or fails, the flow above still completes end to end — the report just fills sequentially from one agent instead of concurrently from three. See [§10](#10-bankable-build-order--fallback-plan).

---

## 4. RAG Core — Highest Priority (45 Marks)

> This section carries **RAG Architecture & Retrieval Quality (25)** + **Accuracy & Grounded Responses (20)**. It is built and verified before any agentic work begins.

### 4.1 Knowledge-Base Management

**Supported formats:** PDF, TXT, CSV, DOCX. PDF is the priority path — the corpus is a PDF and judges will upload PDFs.

| Format | Extraction approach | Notes |
|---|---|---|
| PDF | Text layer extraction with page and font-size metadata retained | Font size drives heading detection (see §4.2). Scanned-image PDFs out of scope. |
| DOCX | Paragraph + heading-style traversal | Native heading styles map directly to our section hierarchy. |
| TXT | Markdown-style / numbered heading detection | Fallback to narrative chunking. |
| CSV | One logical record per row; header row becomes field names | Fits the corpus's tabular chapters (14.1, 14.2). |

**Preloaded corpus.** `Pandora_RAG_Knowledge_2026.pdf` is ingested at build/seed time and committed as a prebuilt index. Rationale: (a) the demo cannot fail on an upload, (b) judges see value instantly, (c) it lets us hand-verify the extraction of all ~130 records rather than trusting a generic parser under time pressure.

**Upload path.** Drag-and-drop with live ingestion progress (extract → chunk → embed → index), a per-document chunk count on completion, and per-document delete. Uploaded documents are appended to the same index with a `document_id`, so cross-document questions work naturally.

### 4.2 Document Processing

#### The chunking decision — our highest-leverage retrieval choice

**Do not use fixed-size character splitting.** This is the single most important instruction in this document.

The Pandora corpus is not prose. It is **~130 atomic records with stable IDs and fixed internal field schemas:**

| Prefix | Entity type | Count | Chapter |
|---|---|---|---|
| `REG-01…10` | Regions & geological zones | 10 | 2 |
| `STL-001…010` | Settlements & governance | 10 | 3 |
| `FAU-001…030` | Fauna species profiles | 30 | 5 |
| `FLR-001…020` | Flora, fungi, medicinal plants | 20 | 6 |
| `MED-001…012` | Health conditions & protocols | 12 | 7 |
| `ACC-001…010` | Accommodation & visitor safety | 10 | 9 |
| `INC-001…010` | Environmental incidents | 10 | 12 |
| `POL-001…010` | Conservation policies | 10 | 13 |
| `KC-01…20` | Knowledge cards | 20 | Appendix B |
| `WS-01…04` | Water-station readings (time series) | 7 rows | 14.1 |
| `SV-101…106` | Wildlife survey records | 6 rows | 14.2 |
| `FN-A`, `FN-B`, `LAB-C` | Conflicting field notes | 3 | 14.3 |

Every record of a type shares an identical field structure. For example, every `INC-*` record has exactly six fields:

> *Location and observations · Initial risk level · Plausible causes · Immediate actions · Minimum incident dataset · Public communication*

And every `FAU-*` record has exactly five:

> *Category and habitat · Ecological role · Known pressures · Protection and response · Monitoring record*

A 1000-character window with 200-character overlap will slice `FAU-014 Blueveil Manta` through the middle of its *Known pressures* field and bleed the tail of `FAU-015 Currentback Turtle` into the same chunk. The retrieved context then contains two species fused into one blob — and the model will confidently attribute the manta's pressures to the turtle.

That failure mode is **explicitly named as a violation by the corpus itself**, in §15.2:

> *"Do not merge details from two species, villages, plants, or incidents merely because their names or habitats are similar."*

Fixed-size chunking doesn't just retrieve slightly worse here. It structurally guarantees the exact error the graders are checking for.

#### Two-tier record-aware chunking

**Tier 1 — Record chunks (primary, ~130 chunks).**
One complete record = one chunk. Never split a record; never merge two records.

- Boundary detection: a record starts at a heading matching `^(REG|STL|FAU|FLR|MED|ACC|INC|POL|KC)-\d+` and ends at the next such heading or the next chapter heading.
- Typical size: 900–1,400 characters — comfortably inside the embedding window.
- **Overlap: none, by design.** Overlap exists to prevent semantic bleed across arbitrary cut points. There are no arbitrary cut points here; the boundaries are the author's own. Adding overlap would reintroduce exactly the cross-record contamination we are eliminating.
- Each chunk is prefixed at index time with a compact provenance header (record ID, name, chapter, region) so the ID travels with the text into the model's context. This measurably improves citation fidelity — the model cannot cite an ID it cannot see.

**Tier 2 — Narrative chunks (secondary, ~90 chunks).**
For genuine prose (chapters 1, 4, 8, 10, 11) and the appendix checklists.

- Split on the deepest heading boundary first (e.g. `4.3 Wetlands and Mangroves`), then pack to **800 tokens with 120-token overlap** only if a section exceeds the limit.
- Rationale for 800/120: sections in this corpus are 3–6 paragraphs. 800 tokens holds a complete sub-section in almost every case, so overlap rarely triggers. The 15% overlap is insurance for the few long sections (Chapter 1, Appendix A), preserving continuity across a forced cut without duplicating enough text to distort scoring.

**Tier 2b — Table chunks.**
Tables (4.5 W1–W4, 12.11 Incident Command Roles, 13 policy summary, 14.1, 14.2) are linearized **one row per chunk**, each carrying the table caption and column headers. A `WS-03` reading must be independently retrievable — it is the evidence that corroborates `INC-005`. Bundling the whole table into one chunk buries it.

**Result:** ~220 high-precision chunks, each semantically complete, each independently citable. Compare to ~450 arbitrary fragments from naive splitting.

#### Metadata schema

Every chunk carries these fields into the index. This is what makes filtering, scoring, and precise citation possible.

| Field | Type | Purpose |
|---|---|---|
| `chunk_id` | key | Primary key |
| `document_id` | filterable | Multi-document support, per-doc delete |
| `document_name` | retrievable | **Required by brief** — shown on every source card |
| `record_id` | filterable, searchable | `INC-005`, `FAU-003`, `WS-03` — the citation anchor |
| `record_type` | filterable, facetable | `incident`, `fauna`, `policy`, `region`, `settlement`, `flora`, `health`, `accommodation`, `knowledge_card`, `monitoring`, `field_note`, `narrative` |
| `title` | retrievable, searchable | e.g. "Vent Plume Release" |
| `chapter` / `section` | filterable, retrievable | **Required by brief** — "12 · Environmental Threats" |
| `page` | filterable, retrievable | **Required by brief** — exact page number |
| `region_id` | filterable, facetable | `REG-05` — enables "everything at Obsidian Reach" |
| `evidence_quality` | filterable, retrievable | Corpus taxonomy — see §4.5 |
| `risk_level` | filterable | `LOW` / `MEDIUM` / `HIGH` / `CRITICAL`, parsed from `INC-*` records |
| `record_date` | filterable, sortable | For `WS-*`, `SV-*`, `FN-*` — enables "preserve time" (rule 4) |
| `field_name` | retrievable | Which sub-field matched, e.g. "Immediate actions" |
| `content` | searchable | The chunk text |
| `content_vector` | vector | 1536-dim embedding |

#### Embeddings

**Model:** `text-embedding-3-small` via Azure AI Foundry. 1536 dimensions.

Chosen over `-3-large` deliberately: ~5× cheaper, ~2× faster to index, and on a 220-chunk corpus of short, distinctive, jargon-heavy records the recall difference is negligible — while the indexing speed difference is very real inside a 5-hour window. Re-indexing the entire corpus must stay under ~60 seconds so we can iterate on chunking without losing time.

**What gets embedded:** the provenance header + record title + chunk content. Embedding the title and record ID alongside the body meaningfully improves retrieval on entity-named queries ("what should we do about a Deepbell stranding?").

Batched at 64 chunks per request with retry-with-backoff on 429.

#### Vector storage

**Azure AI Search**, single index, HNSW.

| Setting | Value | Rationale |
|---|---|---|
| Algorithm | HNSW | Sub-10 ms recall at this scale; fully managed |
| Metric | Cosine | Standard for OpenAI-family embeddings |
| `m` | 4 | Default; ample for ~220 vectors |
| `efConstruction` | 400 | Build-time quality; indexing is cheap here |
| `efSearch` | 500 | Favour recall — our corpus is tiny, latency is not the constraint |
| Semantic config | enabled on `title` + `content` | Powers the L2 reranker (§4.3) |

Azure AI Search is chosen over Chroma/FAISS for one decisive reason: it provides **native hybrid search and a built-in semantic reranker**. Those are two of the brief's bonus features, obtained as managed configuration rather than build time. In a 5-hour window, buying two rubric features with a config block instead of an afternoon is the correct trade.

### 4.3 Semantic Retrieval

#### Hybrid search — and why keyword matters here specifically

Pure vector search is the default choice and it is **wrong for this corpus.**

The corpus is saturated with exact-match tokens that embeddings handle poorly: record IDs (`INC-005`, `FAU-014`), station codes (`WS-03`), policy numbers (`POL-001`), and invented proper nouns with no pretraining signal (*Tideglass Grazer*, *Ventplume Shrimp*, *Mistroot Basin*, *Cloudspine Highlands*). An embedding model has never seen "Ribbonfin Skimmer" and will place it near generic fish vocabulary. BM25 matches it exactly, instantly.

Conversely, a question like *"why are the animals leaving?"* shares no keywords with `FAU-001`'s *"A sudden absence can reflect migration, disturbance, weather, sampling error, or mortality"* — pure keyword search finds nothing; vector search nails it.

**Neither leg alone is sufficient. Hybrid is not a bonus feature here — it is a correctness requirement.**

#### The retrieval pipeline

| Stage | Operation | Output |
|---|---|---|
| 1 | **Query rewriting** — expand abbreviations, resolve last-turn coreference, generate 1 alternate phrasing, extract any explicit record IDs | 2 query variants + ID hints |
| 2 | **Metadata pre-filter** — apply `record_type` / `region_id` / `record_date` filters inferred by the orchestrator | Narrowed candidate set |
| 3 | **BM25 keyword leg** — `k = 30` | 30 candidates |
| 4 | **Vector leg** — `k = 30`, cosine, `efSearch = 500` | 30 candidates |
| 5 | **RRF fusion** — reciprocal rank fusion across both legs and both query variants | ~40 deduplicated candidates |
| 6 | **Semantic reranking** — Azure AI Search semantic ranker (L2 cross-attention) | Reordered, scored `0–4` |
| 7 | **Top-k selection** — take top **6**, or top **8** for comparison queries | Final context |
| 8 | **Score normalization** — rerank score mapped to a `0–100` relevance percentage | Shown on every source card |

#### Why these numbers

- **`k = 30` per leg.** Deliberately over-retrieve. The reranker is the precision instrument; the retrievers only need recall. On a 220-chunk corpus, 30 candidates is ~14% of the index — near-certain to contain every relevant record, at negligible latency.
- **Top 6 into context.** Records average ~1,100 characters, so 6 chunks ≈ 6.6k characters ≈ 1.7k tokens. That leaves generous headroom in `gpt-4o-mini`'s window for the system prompt, conversation, and output — while staying small enough to avoid "lost in the middle" degradation. Six is also the practical ceiling for source cards a judge can actually scan on screen.
- **Top 8 for comparisons.** A compare query legitimately needs both subjects covered (e.g. `INC-001` *and* `INC-005`, plus their supporting evidence). Six risks starving one side.
- **Rerank threshold `1.8` of 4.0.** Below this, the top result is not genuinely on-topic → triggers the insufficient-evidence path (§4.6). Calibrated against known-good and known-absent questions during build.

#### How reranking and query rewriting improve relevance

**Reranking** is the highest-value retrieval upgrade available. Bi-encoder embedding search compresses a whole chunk into one vector before it ever sees the query — cheap and lossy. The semantic ranker scores query and chunk *jointly*, catching relevance that vector distance misses. Concretely: for *"what should we do if shellfish are dying near the black-sand coast?"*, vector search surfaces several generic water-quality sections; the reranker promotes `INC-005 Vent Plume Release` to the top because it jointly matches *shellfish* + *dying* + *coast* + *immediate actions*.

**Query rewriting** repairs three specific failure modes in this corpus:
1. **Vocabulary gap** — a citizen says *"the water looks weird and blue-green"*; the corpus says *"water turns bright turquoise"*. The rewriter emits both.
2. **Coreference** — *"and what about the shrimp there?"* is meaningless standalone. Rewritten to *"Ventplume Shrimp at Obsidian Reach"* using the previous turn.
3. **ID extraction** — a researcher types *"INC-005"*; the rewriter promotes it to a `record_id` filter, guaranteeing an exact hit rather than hoping semantics find it.

### 4.4 Grounded Generation

**Model:** `gpt-4o-mini` via Azure AI Foundry. Temperature `0.1`. `top_p 0.9`.

Low temperature is a grounding decision, not a style one: sampling diversity is precisely the mechanism by which a model drifts from its context into pretrained priors.

#### The generation contract

Every specialist prompt enforces the same non-negotiable contract:

1. **Closed-book.** Answer **only** from the provided context blocks. Pretrained knowledge about Earth oceans, real marine biology, or real emergency protocols is explicitly forbidden — the corpus is fictional and internally consistent, and importing outside facts is a hallucination even when the fact is true on Earth.
2. **Citation per claim.** Every sentence making a factual claim ends with one or more markers `[INC-005]`, `[FAU-003 p.13]`. Uncited sentences are permitted **only** for connective/structural text and are flagged by GroundingGate.
3. **Documented vs inferred, separated.** Anything not directly stated in a source must appear under an explicitly labelled *Model inference* heading. Per §15.2 rule 8. This is a hard structural requirement, not a stylistic preference.
4. **Hypotheses stay hypotheses.** Where the corpus lists plausible causes, they are presented as an unranked hypothesis set with the corpus's own caveat. Never collapsed into a single cause.
5. **No cross-record merging.** Facts about `FAU-014` may never be attributed to `FAU-015`. Each context block is fenced with its record ID and the model is instructed to treat blocks as isolated.
6. **Preserve time and place.** A `WS-03` reading is reported as *"at Vitra Vent Edge on 2026-06-14"*, never as a general fact about Pandoran water.
7. **Health guardrail.** Any `MED-*` retrieval forces inclusion of red-flag symptoms and the fictional-training-material disclaimer. Per §15.2 rule 5.
8. **Abstain over guess.** If context is insufficient, emit the insufficient-evidence response. Never bridge a gap with plausible invention.

Context blocks are injected in a fenced format carrying `record_id`, `document_name`, `chapter`, `page`, and `evidence_quality`, so the model has everything it needs to cite precisely and never has to guess a page number.

#### GroundingGate — the validator

After generation, before display, the draft is decomposed into claim-level sentences and validated. **Eight checks, mapped one-to-one to the corpus's own §15.2 Retrieval Grounding Rules.** This is not our invented notion of "grounded" — it is the published checklist, executed.

| # | Corpus rule (§15.2) | GroundingGate check | On failure |
|---|---|---|---|
| 1 | Cite record IDs or chapter sections for specific claims | Every factual sentence carries ≥1 valid marker resolving to a retrieved chunk | Strike sentence; recompute score |
| 2 | Present multiple plausible causes as hypotheses unless confirmed | If source lists ≥2 causes, answer must not assert one | Force retry with hypothesis instruction |
| 3 | Do not merge details from similar records | Each cited fact traces to the record it's attributed to; no cross-attribution | Strike sentence |
| 4 | Preserve time and location | Claims sourced from dated/located records retain that qualifier | Annotate as scope-unqualified |
| 5 | Health answers include red flags + fictional disclaimer | If any `MED-*` cited, both present | Append both |
| 6 | State when information is absent | If retrieval below threshold, insufficient-evidence message used | Force abstention |
| 7 | When records conflict, summarize the conflict and reliability limits | Conflict detector (§6) triggered → conflict panel populated | Force retry with conflict instruction |
| 8 | Separate documented protocol from model inference | Uncited normative statements are inside a *Model inference* block | Move or strike |

**Outputs:**
- **`groundedness`** = supported claims ÷ total factual claims, `0–100`.
- **Per-sentence verdict** — `supported` / `unsupported`, driving the UI's inline highlighting.
- **`confidence`** — combines groundedness, top rerank score, source count, evidence-quality mix, and conflict presence. Rendered as a meter that always **states its reason**: *"Moderate — 3 sources, 1 unresolved conflict, chain-of-custody incomplete."* A bare number is not explainable; a stated reason is.

**Retry policy:** hard cap of **1**. On failure the query is re-expanded and `k` widened to 10, then regenerated. If it fails again we degrade gracefully — surviving supported claims are shown with unsupported ones visibly struck through and labelled, or, if nothing survives, the insufficient-evidence response. **We never loop.**

### 4.5 Source References

**Required by the brief.** Every answer displays every source it used. No exceptions, no collapsed-by-default panel that a judge has to hunt for.

Each source card shows:

| Element | Example | Brief requirement |
|---|---|---|
| Document name | `Pandora_RAG_Knowledge_2026.pdf` | ✅ Document name |
| Record ID + title | `INC-005 · Vent Plume Release` | ✅ (exceeds — precise anchor) |
| Chapter / section | `12 · Environmental Threats and Emergency Response` | ✅ Section |
| Page | `p. 42` | ✅ Page number |
| Excerpt | Verbatim retrieved text, query terms highlighted | ✅ Retrieved excerpt |
| Relevance | `94%` + bar | ✅ Relevance score |
| Evidence quality | `Verified observation` badge | **Corpus-mandated (page 2)** |
| Risk level | `CRITICAL` chip (word + shape, not colour alone) | Bonus |

#### Evidence-quality labels — the corpus's own taxonomy

Page 2 instructs that RAG applications "should preserve these labels." We carry all five, assigned at ingestion by record type:

| Label | Assigned to | Meaning (corpus glossary) |
|---|---|---|
| **Verified observation** | `WS-*` readings, `SV-*` high-confidence surveys, `INC-*` reported signs | Supported by direct measurement or repeatable evidence |
| **Community tradition** | Chapter 11 cultural knowledge, traditional practice sections | Transmitted local/ancestral knowledge |
| **Provisional interpretation** | `INC-*` plausible causes, interpretation notes | A plausible explanation not yet confirmed |
| **Modeled estimate** | Carrying-capacity figures, projections | Derived, not observed |
| **Disputed report** | `FN-A`, `FN-B`, `LAB-C`, `SV-102` (low confidence) | Challenged by another source or weakened by poor evidence |

This single feature does a lot of work: it satisfies an explicit corpus instruction, it makes the confidence meter explainable rather than arbitrary, and it gives the Conflicting Evidence panel its vocabulary.

### 4.6 Uncertainty Handling — the Honesty Flip

> **Wow feature 2.** Built at **Layer 4**. Target: **Accuracy (20)**.

#### The banner / body split

The brief **mandates a specific sentence**. Our command-center framing wants an actionable headline. We do both — they occupy different slots, so neither is compromised:

| Slot | Content | Why |
|---|---|---|
| **Banner** (headline, large, amber) | **⚠ Insufficient Evidence — Recommend Field Investigation** | Actionable and scannable. Tells a guardian what to *do*, not just what failed. |
| **Body** (first line, verbatim) | *"The available Pandora knowledge base does not contain sufficient evidence to answer this question."* | **The brief's mandated wording, unaltered.** Non-negotiable. |
| **Body** (then) | What was searched · closest partial matches · what evidence would resolve it | Turns a refusal into a next step. |

This is a deliberate improvement over a bare refusal, not a workaround. *"Recommend field investigation"* is exactly the behaviour the corpus asks for in §14.3 (*"recommend additional properly documented sampling"*) and it converts an Accuracy-category requirement into Real-World value at the same time.

#### Triggered deterministically, not at model discretion

Model self-assessment of uncertainty is unreliable; a rule is not. Any of:

| Trigger | Threshold |
|---|---|
| Weak retrieval | Top rerank score `< 1.8 / 4.0` |
| No supported claims | GroundingGate groundedness `= 0` |
| Post-retry failure | Retry exhausted, zero claims survive |
| Sub-agent timeout with no partial result | 8 s elapsed, nothing returned |

#### The response is helpful, not a dead end

A bare refusal is a poor user experience and scores badly on both Accuracy and UX. Ours states: the banner; the mandated sentence; *what was searched* (chapters and record types scanned); the *closest partial matches* with their scores, clearly labelled as insufficient; and *what would answer it* — e.g. *"A water-quality reading for this location and date would be required. See checklist `A.1` — Water Investigation."*

#### Section-level honesty

Because the SITREP has six independently-owned sections (§2.1), the honesty flip operates **per section**, not only per report. A report can legitimately have solid Recommended Actions and an honest *"Cause not established"* in Likely Causes. Partial honesty is more useful — and more credible — than all-or-nothing refusal.

#### The confidence meter

Always present, always **states its reason**. A bare number is not explainable; a stated reason is.

| Level | Condition | Example reason string |
|---|---|---|
| **High** | Groundedness ≥ 90%, top rerank ≥ 3.0, ≥ 3 sources, no conflicts | *"High — 5 sources, all verified observations, no conflicts"* |
| **Moderate** | Groundedness ≥ 70%, or conflicts present | *"Moderate — 3 sources, 1 unresolved conflict, chain of custody incomplete"* |
| **Low** | Groundedness ≥ 40%, or sources are provisional/disputed only | *"Low — 2 sources, both provisional interpretation"* |
| **Insufficient** | Any trigger above | *"Insufficient — no record scored above the relevance threshold"* |

**Why this scores.** The 20-mark Accuracy criterion has three bullets: answers based on retrieved information, hallucinations minimized, *insufficient evidence handled correctly*. Most teams treat the third as an edge case to bolt on at the end. We treat it as a **headline feature** — and we demo it deliberately, on purpose, as the final beat of the pitch.

**Three distinct honest states** — most systems have one:

| State | Condition | Presentation |
|---|---|---|
| **Grounded** | Strong retrieval, high groundedness, no conflict | Answer + sources + high confidence |
| **Contested** | Good retrieval, but sources disagree | Answer presenting *all* positions + Conflicting Evidence panel + moderate confidence + explicit "no confirmed cause" |
| **Insufficient** | Below threshold | The message + what was searched + what's missing |

The **Contested** state is where we win. It is the state the corpus was built to test, and almost no team will have it.

---

## 5. Agentic Architecture — Our Innovation (10 Marks)

> **Design constraint honoured throughout:** innovation must *strengthen* retrieval and grounding, not merely add complexity. Every component below has a retrieval or grounding justification. The agent count is **fixed at 3** and never dynamic. Loops are **hard-capped at 1 retry**.

### 5.1 Why agentic actually helps here

A single prompt must serve every question with one retrieval strategy and one output shape. That is a real ceiling on this corpus, because the question types have genuinely different needs:

- *"Which species are vulnerable to contamination?"* → filter to `record_type = fauna`, cross-reference pressures, output a ranked species list.
- *"What do we do about coral damage?"* → filter to `incident` + `knowledge_card`, output an ordered action card with a severity class.
- *"Compare contamination vs volcanic response"* → retrieve **two disjoint sets** and hold both in view.

That last one is the clincher. A single-agent RAG retrieving top-6 for *"compare water contamination and underwater volcanic event"* returns a blended set that usually over-represents whichever topic embeds closer to the query — and answers one side well and the other thinly. **Two specialists retrieving independently, then synthesizing, is a genuine retrieval-quality improvement, not theatre.** That is why this architecture earns Innovation marks *and* RAG marks.

### 5.2 The Orchestrator

Runs on `gpt-4o-mini`, temperature `0`. Five responsibilities, in order:

| # | Responsibility | Detail |
|---|---|---|
| 1 | **Query rewriting & expansion** | Resolve coreference from last turn, expand vocabulary, extract explicit record IDs, emit 2 query variants |
| 2 | **Classification** | Use case (6 categories, per brief) · severity (**W1–W4, the corpus's own scale**) · query shape (`simple` / `compare` / `summarize`) · metadata filter hints |
| 3 | **Routing** | Dispatch to 1 specialist, or 2 in parallel for `compare` |
| 4 | **Validation** | Run GroundingGate on returned draft(s); decide sufficient / retry / abstain |
| 5 | **Synthesis** | For parallel runs, merge into a unified comparison with a shared citation set; deduplicate overlapping sources |

#### Severity classification uses the corpus's own scale

The orchestrator does **not** invent a severity taxonomy. It classifies against `4.5 Water Incident Classification`:

| Class | Corpus indicators | Corpus immediate response |
|---|---|---|
| **W1 Observation** | Unusual color or odor; no illness or animal distress | Record, sample, compare upstream/downstream, monitor |
| **W2 Advisory** | Minor symptoms, localized fish avoidance, moderate parameter shift | Restrict sensitive use, alternate drinking water, investigate source |
| **W3 Emergency** | Multiple illnesses, fish deaths, toxic reading, severe oxygen loss | Close access, activate medical and ecological teams, isolate inflow |
| **W4 Regional Crisis** | Contamination crosses settlements or affects a major river/reef | Regional command, public warning, external labs, long-term restoration |

This matters more than it looks. A made-up "priority: high" label is an ungrounded model opinion — exactly what the rubric penalizes. A `W3` classification **is itself a cited claim**, traceable to §4.5, and it carries the corpus's own prescribed response. We turned a bonus feature into a grounded one.

### 5.3 The Three Fixed Specialists

> **Wow feature 1 — visible agent assembly.** Built at **Layer 5**. Target: **Innovation (10)** + UX (15).

**Fixed at three. Never dynamic.** A dynamic agent pool is unbounded latency and unbounded failure surface, and it is not demoable in four minutes. Three named specialists map cleanly onto our three required use cases and fit on screen.

#### Each specialist owns a SITREP section

This is the change that makes the agent layer *visible* rather than merely present. The specialists do not each write a competing answer that must then be merged — **they write different parts of the same document, concurrently.**

| Specialist | Owns SITREP section | Fills it from | Renders with badge |
|---|---|---|---|
| 🐋 **Marine-Life Protector** | **Affected Species** | `FAU-*`, `FLR-*`, `POL-*` — each species isolated to its own record | 🐋 |
| 🌊 **Incident Investigator** | **Likely Causes** + conflict panel | `INC-*` plausible causes, `WS-*` readings, `FN-*` / `LAB-*` notes | 🌊 |
| 🚨 **Emergency Responder** | **Recommended Actions** | `INC-*` immediate actions, `A.1–A.4`, `MED-*`, `12.11` command roles | 🚨 |
| ⚙️ **Orchestrator** | **Priority**, **Sources**, **Confidence** | Classification + deduplicated citation union + GroundingGate | ⚙️ |

**Why section ownership beats answer-merging.** Merging three full answers requires a synthesis pass that can itself hallucinate, and it produces one undifferentiated block — the parallelism becomes invisible. Section ownership means each agent's output lands in its own labelled slot with its own badge, so a judge *sees* three agents working without being told. It also removes the merge step entirely for `sitrep` queries, cutting one LLM call and one hallucination surface.

**Sections are independent by construction.** Because each agent writes into a distinct slot, one agent timing out leaves a single section marked unavailable — not a broken report. This is the mechanism behind the §2.1 rule that partial reports are successful reports.

---

#### 🌊 Specialist 1 — Environmental Incident Investigator

| | |
|---|---|
| **Role** | Determine what may have happened, what is actually established, and what remains unknown |
| **Retrieval focus** | `record_type ∈ {incident, monitoring, field_note, region, narrative}`; boosts `INC-*`, `WS-*`, `FN-*`, `LAB-*` |
| **Special behaviour** | **Owns conflict detection.** Compares retrieved records for contradictory claims about the same event/location/date |
| **Output shape** | Investigation Brief — *Observed signs · Hypothesised causes (unranked, with evidence strength) · What the evidence establishes · What it does not · Recommended next evidence steps* |
| **Key guardrail** | Forbidden from asserting a confirmed cause unless a source explicitly confirms it |

This is the specialist that handles the turquoise-water trap.

---

#### 🐋 Specialist 2 — Marine-Life Protector

| | |
|---|---|
| **Role** | Identify affected species, their documented pressures, and protection procedure |
| **Retrieval focus** | `record_type ∈ {fauna, flora, region, policy, knowledge_card}`; boosts `FAU-*`, `FLR-*`, `POL-*` |
| **Special behaviour** | **Species isolation.** Each species assembled from its own record only — directly enforcing §15.2 rule 3 |
| **Output shape** | Species Impact Report — *Species (with ID) · Habitat · Documented pressures relevant to this event · Protection guidance · Applicable policies · Monitoring requirements* |
| **Key guardrail** | Never generalizes one species' pressures to another; never uses real-world marine biology |

---

#### 🚨 Specialist 3 — Emergency Responder

| | |
|---|---|
| **Role** | Convert evidence into a safe, ordered, executable action plan |
| **Retrieval focus** | `record_type ∈ {incident, knowledge_card, health, settlement, policy}` + Appendix A checklists; boosts `INC-*` immediate actions, `MED-*`, `A.1–A.4` |
| **Special behaviour** | Emits the **corpus's own KC-01 communication template** |
| **Output shape** | **Incident Action Card** — *Severity (W1–W4, cited) · Immediate actions (ordered, each cited) · Responder safety · Incident command roles to activate (§12.11) · Public communication draft · Minimum incident dataset to record · Next review time* |
| **Key guardrail** | Health content triggers red flags + fictional-material disclaimer automatically |

**The public communication draft uses the corpus's verbatim template (KC-01):**

> *"At [time] in [location], we observed [verified signs]. The cause is [confirmed/not yet confirmed]. People should [actions]. Avoid [restricted actions]. Report [symptoms or observations] through [channel]. The next update will be issued at [time]."*

Filling the corpus's own template with retrieved evidence is about as grounded as generation gets — and it produces something a real incident lead could read aloud, which is exactly the "practical and clearly explained" language of the 20-mark Real-World criterion.

---

### 5.4 Routing — three modes

The orchestrator picks one of exactly **three** dispatch modes. The agent roster is always the same three specialists; only how many fire, and on what, changes.

| Mode | Trigger | Dispatch | Output |
|---|---|---|---|
| **`sitrep`** *(default for situations)* | Incident-shaped input: an observation, a location, a symptom, or severity ≥ W1 — *"the water near Awa Reef has turned turquoise"* | **All 3 in parallel**, each filling its owned section | Full six-section Situation Report |
| **`focused`** | Single-topic lookup — *"what is the approach distance for a Deepbell Singer?"* | **1 specialist**, by topic signal | SITREP with the relevant section filled, others marked *not applicable to this query* |
| **`compare`** | "compare", "versus", "difference between", two subjects detected | **2 specialists in parallel** on disjoint sub-queries → synthesis | Side-by-side comparison report |

**Focused-mode signals** (unchanged from Rev 1): species name or `FAU-*`/`FLR-*` ID → Marine-Life Protector · "what should we do", "immediate", "respond" → Emergency Responder · "what caused", "why did", "investigate" → Investigator · ambiguous → Investigator (safest default, it never asserts causes) · "summarize", "across the reports" → Investigator with `k` widened to 10.

**`sitrep` mode is the headline.** Three agents fire at once, three sections fill at once, on screen. No merge step — each writes into its own slot. This is the demo's Beat 3.

**`compare` mode** — for *"Compare the recommended responses for water contamination and an underwater volcanic event"*: the orchestrator decomposes into two sub-questions, dispatches Investigator (→ `INC-001` Turquoise Water Event) and Emergency Responder (→ `INC-005` Vent Plume Release) **concurrently**, then synthesizes side by side. Each side retrieved independently, so neither is starved — this is the genuine retrieval-quality win described in §5.1, not theatre.

**Mode is shown in the trace**, so a judge can see the routing decision and its reason: *"Incident indicators detected → sitrep mode → dispatching 3 specialists in parallel."*

### 5.5 Validation, Retry, Timeouts, Partial Results

**These limits are absolute. Unbounded agent loops are the single most common way a hackathon demo dies on stage.**

| Control | Value | Rationale |
|---|---|---|
| Retry cap | **1**, hard | Second retry has poor marginal yield and doubles worst-case latency |
| Per-sub-agent timeout | **8 s** | ~2.5× expected 3 s response |
| Total orchestration budget | **25 s** | Hard ceiling; orchestrator returns best available at 25 s regardless |
| Max specialists per query | **3** | `sitrep` mode; 2 for `compare`, 1 for `focused` |
| Max total LLM calls per query | **8** | Orchestrate(1) + specialists(≤3) + retry(≤1) + synthesis(≤1) + validate(1) + conflict check(1) |

#### Parallelism math — why 3 agents does not mean 3× the wait

The three specialists are dispatched **concurrently, not sequentially.** Wall-clock cost is the *slowest* agent, not the sum:

| | Sequential (wrong) | Parallel (ours) |
|---|---|---|
| 3 specialists @ ~3 s each | ~9 s | **~3 s** |
| Worst case, all 3 hit the 8 s timeout | 24 s | **8 s** |
| Full `sitrep` query, end to end | ~13 s | **~5–6 s** |

Total orchestration budget stays at 25 s with comfortable headroom. Adding the third agent costs roughly nothing in wall clock — which is exactly why three-way section assembly is affordable, and why it looks impressive rather than slow.

**Graceful degradation ladder** — each rung is a real report, never a crash:

1. **All specialists return** → complete six-section SITREP.
2. **Some return, some time out** → **the report still renders.** Completed sections are fully populated; a timed-out section shows its honest empty state and an explicit note: *"🐋 Marine-Life Protector did not respond within 8 s — Affected Species unavailable for this report."* Honest partial > silent partial, and per §2.1 this is a *successful* report.
3. **All specialists fail, retrieval succeeded** → fall back to **Layer 2 single-agent generation** over the already-retrieved chunks, filling the same six sections sequentially. Structurally identical output; a judge cannot tell the difference. Still fully grounded and cited.
4. **Retrieval itself fails** → the honesty flip: *"⚠ Insufficient Evidence — Recommend Field Investigation"* with the searched-scope explanation.

**Rung 3 is the safety net that makes the whole architecture safe to demo.** The agentic layer sits *on top of* a working single-agent RAG that produces the identical report format (Layer 2 in §10). Any agentic failure degrades to that, not to an error screen. **The fallback is not a separate plan — it is a live runtime path**, and it is the reason Layer 5 can never take down Layer 2.

---

## 6. Advanced Features & Rubric Mapping

### 6.1 Implementing

| Feature | Primary rubric target | Why it earns marks |
|---|---|---|
| **Hybrid search (BM25 + vector, RRF)** | RAG **25** | Correctness requirement, not a nicety — record IDs and invented proper nouns need exact match (§4.3) |
| **Semantic reranking** | RAG **25** | Highest-value precision upgrade; joint query-chunk scoring |
| **Record-aware chunking** | RAG **25** | Our biggest differentiator; prevents the cross-record merge the corpus explicitly prohibits |
| **Query rewriting & expansion** | RAG **25** | Closes vocabulary gap, resolves coreference, promotes IDs to filters |
| **Metadata filtering** | RAG **25** | Region/type/date/severity narrowing before search |
| **Relevance + confidence scoring** | Accuracy **20** + required sources | Brief mandates relevance score; confidence meter states its reason |
| **GroundingGate (8 corpus rules)** | Accuracy **20** | Executes the corpus's published grounding checklist verbatim |
| **Evidence-quality labels** | Accuracy **20** | Explicitly instructed by corpus page 2 |
| **🔥 Conflict detection & presentation** | Accuracy **20** + Innovation **10** | Answers the corpus's planted trap exactly as specified |
| **Emergency-priority classification (W1–W4)** | Real-world **20** | Grounded triage using the corpus's own scale, not an invented label |
| **Incident Action Cards** | Real-world **20** | Executable output a real incident lead could act on |
| **Multi-document comparison** | Real-world **20** + Innovation **10** | Covers demo Q4; parallel retrieval genuinely improves both sides |
| **Agentic orchestration** | Innovation **10** | Visible, bounded, purpose-built |
| **Visible orchestration trace** | Innovation **10** + UX **15** | Makes the invisible legible to judges |
| **🏆 Situation Report format** | Real-world **20** + UX **15** | The format *is* the practical value — priority, species, causes, actions, sources, confidence in one operational document (§2.1) |
| **🏆 Visible parallel agent assembly** | Innovation **10** + UX **15** | Three agents filling three report sections concurrently, on screen (§5.3) — makes sophistication perceivable |
| **🏆 Map-based incident view** | UX **15** + Real-world **20** | Stylized Pandora map; `REG-*` zones lit by priority; click to filter sources by region (§8.5) |
| **🏆 Role toggle (Guardian/Researcher/Citizen)** | Real-world **20** + Innovation **10** | Listed bonus feature. Re-renders the **same frozen evidence** in three registers — no re-query, so citations never shift (§8.6) |
| **Light conversation memory (last turn)** | UX **15** | Enables natural follow-ups; strictly bounded to coreference resolution |

*🏆 = one of the five wow features (§2.2).*

#### Conflict detection — the mechanism

Worth specifying precisely, since it is our highest-value feature.

**Detection.** After retrieval, the Investigator scans the retrieved set for records that (a) describe the same location/event/date and (b) assert incompatible claims. Two signals drive it:
- **Structural** — any chunk labelled `evidence_quality = disputed report` in the set; or ≥2 `field_note` records on the same event; or ≥2 `SV-*` records for the same species+region with differing counts.
- **Semantic** — a focused LLM check over the retrieved set: *"Do any of these records make incompatible claims about the same event? Return record ID pairs and the nature of the conflict."*

**Presentation.** When triggered:
- The answer explicitly declines to resolve the conflict and states that no cause is confirmed.
- A **Conflicting Evidence panel** renders each position in its own column — record ID, claim, evidence quality, and *reliability limitation* (e.g. *"chain of custody incomplete"*, *"survey effort not normalized"*).
- Confidence drops to Moderate with the conflict named as the reason.
- The answer recommends the evidence that would resolve it, citing Appendix A.

**Two conflicts are pre-verified in the corpus and will be demoed:**

| Conflict | Records | Reliability limitation |
|---|---|---|
| Turquoise water cause at Awa Reef | `FN-A` (plankton bloom, no chemical odor) vs `FN-B` (damaged waste container at upstream pigment workshop, entry unconfirmed) vs `LAB-C` (harmless carbonates + moderate plankton) | **`LAB-C` chain-of-custody form incomplete**; `FN-B` never confirmed material entered water |
| Tideglass Grazer population at Awa Reef | `SV-101` (42 individuals, 2 divers × 40 min, high confidence) vs `SV-102` (17 individuals, 1 diver × 20 min, low confidence) | **Survey effort not normalized** — corpus warns a lower count from shorter effort is *not* evidence of decline |

The second is a subtler trap than the first, and catching it is a strong signal of retrieval quality.

### 6.2 Skipping — and why

Deliberate scope discipline. Each of these is a listed bonus feature we are consciously declining.

| Feature | Why not |
|---|---|
| **Voice input** | Browser speech API is ~30 min, but adds live-demo failure surface (mic permissions, ambient noise in a judging room) for zero grounding benefit. Bad risk/reward on stage. |
| **Multilingual** | Corpus is English-only; translating answers would break verbatim citation fidelity — actively harmful to our core strength. |
| **Map-based *retrieval*** | Querying *by geography* ("show everything within 10 km of…") needs geospatial indexing the corpus does not support — it has named regions, not coordinates. **Note the distinction: map *visualization* is in scope (§8.5, Layer 6); map *retrieval* is not.** The map reads `region_id` metadata we already index; it never drives search. |
| **Knowledge-graph store** | Genuine value, but a real graph store is 2+ hours. We capture ~80% of the benefit for ~5% of the cost via `region_id` and `record_type` metadata cross-linking. |
| **Deep conversation memory** | Full history invites context drift and citation confusion. Last-turn coreference only — bounded and safe. |
| **Fine-tuning / custom embeddings** | Impossible in 5 hours; no benefit at 220 chunks. |
| **User-configurable chunking UI** | Judges evaluate output, not knobs. |

---

## 7. Visible Orchestration

**The problem this solves:** agentic architecture is invisible. A judge sees a text box and an answer — identical to every other team's. Sophistication that cannot be perceived earns nothing.

**The solution:** stream the orchestration live. The agent's reasoning becomes a first-class UI surface.

### 7.1 Trace contents

Every step emitted to the client over Server-Sent Events as it happens:

| Step | Displayed | Example |
|---|---|---|
| `query.received` | The raw question | *"Compare the recommended responses for water contamination and an underwater volcanic event"* |
| `query.rewritten` | Rewritten + variants | *"water contamination response protocol"* / *"underwater volcanic eruption vent response"* |
| `query.classified` | Use case · severity · shape | *Emergency Response · W3 · compare* |
| `priority.classified` | Triage banner renders **immediately** | *"🔴 W3 Emergency — multiple illnesses / fish deaths indicators present [§4.5]"* |
| `map.zone_lit` | Map zone ignites | *"REG-01 Luminous Shelf → 🔴"* |
| `route.decided` | Mode, which specialists, and **why** | *"Incident indicators detected → sitrep mode → dispatching 3 specialists in parallel"* |
| `retrieval.started` | Per specialist: filters, k | *"BM25 + vector, k=30, filter: record_type=incident"* |
| `retrieval.completed` | Candidates found, reranked, kept | *"38 candidates → reranked → top 8 · best score 3.71"* |
| `agent.thinking` | Specialist active, live elapsed | *"🌊 Incident Investigator — analysing 8 sources… 1.8 s"* |
| **`section.filling`** | **A SITREP section begins streaming, badged with its owning agent** | *"🐋 Affected Species — filling…"* |
| **`section.completed`** | **Section done: claim count + source count** | *"🐋 Affected Species — 3 species, 4 claims, 4 sources · 2.6 s"* |
| **`section.unavailable`** | **Section honestly empty, with reason** | *"🌊 Likely Causes — cause not established, 3 records conflict"* |
| `agent.completed` | Result + claim count | *"🚨 Emergency Responder — 6 claims, 5 sources · 2.9 s"* |
| `conflict.detected` | Conflict found | *"⚠️ 3 records disagree on cause — FN-A / FN-B / LAB-C"* |
| `validation.running` | GroundingGate checks | *"Checking 8 grounding rules…"* |
| `validation.result` | Per-rule pass/fail + score | *"8/8 passed · groundedness 96%"* |
| `synthesis.started` | Merging parallel results | *"Synthesising 2 specialist reports"* |
| `answer.streaming` | Tokens as generated | — |
| `answer.completed` | Totals | *"4.2 s · 6 LLM calls · 11 sources"* |

Timeouts, retries, and partial results are shown with equal prominence: *"⏱ Marine-Life Protector timed out at 8 s — continuing with partial result."* **Showing a handled failure builds more credibility with judges than hiding it** — it demonstrates the timeout logic is real.

### 7.2 UI presentation

A persistent **Orchestration Rail** down the right side (collapsible; bottom drawer on mobile).

- **Three specialist nodes**, always visible as bioluminescent orbs. Dormant = dim outline. Active = ignites, pulses, radiates a soft cyan bloom with a live elapsed counter. Complete = steady glow + claim/source count. Timed out = amber ring + "partial".
- **Parallel work is unmistakable** — on a `sitrep` query, **all three orbs ignite simultaneously.** This is the visual that sells the architecture in one glance, with no explanation needed.
- **Orb ↔ section coupling** — each orb is visually tethered to the SITREP section it owns: a faint bioluminescent thread runs from the orb to its section, and the section's left border glows in the agent's colour while filling. When three sections fill at once with three threads pulsing, *nobody needs the architecture explained.* **This is the single most important visual in the product** — it converts an invisible backend design into something a judge grasps in two seconds.
- **Sections fill out of order, and that's the point** — Recommended Actions may land before Affected Species. Seeing sections complete in a non-sequential order is the proof that they were genuinely concurrent, not scripted.
- **Step timeline** streams beneath the orbs, newest last, each with its duration.
- **GroundingGate panel** — eight rule rows that tick green in sequence as they pass. Watching a published eight-rule checklist validate in real time is a powerful, concrete credibility signal.
- **Replay** — after completion the trace stays; a scrub control replays it. Critical for demo recovery: if the live network is slow, we replay a cached trace at full speed instead of standing in silence.

---

## 8. UI/UX & Pandora Theme (15 Marks)

> Target: **Best UI/UX Design Award.** The brief asks for "simple and usable" plus a Pandora-inspired theme. We deliver both — usability first, atmosphere second, never atmosphere at usability's expense.

### 8.1 Required elements — all present, all obvious

| Requirement | Implementation |
|---|---|
| Document-upload area | Drag-and-drop zone, top of Knowledge panel. Live ingestion progress. Corpus preloaded and listed. |
| Question-input area | Centre stage. Large, always-focused, with Pandora-specific example-question chips. |
| Generated-answer section | **The Situation Report** — primary column, centre stage. Six sections (§2.1) streaming in progressively, each badged with its owning agent, inline citation chips throughout. Topped by the triage banner. |
| Retrieved-sources section | Persistent left/lower panel — **never collapsed by default.** Full card per §4.5. |
| Clear / reset | Explicit "New Investigation" control. Clears conversation, trace, sources. |

### 8.2 Visual direction — "the abyss at night"

**Concept:** the deep-water bioluminescence of *The Way of Water* — an interface that feels alive but stays legible. Dark, calm, deep, with light used as *meaning* rather than decoration: **things glow because they are active or because they are evidence.**

| Token | Value | Use |
|---|---|---|
| Abyss (base) | `#04121C` | Page background |
| Deep current | `#0A2233` | Panels, cards |
| Surface glass | `rgba(255,255,255,0.04)` + blur | Elevated surfaces |
| Bioluminescent cyan | `#3EE8D0` | Primary accent, active agents, citations |
| Reef teal | `#1FA9A0` | Secondary, relevance bars |
| Spirit violet | `#7B6BF0` | Innovation/agentic accents |
| Warning amber | `#F0A93E` | Advisory (W2), partial results |
| Coral alert | `#F0644E` | Emergency (W3/W4) |
| Foam (text) | `#E8F6F5` | Primary text |
| Mist (muted) | `#8FAFB8` | Secondary text |

**Typography.** Display: a humanist sans with slightly organic letterforms for headings. Body: Inter (or system UI) for absolute legibility. Mono: JetBrains Mono for record IDs — IDs read as *data*, which reinforces the evidence framing.

**Motion — restrained and purposeful.**
- Slow plankton drift in the page background: sparse particles, very low opacity, `prefers-reduced-motion` respected. Atmosphere without distraction.
- Active agent orbs "breathe" — 2.4 s ease-in-out glow cycle.
- Citation chips ripple outward when their source card is spotlighted.
- Answers fade-and-rise in as they stream.
- Nothing bounces, nothing spins, nothing demands attention that isn't earning it.

**Signature interactions:**
1. **Inline citation chips.** Every claim ends with `[INC-005]` as a small glowing chip. Hover → the chip and its source card both illuminate and the card scrolls into view with its excerpt highlighted. Click → pins it. **This is the feature that makes grounding *felt* rather than claimed** — a judge can verify any sentence in one gesture.
2. **The orchestration rail** (§7.2).
3. **Confidence meter that explains itself.** A luminous arc plus a plain-language reason. Never a naked number.
4. **Conflicting Evidence panel.** Contested claims in side-by-side columns, each with its record ID, evidence-quality badge, and reliability limitation. Visually asserts *we did not pick a winner.*
5. **Severity chip.** W1–W4 as word + shape + colour.

### 8.3 Accessibility — and why it scores here

Per corpus §11.1: *"Do not use color alone for hazard levels; pair it with words and shapes."*

We follow the corpus's own accessibility rule, which is both correct and a rubric point:

- Severity always = **colour + word + shape** (W2 amber triangle "Advisory"; W3 coral octagon "Emergency").
- All text ≥ 4.5:1 contrast on the dark base.
- Full keyboard navigation; visible focus rings in bioluminescent cyan.
- `prefers-reduced-motion` disables drift, breathing, and ripples.
- Streaming answers announced via ARIA live regions.
- Semantic landmarks throughout.

Mentioning in the pitch that our hazard indicators follow the corpus's own communication guidance is a small, precise detail that signals we read the material properly.

### 8.4 Command Center layout

**Desktop (three columns):**

- **Left (300 px)** — *Knowledge & Map.* Upload zone, document list with chunk counts, corpus stats (*"220 chunks · 130 records · 15 chapters"*), and the **Pandora map panel** (§8.5) below.
- **Centre (fluid)** — *The Situation Report.* Question input at top; then the triage banner; then the six report sections streaming in, each with its agent badge and glowing left border; confidence meter; conflict panel; source cards beneath. **The role toggle sits in the report header** (§8.6).
- **Right (320 px, collapsible)** — *Orchestration Rail* (§7.2).

**Tablet** — left column collapses to a drawer; rail moves to a bottom sheet; map becomes a collapsible card above the report.
**Mobile** — single column, report first; rail becomes an expandable summary strip; map collapses to a zone chip row; source cards stack.

#### The triage banner

> **Wow feature 3.** Built at **Layer 3**. Target: **Real-world (20)**.

Full-width, directly above the report. The **first** thing that renders — before any generation completes — because priority is what a guardian needs in the first second.

| Level | Corpus class | Visual | Shape | Label |
|---|---|---|---|---|
| 🔴 | **W3 Emergency / W4 Regional Crisis** | Coral alert `#F0644E`, pulsing border | Octagon | **EMERGENCY** / **REGIONAL CRISIS** |
| 🟠 | **W2 Advisory** | Warning amber `#F0A93E`, steady | Triangle | **ADVISORY** |
| 🟢 | **W1 Observation** / informational | Reef teal `#1FA9A0`, steady | Circle | **OBSERVATION** |

**The banner always states its reason, and the reason is cited.** Not *"Priority: High"* but:

> 🔴 **W3 EMERGENCY** — *fish deaths and severe oxygen loss reported; matches W3 indicators* `[§4.5 Water Incident Classification, p.12]`

That citation is the whole point. A made-up severity label is an ungrounded model opinion — exactly what the rubric penalizes. A `W3` classification traced to the corpus's own scale **is itself a grounded claim.** We turned a bonus feature into a grounding feature.

Colour never carries the meaning alone — level, shape, and word are always present together, per corpus §11.1.

---

### 8.5 The Pandora Map Panel (Layer 6)

> **Wow feature 4.** Built at **Layer 6**. Target: **UX (15)** + Real-world (20).

A stylized, hand-drawn-feel map of Pandora — **not** a real geographic map, and not an image asset from the corpus (there are none). Ten fixed zones corresponding to `REG-01` … `REG-10`, hand-placed once as inline SVG paths.

| Aspect | Spec |
|---|---|
| **Rendering** | Inline SVG, ten `<path>` zones + coastline. Dark abyssal base with faint bioluminescent contour lines. |
| **Idle state** | All zones dim teal outline, gently breathing. Reads as a living world, not a diagram. |
| **Active state** | Zones referenced by the current report **ignite** in their triage colour with a radial bloom and a soft ripple outward — bioluminescence responding to disturbance. |
| **Data source** | The `region_id` metadata **already on every chunk** (§4.2). Zero new retrieval work — the map is a projection of data we index anyway. |
| **Interaction** | Hover → zone name + active incident count. Click → filters the report's Sources section to that region, and dims non-matching source cards. |
| **Multi-zone** | A report citing several regions lights all of them, each at its own priority — instantly conveying *spread*, which is precisely what separates W3 from W4. |
| **Empty state** | No region resolved → map stays idle with *"No region identified in the available evidence"*. Honest, consistent with §2.1 rule 3. |

**Why it earns marks rather than being decoration.** The corpus's central thesis is *connectivity* — chapter 1's "living network", the principle that "water, migration routes, food webs, and cultural practices cross village boundaries." A map is the only way to *show* that a `REG-05` vent event and a `REG-01` reef are part of one system. It also makes W4 ("contamination crosses settlements") visually self-evident: multiple zones lit at once.

**Cost control.** Ten static SVG paths, one colour binding, one hover handler. It is genuinely a ~30-minute component, which is why it survives at Layer 6 while heavier ideas were cut.

---

### 8.6 Role Toggle (Layer 6)

> **Wow feature 5.** Built at **Layer 6**. Target: Real-world (20) + **Innovation (10)**.

A three-way segmented control in the report header: **Guardian · Researcher · Citizen.**

| Role | Register | Depth | Emphasis |
|---|---|---|---|
| **Guardian** *(default)* | Operational, imperative | Full protocol detail | Immediate actions, safety, command roles, next review time |
| **Researcher** | Technical, precise | Maximum — includes measurements, survey effort, evidence-quality labels, methodology caveats | Data provenance, conflicts, chain of custody, what would resolve uncertainty |
| **Citizen** | Plain language, no jargon | Condensed | What it means for me, what to avoid, where to report, when the next update comes |

**The hard rule: re-render, never re-query.**

Flipping the toggle **does not** re-run retrieval, re-run agents, or re-run GroundingGate. It re-renders the *same frozen evidence set* — the identical claims, the identical record IDs, the identical citations — in a different register. One retrieval, one grounded claim set, three presentations.

This is a correctness requirement, not an optimization. If flipping Guardian → Citizen re-ran the pipeline, a judge would watch the cited evidence shift between roles and the grounding story we spent 45 marks building would visibly collapse. It is also faster (no API call — a pure client-side re-render from the persisted claim set) and therefore demos instantly.

**The Citizen view uses the corpus's own communication template** (`KC-01`), so the plain-language rendering is itself grounded rather than freely paraphrased:

> *"At [time] in [location], we observed [verified signs]. The cause is [confirmed/not yet confirmed]. People should [actions]. Avoid [restricted actions]. Report [symptoms] through [channel]. The next update will be issued at [time]."*

**The pitch line:** *"Same evidence. Same record IDs. Three audiences."* — which is exactly the corpus's §11.1 instruction to *"use plain-language summaries alongside technical reports."*

---

## 9. Data Model

**Split of responsibilities:** Azure AI Search owns vectors and search-time metadata. PostgreSQL (EF Core) owns durable application state, audit, and traces. No duplication of chunk *content* as source of truth — Search is authoritative for retrieval; Postgres stores the chunk reference and metadata for traceability.

### 9.1 PostgreSQL (EF Core)

**`Documents`**
| Column | Type | Notes |
|---|---|---|
| `Id` | uuid PK | |
| `FileName` | text | Displayed on source cards |
| `ContentType` | text | pdf / txt / csv / docx |
| `SizeBytes` | bigint | |
| `PageCount` | int | |
| `IsPreloaded` | bool | True for the Pandora corpus |
| `IngestStatus` | enum | Pending / Extracting / Chunking / Embedding / Indexed / Failed |
| `ChunkCount` | int | |
| `UploadedByUserId` | uuid FK → Users | Nullable |
| `CreatedAt` | timestamptz | |

**`Chunks`** — metadata mirror for traceability and UI; vector lives only in Search.
| Column | Type | Notes |
|---|---|---|
| `Id` | uuid PK | Matches Search `chunk_id` |
| `DocumentId` | uuid FK | |
| `RecordId` | text | `INC-005` — indexed |
| `RecordType` | enum | incident / fauna / flora / policy / region / settlement / health / accommodation / knowledge_card / monitoring / field_note / narrative |
| `Title` | text | |
| `Chapter`, `Section` | text | |
| `Page` | int | |
| `RegionId` | text | `REG-05`, nullable |
| `EvidenceQuality` | enum | 5-value corpus taxonomy |
| `RiskLevel` | enum | Low / Medium / High / Critical, nullable |
| `RecordDate` | date | Nullable — for `WS-*`, `SV-*`, `FN-*` |
| `FieldName` | text | Nullable |
| `Content` | text | |
| `TokenCount` | int | |

**`Conversations`** — `Id`, `UserId`, `RoleLens`, `Title`, `CreatedAt`.

**`Queries`** — one row per question.
`Id`, `ConversationId`, `RawQuestion`, `RewrittenQuestion`, `UseCase`, `SeverityClass` (W1–W4), `QueryShape`, `AnswerText`, `GroundednessScore`, `ConfidenceScore`, `ConfidenceReason`, `WasInsufficient`, `HadConflict`, `TotalLatencyMs`, `LlmCallCount`, `CreatedAt`.

**`SituationReports`** — one per query; the Command Center's output object.
| Column | Type | Notes |
|---|---|---|
| `Id` | uuid PK | |
| `QueryId` | uuid FK | 1:1 with `Queries` |
| `PriorityClass` | enum | `W1` / `W2` / `W3` / `W4` / `Informational` |
| `PriorityReason` | text | Human-readable, e.g. *"fish deaths and severe oxygen loss reported"* |
| `PriorityCitation` | text | Record/section the classification is grounded in — `§4.5 p.12` |
| `AffectedRegionIds` | text[] | `REG-01`, `REG-05` — **drives the map** (§8.5) |
| `AssemblyMode` | enum | `Sitrep` / `Focused` / `Compare` / `SingleAgentFallback` — records which path produced it |
| `ConfidenceLevel` | enum | High / Moderate / Low / Insufficient |
| `ConfidenceReason` | text | The stated reason shown on the meter |
| `WasPartial` | bool | True if any section timed out |

**`ReportSections`** — one row per SITREP section; the unit of independent success or failure.
| Column | Type | Notes |
|---|---|---|
| `Id` | uuid PK | |
| `SituationReportId` | uuid FK | |
| `SectionType` | enum | `Priority` / `AffectedSpecies` / `LikelyCauses` / `RecommendedActions` / `Sources` / `Confidence` |
| `OwningAgent` | enum | `Orchestrator` / `MarineLifeProtector` / `IncidentInvestigator` / `EmergencyResponder` |
| `Status` | enum | `Filled` / `Empty` / `TimedOut` / `NotApplicable` |
| `EmptyReason` | text | Nullable — *"cause not established, 3 records conflict"* |
| `Content` | text | Rendered markdown for this section |
| `ClaimCount` | int | Factual claims made |
| `SupportedClaimCount` | int | Claims that passed GroundingGate — section-level groundedness |
| `DurationMs` | int | Fill time; powers the trace |
| `DisplayOrder` | int | Fixed section order per §2.1 |

> **Why sections are rows, not JSON on the report.** Independent status per section is the whole point of §2.1 — a section must be able to time out without touching its siblings, and the trace must be able to stream `section.completed` events individually. Modelling them as rows makes partial reports a first-class, queryable state rather than a parsing exercise.

**Role toggle stores nothing new.** It re-renders `ReportSections.Content` client-side against the frozen `Citations` set — no additional persistence, no re-query (§8.6).

**`Citations`** — the evidence trail; one row per source used in an answer.
`Id`, `QueryId`, `SituationReportId`, `SectionType`, `ChunkId`, `RecordId`, `RelevanceScore`, `RerankScore`, `Excerpt`, `DisplayOrder`, `WasCitedInline`.

*(`SectionType` added so the Sources section can show which report section each citation supports, and so clicking a map zone can filter citations by region via `Chunks.RegionId`.)*

**`AgentRuns`** — one per specialist invocation.
`Id`, `QueryId`, `AgentName`, `Status` (Completed / TimedOut / Failed / Retried), `AttemptNumber`, `RetrievedCount`, `ClaimCount`, `DurationMs`, `StartedAt`.

**`AgentSteps`** — the replayable trace.
`Id`, `QueryId`, `AgentRunId` (nullable — orchestrator steps have none), `StepType` (matches §7.1), `Payload` (jsonb), `DurationMs`, `SequenceNumber`, `OccurredAt`.

**`GroundingChecks`** — per-rule audit.
`Id`, `QueryId`, `RuleNumber` (1–8), `RuleName`, `Passed`, `Detail`.

**`Conflicts`** — `Id`, `QueryId`, `RecordIdA`, `RecordIdB`, `ConflictNature`, `ReliabilityLimitation`.

**`Users`** — `Id`, `SupabaseUserId`, `Email`, `DisplayName`, `Role` (Guardian / Researcher / Citizen), `CreatedAt`.

### 9.2 Azure AI Search index

Single index `pandora-knowledge`, fields exactly as §4.2's metadata table, plus `content_vector` (1536-dim, HNSW, cosine) and a semantic configuration over `title` + `content`.

### 9.3 Why the trace is persisted

`AgentSteps`, `GroundingChecks`, and `Citations` are not logging — they are **product**. They power trace replay (demo insurance), they are the "evidence of retrieved sources for each answer" the submission explicitly requires, and they let us prove in the pitch that grounding is audited rather than asserted.

---

## 10. Bankable Build Order & Fallback Plan

> **This section is binding.** It is the difference between winning and demoing a broken app.

### 10.0 The banking principle

Most hackathon teams build **horizontally** — a bit of ingestion, a bit of UI, a bit of agents — and at T+4:30 they have five things that are each 70% done and nothing that works end to end. They demo apologies.

We build **vertically, in layers.** Each layer is a **complete, working, demoable product on its own.** We finish a layer, commit it, tag it, and only then start the next. At any moment from T+2:00 onward, if everything stopped, we would still have something we could submit and demo without embarrassment.

**Three iron rules:**

| Rule | Meaning |
|---|---|
| **1 · Every layer is independently demoable** | Not "compiles" — *demoable*. You can ask it a question and get a grounded, cited answer on screen. |
| **2 · A later layer breaking must NEVER take down an earlier one** | Enforced three ways: a **feature flag** per layer, a **git tag** per layer, and the **runtime degradation ladder** in §5.5. Layer 5 failing falls back to Layer 2's output — same report, filled sequentially. |
| **3 · Marks are banked, not promised** | Layer 1 alone banks the 45-mark core. Everything after is additive upside on a green build. |

### 10.1 The six layers

| Layer | Delivers | Banks | Flag | Tag & gate |
|---|---|---|---|---|
| **1** | **Core single-agent RAG** | **45 marks — a complete submission on its own** | *(always on)* | **T+2:00 · `v1-core-rag`** |
| **2** | Situation Report shell | Real-world 20 · UX 15 | `SITREP_SHELL` | T+2:40 · `v2-sitrep` |
| **3** | Triage banner | Real-world 20 | `TRIAGE_BANNER` | T+3:00 |
| **4** | Confidence meter + honesty flip | Accuracy 20 | `CONFIDENCE_METER` | T+3:20 · `v3-honest` |
| **5** | Parallel specialist agents fill sections live | Innovation 10 · UX 15 | `AGENTIC_ENABLED` | T+4:10 · `v4-agentic` |
| **6** | Map view · role toggle · orchestration animation | UX 15 · Innovation 10 | `MAP_VIEW`, `ROLE_TOGGLE`, `ORCH_ANIM` | T+4:40 *(if time)* |

---

#### 🟦 Layer 1 — Core single-agent RAG · **BUILD THIS FIRST**

**The complete path:**

> Ingest → record-aware chunk → embed → Azure AI Search → hybrid retrieve + rerank → **grounded generation from retrieved context only** → sources (document name · section/page · excerpt · relevance score) → insufficient-evidence handling

**This is a complete, competitive submission by itself.** It satisfies **all seven** minimum functional requirements in the brief, and already includes two bonus features (hybrid search, reranking) plus our strongest differentiator (record-aware chunking, §4.2).

**It banks the 45 marks that matter most** — RAG Architecture & Retrieval Quality (25) + Accuracy & Grounded Responses (20). Those two categories are worth more than everything in Layers 2–6 combined. **Nothing else starts until this is green and tagged.**

*Demoable as:* a working RAG app — ask any of the 7 brief questions, get a grounded cited answer with source cards.

---

#### 🟦 Layer 2 — Situation Report shell

Same single agent, one retrieval, one generation — but the output is **formatted into the six SITREP sections** (§2.1) instead of a paragraph. The agent fills sections sequentially in one pass.

*Isolation:* pure presentation + prompt change over Layer 1. `SITREP_SHELL=false` reverts to Layer 1's prose answer instantly.
*Why early:* this is where the *"command center, not chatbot"* framing lands, and it costs one prompt rewrite plus a renderer. Highest value-per-minute in the build.
*Critical property:* **Layer 2's output is structurally identical to Layer 5's.** That identity is what makes the agentic fallback invisible.

*Demoable as:* the Guardian Command Center, single-agent. Already looks like the finished product.

---

#### 🟦 Layer 3 — Triage banner

🔴/🟠/🟢 with a **cited** reason, classified against the corpus's own W1–W4 scale (§8.4).

*Isolation:* renders above the report; failure hides the banner and touches nothing else.
*Cost:* one classification field already produced by the orchestrator prompt + one component.

*Demoable as:* Layer 2 + instant visual priority.

---

#### 🟦 Layer 4 — Confidence meter + honesty flip

The full uncertainty design (§4.6): confidence meter that states its reason, and *"⚠ Insufficient Evidence — Recommend Field Investigation"* on thin evidence.

*Isolation:* `CONFIDENCE_METER=false` → answers still render, meter hidden, insufficient-evidence still handled by Layer 1's baseline path (which already implements the brief's mandated sentence).
*Why here:* this completes **all 45 core marks plus the honesty story** before any agent code exists. **At T+3:20 we are already a strong 1st-place candidate.** Everything after is award-hunting.

*Demoable as:* a fully honest, fully grounded command center. **This is the tag we would ship if the venue burned down.**

---

#### 🟥 Layer 5 — Parallel specialist agents fill sections live

The agentic layer (§5). Three fixed specialists, each owning a SITREP section, dispatched concurrently and visibly.

**Hard constraints — all specified in §5.5, restated here because this is the layer that can hurt us:**

| Constraint | Value |
|---|---|
| Agent count | **Fixed at 3.** Never dynamic. |
| Refinement loop | **Hard-capped at 1 retry**, enforced by a counter in orchestrator state — not by prompt instruction |
| Timeout | **8 s per agent call**, no exceptions |
| Partial results | A timed-out section renders its honest empty state; **the report still ships** |
| **Degradation** | **Any agent failure → falls back to Layer 2 single-agent generation.** Same six sections, filled sequentially. A judge cannot tell. |

*Isolation:* `AGENTIC_ENABLED=false` → Layer 2. This is the **only** layer that can fail loudly, and its failure target is a fully working, fully grounded report.

*Demoable as:* the full wow — three orbs igniting, three sections filling at once.

---

#### 🟩 Layer 6 — Map view · role toggle · orchestration animation

Three *independent* flags (§8.5, §8.6, §7.2), deliberately not one. A broken map must not cost us the role toggle.

*Isolation:* each flag off → that element simply doesn't render. Zero effect on the report.
*Status:* **pure garnish. Built only if Layers 1–5 are green and tagged.** Cut without hesitation.

---

### 10.2 Build timeline

| Time | Layer | Milestone | Gate |
|---|---|---|---|
| **T+0:00 – 0:30** | 1 | Scaffold: .NET API + Next.js, Azure AI Search index created, Foundry connectivity verified. **API contract frozen.** | Both endpoints respond |
| **T+0:30 – 1:15** | 1 | Ingestion: PDF extraction, record-aware chunker, embedding, indexing. Corpus indexed. | **Manual verification: 10 sampled records — `INC-005`, `FAU-014`, `WS-03`, `FN-A`, `POL-001`, `KC-01` — each a clean, complete, unmerged chunk** |
| **T+1:15 – 1:45** | 1 | Retrieval: hybrid + rerank + scores. Tested via API against all 7 brief questions. | Correct records in top-6 for all 7 |
| **T+1:45 – 2:00** | 1 | Grounded generation + citations + source cards + insufficient-evidence path | **🔒 GATE: `v1-core-rag` tagged. 45 marks banked.** |
| **T+2:00 – 2:40** | 2 | UI: theme, Command Center layout, question input, streaming, **SITREP six-section renderer**, inline citation chips, reset | **🔒 GATE: `v2-sitrep` tagged** |
| **T+2:40 – 3:00** | 3 | Triage banner: W1–W4 classification + cited reason + 🔴/🟠/🟢 component | Banner renders before generation completes |
| **T+3:00 – 3:20** | 4 | GroundingGate (8 rules) + confidence meter + honesty flip + conflict detection | **🔒 GATE: `v3-honest` tagged. Turquoise question produces Contested state. Record backup demo video NOW.** |
| **T+3:20 – 4:10** | 5 | Orchestrator + 3 specialists + section ownership + `sitrep`/`compare` routing + timeouts + degradation | **🔒 GATE: `v4-agentic` tagged.** Flag off ⇒ clean Layer 2 |
| **T+4:10 – 4:30** | 5–6 | Orchestration rail + orb↔section threads; then map view, role toggle | Parallel orbs visible; each Layer-6 flag independently togglable |
| **T+4:30 – 4:45** | — | README, architecture diagram, prebuilt-component disclosure, **re-record backup video** | All 9 submission items exist |
| **T+4:45 – 5:00** | — | **CODE FREEZE. Rehearse demo twice against a timer.** | No commits after 4:45 |

**Note the video is recorded twice** — once at T+3:20 against `v3-honest` (a guaranteed-good demo), and again at T+4:45 against the final build. If the final build misbehaves on stage, the T+3:20 video is still a strong, honest demo of a complete system.

### 10.3 Feature flags — one per layer

Every layer above Layer 1 sits behind an independently revertable flag. **Flags are wired the moment the layer starts, not after it finishes** — a half-built layer is always off by default.

| Flag | Layer | Off behaviour |
|---|---|---|
| `SITREP_SHELL` | 2 | Layer 1 prose answer with source cards |
| `TRIAGE_BANNER` | 3 | Report renders without the priority banner |
| `CONFIDENCE_METER` | 4 | Meter hidden; Layer 1 insufficient-evidence path still active |
| `GROUNDING_GATE_STRICT` | 4 | Score computed and shown, but never blocks an answer |
| `CONFLICT_DETECTION` | 4 | Standard grounded answer, no conflict panel |
| `AGENTIC_ENABLED` | 5 | **Layer 2 single-agent fill — identical report structure** |
| `MAP_VIEW` | 6 | Left column shows knowledge panel only |
| `ROLE_TOGGLE` | 6 | Guardian register only |
| `ORCH_ANIM` | 6 | Rail shows a plain text step list |
| `DEMO_MODE` | — | Serves cached responses for the 4 demo questions — zero API dependency |

**If anything is unstable at T+4:45, we flip the flag rather than debug. We demo a smaller thing that works, never a bigger thing that doesn't.**

### 10.4 What "banked" means in practice

| If we stop at… | We can still submit | Realistic score |
|---|---|---|
| **Layer 1** (T+2:00) | A complete, grounded, cited RAG app meeting all 7 minimum requirements | Strong pass — the 45-mark core, plus retrieval bonuses |
| **Layer 4** (T+3:20) | A polished, honest Guardian Command Center | **1st-place contender without a single agent** |
| **Layer 5** (T+4:10) | Full agentic assembly, visible | 1st place + Innovation contender |
| **Layer 6** (T+4:40) | Everything | 1st + Innovation + UI/UX |

The point of the table: **we are never gambling.** Each additional layer raises the ceiling without ever lowering the floor.

---

## 11. Use-Case Coverage

The brief requires **at least three**. We cover **five**, all grounded in real corpus records.

### ✅ 1 · Environmental Incident Investigation *(required — primary)*
**Agent:** Incident Investigator · **Records:** `INC-001…010`, `WS-01…04`, `FN-A/B`, `LAB-C`, `REG-*`
Identifies causes as hypotheses, affected areas, risks, and next evidence steps. **Owns the contradiction-handling case.**
> *Demo Q: "What are the possible causes of unusual changes in Pandora's ocean water?"* → `INC-001`'s four hypotheses (mineral sediment, plankton bloom, chemical release, light reflection), presented unranked with the corpus's own caveat, cross-referenced to `WS-01`'s 2026-06-02 Awa Reef reading.

### ✅ 2 · Marine-Life Protection *(required)*
**Agent:** Marine-Life Protector · **Records:** `FAU-001…030`, `FLR-*`, `POL-002/006/007/008`, `REG-*`
Species, habitats, documented pressures, protection procedures — each species isolated to its own record.
> *Demo Q: "Which marine species are most vulnerable to water contamination?"* → `FAU-001` Tideglass Grazer (juveniles vulnerable to turbidity), `FAU-002` Ribbonfin Skimmer (sensitive to oil films), `FAU-018` Ventplume Shrimp — each cited to its own record, no cross-attribution.

### ✅ 3 · Emergency Response *(required)*
**Agent:** Emergency Responder · **Records:** `INC-*` immediate actions, `4.5` W1–W4, `12.11` command roles, `MED-*`, `A.1–A.3`, `POL-010`
Ordered, cited action cards with severity class, responder safety, command roles, and a public-communication draft.
> *Demo Q: "What immediate actions should guardians take after detecting coral damage?"* → `INC-002` Coral Break Field: close site, map fragments, identify continuing hazards, stabilize only with trained team — plus `KC-01` reef-restoration guidance and the `A.2` checklist.

### ✅ 4 · Research Assistant *(bonus)*
**Agent:** Investigator, `k=10` · **Records:** `14.1`, `14.2`, `14.3`, cross-chapter
Summarizes, compares documents, identifies patterns — **including the survey-effort normalization trap.**
> *Demo Q: "Summarize the major environmental threats mentioned across the uploaded reports."* → synthesis across all ten `INC-*` records grouped by risk level, every claim cited.

### ✅ 5 · Community Knowledge Assistant *(bonus)*
**Agent:** Marine-Life Protector / Investigator · **Records:** Chapter 11, `1.1` Ecological Principles, `POL-005`, `STL-*`
Traditional ecological knowledge, labelled `community tradition` and never conflated with measurement.
> *Demo Q: "What traditional community practices can support marine conservation?"* → `1.1` reciprocity/connectivity/precaution, `POL-002` breeding-season closure, `POL-009` waste return — with `POL-005` community data-consent noted.

### Suggested-question coverage

| # | Brief's suggested question | Covered by | Shown in demo |
|---|---|---|---|
| 1 | Possible causes of unusual ocean-water changes | UC1 | ✅ |
| 2 | Marine species most vulnerable to contamination | UC2 | ✅ |
| 3 | Immediate actions after coral damage | UC3 | ✅ **Demo Q1** |
| 4 | Compare water contamination vs underwater volcanic event | UC1+UC3 parallel | ✅ **Demo Q2** |
| 5 | Traditional practices supporting marine conservation | UC5 | ✅ |
| 6 | Summarize major threats across reports | UC4 | ✅ |
| 7 | Which areas need emergency attention first | UC3 (W1–W4 ranking) | ✅ |

Plus the corpus's own §15.1 test questions — *immediate steps for water colour change near Awa Reef*, *compare Reef Cut Infection and Marine Sting Reaction*, *safest accommodation for a traveller with limited mobility during storm season* — all verified working. **We test against the corpus's suggested questions as well as the brief's, because the graders wrote both.**

---

## 12. Scope

### In scope

| Area | Committed |
|---|---|
| Ingestion | PDF (primary) + TXT/CSV/DOCX; preloaded corpus; upload + delete |
| Chunking | Two-tier record-aware + narrative + table-row |
| Embeddings | `text-embedding-3-small`, batched |
| Vector store | Azure AI Search, HNSW, hybrid + semantic ranker |
| Retrieval | Query rewriting, metadata filters, RRF hybrid, rerank, scoring |
| Generation | `gpt-4o-mini`, closed-book, per-claim citations |
| Grounding | GroundingGate 8 rules, groundedness + confidence with reason |
| Uncertainty | Three states: Grounded / Contested / Insufficient |
| Agentic | Orchestrator + 3 fixed specialists, parallel compare, 1 retry, 8 s timeouts |
| Conflicts | Detection + side-by-side panel + reliability limitations |
| Severity | W1–W4 grounded classification |
| **Situation Report** | Six-section report contract (§2.1); independent per-section status; identical structure in single-agent and multi-agent modes |
| **Triage banner** | 🔴/🟠/🟢 with cited W1–W4 reason (Layer 3) |
| UI | Full theme, Command Center layout, streaming, inline citations, source cards, orchestration rail with orb↔section threads, reset |
| **Map visualization** | Stylized 10-zone Pandora map lit by priority; click-to-filter sources by region (Layer 6) |
| **Role toggle** | Guardian / Researcher / Citizen — re-render from frozen evidence, no re-query (Layer 6) |
| Docs | README, architecture diagram, this file |

### Out of scope

| Excluded | Reason |
|---|---|
| Voice input | Live-demo risk; no grounding benefit |
| Multilingual | Breaks verbatim citation fidelity |
| Image retrieval | No images in corpus |
| Map-based *retrieval* | Geospatial querying needs coordinates the corpus doesn't have — it has named regions. **Map *visualization* is in scope (Layer 6); map *retrieval* is not.** The map projects `region_id` metadata we already index; it never drives search. |
| Knowledge-graph database | 80% of benefit already via metadata cross-links |
| OCR / scanned PDFs | Corpus has a text layer |
| Real-time collaboration | Not in rubric |
| Full conversation memory | Last-turn coreference only |
| Fine-tuning | Impossible in window |
| Mobile-native app | Responsive web is sufficient |
| Comprehensive test suite | Manual verification against 10 fixed questions instead |

### Explicitly de-risked off the critical path

**A note on the stack.** Next.js + .NET/EF Core + Azure AI Foundry + Azure AI Search + Azure PostgreSQL + Supabase auth + Azure deployment is a lot of integration surface for five hours. It is a strong, defensible, production-shaped stack and we are keeping it — but two components are moved off the critical path so they can never block the demo:

| Component | Treatment |
|---|---|
| **Supabase auth** | Not on the critical path. Role selection ships as a **client-side role lens** (Guardian/Researcher/Citizen) — which is what the rubric actually rewards, and it needs no auth. Supabase is wired only if the build is green and ahead of schedule. A login wall between a judge and the demo is pure downside. |
| **Azure PostgreSQL** | Behind an `IKnowledgeRepository` interface with an **in-memory implementation as the default for the demo**. Postgres is the production target and will be wired if time permits, but a database outage or connection-string mistake must not be able to take down the app on stage. |
| **Azure deployment** | Deployed if green by T+4:30, but **the demo runs locally.** Conference Wi-Fi is a well-known way to lose a hackathon. GitHub repo is the deliverable; local is the demo. |

**Azure AI Search is the one hard external dependency,** because retrieval genuinely requires it. It is provisioned and verified in the first 30 minutes, before anything depends on it.

---

## 13. Innovation & Pitch Angle

### 13.1 Why this wins

**Every other team will build the same app.** Upload a PDF, split at 1000/200, embed into Chroma, retrieve `k=4`, generate, list sources in a grey box at the bottom. It will work. It will score ~65. And every one of them will look identical to the judges by the fourth demo.

We win on a different axis: **we read the corpus, and the corpus told us how it would be graded.**

| Their solution | Ours | Marks |
|---|---|---|
| Fixed 1000/200 splitting | Record-aware chunking on the corpus's own record boundaries | RAG **25** |
| Vector-only search | Hybrid + semantic rerank + query rewriting + metadata filters | RAG **25** |
| "Sources" list at the bottom | Inline per-claim citation chips that spotlight their source on hover | Accuracy **20** + UX **15** |
| "The cause was a plankton bloom" | *"No cause is confirmed — three records disagree, and `LAB-C`'s chain of custody is incomplete"* | **Accuracy 20** |
| Trust-me grounding | GroundingGate — the corpus's own 8 published rules, ticking green on screen | Accuracy **20** |
| Invented "priority: high" | W1–W4, cited to §4.5 | Real-world **20** |
| Wall of prose | Incident Action Card with command roles and a public-comms draft | Real-world **20** |
| Invisible pipeline | Live orchestration rail; two specialists igniting in parallel | Innovation **10** + UX **15** |
| Generic chat UI | Bioluminescent evidence console, accessible per the corpus's own §11.1 | UX **15** |

**The one-line pitch:** *Everyone else built a chatbot that answers questions about Pandora. We built an evidence system that knows when Pandora doesn't have the answer — and proves it, one citation at a time.*

### 13.2 Demo Script (3–5 minutes) — five visible wow-beats

**One incident, followed end to end.** Not a feature tour — a single guardian's situation, from "something is wrong" to "here is what we know, what we don't, and what to do." Every beat is something the judges *see*, not something we claim.

| Beat | Wow feature | Time |
|---|---|---|
| **1** — The incident is described | *(setup)* | 0:30 |
| **2** — 🔴 The map lights the zone | #4 Map + #3 Triage | 0:45 |
| **3** — Three agents assemble the report in parallel | #1 Visible agent assembly | 1:20 |
| **4** — Grounded answer, sources, confidence — **and the refusal** | #2 Honesty (the kill shot) | 2:05 |
| **5** — Role toggle, then the unanswerable question | #5 Role toggle + #2 Honesty | 3:25 |

---

**0:00 – 0:30 · The problem, made concrete.**
> "A guardian is standing on the shore at Awa Reef. The water has turned turquoise overnight and the fish are moving offshore. Everything they need is in Pandora's archive — an incident playbook on page 40, a water reading on page 47, three conflicting field notes on page 47, a species profile on page 12, a policy on page 46. Six records, thirty pages apart. They have minutes, not an afternoon."

---

#### ▸ BEAT 1 — the guardian describes it (0:30 – 0:45)

Typed in plain language, exactly as a guardian would say it — **not** a keyword query:

> *"The water near Awa Reef has turned turquoise and the fish are leaving the area."*

> "No keywords. No document names. Just what they can see."

---

#### ▸ BEAT 2 — 🔴 the map lights up (0:45 – 1:20)

**Before a single word of the answer is generated**, two things appear:

- The **triage banner** snaps to **🔴 W3 EMERGENCY** — *"fish avoidance and water discolouration with offshore movement"* — with the citation `[§4.5 Water Incident Classification, p.12]` visible on it.
- On the map, **`REG-01` Luminous Shelf ignites red**, ripple radiating outward.

> "Two things happened before the AI wrote anything. Priority, and place. And notice the priority isn't a label we invented — it's classified against **your** W1–W4 scale, on page 12, and it's cited like every other claim. A made-up 'priority: high' is just the model's opinion. This one is evidence."

---

#### ▸ BEAT 3 — three agents assemble the report, live (1:20 – 2:05)

Three orbs on the right rail **ignite simultaneously.** Three glowing threads run from the orbs to three sections of the report, and those sections begin filling **at the same time** — out of order.

> "Watch the report build itself. Three specialists, dispatched in parallel. The Marine-Life Protector is filling Affected Species. The Incident Investigator is on Likely Causes. The Emergency Responder is writing Recommended Actions. They're not taking turns — they each own a section of the same document."

Recommended Actions lands before Affected Species.

> "See how they finished out of order? That's how you know it's genuinely concurrent and not an animation. Three agents, about three seconds — the same wall-clock cost as one."

---

#### ▸ BEAT 4 — grounded answer, sources, confidence… and the refusal (2:05 – 3:25)

**First, the grounding.** Hover a citation chip in Recommended Actions — its source card ignites: verbatim excerpt, `INC-001`, page 40, 94% relevance, `Verified observation`.

> "Every sentence is anchored to a record ID. Hover any claim and you see the exact text it came from, on the exact page. Nothing here is the model's imagination."

**Then the kill shot.** Scroll to **Likely Causes**.

> "Now — here's the question every RAG system on this dataset gets wrong."

The section **refuses to name a cause.** The Conflicting Evidence panel shows three columns:

| `FN-A` | `FN-B` | `LAB-C` |
|---|---|---|
| Plankton bloom; began after 3 calm hot days; **no chemical odor** | Upstream pigment workshop maintenance; **damaged waste container** — entry into water *unconfirmed* | Harmless carbonates + moderate plankton — **chain-of-custody form incomplete** |
| `Disputed report` | `Disputed report` | `Disputed report` |

Confidence meter: *"**Moderate** — 3 sources, 1 unresolved conflict, chain of custody incomplete."*
Recommendation: documented resampling per checklist `A.1`.

> "Three records disagree. A normal RAG app picks the most confident-sounding one and tells you it was a plankton bloom. Ours won't — because the lab sample's chain of custody was never completed, and that single fact means nobody actually knows yet."

**Then open the judges' own corpus to page 48 and read aloud:**

> *"RAG evaluation expectation: an answer should present all three records, identify the incomplete chain of custody, avoid declaring a confirmed cause, and recommend additional properly documented sampling."*

Pause.

> "That's your corpus. Not our prompt. It specifies the expected behaviour — and our system matches it line for line, because we implemented all eight of your Retrieval Grounding Rules from section 15.2 as an actual validator. You can watch them pass, right here, on every single answer."

*(Point at the GroundingGate panel: 8/8 green.)*

---

#### ▸ BEAT 5 — role toggle, then the honest refusal (3:25 – 4:25)

**Flip the toggle: Guardian → Citizen.** The report re-renders instantly in plain language — the `KC-01` communication template, filled.

> "Same report. Same evidence. Same record IDs. Different audience."

**Flip again: → Researcher.** Measurements appear, survey-effort caveats, evidence-quality labels, methodology limits.

> "And critically — the citations didn't change. We re-render from the same frozen evidence set. If flipping this re-ran the search, the facts could shift between roles, and everything we just showed you about grounding would be worthless."

**Now ask something the corpus cannot answer** — e.g. *"What is the population of the Deepbell Singer in the Whispering Dunes?"* (wrong habitat, no such record).

The banner turns amber:

> **⚠ Insufficient Evidence — Recommend Field Investigation**
> *"The available Pandora knowledge base does not contain sufficient evidence to answer this question."*
> Searched: chapters 5, 14 · record types `fauna`, `monitoring` · closest match `SV-105` (Deep Current, 41%) — insufficient.
> To resolve: an acoustic survey record for this species in this region. See checklist `A.2`.

> "It would have been very easy to make something up here. Confident, fluent, completely wrong. In an environmental emergency, that gets someone hurt. So instead it tells you what it searched, what it found, and what evidence would actually answer the question."

---

**4:25 – 4:45 · Close.**

> "Retrieve evidence. Explain its reasoning. Acknowledge uncertainty. Help Pandora make better decisions. That's the Final Mission on page 8 of your brief — and it's the four things this system does on every single query."

---

#### Demo safety net

| Risk on stage | Mitigation |
|---|---|
| Network slow / API stalls | `DEMO_MODE` serves cached responses for all four demo questions — instant, deterministic, offline |
| A layer misbehaves | Flip its flag between beats; the report still renders (§10.3) |
| Total failure | Backup video (recorded at T+3:20 **and** T+4:45) |
| Running long | **Beats 1–4 alone are a complete, winning demo.** Beat 5's role toggle is the first thing cut; the unanswerable question is never cut — it's the close. |

### 13.3 Judge-question preparation

| Likely question | Answer |
|---|---|
| "Why not just fixed-size chunking?" | It would merge `FAU-014` into `FAU-015` — the exact failure §15.2 rule 3 prohibits. Show a side-by-side of both chunkings on the same query. |
| "How do you know it isn't hallucinating?" | GroundingGate — every factual sentence must resolve to a retrieved chunk or it's struck. Show the 8 checks and the audit trail. |
| "Isn't the agent layer overkill?" | It measurably improves compare-query retrieval. Toggle `AGENTIC_ENABLED` off live — the report still renders identically from one agent, but the compare answer is visibly thinner on one side. The architecture earns its place; it isn't load-bearing for correctness. |
| "What if the LLM ignores your instructions?" | It sometimes does — which is why validation is deterministic post-processing, not a prompt. |
| "Does it work on new documents?" | Yes — upload one live. Record-aware chunking degrades gracefully to narrative chunking on unstructured text. |

---

## 14. Submission Checklist

| # | Requirement | Deliverable | Owner gate |
|---|---|---|---|
| 1 | Working RAG application | Running app; local demo primary, Azure deploy if green | T+4:30 |
| 2 | GitHub repository | Public repo, clean history, `v1-baseline` and `v2-ui` tagged | Continuous |
| 3 | README with setup + usage | Prereqs, env vars, `dotnet run` + `npm run dev`, corpus seeding, 7 sample questions, troubleshooting | T+4:45 |
| 4 | Architecture diagram | Mermaid diagram in README: ingestion pipeline → index → orchestrator → 3 specialists → GroundingGate → UI | T+4:40 |
| 5 | Demonstration, 3+ questions | Coral damage · parallel compare · turquoise conflict · out-of-corpus refusal (**4 shown**) | Rehearsed T+4:45 |
| 6 | Evidence of retrieved sources | Source cards visible on every answer; `Citations` table persists the trail; screenshots in README | Built-in |
| 7 | 3–5 minute presentation | Narrative per §13.2, rehearsed twice against a timer | T+5:00 |
| 8 | **Disclosure of prebuilt components** | *(Rules requirement — do not skip.)* README section listing: Azure AI Foundry (`gpt-4o-mini`, `text-embedding-3-small`), Azure AI Search (HNSW + semantic ranker), Semantic Kernel, EF Core, Next.js, and the provided corpus. All application logic — chunker, retrieval pipeline, orchestrator, specialists, GroundingGate, conflict detection, UI — written during the event. | T+4:45 |
| 9 | **Backup demo video** | Full 4-minute screen recording. **Recorded at T+3:20 against `v3-honest`, re-recorded at T+4:45 against final.** Two videos means even a total Layer-5 failure still has a complete, honest demo on file. | T+3:20 |

---

## 15. Risks & Mitigations

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| 1 | **Agent loop runaway** | 🔴 Critical | Hard cap of **1 retry**, enforced by a counter in orchestrator state — **not** by prompt instruction (a prompt can be ignored; a counter cannot). Max **8 LLM calls/query**, enforced at the dispatcher. Agent count **fixed at 3** — no dynamic spawning. 25 s total budget with a hard return regardless of agent state. **No recursion anywhere**: the call graph is a fixed-depth tree by construction — orchestrator → specialists → done. An agent cannot dispatch another agent. |
| 2 | **Latency kills the demo** | 🔴 Critical | 8 s per-agent timeout, 25 s total. **Triage banner and map render before generation starts** (§3 step 3) — the screen has meaningful content in <500 ms, never a spinner. Sections stream individually as they complete. Three specialists run **concurrently**, so `sitrep` costs ~3 s wall clock, not ~9 s (§5.5). Demo questions pre-warmed; `DEMO_MODE` cache as the floor. |
| 3 | **.NET ⇄ Next.js integration burns time** | 🟠 High | Contract agreed and **frozen in the first 30 minutes** (a Layer 1 gate): `POST /api/query` (SSE), `POST /api/documents`, `GET /api/documents`, `DELETE /api/documents/{id}`. The SSE event schema is the §7.1 trace table — fixed up front, so new step types (`section.filling` etc.) are additive and never breaking. Frontend built against a **mock SSE stream** from minute 0, so UI and backend proceed in parallel and integration is a URL swap. CORS configured immediately, not debugged at T+4:00. |
| 4 | **Live demo failure** | 🔴 Critical | (a) Backup video recorded **twice** — T+3:20 against `v3-honest` and T+4:45 against final. (b) Demo runs **locally**, never on conference Wi-Fi. (c) `DEMO_MODE` serves cached responses for all four demo questions — instant, deterministic, zero API dependency. (d) Trace replay works offline. (e) **Ten feature flags** (§10.3) revert any unstable layer in seconds. (f) Five tagged commits — we can check out any earlier layer and demo it. |
| 5 | **Azure AI Search provisioning fails/slow** | 🟠 High | Provisioned and smoke-tested in the first 30 min, before dependent work starts. Fallback: in-memory cosine search over 220 vectors — trivially fast at this scale — behind the same `IRetriever` interface. Costs hybrid + reranker, keeps the app alive. |
| 6 | **Semantic ranker unavailable on tier** | 🟡 Medium | Fallback to LLM rerank: `gpt-4o-mini` scores 30 candidates in one batched call (~600 ms). Same interface, marginally slower, still a genuine rerank stage. |
| 7 | **PDF extraction mangles the corpus** | 🟠 High | The highest-impact silent failure. Mitigated by an explicit **T+1:15 verification gate**: 10 named records manually inspected for clean boundaries. Chunker falls back to narrative mode if record-ID detection finds fewer than 50 records. |
| 8 | **Model ignores citation format** | 🟡 Medium | Deterministic post-processing, not prompt trust: unparseable/unresolvable markers are stripped and the sentence marked unsupported. Low temperature (0.1) + few-shot citation examples in the system prompt. |
| 9 | **Conflict detection misfires** | 🟡 Medium | Structural signals first (`disputed report` label, multiple field notes on one event) — deterministic and reliable. Semantic check is confirmatory only. Both known conflicts hard-verified before demo. `CONFLICT_DETECTION` flag disables it if noisy. |
| 10 | **Over-abstention (refusing answerable questions)** | 🟡 Medium | Threshold `1.8/4.0` calibrated against all 7 brief questions + all 3 corpus §15.1 questions before freeze. Insufficient-evidence responses always show closest partial matches, so a false abstention still gives the judge something. |
| 11 | **Scope creep past T+4:45** | 🟠 High | Hard code freeze at T+4:45. Last 15 minutes are rehearsal only. Any incomplete feature is flag-disabled, not finished. |
| 12 | **Azure API rate limits / quota** | 🟡 Medium | Batched embeddings with backoff. Response cache keyed on normalized query — rehearsal runs cost nothing after the first. `DEMO_MODE` bypasses the API entirely. |
| 13 | **Supabase/Postgres integration eats the buffer** | 🟡 Medium | Both explicitly off the critical path (§12). In-memory repository is the demo default. Neither can block a deliverable. |
| 14 | **Layer bleed — a later layer breaks an earlier one** | 🔴 Critical | The failure mode the Bankable Build Order exists to prevent. Three independent defences: (a) **feature flag per layer**, wired *before* the layer is built so a half-finished layer defaults off; (b) **git tag per layer** — any earlier layer is one checkout away; (c) **runtime degradation ladder** (§5.5) — Layer 5 failing falls through to Layer 2's identical report structure. **Enforcement rule: no layer may modify code owned by an earlier layer.** Layer 5 adds an orchestrator that *calls* Layer 1's retriever and generator; it never edits them. |
| 15 | **Partial report reads as a bug** | 🟡 Medium | A blank section looks broken; a section that says *"🐋 Marine-Life Protector did not respond within 8 s — Affected Species unavailable"* looks rigorous. Every section has a **defined, visible empty state with a reason** (§2.1 rule 3). We rehearse the partial-report case deliberately so it can be narrated as designed behaviour rather than discovered live. |
| 16 | **Role toggle shifts citations** | 🟠 High | Would visibly destroy the grounding story mid-demo. Prevented structurally: the toggle is a **client-side re-render over the frozen `Citations` set** — it has no code path to retrieval (§8.6). Verified before freeze by flipping all three roles on the turquoise question and diffing the cited record IDs — they must be identical. |

---

## Appendix — Corpus Quick Reference

**Structure:** 15 chapters + Appendix A (4 field checklists) + Appendix B (20 knowledge cards). 56 pages.

**Regions:** `REG-01` Luminous Shelf · `REG-02` Emerald Canopy · `REG-03` Cloudspine Highlands · `REG-04` Silverreed Wetlands · `REG-05` Obsidian Reach · `REG-06` Whispering Dunes · `REG-07` Deep Current Expanse · `REG-08` Mistroot Basin · `REG-09` Aurora Mangroves · `REG-10` Sunfall Archipelago

**Incidents:**

| ID | Name | Region | Risk |
|---|---|---|---|
| `INC-001` | Turquoise Water Event | Luminous Shelf | HIGH |
| `INC-002` | Coral Break Field | Awa Reef | MEDIUM |
| `INC-003` | Wetland Fever Cluster | Silverreed Wetlands | HIGH |
| `INC-004` | Canopy Silence | Emerald Canopy | MEDIUM |
| `INC-005` | Vent Plume Release | Obsidian Reach | **CRITICAL** |
| `INC-006` | Oasis Drawdown | Whispering Dunes | HIGH |
| `INC-007` | Deepbell Stranding | Sunfall Archipelago | **CRITICAL** |
| `INC-008` | Terrace Collapse | Mistroot Basin | HIGH |
| `INC-009` | Mangrove Root Dieback | Aurora Mangroves | MEDIUM |
| `INC-010` | Visitor Waste Surge | Multiple sites | MEDIUM |

**Seasons:** Rising Waters · Clear Sky · Bloom Tide · Deep Current

**Evidence-quality taxonomy:** verified observation · community tradition · provisional interpretation · modeled estimate · disputed report

**Key cross-links to exploit in retrieval:**
- `INC-005` (yellow plume, dead shellfish, Obsidian Reach) ⟷ `WS-03` reading 2026-06-14 (34.2 °C, DO 3.8, yellow plume, shellfish closure) — **measurement corroborating an incident record**
- `INC-001` / `INC-002` (Awa Reef area) ⟷ `WS-01` 2026-06-02 (mild green tint, fewer grazers) ⟷ `FN-A` / `FN-B` / `LAB-C` ⟷ `SV-101` / `SV-102` (grazer counts) — **the dense evidence cluster where the demo lives**
- `FAU-003` Deepbell Singer (approach distance 300 m, ship noise & entanglement) ⟷ `INC-007` Deepbell Stranding — **species profile informing an incident response**

---

*End of SOLUTION.md — source of truth for Pandora Knowledge Guardian, Builderthon 2026.*

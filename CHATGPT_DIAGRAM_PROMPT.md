# ChatGPT prompts — generating the Pandora architecture diagram

Three prompts, for three different outputs. **Prompt A** is the one you probably want.

---

## Prompt A — polished architecture image (GPT-4o / GPT-5 image generation)

> Copy everything inside the block into ChatGPT.

```
Create a single high-resolution landscape architecture diagram (16:9, poster quality, flat vector
style — no 3D, no isometric, no gradients on shapes) for a RAG system called
"Pandora Knowledge Guardian — Guardian Command Center".

VISUAL STYLE
- Deep-ocean bioluminescent theme. Background #04121C. Boxes #0A2233 with 1.5px glowing borders and
  rounded corners.
- Border/accent colours carry meaning: cyan #3EE8D0 = user-facing + specialist agents,
  violet #7B6BF0 = orchestration, teal #1FA9A0 = retrieval + ingestion, amber #F0A93E = validation
  and honesty, coral #F0644E = emergency priority.
- Text: near-white #E8F6F5, clean geometric sans. Record IDs and code in monospace.
- Arrows: thin, glowing, with clear arrowheads. Solid = data/control flow. Dashed = live event
  streaming. Every arrow labelled.
- Calm and legible above all. This is an engineering diagram with atmosphere, not an art piece.
  No characters, no creatures, no photorealism, no Avatar movie imagery.

LAYOUT — five horizontal bands, top to bottom.

BAND 1 — CLIENT (cyan)
One wide rounded panel labelled "Next.js Command Center" split into three tiles:
  "Situation Report" · "Pandora Map + Triage Banner" · "Orchestration Rail (3 agent orbs)"

BAND 2 — GATEWAY (cyan)
One box: "FastAPI Backend Gateway — REST + Server-Sent Events".
Arrow down from Band 1 labelled "POST /api/v1/query".
Dashed arrow back up labelled "SSE trace events".
Small note beside it: "the browser never talks to anything else".

BAND 3 — ORCHESTRATION (violet)
Box labelled "⚙️ Orchestrator · gpt-4o-mini · temp 0" containing four stacked steps:
  "1 Rewrite & expand" → "2 Classify use case + severity W1–W4 (cited)" →
  "3 Route: sitrep | focused | compare" → "4 Validate & synthesise"
A coral arrow branches right from step 2 to a small coral box:
  "🔴 Triage banner + map zone — renders in under 500 ms, before any generation"

BAND 4 — PARALLEL WORK (the visual centrepiece)
Left: a teal box "Retrieval Pipeline" showing a horizontal chain:
  "metadata filter" → "BM25 k=30" and "vector k=30" (two parallel lanes) → "RRF fusion ~40"
  → "semantic rerank 0–4" → "top-6"
Right: THREE cyan boxes side by side, visually equal, all fed by simultaneous arrows from the
Orchestrator to show concurrency (label the arrow bundle "dispatched in parallel · 8 s timeout each"):
  "🐋 Marine-Life Protector → Affected Species"
  "🌊 Incident Investigator → Likely Causes + conflicts"
  "🚨 Emergency Responder → Recommended Actions"
Each specialist box has a thin two-way arrow to the Retrieval Pipeline.

BAND 5 — VALIDATION AND OUTPUT
An amber diamond/hexagon: "GroundingGate — 8 corpus rules". Three labelled arrows leave it:
  "pass" → down to the report
  "fail · 1 retry only" → a curved arrow back up to Retrieval
  "below threshold" → an amber box "⚠ Insufficient Evidence — Recommend Field Investigation"
Bottom centre: a tall cyan panel titled "THE SITUATION REPORT" listing six numbered rows:
  "1 Priority (W1–W4, cited)" · "2 Affected Species" · "3 Likely Causes" ·
  "4 Recommended Actions" · "5 Sources" · "6 Confidence (states its reason)"
Each of rows 2, 3, 4 has a small emoji badge (🐋 🌊 🚨) on its left edge, connected by a faint
glowing thread up to the matching specialist box in Band 4.
To the right of the report: a small violet box "Role toggle — Guardian / Researcher / Citizen ·
re-render only, never re-query".

RIGHT-HAND COLUMN — external services (draw as cylinders, vertically stacked, connected by dashed
lines to the components that use them):
  "Azure AI Search — 220 chunks, HNSW, hybrid + semantic ranker"
  "Azure AI Foundry — gpt-4o-mini · text-embedding-3-small"
  "PostgreSQL — reports · citations · trace · grounding audit"

Include a small legend box in a bottom corner explaining the five accent colours.
Spell every label exactly as written. Prioritise crisp, correct, readable text over decoration.
```

**If the text comes out garbled** (image models often mangle dense labels), send this follow-up:

```
Regenerate with roughly half the text: keep only the band titles, the three specialist names, the
six Situation Report rows, and the arrow labels. Drop all sub-labels and the legend. Increase font
size and spacing so every remaining word is sharply legible.
```

---

## Prompt B — editable diagram code (recommended for the README)

Use this when you want something you can version-control and edit, rather than a picture.

```
You are a systems architect. Produce a Mermaid `flowchart TB` diagram for a RAG application with
these components and flows. Output only the Mermaid code block — no commentary.

Client: Next.js Command Center (Situation Report, Pandora map, triage banner, orchestration rail).
Gateway: FastAPI backend — REST in, Server-Sent Events out. The browser talks only to this.
Agent service: FastAPI + LangChain, not publicly routable. Contains:
  - Orchestrator (gpt-4o-mini, temp 0): rewrites the query, classifies severity on a W1–W4 scale
    with a citation, routes to one of three modes — sitrep (3 agents parallel), focused (1),
    compare (2).
  - Retrieval pipeline: metadata pre-filter → BM25 k=30 + vector k=30 → RRF fusion → semantic
    rerank (0–4 scale) → top-6 (top-8 for compare).
  - Three fixed specialists dispatched in parallel, each owning one report section, 8 s timeout:
    Marine-Life Protector → Affected Species; Incident Investigator → Likely Causes;
    Emergency Responder → Recommended Actions.
  - GroundingGate: 8 validation rules. Pass → render. Fail → exactly one retry back to retrieval.
    Below relevance threshold 1.8/4.0 → "Insufficient Evidence — Recommend Field Investigation".
Output: a six-section Situation Report — Priority, Affected Species, Likely Causes, Recommended
Actions, Sources, Confidence — then a client-side role toggle that re-renders without re-querying.
External: Azure AI Search (HNSW, hybrid, semantic ranker), Azure AI Foundry (gpt-4o-mini,
text-embedding-3-small), PostgreSQL (reports, citations, trace).

Requirements: use subgraphs for orchestrator / retrieval / specialists / report. Label every edge.
Show the SSE trace as dashed edges to the orchestration rail. Apply a dark bioluminescent palette
via `style` lines: background #04121C, nodes #0A2233, strokes #3EE8D0 (client/agents),
#7B6BF0 (orchestration), #1FA9A0 (retrieval), #F0A93E (validation), #F0644E (emergency).
Quote every node label so special characters parse. Verify the syntax renders before answering.
```

---

## Prompt C — one-shot, using the source document

Fastest path if you can attach files. Upload `SOLUTION.md` (or paste §2.1, §4, §5, §7) and send:

```
Attached is the full solution design for a RAG system. Read it, then produce a single architecture
diagram covering: the ingestion pipeline (record-aware two-tier chunking → embeddings → vector
index), the query runtime (orchestrator → parallel specialists → GroundingGate → six-section
Situation Report), and the failure/degradation path. Give it to me as Mermaid I can paste into a
GitHub README, then a separate image-generation prompt I can use to render a poster version in a
dark bioluminescent deep-ocean style. Do not invent components that are not in the document.
```

---

## Notes

- **Prompt A** gives you a pitch-deck visual. **Prompt B** gives you the README diagram (item 4 on
  the §14 submission checklist). Do both — they serve different audiences.
- The submission checklist specifically asks for a **Mermaid diagram in the README**, so B (or the
  already-written `ARCHITECTURE_DIAGRAM.md`) is the deliverable; A is presentation polish.
- Image models mangle dense text. Always ask for a text-light second pass, and check every label
  before it goes on a slide — a diagram that says "GroundingGata" in front of judges is worse than
  no diagram.

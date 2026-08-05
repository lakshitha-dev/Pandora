# UI_SPEC.md — Functional UI Specification

**Pandora Knowledge Guardian** — what every screen must do and contain.

---

## ⚠️ Read this first: what this document is and isn't

**This spec describes function, not appearance.**

| This document decides | **Nipuna** decides |
|---|---|
| Which screens exist and what each is for | Colour palette |
| What content appears in each region | Typography and type scale |
| What the user can do on each screen | Spacing, sizing, and layout proportions |
| Every state a screen can be in | Component library and styling approach |
| What must never be hidden on mobile | Iconography and illustration |
| Required copy for trust-critical moments | Animation and micro-interaction |
| Accessibility requirements (functional) | Visual hierarchy and overall look |

Layout is described as **named regions** — "primary column", "side panel" — never as pixel
positions or grid specs. If a region should sit left or right, stack or float, that's a design
call. Where this spec says *"must be visible without scrolling"* or *"must not be behind a click"*,
that's a functional constraint on the experience, not a layout instruction.

**Nipuna: you own the look. Push back on anything here that fights good design.**

> **The brief asks for a visual theme "inspired by Pandora's oceans, bioluminescent environment,
> nature, and interconnected ecosystem," and 15 marks ride on it.** `SOLUTION.md` §8.2 proposes a
> direction — *"the abyss at night"*, with light used as **meaning** rather than decoration: things
> glow because they are active or because they are evidence. **That is a suggestion, including its
> palette.** Take it, improve it, or replace it. What this spec requires is that atmosphere never
> costs legibility.

---

## Site Map

Seven routes. Three public, four behind auth.

| Route | Access | Purpose | Priority |
|---|---|---|---|
| `/` | Public | Landing page — explain the product in 15 seconds | **High** — first thing judges see |
| `/login` | Public | Sign in | High |
| `/signup` | Public | Create account | High |
| `/app` | Authed | **Command Center — the core screen** | **Critical** |
| `/app/documents` | Authed | Knowledge base — the preloaded corpus, upload, monitor, delete | **Critical** |
| `/app/incidents` | Authed | Incident register — browse `INC-*` records by risk and region | Medium |
| `/app/investigations` | Authed | Past situation reports | Low — build only if time |

**Build order:** `/app` → `/app/documents` → `/login`/`/signup` → `/` → `/app/incidents` →
`/app/investigations`. The Command Center first, because everything else exists to serve it.

> **A demo account is pre-seeded.** Auth is real and the routes exist, but **nobody signs up on
> stage** — a login wall between a judge and the demo is pure downside. Build the auth pages
> properly, then never show them in the demo.

---

## App Shell

Everything under `/app/*` shares one persistent shell.

**Regions**

| Region | Contains | Behaviour |
|---|---|---|
| **Brand / home** | Product name, links to `/app` | Always visible |
| **Primary navigation** | Command Center · Knowledge · Incidents · Investigations | Current section clearly indicated |
| **Corpus status** | *"Pandora corpus indexed · 221 chunks · 130 records"* | Small, persistent. **It's the reassurance that retrieval is live** — and it's the fastest way to notice the index went down. |
| **Account** | User email, sign out | Can be collapsed into a menu |
| **Content area** | The current screen | — |

**Requirements**
- Navigation is reachable from every authenticated screen. A user must never be stranded.
- Unauthenticated access to any `/app/*` route redirects to `/login`, preserving the intended
  destination so sign-in returns the user there.
- If `corpus_indexed` is false, the shell says so prominently on every screen. Nothing else works.

---

## `/` — Landing Page

**Purpose:** a visitor (or judge) understands what this is, who it's for, and why it's different,
within about 15 seconds. Ends with a way in.

**Audience:** first-time visitors. Assume zero context about Pandora.

### Regions and content

| Region | Must contain |
|---|---|
| **Header** | Product name · link to Sign in · primary "Enter the Command Center" action |
| **Hero** | A one-line statement of what the product does, in plain language — not a tagline. A supporting sentence naming the audience (Pandora's guardians, researchers, and communities). Primary call to action. |
| **The problem** | Two or three sentences: when an incident happens, the answer exists but is scattered across incident playbooks, water readings, species profiles, and policies that never reference each other — and a guardian has minutes, not an afternoon. |
| **What it does** | Three items — **(1)** Describe a situation in plain language · **(2)** Get a structured Situation Report where every claim cites a real record · **(3)** It tells you what nobody knows yet, instead of guessing. **Item 3 is the differentiator and should read as the strongest of the three.** |
| **How it works** | Three steps: Describe what you see → Evidence is retrieved and validated → Read a cited report with its confidence and its gaps. |
| **Proof** | A realistic worked example — the turquoise-water question, a shortened report with a visible record-ID citation, and the *"no cause is confirmed — three records disagree"* moment. **Static content is fine.** This is the highest-value region on the page: it shows rather than claims. |
| **Closing call to action** | Repeat the primary action so the user needn't scroll back up |
| **Footer** | Team names, *Pandora Builderthon 2026*, GitHub link |

### States
Static page — no loading, empty, or error states.

### Notes
- No fabricated social proof. No fake testimonials, logos, or "trusted by" counts. Judges notice.
- If time is short, hero + what-it-does + proof + call to action is a complete landing page.
- **Do not oversell the AI.** The product's claim is *"it shows its evidence and admits its limits"* —
  a page promising an omniscient oracle undercuts the demo that follows.

---

## `/login` and `/signup` — Authentication

**Purpose:** get the user into the app with minimum friction.

### Regions and content

| Region | Must contain |
|---|---|
| **Form** | Email field, password field, submit. Both fields have associated labels. |
| **Switch** | Link to the opposite page ("Need an account?" / "Already have one?") |
| **Errors** | Inline, next to the relevant field where possible; a form-level message otherwise |

### States

| State | Behaviour |
|---|---|
| Idle | Submit enabled once both fields have content |
| Submitting | Submit disabled with a busy indication — **must be impossible to double-submit** |
| Invalid credentials | Clear message. Never reveal whether the email exists. |
| Network / server error | Distinguish from invalid credentials — "Couldn't reach the server, try again" |
| Success | Redirect to `/app`, or to the originally requested route if there was one |

### Notes
- Signup goes **straight to `/app`** — no email-confirmation wall, no onboarding tour. During a
  demo, every extra step is a step that can fail.
- **No empty-state problem here.** Unlike an upload-first product, `/app` works immediately because
  the corpus is preloaded. A brand-new user can ask a question one second after signing in.

---

## `/app` — Command Center ★ the core screen

**Purpose:** the guardian describes a situation and gets a grounded, cited **Situation Report**.
**This is the demo. It gets the most care.**

### Regions

| Region | Contains |
|---|---|
| **Question input** | Text input (multi-line capable), submit. Prominent — the screen's primary action. |
| **Triage banner** | Priority class with its cited reason. **Renders before generation completes.** |
| **Situation Report** | Six sections in fixed order, each badged with its owning agent |
| **Sources** | One card per cited chunk |
| **Confidence** | Level plus the reason for it |
| **Conflicting Evidence** | Contested positions side by side, when a conflict was detected |
| **Orchestration rail** | Live trace of the pipeline — agent orbs, step timeline, grounding checks |
| **Map** | Ten Pandora zones; affected ones lit by priority |
| **Role toggle** | Guardian / Researcher / Citizen, in the report header |
| **Reset** | "New Investigation" |

`SOLUTION.md` §8.4 proposes three columns — knowledge & map left, report centre, rail right — with
the rail collapsible and everything re-flowing on tablet and mobile. **Arrangement is Nipuna's call.**

### Content requirements

**Question input**
- Accepts a full sentence comfortably — guardians describe situations (*"the water near Awa Reef has
  turned turquoise and the fish are leaving"*), they don't type keywords.
- Submit on Enter; newline on Shift+Enter.
- Show 3–4 clickable example questions when empty. In a demo, nobody wants to invent a question on
  the spot. Use these (from the brief and the corpus's own §15.1):
  - *"The water near Awa Reef has turned turquoise and the fish are leaving the area."*
  - *"What immediate actions should guardians take after detecting coral damage?"*
  - *"Compare the recommended responses for water contamination and an underwater volcanic event."*
  - *"Which marine species are most vulnerable to water contamination?"*

**Triage banner**
- Full-width, directly above the report. **The first thing that renders** — priority is what a
  guardian needs in the first second, and it arrives from the `priority.classified` SSE event before
  any text is generated.
- **Always states its reason, and the reason is cited.** Not *"Priority: High"* but:
  > 🔴 **W3 EMERGENCY** — *fish avoidance and water discolouration with offshore movement* `[§4.5 Water Incident Classification, p.12]`
- **Never colour alone** — level, shape, and word always appear together (see Accessibility).

| Class | Label | Shape |
|---|---|---|
| `W4` | **REGIONAL CRISIS** | Octagon |
| `W3` | **EMERGENCY** | Octagon |
| `W2` | **ADVISORY** | Triangle |
| `W1` | **OBSERVATION** | Circle |
| `informational` | **INFORMATIONAL** | Circle |

**Situation Report — six sections, fixed order**

| # | Section | Owner | Backed by | If it cannot be filled |
|---|---|---|---|---|
| 1 | **Priority** | Orchestrator | `situation_report.priority` | 🟢 *"Informational — no incident indicators detected"* |
| 2 | **Affected Species** | 🐋 Marine-Life Protector | `sections[]` · `affected_species` · `marine_life_protector` | *"No species records matched this query"* — **never guessed** |
| 3 | **Likely Causes** | 🌊 Incident Investigator | `sections[]` · `likely_causes` · `incident_investigator` | *"Cause not established"* + conflict panel. **Never collapses to one cause.** |
| 4 | **Recommended Actions** | 🚨 Emergency Responder | `sections[]` · `recommended_actions` · `emergency_responder` | *"No documented protocol retrieved — recommend field investigation"* |
| 5 | **Sources** | Orchestrator | top-level `citations[]` | Always populated if anything was retrieved |
| 6 | **Confidence** | Orchestrator | `situation_report.confidence` | Always populated — including *"Insufficient"* |

> **Note the asymmetry:** only sections 2–4 are rows in the `sections[]` array. Priority, Sources, and
> Confidence are the orchestrator's own top-level fields (`docs/API_CONTRACT.md` §1.1). The screen
> still presents six sections in this fixed order — the data just arrives from two places.

Four rules govern the report, and all four are **functional requirements, not styling**:

1. **Sections are independent.** One section failing or timing out **never blanks the others**. A
   report with three of four content sections filled and the fourth honestly marked unavailable is a
   **successful** report — not an error state. Do not render a global error because one section failed.
2. **Every section is independently cited.** Claims carry their own record IDs; Sources is the union.
3. **Empty is a valid, visible state.** An unfilled section renders its `empty_reason`. A blank
   section looks like a bug; a section that says *"No species records matched"* looks like rigour.
4. **The report is the same object in every mode.** Single-agent (Layer 2) and three-agent parallel
   (Layer 5) produce the **identical** structure — only the fill mechanism differs. **This is what
   makes the degradation ladder invisible to a judge, so the renderer must not branch on
   `assembly_mode`.**

Each section shows its **owning agent's badge**. Sections render **the moment they arrive** — and
they will arrive **out of order**. That is the point: non-sequential completion is the proof the
agents were genuinely concurrent rather than scripted. **Do not buffer sections to display them in
order.**

**Citation chips**
- Markers are **record IDs in brackets** — `[INC-005]`, `[FAU-003 p.13]` — not integers.
- **Each is interactive.** Activating one draws attention to the matching source card and scrolls it
  into view with its excerpt highlighted. This is how a user verifies a claim, and the moment that
  proves the answer is grounded rather than invented — **treat it as a headline feature, not a
  footnote.**
- Must be **keyboard-reachable, not hover-only.** Hover is an enhancement; it cannot be the only way.
- A marker that doesn't resolve to a citation must render as **plain text, never a broken chip**.
- Sentences flagged unsupported by GroundingGate render **visibly struck through and labelled** —
  not hidden. Showing what was rejected is more credible than silently dropping it.
- Content inside a *Model inference* block must be **visually distinct from documented protocol**.
  Corpus §15.2 rule 8 requires the separation; the UI has to make it legible.

**Source cards** — one per entry in `citations[]`, each showing:
- Record ID and title — `INC-005 · Vent Plume Release`
- Document name
- Chapter / section
- **Page number**
- The verbatim excerpt, query terms highlighted
- Relevance score (`0.0`–`1.0`, presented however Nipuna judges readable)
- **Evidence-quality badge** — `Verified observation` · `Community tradition` ·
  `Provisional interpretation` · `Modeled estimate` · `Disputed report`
- Risk level chip where present — **word + shape, not colour alone**

Sources must be **visible on the same screen as the report**, not hidden behind a tab or accordion.
If a judge has to click to find the evidence, the grounding story is weakened.

> The evidence-quality badge is **mandated by the corpus itself** (page 2: RAG applications "should
> preserve these labels"). It is not decoration — it's what makes the confidence meter explainable
> and gives the conflict panel its vocabulary.

**Confidence meter**
- Level plus **the reason for it, in words** — never a bare number or an unexplained badge.
  > *"Moderate — 3 sources, 1 unresolved conflict, chain of custody incomplete"*
- **Not colour alone.** Pair any colour with the level word.
- Always present, including on the insufficient-evidence state.

**Conflicting Evidence panel** — when `conflicts[]` is non-empty:
- Each position in **its own column or row**: record ID, the claim, evidence-quality badge, and its
  **reliability limitation** (*"chain of custody incomplete"*, *"survey effort not normalized"*).
- Must **visually assert that no winner was picked.** Equal weight, no ordering that implies ranking.
- Show the resolution recommendation — what evidence would settle it.
- **This panel is the single highest-value thing on the screen.** It is the state the corpus was
  built to test and almost no other team will have it. It must not be collapsed by default, and it
  must be obvious at a glance that the system is *declining* to answer rather than failing to.

**Orchestration rail** *(Layer 5–6)*
- **Three specialist nodes**, always visible. Dormant = dim. Active = ignited with a live elapsed
  counter. Complete = steady with claim/source count. Timed out = a distinct "partial" treatment.
- **Parallel work must be unmistakable** — on a `sitrep` query, all three ignite **simultaneously**.
- **Orb ↔ section coupling** — each orb is visually tethered to the section it owns. When three
  sections fill at once, nobody needs the architecture explained. `SOLUTION.md` calls this the single
  most important visual in the product.
- **Step timeline** beneath the orbs, newest last, each with its duration.
- **GroundingGate panel** — eight rule rows that tick through as they pass. Watching a published
  eight-rule checklist validate in real time is a concrete credibility signal.
- **Replay** — after completion the trace stays; a scrub control replays it. **Critical for demo
  recovery:** if the live network stalls, we replay a cached trace instead of standing in silence.
- Timeouts and retries are shown with **equal prominence** to successes. A visible handled failure
  proves the timeout logic is real.

**Map panel** *(Layer 6)*
- Ten fixed zones for `REG-01` … `REG-10`, hand-placed once as inline SVG. **Not** a real
  geographic map — the corpus has named regions, no coordinates, and no map images.
- Idle: all zones dim. Active: zones in `affected_region_ids` light **in their triage colour**.
- Hover → zone name. Click → filters the Sources section to that region and dims non-matching cards.
- **Multi-zone lighting conveys spread** — which is precisely what separates W3 from W4.
- Empty state: *"No region identified in the available evidence."*
- The map is a **projection of `region_id` metadata already indexed**. It never drives retrieval.

**Role toggle** *(Layer 6)* — three-way control in the report header:

| Role | Register | Depth | Emphasis |
|---|---|---|---|
| **Guardian** *(default)* | Operational, imperative | Full protocol detail | Immediate actions, safety, command roles, next review time |
| **Researcher** | Technical, precise | Maximum — measurements, survey effort, evidence-quality labels, methodology caveats | Provenance, conflicts, chain of custody, what would resolve uncertainty |
| **Citizen** | Plain language, no jargon | Condensed | What it means for me, what to avoid, where to report, when the next update comes |

> **The hard rule: re-render, never re-query.** Flipping the toggle **must not** trigger a network
> call. It re-renders the *same frozen evidence set* — identical claims, identical record IDs,
> identical citations — in a different register.
>
> **This is a correctness requirement, not an optimization.** If flipping Guardian → Citizen re-ran
> retrieval, a judge would watch the cited evidence shift between roles and the grounding story would
> visibly collapse. Register, depth, and jargon change; **record IDs and claims never do.**

**Reset** — an explicit "New Investigation" control. Clears conversation, report, trace, map state,
and sources in one click.

### States

| State | Trigger | Required behaviour |
|---|---|---|
| **Ready** | Screen loads | Question input with example questions. **No empty state needed** — the corpus is preloaded, so the app is useful immediately. |
| **Classifying** | Question submitted | Report skeleton with six labelled empty slots. **The triage banner and map zone appear within ~500 ms**, before any text. The screen is never blank and never spinning. |
| **Assembling** | Specialists dispatched | Sections fill progressively **and out of order**, each badged. Orbs active. Input disabled to prevent double-submit. |
| **Complete** | All sections done, `has_sufficient_evidence: true` | Full report + sources + confidence + conflict panel if present |
| **Partial** | `was_partial: true` | **The report still renders.** Timed-out sections show their reason and which agent didn't respond. **This is a success state — never style it as an error.** |
| **Contested** | `conflicts[]` non-empty | Likely Causes explicitly declines to name a cause; conflict panel prominent; confidence Moderate with the conflict named as the reason |
| **Insufficient evidence** | `has_sufficient_evidence: false` | Amber banner *"⚠ Insufficient Evidence — Recommend Field Investigation"*, then the mandated sentence, then what was searched · closest sub-threshold matches (clearly labelled insufficient) · what would resolve it. **No sources section, no fabricated content. Must read as an honest limitation, not an error** — getting this tone right is a scoring moment. |
| **Corpus not indexed** | `422 corpus_not_indexed` | This *is* a real problem. Say plainly that the knowledge base isn't available and nothing can be answered. |
| **Service unavailable** | `502` / `504` | This *is* an error. Say so plainly and offer retry. **Keep any previous report on screen** — don't wipe the user's work. |
| **Stream dropped** | SSE connection lost | Fall back silently to the non-streaming response. The report arrives complete instead of progressively. Never show a raw connection error. |
| **Demo mode** | `DEMO_MODE` on | Cached responses for the demo questions, served instantly. Indistinguishable to a viewer. |

### Notes
- Previous question/report pairs may remain visible in the session, but conversation history is out
  of scope beyond last-turn coreference (see `docs/PROJECT.md`).
- The demo runs on this screen. It must survive a projector, a resized window, and someone clicking
  the wrong thing.

---

## `/app/documents` — Knowledge Base

**Purpose:** show what the system knows, and let a user add to it.

### Regions

| Region | Contains |
|---|---|
| **Corpus card** | The preloaded Pandora corpus, pinned first |
| **Upload** | Drop zone + file picker. States accepted formats and the size limit. |
| **List** | One row per uploaded document |

### Content requirements

**Corpus card** — pinned at the top, visually distinct from uploads:
- *"Pandora_RAG_Knowledge_2026.pdf — 56 pages · 130 records · 221 chunks · Indexed"*
- **Not deletable.** No delete control at all — not a disabled one, and never a confirm dialog that
  then fails with `403`. It's the demo; removing the affordance is the correct design.
- Worth surfacing the record-type breakdown (30 fauna · 20 flora · 10 incidents · …). It's concrete
  proof that record-aware chunking worked, which is a 25-mark differentiator made visible.

**Upload**
- Drag-and-drop **and** a click-to-browse fallback. Drag-and-drop alone fails on touch devices and
  for keyboard users.
- States accepted types (PDF, DOCX, CSV, TXT) and the **10 MB** limit *before* the user tries.
- Live ingestion progress: extract → chunk → embed → index.

**Document row**
- File name · type · size · upload time
- **Status:** Pending → Indexing → Indexed, or Failed
- Page count, chunk count, and **record count** once indexed — small proof that something real happened
- Chunking mode (`record_aware` / `narrative`). A `narrative` result on an arbitrary upload is
  **normal and correct**, not a failure — label it so nobody reads it as one.
- Delete action
- Failed rows show the error message

### States

| State | Behaviour |
|---|---|
| **Corpus only** | The normal state, and **not an empty state.** The system is fully usable. Copy should invite a question, not apologise for emptiness. |
| **Uploading** | Per-file progress. Other rows stay usable. |
| **Indexing** | The row updates **without the user refreshing**. Frontend polls `GET /api/v1/documents/{id}`. |
| **Indexed** | Ready-to-query indication, counts shown |
| **Failed** | Error message on the row. Other documents unaffected. Retry or delete available. |
| **Rejected upload** | Wrong type or too large — say which, **before** any upload begins |
| **Delete confirmation** | Deletion is irreversible and removes the document from future reports. Confirm first, and say that. |

### Notes
- Status must change **without a manual refresh**. A user who has to reload to see "Indexed" will
  assume it's broken.

---

## `/app/incidents` — Incident Register

**Purpose:** browse the corpus's ten documented incidents by risk and region. **A shortcut into the
Command Center, not a document reader.**

### Regions and content

| Region | Must contain |
|---|---|
| **Filter** | By risk level (Low / Medium / High / Critical) and by region |
| **List** | One row per `INC-*` record: record ID, title, region name, risk level, chapter, page, a short excerpt, evidence-quality badge |

- Risk level is **word + shape, not colour alone**.
- Selecting a row **pre-fills the Command Center question box** and navigates to `/app`. It does not
  open a detail reader — the report *is* the detail view.
- Backed by `GET /api/v1/incidents`, a projection of metadata already indexed. **No LLM call, no
  retrieval** — this screen is cheap by construction.

### States
Loading · list · filtered-to-empty (*"No incidents match these filters"*) · error.

### Notes
- **Cut this before `/app/documents` but after `/app/investigations`** if time runs short. It is the
  cheapest of the three secondary screens and it gives the map a natural companion, but the demo
  never depends on it.

---

## `/app/investigations` — Past Situation Reports *(build only if time)*

**Purpose:** revisit an earlier investigation without re-asking.

**Content:** list of past questions with timestamp, priority class, confidence level, citation count,
and whether a conflict was found or evidence was insufficient. Selecting one shows the full report
with its sources — and **replays its orchestration trace**, which is genuinely useful demo insurance.

**States:** empty (link to `/app`) · list · detail.

**Cut this first** if time is tight. It demos poorly compared with `/app`.

---

## Key Flows

### The demo path — situation to report
```
/app  →  type a situation in plain language  →  submit
   →  triage banner + map zone render (<500ms, before any text)
   →  three orbs ignite simultaneously
   →  sections fill out of order, each badged with its agent
   →  activate a citation chip  →  source card spotlights, excerpt highlighted, page visible
   →  read Likely Causes  →  it declines to name a cause
   →  conflict panel: FN-A / FN-B / LAB-C side by side, chain of custody flagged
   →  confidence: "Moderate — 3 sources, 1 unresolved conflict"
   →  flip role toggle  →  same report, same record IDs, different register
```
**This is the demo path. Rehearse it.** Beats 1–4 alone are a complete demo; the role toggle is the
first thing cut for time.

### The honest refusal — the closing beat
```
ask something the corpus cannot answer
   →  amber banner: "⚠ Insufficient Evidence — Recommend Field Investigation"
   →  the mandated sentence, verbatim
   →  what was searched · closest sub-threshold match, labelled insufficient
   →  what evidence would resolve it, citing an Appendix A checklist
```
**Never cut this.** It closes the pitch.

### First run — signup to first report
```
/signup  →  /app  →  corpus is already indexed  →  click an example question
         →  report assembles  →  done
```
**Note what's missing: there is no upload step.** The corpus is preloaded, so a new user reaches a
grounded, cited report in one click. Do not introduce a setup wall that doesn't need to exist.

### Document lifecycle
```
upload  →  validate type + size (client-side first)  →  202 accepted
   →  row appears as Pending  →  poll  →  Indexing  →  Indexed (+ chunk/record counts)
   →  document is now queryable alongside the corpus
   →  delete  →  confirm  →  removed from list and from future reports
```

---

## Responsive Behaviour

Design mobile-first. Judges may open this on a phone.

| Region | Desktop | Narrow screens |
|---|---|---|
| App navigation | Persistent | Collapsible — **corpus status must remain reachable** |
| Report + sources | Side by side or stacked, designer's call | Stacked, report first, sources directly beneath |
| Citation chips | Hover or click | **Click/tap — hover does not exist on touch.** A hover-only citation is broken on mobile. |
| Orchestration rail | Persistent side panel | Bottom sheet or expandable summary strip — **but the three agent states must stay visible**, since that's the innovation story |
| Map | Panel | Collapsible card, or a zone chip row. Lit zones must remain identifiable. |
| Conflict panel | Side-by-side columns | Stacked cards — **but equal visual weight must survive.** Stacking must not imply the first position is the answer. |
| Role toggle | Segmented control | Full width, comfortably tappable |
| Triage banner | Full width | Full width — **never collapsed or truncated.** It's the first thing a guardian needs. |
| Landing page | Multi-column allowed | Single column |

**Nothing is hidden on mobile — it re-flows.** If content isn't important enough for a phone, ask
whether it belongs on desktop either.

---

## State Catalogue

Every state that must exist somewhere. Missing states are how a demo breaks live.

| Type | Where | Required |
|---|---|---|
| **Loading** | Classifying · Assembling · Upload · Indexing · Any list fetch | Visible progress; no frozen screens |
| **Progressive** | Report sections arriving one at a time, **out of order** | Each renders on arrival; never buffered into order |
| **Empty (valid)** | A section with no matching records · map with no region · filtered-to-empty lists | **Renders its reason.** Never a blank box. |
| **Partial** | `was_partial: true` — a section timed out | Report still renders; the failed section names its agent and reason. **A success state.** |
| **Contested** | Records disagree | All positions shown; no winner picked; confidence names the conflict |
| **Honest limitation** | `has_sufficient_evidence: false` | **Not styled as an error** — this is the system being trustworthy |
| **Error** | Auth failure · Upload rejected · Ingest failed · 502/504 · corpus not indexed | States what happened and what to do next |
| **Success** | Upload complete · Document deleted | Brief confirmation; doesn't block the next action |

**The three that most teams get wrong, and where our marks are:** *Empty (valid)*, *Partial*, and
*Honest limitation*. All three must look like **rigour**, not breakage.

---

## Accessibility Requirements

Functional, not visual. Non-negotiable.

> **The corpus specifies this itself**, in §11.1: *"Do not use color alone for hazard levels; pair it
> with words and shapes."* Following the graders' own communication guidance is both correct and a
> rubric point.

- **Colour is never the only signal.** Triage class, risk level, evidence quality, document status,
  section status, and confidence each pair colour with text **and**, for hazard levels, shape.
- Every interactive element is **keyboard reachable** with a visible focus indicator.
- **Citation chips are keyboard-activatable.** Hover-only is a failure — it excludes keyboard and
  touch users both.
- Real semantics: `<button>` for actions, `<a>` for navigation. Never a click handler on a `<div>`.
- Every form field has an associated `<label>`.
- **The report region announces when new content arrives** via an ARIA live region, so screen-reader
  users know a section landed. With sections streaming in out of order this matters more than usual —
  announce *which* section arrived, not just that something changed.
- `prefers-reduced-motion` disables background drift, orb breathing, and ripples. Any animation that
  conveys information (a section filling, a zone lighting) must remain comprehensible without motion.
- Meaningful `alt` text on informative images; empty `alt` on decorative ones. The map needs a text
  equivalent listing the lit regions.
- Logical focus order — tab through each screen and check it makes sense.

---

## Microcopy That Matters

Four moments where the exact words carry the product's trustworthiness. Nipuna may reword the
others — but **the mandated sentence is not reworded.**

**1 · Insufficient evidence — the mandated sentence.** The brief requires this wording. The backend
supplies it in `insufficient_evidence.message`; render it **verbatim** as the body's first line:

> "The available Pandora knowledge base does not contain sufficient evidence to answer this question."

Above it, the actionable headline:

> ⚠ **Insufficient Evidence — Recommend Field Investigation**

Never "No results found." Never an error toast. **The system explaining its own limits is the
feature.** Follow with what was searched, the closest sub-threshold matches labelled as insufficient,
and what evidence would resolve it — a refusal that turns into a next step.

**2 · No confirmed cause** — must be unambiguous that the system is *declining*, not *failing*:

> "No cause is established. Three records make incompatible claims about this event and the corpus
> does not resolve them."

Not "Unable to determine cause." Not "Error analysing causes." The system knows exactly what it
knows; it is refusing to overstate it.

**3 · A section that timed out** — must read as designed behaviour:

> "🐋 Marine-Life Protector did not respond within 8 s — Affected Species unavailable for this report."

Not "Something went wrong." A blank section looks broken; a named agent and a stated timeout looks
rigorous.

**4 · Role toggle** — must make the grounding guarantee explicit:

> "Same evidence. Same record IDs. Three audiences."

---

## Open Items

| Item | Owner | Note |
|---|---|---|
| Final palette and type scale | Nipuna | `SOLUTION.md` §8.2 is a starting point, not a mandate |
| Map zone shapes and placement | Nipuna | Ten stylized zones, hand-placed once. Aesthetic, not cartographic. |
| Orb ↔ section tether treatment | Nipuna | The single most important visual in the product — worth the time |
| Product wordmark | All | — |
| Worked example on the landing page | Nipuna + Lakshitha | Use a **real** report from the corpus, not invented copy |
| Whether `/app/investigations` ships | All | Decide at the T+4:10 check — cut first |

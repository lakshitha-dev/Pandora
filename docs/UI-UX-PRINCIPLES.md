# UI/UX Principles — Pandora Knowledge Guardian

> Companion to [`SOLUTION.md`](../SOLUTION.md). Where SOLUTION.md specifies *what*
> the Guardian Command Center is, this document states *why each interface
> decision is the way it is* — and records the measurements behind the claims.
>
> **Target:** User Interface and Experience (15 marks) + Best UI/UX Design Award.

---

## Contents

| § | Section |
|---|---|
| 1 | [Sample files](#1-sample-files) |
| 2 | [Contrast audit — including one failure found](#2-contrast-audit) |
| 3 | [The ten principles](#3-the-ten-principles) |
| 4 | [What changed from `theme-1-abyss-bioluminescent.html`](#4-what-changed-from-the-first-mockup) |
| 5 | [Accessibility ledger](#5-accessibility-ledger) |
| 6 | [Motion budget](#6-motion-budget) |
| 7 | [Rubric mapping](#7-rubric-mapping) |
| 8 | [Open decisions](#8-open-decisions) |

---

## 1. Sample files

Standalone HTML — no build step, no dependencies, no network. Open
[`ui/index.html`](../ui/index.html) for a navigable gallery, or any file directly.

| File | Purpose |
|---|---|
| [`ui/pandora.css`](../ui/pandora.css) | **Single source of truth** for tokens and components. Cascade layers, `color-mix()` tinting, container queries, fluid `clamp()` type, logical properties. |
| [`ui/index.html`](../ui/index.html) | Gallery — every screen from one page. |
| [`ui/01-design-system.html`](../ui/01-design-system.html) | Token reference and principle ledger. Every colour pairing carries a measured contrast ratio. Component and state gallery. |
| [`ui/02-command-center.html`](../ui/02-command-center.html) | The primary screen. Implements §8.4 three-column layout, §2.1 six-section SITREP, §7.2 orchestration rail, §8.5 map panel, §8.6 role toggle. |
| [`ui/03-answer-states.html`](../ui/03-answer-states.html) | The three honest states from §4.6 — Grounded, Contested, Insufficient — including the banner/body split. |
| [`ui/04-lifecycle.html`](../ui/04-lifecycle.html) | First run, ingestion progress, mid-flight assembly with skeletons, and agent timeout → valid partial report (§2.1 rule 1). |
| [`ui/05-role-views.html`](../ui/05-role-views.html) | Guardian / Researcher / Citizen rendered side by side from one frozen evidence set (§8.6). |
| [`ui/06-compare-mode.html`](../ui/06-compare-mode.html) | INC-001 vs INC-005 aligned field by field, with the decomposition trace (§5.4 `compare` routing). |

### Why a shared stylesheet

Files 01–03 were first written with three inline copies of the token block. That is
how the violet drift happened in the first place — a value corrected in one file and
missed in another. `pandora.css` makes the token set single-sourced, so a hue change
propagates everywhere. `color-mix()` does the heavy lifting: one hue token yields
its whole family of fill, border and glow tints, which removed roughly forty
hand-written `rgba()` values and the drift risk that came with them.

Files 01–03 remain self-contained by design — they document the system and should
survive being opened in isolation. Files 04–06 and the index consume the shared
sheet.

**All content in these files is real.** Every record ID, page number, excerpt and
measurement is drawn from `Pandora_RAG_Knowledge_2026.pdf` as actually ingested by
the pipeline in `src/lib/corpus/` — 188 chunks across 15 chapters, verified by
`npx tsx scripts/inspect-chunks.ts`. Nothing is invented placeholder text, because
a mockup citing a record that does not exist teaches the wrong thing about what
the system can do.

---

## 2. Contrast audit

SOLUTION.md §8.3 claims *"All text ≥ 4.5:1 contrast on the dark base."* We measured
every token pair using the WCAG 2.1 relative-luminance formula against
`--deep #0A2233`, the panel surface that all body text actually sits on.

| Token | Hex | Ratio on `#0A2233` | Verdict |
|---|---|---|---|
| Foam (primary text) | `#E8F6F5` | **15.70:1** | AAA ✓ |
| Lume (verified) | `#A8F5C8` | **13.90:1** | AAA ✓ |
| Bioluminescent cyan | `#3EE8D0` | **10.59:1** | AAA ✓ |
| Warning amber | `#F0A93E` | **8.10:1** | AAA ✓ |
| Mist (secondary text) | `#8FAFB8` | **6.97:1** | AA ✓ |
| Reef teal | `#1FA9A0` | **5.61:1** | AA ✓ |
| Coral alert | `#F0644E` | **5.15:1** | AA ✓ |
| ~~Spirit violet~~ | ~~`#7B6BF0`~~ | **4.04:1** | ✗ **FAILS AA** |
| Spirit violet (corrected) | `#9A8DF5` | **5.82:1** | AA ✓ |

### The one failure, and why it mattered

Spirit violet is the agentic-accent colour. It lands on the Orchestrator badge,
agent labels in the rail, and the withheld-sources notice — all of which carry
information a user needs to read. At 4.04:1 it sat below the 4.5:1 floor for body
text.

`#9A8DF5` is visually near-identical, preserves the violet's role as the "human /
agentic" hue, and clears AA at 5.82:1. The corrected value is used in
`02-command-center.html` and `03-answer-states.html`.

### A second-tier token was added deliberately

Metadata — page locators, chunk counts, relevance scores — needs to recede without
becoming unreadable. Mist at 6.97:1 is heavier than that role wants, so
`--mist-dim #6E8E9C` (**4.72:1**) was introduced as the floor. Nothing in the
system goes below it. The first mockup's tertiary ink was `#4d7385` at **3.66:1**,
and it was carrying relevance scores and page numbers — exactly the values a
sceptical judge leans in to read.

---

## 3. The ten principles

### 1. Make the retrieval visible

Three columns put knowledge base, situation report, and orchestration on screen at
once. The rail streams what actually ran: decompose → hybrid search → dedupe →
rerank → cluster fill → ground → validate.

**Why.** The product claim is "grounded, not guessed," and the rules state a
chatbot without retrieval does not qualify. A single answer bubble is
indistinguishable from a plain chatbot. Visible provenance is the interface's core
job, not a debug affordance.

### 2. Never encode state in colour alone

Every severity indicator pairs **glyph + word + colour**. W2 is an amber triangle
labelled ADVISORY; W3 is a coral octagon labelled EMERGENCY. Legible in greyscale,
to a colour-blind viewer, and through a washed-out projector.

**Why.** This is not a generic accessibility nicety — the corpus mandates it.
§11.1: *"Do not use color alone for hazard levels; pair it with words and shapes."*
The knowledge base we serve states the rule, so the interface obeys it. That is a
precise detail worth one sentence in the pitch.

### 3. Uncertainty is a designed state, not an error

Three honest states, not one. Insufficient gets a composed screen: actionable
banner, the brief's mandated sentence verbatim, what was searched, the closest
matches with scores against the threshold, and what evidence would resolve it.
Styled amber, never coral.

**Why.** Requirement 6 demands explicit uncertainty handling and 20 marks ride on
grounded accuracy. A system that looks embarrassed when it refuses teaches the
user to distrust the refusal — which is the one output most worth trusting.

### 4. Separate documented protocol from inference — structurally

Two visually distinct regions, not a prose heading. Protocol carries a solid lume
left rule and a record ID; inference carries a dashed amber rule and says
*"Model inference — verify before acting."* Evidence-quality chips label each
source with the corpus's own five grades.

**Why.** §15.2 requires it: *"For recommendations, separate documented protocol
from model-generated inference."* Chapter 1 defines the five grades and asks that
RAG applications preserve the labels, so they are chunk metadata rather than
adjectives in prose.

### 5. Bind every claim to a reachable source

Citation chips are baseline-aligned (not superscript), 38px wide showing the
record ID itself, with an invisible 44px hit target. Hover or focus highlights the
matching source card; click scrolls it into view and holds the highlight.

**Why.** Chips showing `INC-001` rather than `1` mean the citation is legible
without cross-referencing. Superscript chips at 10px violate Fitts's law and
perturb line-height. An oversized invisible target keeps the prose calm and the
chip easy to hit — on a trackpad, on stage, under pressure.

### 6. Progressive disclosure over dense dumps

Report first, then sources, then raw chunks behind a control. The knowledge panel
shows corpus *structure* — 188 chunks, 135 records, 15 chapters, and the 958
hoisted boilerplate sentences — not a wall of filenames.

**Why.** A judge has three to five minutes. Showing everything at once means
nothing is read. The depth must exist for the sceptic and stay out of the way for
everyone else.

### 7. Respect the reading measure

Report prose is capped at `68ch` regardless of viewport width.

**Why.** 45–75 characters per line is the long-established readability band. The
first mockup's centre column ran past 90ch at 1400px. The answer *is* the product;
it has to be pleasant to read, and comfortable prose reads as competent prose.

### 8. Theme through restraint

Bioluminescence is carried by three cheap effects: two drifting radial light
shafts, twelve rising plankton particles, and glow confined to interactive or
verified elements. Animation pauses on hidden tab and stops under
`prefers-reduced-motion`.

**Why.** The first mockup ran 26 particles plus two 60vw `blur(90px)` gradients
compositing continuously. Comfortable on a dev laptop, risky on unknown projector
hardware. Dropped frames during the demo cost more than the extra particles earn.

### 9. Keyboard and screen reader are first-class

Skip link is the first tab stop. All controls reach 44px minimum (36px for
tertiary tools). The orchestration trace is `role="log" aria-live="polite"` so
progress is announced. Role and filter groups carry real `aria-pressed`. Focus
ring is 2px cyan at 2px offset, never removed.

**Why.** The corpus asks for symbols and audio for people with limited literacy,
and for confirmed understanding of emergency messages. A tool for emergency
response that only works with a mouse and working eyes contradicts its own
content.

### 10. Every control must change something real

The role toggle applies an access-class filter per POL-005. A Citizen asking for
clinical dosing gets a withheld-source notice naming what was withheld and why —
not a silently identical answer.

**Why.** A decorative control is worse than a missing one. A judge who clicks a
persona, sees no change, and concludes it is theatre will discount everything else
on screen, including the parts that are real.

> **One caveat on the role toggle, per §8.6.** It re-renders from the frozen
> evidence set — it must never re-query. If flipping Guardian → Citizen re-ran
> retrieval, the cited evidence could shift between roles and a judge would watch
> the facts change on screen. Register and depth change; record IDs never do.
> Note that this sits in tension with the access-class filter, which *does* change
> the retrievable set — so clearance is resolved **at query time from the active
> role**, and the toggle then re-renders within that clearance. Changing clearance
> is an explicit re-query, and the UI says so.

---

## 4. What changed from the first mockup

`theme-1-abyss-bioluminescent.html` was a strong starting point. Its three-column
layout, citation↔source spotlight, pipeline stepper, and treatment of
insufficient-evidence as a full screen were all correct and are preserved.

Eight changes were made:

| # | Change | Reason |
|---|---|---|
| 1 | Tertiary ink `#4d7385` → `#7c9caf`, then aligned to the SOLUTION.md palette with `--mist-dim` at 4.72:1 | 3.66:1 failed AA while carrying scores and page numbers |
| 2 | Severity gained a glyph and a word | Corpus §11.1 forbids colour-only hazard encoding |
| 3 | All Avatar film terms replaced with real corpus records | `ilu`, `Tsahìk`, `Metkayina`, `Kelutral inlet` cannot be grounded by retrieval — every citation would have been fake. The corpus is explicitly original and carries a notice that it is not an Avatar guide |
| 4 | Added the contradiction panel | §14.3 plants FN-A / FN-B / LAB-C and publishes the expected behaviour. It was the single largest missing scoring opportunity |
| 5 | Protocol vs inference made structural | §15.2 asks for the separation; a prose heading is not a separation |
| 6 | Citation chips: baseline-aligned, 38px, record ID visible, 44px hit area | Fitts's law; 10px superscript also shifted line-height |
| 7 | Prose capped at 68ch | Centre column exceeded 90ch at wide viewports |
| 8 | Particles 26 → 12, blur 90px → 70px, pause on hidden tab | Projector-safety; continuous GPU compositing risks frame drops mid-demo |

Restructured to the SOLUTION.md spec: the six-section SITREP with per-section
agent ownership, the triage banner above the report, the orchestration rail with
three orbs and the eight-rule GroundingGate panel, the ten-zone map, and the role
toggle in the report header.

---

## 5. Accessibility ledger

| Requirement | Implementation | Verified |
|---|---|---|
| Text contrast ≥ 4.5:1 | All nine tokens measured; violet corrected | ✓ measured, §2 |
| Non-text contrast ≥ 3:1 | Focus ring 13.9:1; borders and bars above 3:1 | ✓ |
| No colour-only meaning | Severity = glyph + word + colour; scores show the number beside the bar | ✓ |
| Keyboard reachable | Skip link first; all interactive elements tabbable; citation chips respond to Enter and Space | ✓ |
| Visible focus | 2px cyan, 2px offset, never removed | ✓ |
| Target size | 44px primary, 36px tertiary; citation chips 38×19px visual with 44px hit area | ✓ |
| Live regions | Orchestration trace `role="log" aria-live="polite"`; triage banner `role="status"` | ✓ |
| Reduced motion | Drift, breathing and particles disabled; transitions collapse to 1ms | ✓ |
| Landmarks and names | `<header>`, `<main>`, `<section aria-labelledby>` throughout; decorative SVG `aria-hidden` | ✓ |
| Meaningful alt text | Map carries a description of its current lit state, not just "map" | ✓ |
| No horizontal page scroll | Wide content scrolls inside its own container | ✓ |

**Not yet done.** No screen-reader pass with NVDA or VoiceOver — the markup is
correct by construction but unverified against a real assistive technology. Worth
saying plainly rather than claiming coverage we have not tested.

---

## 6. Motion budget

| Effect | Duration | Notes |
|---|---|---|
| Feedback (hover, chip highlight) | 150ms | Below the ~200ms threshold where interaction feels indirect |
| Transition (card state, section fill) | 240ms | |
| Ambient drift | 32s, 2 layers, `blur(70px)` | `will-change: transform`, paused when tab hidden |
| Plankton | 20–40s each, 12 particles | Paused when tab hidden |
| Agent orb breathing | 2.4s ease-in-out | Only while an agent is active |
| Zone pulse (W3/W4 only) | 2.6s | W2 and idle are steady — pulsing is reserved for genuine emergency |

Single easing curve throughout: `cubic-bezier(.4, 0, .2, 1)`. Nothing bounces,
nothing spins, nothing above 300ms — anything slower reads as lag during a live
demo rather than as polish.

**One deliberate motion choice worth calling out.** The three agent orbs ignite
*simultaneously* and their sections complete *out of order* — Marine-Life at 2.6s,
Emergency Responder at 2.9s, Investigator at 3.4s. Out-of-order completion is the
visual proof that the work was genuinely concurrent rather than a scripted
sequence. A staged animation that always completes top-to-bottom would look
choreographed, and a judge would be right to suspect it.

---

## 7. Rubric mapping

The UI/UX category is 15 marks, but interface decisions carry weight in three
others.

| Rubric criterion | Marks | What the interface contributes |
|---|---|---|
| User Interface and Experience | **15** | Three-column command centre; clear/reset; upload zone; question area; report; persistent sources; Pandora theme via depth ramp and restrained bioluminescence |
| Accuracy and Grounded Responses | 20 | Citation chips bound to reachable sources; evidence-quality chips; contradiction panel; three honest states; confidence that states its reason |
| Real-World Problem Solving | 20 | SITREP format is executable by an incident lead — priority class, species list, ranked hypotheses, ordered actions, public-alert draft from the corpus's own KC-01 template |
| Innovation | 10 | Visible agent assembly with per-section ownership; GroundingGate's eight published rules ticking in real time; map as a projection of `region_id` metadata already indexed |

**The strategic point.** Retrieval plus grounded accuracy is 45 marks; UI/UX is
15 and Innovation 10. A design where the visually striking parts *are* the
correctness parts scores in every column instead of trading between them. The
contradiction panel is simultaneously the most distinctive thing on screen and the
mechanism that satisfies §15.2 rule 7. That is not a coincidence — it is the
design constraint.

---

## 8. Open decisions

Flagged rather than silently resolved:

1. **Orb-to-section threads.** §7.2 calls the bioluminescent thread from orb to
   owned section *"the single most important visual in the product."* The samples
   implement the coupling through agent-coloured section borders plus a matching
   orb ring and an explicit `↳ Affected Species` label. Literal cross-column SVG
   threads depend on runtime layout and break at narrow widths; they are
   achievable in the React build with a resize observer, and they are the right
   thing to add there. The static samples deliberately use the robust version.

2. **Map zone shapes** are hand-placed stylised blobs. The corpus contains no
   geography beyond region descriptions, so any arrangement is invented. Current
   placement groups coastal regions toward the lower left and highlands upper
   right, which is defensible but arbitrary — worth one deliberate pass if time
   allows.

3. **Role toggle vs access clearance** interact, as noted in principle 10.
   Resolved as: clearance is bound at query time, the toggle re-renders within it,
   and changing clearance is an explicit re-query the UI announces. This is the
   only place where the "never re-query" rule bends, and it bends for a stated
   reason.

4. **Screen-reader verification** is outstanding (§5).

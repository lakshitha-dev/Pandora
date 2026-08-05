# UI_SPEC.md — Functional UI Specification

**SME Business Intelligence Assistant** — what every screen must do and contain.

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

---

## Site Map

Seven routes. Three public, four behind auth.

| Route | Access | Purpose | Priority |
|---|---|---|---|
| `/` | Public | Landing page — explain the product in 15 seconds | **High** — first thing judges see |
| `/login` | Public | Sign in | High |
| `/signup` | Public | Create account | High |
| `/app` | Authed | **Ask workspace — the core screen** | **Critical** |
| `/app/documents` | Authed | Document library — upload, monitor, delete | **Critical** |
| `/app/actions` | Authed | Agent action inbox — review and approve | **Critical** |
| `/app/history` | Authed | Past questions and answers | Low — build only if time |

**Build order:** `/app` → `/app/documents` → `/app/actions` → `/login`/`/signup` → `/` → `/app/history`.
The workspace first, because everything else exists to serve it. The landing page late, because
it's the easiest to produce quickly and the least likely to break.

---

## App Shell

Everything under `/app/*` shares one persistent shell.

**Regions**

| Region | Contains | Behaviour |
|---|---|---|
| **Brand / home** | Product name, links to `/app` | Always visible |
| **Primary navigation** | Ask · Documents · Actions · History | Current section clearly indicated. **Actions carries a count badge when items are pending** — that's how users discover the agent did something. |
| **Account** | User email, sign out | Can be collapsed into a menu |
| **Content area** | The current screen | — |

**Requirements**
- Navigation is reachable from every authenticated screen. A user must never be stranded.
- The pending-action count updates after any approve/reject without a full page reload.
- Unauthenticated access to any `/app/*` route redirects to `/login`, preserving the intended
  destination so sign-in returns the user there.

---

## `/` — Landing Page

**Purpose:** a visitor (or judge) understands what this is, who it's for, and why it's different,
within about 15 seconds. Ends with a way in.

**Audience:** first-time visitors. Assume zero context.

### Regions and content

| Region | Must contain |
|---|---|
| **Header** | Product name · link to Sign in · primary "Get started" action |
| **Hero** | A one-line statement of what the product does, in plain language — not a tagline. A supporting sentence naming the audience (small and medium businesses). Primary call to action. |
| **The problem** | Two or three sentences: business answers are buried across invoices, contracts, and reports, and finding them means opening files one at a time. |
| **What it does** | Three items — **(1)** Ask questions in plain language · **(2)** Every answer cites its source documents · **(3)** The assistant proposes the action that follows, and you approve it. Item 3 is the differentiator and should read as the strongest of the three. |
| **How it works** | Three steps: Upload your documents → Ask a question → Get a cited answer and a suggested next step. |
| **Proof** | A realistic worked example — a question, a shortened answer with a visible citation, and a proposed action. **Static content is fine.** This is the highest-value region on the page: it shows rather than claims. |
| **Closing call to action** | Repeat the primary action so the user needn't scroll back up |
| **Footer** | Team names, hackathon name `[FILL AT KICKOFF]`, GitHub link |

### States
Static page — no loading, empty, or error states.

### Notes
- No fabricated social proof. No fake testimonials, customer logos, or "trusted by" counts.
  Judges notice, and it costs credibility.
- If time is short, hero + what-it-does + proof + call to action is a complete landing page.
  Cut the rest.

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
- `/app` handles the "brand new user with nothing" case itself (see its empty state).

---

## `/app` — Ask Workspace ★ the core screen

**Purpose:** the user asks a question and gets a grounded, cited answer — plus, when warranted, a
proposed action. **This is the demo. It gets the most care.**

### Regions

| Region | Contains |
|---|---|
| **Question input** | Text input (multi-line capable), submit. Prominent — this is the screen's primary action. |
| **Scope selector** *(optional)* | Restrict the question to selected documents. Defaults to all. Cut if time is short. |
| **Answer** | The generated answer with inline citation markers |
| **Sources** | One card per cited document chunk |
| **Action** | The proposed agent action, when one exists |
| **Confidence** | The system's confidence, with its reason |

### Content requirements

**Question input**
- Accepts a full sentence comfortably — users type *"which invoices are overdue and who do I need to chase?"*, not keywords.
- Submit on Enter; newline on Shift+Enter.
- Show 3–4 clickable example questions when the input is empty. In a demo, nobody wants to think of a question on the spot. `[FILL AT KICKOFF]` once the dataset is known.

**Answer**
- Renders markdown (the backend returns markdown).
- Contains inline citation markers `[1]`, `[2]` matching `citations[].marker` from
  `POST /api/v1/ask`.
- **Each marker is interactive.** Activating one draws attention to the matching source card.
  This is how a user verifies a claim, and it's the moment that proves the answer is grounded
  rather than invented — **treat it as a headline feature, not a footnote.**
- Must be keyboard-reachable, not hover-only. Hover is an enhancement; it cannot be the only way.

**Source cards** — one per entry in `citations[]`, each showing:
- Marker number (ties it to the answer)
- Document name
- Page and/or section
- The verbatim excerpt the claim came from
- Relevance score (`0.0`–`1.0`, presented however Nipuna judges readable)

Sources must be **visible on the same screen as the answer**, not hidden behind a tab or
accordion. If a judge has to click to find the evidence, the grounding story is weakened.

**Action card** — only when `suggested_action` is non-null:
- Title, plain-language rationale, and a readable rendering of the payload
- Three controls: **Approve · Edit · Reject**
- Which citations justify the action
- **`draft_email` must show the full drafted subject and body**, editable before approval
- Must clearly read as *proposed, not done*. Nothing has happened yet.

**Confidence**
- Level plus the reason for it — never a bare number or an unexplained badge.
- **Not colour alone.** Pair any colour with a word.

### States

| State | Trigger | Required behaviour |
|---|---|---|
| **First run — no documents** | User has zero indexed documents | Don't show an empty question box. Explain that documents are needed and link to `/app/documents`. This is the very first thing a new user sees — make it a clear next step, not a dead end. |
| **Ready** | ≥1 indexed document, no question asked | Question input with example questions |
| **Thinking** | Question submitted | Visible progress. **The request can take several seconds** — a frozen screen reads as broken. Input disabled to prevent double-submit. |
| **Answered** | Success, `has_sufficient_evidence: true` | Answer + sources + confidence; action card if present |
| **Answered, no action** | `suggested_action: null` | Everything above, no action card. **This is the common case — design for it as the default, not the exception.** |
| **Insufficient evidence** | `has_sufficient_evidence: false` | Show the answer text (it explains what was searched). **No sources, no action card.** Must read as an honest limitation, *not* as an error — no red, no warning icon, no "something went wrong" framing. Getting this tone right is a scoring moment. |
| **No documents indexed** | `422 no_documents_indexed` | Same as first-run |
| **Service unavailable** | `502` / `504` | This *is* an error. Say so plainly and offer retry. Keep any previous answer on screen — don't wipe the user's work. |

### Notes
- Previous question/answer pairs may remain visible in the session, but conversation history is
  out of scope beyond last-turn coreference (see `docs/PROJECT.md`).
- The demo runs on this screen. It must survive a projector, a resized window, and someone
  clicking the wrong thing.

---

## `/app/documents` — Document Library

**Purpose:** get documents in, and see when they're ready to query.

### Regions

| Region | Contains |
|---|---|
| **Upload** | Drop zone + file picker. States accepted formats and the size limit. |
| **List** | One row per document |
| **Row detail** | Per-document metadata and actions |

### Content requirements

**Upload**
- Drag-and-drop **and** a click-to-browse fallback. Drag-and-drop alone fails on touch devices
  and for keyboard users.
- States accepted types (PDF, DOCX, CSV, TXT) and the **10 MB** limit *before* the user tries.
- Multiple files at once is nice to have, not required.

**Document row**
- File name · type · size · upload time
- **Status:** Pending → Indexing → Indexed, or Failed
- Page count and chunk count once indexed — small proof that something real happened
- Delete action
- Failed rows show the error message

### States

| State | Behaviour |
|---|---|
| **Empty** | Explain what to upload and why. This is a new user's likely first screen — the emptiness should feel like a starting point, not a void. |
| **Uploading** | Per-file progress. Other rows stay usable. |
| **Indexing** | The row updates without the user refreshing. **Indexing takes time and the user must not be left wondering.** Frontend polls `GET /api/v1/documents/{id}`. |
| **Indexed** | Ready-to-query indication, page/chunk counts shown |
| **Failed** | Error message on the row. Other documents unaffected. Retry or delete available. |
| **Rejected upload** | Wrong type or too large — say which, before any upload begins |
| **Delete confirmation** | Deletion is irreversible and removes the document's answers-source. Confirm first. |

### Notes
- Status must change **without a manual refresh**. A user who has to reload to see "Indexed"
  will assume it's broken.
- Deleting removes the document from future answers — the confirmation should say so.

---

## `/app/actions` — Agent Action Inbox

**Purpose:** review what the assistant proposed, and decide. **This screen is the product's
second differentiator** — it's the standing evidence that the assistant does more than answer.

### Regions

| Region | Contains |
|---|---|
| **Filter** | By status (Proposed / Approved / Rejected / Completed) and by type |
| **List** | One card or row per action |
| **Detail** | Full payload and the citations behind it |

### Content requirements

**Action item**
- Type — flag invoice · draft email · create task — clearly distinguished, and **not by colour
  alone**
- Title and plain-language rationale
- Status
- When it was created; when it was resolved
- The citations that justified it, with document name and excerpt
- Full payload, rendered readably per type:
  - **flag_invoice** — invoice number, supplier, amount, currency, due date, days overdue
  - **draft_email** — recipient, subject, and the **complete body**
  - **create_task** — title, description, due date, priority
- Controls appropriate to status: **Approve · Edit · Reject** on proposed items; **Mark complete**
  on approved ones

### States

| State | Behaviour |
|---|---|
| **Empty** | Explain that actions appear here when the assistant proposes one while answering. Link to `/app`. |
| **Has pending** | Pending items are unmistakably the ones needing attention |
| **Editing** | `draft_email` body and `create_task` fields are editable before approval. Save on approve. |
| **Resolving** | Control disabled during the request; no double-submit |
| **Already resolved** (`409`) | Someone resolved it in another tab. Refresh the item, don't error out. |
| **All resolved** | A finished-state message, not a blank screen |

### Notes
- **A drafted email is never sent** (see `docs/PROJECT.md` scope). The UI must not imply it was.
  Approving means *recorded and approved* — say that.
- The pending count here drives the navigation badge.

---

## `/app/history` — Past Answers *(build only if time)*

**Purpose:** revisit an earlier question without re-asking.

**Content:** list of past questions with timestamp, an excerpt of the answer, citation count,
and whether an action came out of it. Selecting one shows the full answer with its sources.

**States:** empty (link to `/app`) · list · detail.

**Cut this first** if time is tight. It demos poorly compared with `/app` and `/app/actions`.

---

## Key Flows

### First run — signup to first answer
```
/signup  →  /app (no documents)  →  prompt to add documents  →  /app/documents
         →  upload  →  status: indexing  →  status: indexed
         →  /app  →  example question or own question
         →  thinking  →  answer + sources (+ action card)
```
**The critical link is `/app` empty state → `/app/documents`.** A new user landing on an empty
question box with no idea what to do is the single most likely way to lose someone in the first
30 seconds.

### Ask → verify → act
```
type question  →  submit  →  thinking  →  answer renders
   →  activate citation [1]  →  matching source card highlights, excerpt visible
   →  read action card  →  Approve (or Edit, or Reject)
   →  action recorded  →  nav badge updates
```
**This is the demo path. Rehearse it.**

### Document lifecycle
```
upload  →  validate type + size (client-side first)  →  202 accepted
   →  row appears as Pending  →  poll  →  Indexing  →  Indexed (+ counts)
   →  document is now queryable
   →  delete  →  confirm  →  removed from list and from future answers
```

---

## Responsive Behaviour

Design mobile-first. Judges may open this on a phone.

| Region | Desktop | Narrow screens |
|---|---|---|
| App navigation | Persistent | Collapsible — **but the Actions pending badge must remain visible even when collapsed** |
| Answer + sources | Side by side or stacked, designer's call | Stacked, answer first, sources directly beneath |
| Citation interaction | Hover or click | **Click/tap — hover does not exist on touch.** A hover-only citation link is broken on mobile. |
| Action card controls | Inline | Full width, comfortably tappable |
| Document list | Full table | Reduced columns — but **status must always survive**; it's the reason the screen exists |
| Landing page | Multi-column allowed | Single column |

**Nothing is hidden on mobile — it re-flows.** If content isn't important enough for a phone, ask
whether it belongs on desktop either.

---

## State Catalogue

Every state that must exist somewhere. Missing states are how a demo breaks live.

| Type | Where | Required |
|---|---|---|
| **Loading** | Ask (thinking) · Upload · Indexing · Action resolving · Any list fetch | Visible progress; no frozen screens |
| **Empty** | No documents · No actions · No history · No answer yet | Explains what goes here and links to the next step |
| **Error** | Auth failure · Upload rejected · Ingest failed · 502/504 · 409 conflict | States what happened and what to do next |
| **Partial** | Some documents indexed, others still indexing | User can query what's ready |
| **Honest limitation** | Insufficient evidence | **Not styled as an error** — this is the system being trustworthy |
| **Success** | Upload complete · Action approved · Document deleted | Brief confirmation; doesn't block the next action |

---

## Accessibility Requirements

Functional, not visual. Non-negotiable.

- Every interactive element is **keyboard reachable** with a visible focus indicator.
- **Citation markers are keyboard-activatable.** Hover-only is a failure — it excludes keyboard
  and touch users both.
- Real semantics: `<button>` for actions, `<a>` for navigation. Never a click handler on a `<div>`.
- Every form field has an associated `<label>`.
- **Colour is never the only signal.** Document status, action type, action status, and confidence
  each pair colour with text or shape.
- The answer region announces when new content arrives, so screen-reader users know the response
  landed.
- Meaningful `alt` text on informative images; empty `alt` on decorative ones.
- Logical focus order — tab through each screen and check it makes sense.

---

## Microcopy That Matters

Three moments where the exact words carry the product's trustworthiness. Nipuna may reword —
but the *meaning* must survive.

**Insufficient evidence** — the backend supplies this text; render it as an ordinary answer, not
an error:
> "I couldn't find enough evidence in your documents to answer this. I searched 3 documents for
> information about 2025 tax filings, but the uploaded set only covers July 2026 invoices and
> supplier agreements."

Never "No results found." Never an error toast. The system explaining its own limits **is** the
feature.

**Action approval** — must be unambiguous that nothing was executed:
> "Approved and recorded. This action is logged in your Actions list."

Not "Sent." Not "Done." A drafted email was drafted, not sent.

**Empty workspace** — a starting point, not a void:
> "Add a document to get started. Once it's indexed, you can ask questions about it and get
> answers with sources."

---

## Open Items

| Item | Owner | Note |
|---|---|---|
| Example questions for the empty state | All | `[FILL AT KICKOFF]` — depends on the demo dataset |
| Product name and wordmark | All | `[FILL AT KICKOFF]` |
| Hackathon name for the footer | All | `[FILL AT KICKOFF]` |
| Worked example on the landing page | Nipuna + Lakshitha | Use a real answer from the demo dataset, not invented copy |
| Whether `/app/history` ships | All | Decide at the time check — cut first |

# PROJECT.md — North Star

**SME Business Intelligence Assistant** — a web application
*Ask your business documents anything. Get a cited answer — and the action that follows from it.*

> One page. If a decision isn't in here or in the Decisions Log, it hasn't been made.

---

## What We're Building

Small and medium businesses sit on documents that hold every answer they need — invoices,
contracts, supplier agreements, expense reports, meeting notes — and no practical way to ask
questions of them. The information exists; retrieving it means someone opening files one at a time.

We're building an **agentic RAG assistant** that does two things a search box can't:

1. **Answers in natural language, with citations.** Ask *"which suppliers raised prices this
   quarter?"* and get a real answer grounded in the actual documents, with the source of every
   claim shown and clickable.
2. **Takes the action the answer implies.** A question isn't always just a question. When the
   answer is *"invoice #4471 is 30 days overdue"*, the useful next step isn't more prose — it's
   flagging the invoice, drafting the chase email, or creating a task. The agent proposes that
   action; the user approves it with one click.

**The distinction that matters:** a chatbot tells you what it found. Ours closes the loop between
finding out and doing something about it.

**Who it's for:** an SME owner, office manager, or bookkeeper — someone with no analyst on staff
and no time to read forty PDFs.

**The deliverable is a full web application**, not an API with a chat box: a public landing page
that explains the product, sign-in, and a four-screen authenticated workspace. Seven routes in
total — see [In scope](#-in-scope) below and `docs/UI_SPEC.md` for what each screen must do.

**Specific challenge brief / theme:** `[FILL AT KICKOFF]`
**Judging criteria and weights:** `[FILL AT KICKOFF]`
**Time limit and submission deadline:** `[FILL AT KICKOFF]`
**Demo dataset:** `[FILL AT KICKOFF]` — target ~20–50 realistic business documents

---

## The ONE Core User Flow

Everything else is secondary. If this works end to end, we have a product.

**Scenario:** an office manager wants to know which invoices need chasing.

| # | Step | What the user does | What the system does |
|---|---|---|---|
| 1 | **Sign in** | Logs in | Supabase Auth issues a JWT; every later request carries it |
| 2 | **Upload** | Drags in PDFs / DOCX / CSV | Backend stores metadata in Postgres, hands the file to the agent service |
| 3 | **Index** | *(watches a progress bar)* | Agent service extracts text → chunks → embeds with `text-embedding-3-small` → writes vectors to Azure AI Search |
| 4 | **Ask** | Types *"Which invoices are overdue and who do I need to chase?"* | Backend forwards the question to the agent service |
| 5 | **Retrieve** | — | LangChain runs hybrid retrieval over Azure AI Search, returns the top-k chunks |
| 6 | **Answer** | — | `gpt-4o-mini` generates an answer **strictly from retrieved context**, emitting a citation marker per claim |
| 7 | **Read the answer** | Reads it | Answer renders with **inline citation chips**; hovering one highlights the source card — document name, page, excerpt, relevance score |
| 8 | **🔥 Agent proposes an action** | — | The agent classifies the query as action-worthy and proposes a concrete step: *"Flag invoice #4471 (₨120,000, 32 days overdue)"* or *"Draft a payment-reminder email to Silverline Supplies"* |
| 9 | **Approve** | Clicks **Approve** (or Reject, or edits first) | Nothing executes without this click. Human-in-the-loop is a hard rule. |
| 10 | **Record** | Sees it in the actions list | Action written to Postgres with status, timestamp, and the citations that justified it |
| 11 | **Honest failure** | — | If retrieval finds nothing relevant: *"I couldn't find enough evidence in your documents to answer this."* Never invented. |

**The demo moment is step 8.** Steps 1–7 are a good RAG app that many teams will build. Step 8 is
the one where a judge sits up — the assistant stops describing the problem and starts solving it.

---

## Scope

### ✅ In scope

| Area | What we're building |
|---|---|
| **Website — 7 routes** | `/` landing · `/login` · `/signup` · `/app` ask workspace ★ · `/app/documents` · `/app/actions` · `/app/history` *(if time)*. Full specs in `docs/UI_SPEC.md`. |
| Ingestion | Upload PDF / DOCX / CSV / TXT; extract, chunk, embed, index |
| Retrieval | Vector + keyword hybrid search over Azure AI Search |
| Generation | Grounded answers from retrieved context only, `gpt-4o-mini` |
| Citations | Per-claim inline chips → document name, page/section, excerpt, relevance score |
| **Agent actions** | Three fixed types: **flag invoice · draft email · create task** |
| **Approval gate** | Every action requires explicit user approval before it's recorded |
| Uncertainty | Explicit "not enough evidence" response — no fabrication |
| Auth | Supabase email/password sign-in |
| Actions list | View, filter, approve/reject/complete agent actions |
| Deploy | Live on Azure — App Service (backend + agent) + Static Web Apps (frontend) |

### ❌ Out of scope

| Excluded | Why |
|---|---|
| **Marketing site beyond one landing page** | No blog, pricing page, about page, or docs site. One `/` that explains the product is enough. |
| **Onboarding tour / product walkthrough** | The `/app` empty state links to `/app/documents`. That's the onboarding. |
| **Email confirmation on signup** | Straight to `/app`. Every extra step in a demo is a step that can fail. |
| Real email sending | Draft and display it — actually wiring SMTP is demo risk with no demo value |
| Real accounting integrations (Xero, QuickBooks) | Days of OAuth work; the agent-action *concept* demos without it |
| Multi-tenant / org management | One user, their own documents |
| Roles & permissions | No admin/viewer split |
| Billing / subscriptions | Not a product yet |
| Mobile-native app | Responsive web only |
| Real-time collaboration | Single user per session |
| Fine-tuned models | Off-the-shelf, prompt-engineered |
| Dynamic agent tools | The three action types are **fixed**. Not configurable, not extensible at runtime. |
| Conversation memory | Last-turn coreference at most — no long history |
| OCR / scanned documents | Text-layer PDFs only |

**Scope defence:** the three action types are fixed and the approval gate is mandatory. Both
constraints exist to keep the agent bounded and demoable. Resist adding a fourth action type.

---

## Decisions Log

Append a row whenever you make a call that affects someone else's work. Newest at the bottom.

| Date | Decision | Why |
|---|---|---|
| `[KICKOFF]` | **Backend is Python + FastAPI** (SQLAlchemy + Alembic), not C# .NET | One language across both services — one runtime, one set of idioms, and either backend person can read the other's code. Also removes the .NET snake_case configuration entirely. |
| `[KICKOFF]` | **Two Python services kept separate** — `backend/` gateway + `agent/` | Both are FastAPI and could merge, but the split buys independent deploys and unambiguous ownership: Manujaya redeploys the API without touching retrieval; Lakshitha rebuilds chains without risking auth or the DB. |
| `[KICKOFF]` | **OpenAI models on Azure AI Foundry** — `gpt-4o-mini` + `text-embedding-3-small`. Settled. | One client, one endpoint, one key shared by generation and embeddings. Everything stays on Azure and bills to one place. No alternative provider is kept on the table — a documented option nobody takes is just noise. |
| `[KICKOFF]` | Frontend never calls the agent service directly | One origin, one auth surface, one CORS config to debug. |
| `[KICKOFF]` | JSON is `snake_case` on every wire | Python, Pydantic, SQLAlchemy, and Postgres all use it natively — one convention, zero configuration, no translation layer anywhere. |
| `[KICKOFF]` | Agent actions require explicit user approval | Nothing auto-executes. Safer product, better demo, and it removes a whole class of failure. |
| `[KICKOFF]` | **Deliverable is a 7-route web application**, not just an API | Judges interact with a website. The landing page and the workspace both count. |
| `[KICKOFF]` | **`docs/UI_SPEC.md` specifies screen function only; Nipuna owns all visual design** | Colour, type, spacing, components, and iconography are design decisions and shouldn't be frozen in a spec written by someone else. |
| 2026-08-05 | **Windows devs run the backend with `python run.py`, not `uvicorn app.main:app`** *(Manujaya)* | psycopg's async mode cannot use Windows' default `ProactorEventLoop`, and uvicorn builds that loop before it imports the app — so the app can't fix it from the inside. `run.py` sets the selector policy first. Linux/App Service keeps the plain uvicorn command. |
| 2026-08-05 | **`AGENT_STUB_MODE` and `AUTH_DISABLED` env switches on the backend** *(Manujaya)* | Lets the gateway serve the contract's exact payloads before Supabase, Postgres, or `agent/` exist — Nipuna integrates against the real backend on day 0 instead of fixtures. Both log a warning at startup and must never be set in App Service config. |
| 2026-08-05 | **Proposed: add `DELETE /rag/documents/{id}` to API_CONTRACT Part 2** *(Manujaya → Lakshitha, needs 👍)* | Deleting a document must clear its AI Search vectors, but Part 2 has no delete endpoint and the gateway holds no search credentials by design. Until it exists the backend calls the path, treats 404/405 as not-implemented, logs it, and completes the Postgres delete. |
| | | |

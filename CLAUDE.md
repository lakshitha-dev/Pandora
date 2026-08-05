# CLAUDE.md — Shared Conventions

**Project:** **Pandora Knowledge Guardian** — the *Guardian Command Center*, a web application
**Challenge:** Pandora Builderthon 2026 · *"Echoes of Pandora: An AI Knowledge Guardian for a Living
Ecosystem"* — theme: **Avatar: The Way of Water** · **5-hour build**
**Team:** 4 people working in parallel. These are the rules that make our code fit together at merge.

> **What we're building, in one line:** a Retrieval-Augmented Generation system that turns a
> guardian's plain-language description of an environmental incident into a cited **Situation
> Report** — and says plainly when the corpus doesn't know. Design source of truth: `SOLUTION.md`.
> Challenge brief: `PANDORA_RAG_HACKATHON_2026.md`. Knowledge corpus:
> `Pandora_RAG_Knowledge_2026 (1).pdf`.

> Read this before your first commit. It's short on purpose.

---

## Stack

| Layer | Technology | Owner |
|---|---|---|
| Frontend | Next.js (scaffolded with v0), TypeScript — **7 routes, public + authenticated** | **Nipuna** (P2) |
| Backend (gateway) | **Python + FastAPI** · SQLAlchemy 2.0 · Alembic · Pydantic v2 | **Manujaya** (P3) |
| RAG + Agent | **Python + FastAPI + LangChain** · `text-embedding-3-small` · **`gpt-5-mini`** (a *reasoning* model — `gpt-4o-mini` is not deployed; see the `[LAYER 1]` row in `docs/PROJECT.md`), via Azure AI Foundry | **Lakshitha** (P1) |
| Vector store | Azure AI Search (free **F0** tier → API keys, no managed identity, **no semantic reranker**) | P1 / P4 |
| App database | Azure Database for PostgreSQL — documents, chunks, situation reports, traces | P3 |
| Auth | Supabase Auth (only piece outside Azure) | P3 |
| Streaming | Server-Sent Events (`sse-starlette`) — the orchestration trace, agent → gateway → browser | P1 / P2 / P3 |
| Knowledge corpus | `Pandora_RAG_Knowledge_2026 (1).pdf` — 56 pp, ~130 records, **pre-indexed at seed time** | P1 / P4 |
| Deploy | Azure App Service ×2 (backend + agent) · Azure Static Web Apps (frontend) | **Malindu** (P4) |
| Repo | GitHub — **`.env` gitignored before first commit** | P4 |

**Two Python services, not one.** The backend is the gateway: it owns auth, Postgres, and the
public API. The agent service owns LangChain, retrieval, and the vector index, and is **not
publicly routable** — only the backend calls it. Separating them keeps deploys independent and
gives Manujaya and Lakshitha their own service to own.

---

## Folder Structure

```
/
├── CLAUDE.md              ← you are here
├── docs/                  ← PROJECT · UI_SPEC · API_CONTRACT · ARCHITECTURE · TASKS · TECH_STACK
├── frontend/              Next.js              — Nipuna
├── backend/               FastAPI gateway      — Manujaya
├── agent/                 FastAPI + LangChain  — Lakshitha
├── infra/                 Bicep / az CLI / GH Actions — Malindu
├── SOLUTION.md            design source of truth — read §2.1, §4, §10 first
├── PANDORA_RAG_HACKATHON_2026.md    the brief (read-only)
├── Pandora_RAG_Knowledge_2026.md    the corpus, markdown reference copy
├── .env.example           committed — every key, dummy values
└── .gitignore             .env, __pycache__/, .venv/, node_modules/, .next/
```

**Stay in your folder.** Cross-folder edits need a heads-up in the team channel first.

### Inside each service

```
frontend/  app/  components/  lib/  hooks/  types/

backend/   app/
             api/        routers, one file per resource
             core/       config, security, dependencies
             db/         SQLAlchemy models, session
             schemas/    Pydantic request/response models
             services/   business logic, agent HTTP client
           alembic/      migrations

agent/     app/
             routers/    /rag, /agent, /health
             chains/     LangChain composition
             agents/     orchestrator + the 3 fixed specialists
             retrieval/  hybrid search, RRF fusion, LLM reranker
             grounding/  GroundingGate (8 corpus rules), conflict detection
             ingestion/  extract, record-aware chunk, embed, index
             models/     Pydantic models
           tests/
```

### Frontend routes — seven of them

```
app/
  page.tsx                    /                     public   landing
  login/page.tsx              /login                public
  signup/page.tsx             /signup               public
  app/
    layout.tsx                                      ← auth guard + app shell live here
    page.tsx                  /app                  authed   Command Center ★
    documents/page.tsx        /app/documents        authed   knowledge base
    incidents/page.tsx        /app/incidents        authed   incident register
    investigations/page.tsx   /app/investigations   authed   past reports (only if time)
```

- **The auth guard belongs in `app/app/layout.tsx`**, not repeated per page. One place to get right.
- Pages compose; they don't implement. Logic lives in `components/` and `hooks/`.
- Full screen-by-screen requirements: **`docs/UI_SPEC.md`**.

---

## Naming Conventions

This is where merges break. Follow it exactly.

| What | Convention | Example |
|---|---|---|
| React components | `PascalCase.tsx` | `SourceCard.tsx`, `SituationReport.tsx` |
| Hooks | `useThing.ts` | `useAskQuestion.ts`, `useSitrepStream.ts` |
| TS utils / lib | `camelCase.ts` | `formatCitation.ts` |
| Next.js route folders | `kebab-case` | `app/app/incidents/` |
| Python — files, functions, variables | `snake_case` | `chunk_document.py`, `def build_index()` |
| Python — classes | `PascalCase` | `class RetrievalChain`, `class GroundingGate` |
| Python — Pydantic models | `PascalCase`, named after the contract | `AskRequest`, `SituationReport` |
| Python — routers | One file per resource, plural | `api/documents.py`, `api/situation_reports.py` |
| **API routes** | `/api/v1/kebab-case-plural` | `/api/v1/documents`, `/api/v1/situation-reports` |
| **JSON fields** | `snake_case` — every wire, both services | `situation_report`, `record_id`, `created_at` |
| **DB tables & columns** | `snake_case`, plural tables | `situation_reports`, `report_sections`, `created_at` |
| **Corpus record IDs** | verbatim from the corpus, **never re-cased** | `INC-005`, `FAU-014`, `WS-03`, `REG-01` |
| Env vars | `SCREAMING_SNAKE_CASE` | `AZURE_SEARCH_API_KEY` |
| Git branches | `<name>/<short-desc>` | `nipuna/answer-panel` |

**One casing convention, zero configuration.** Python, Pydantic, SQLAlchemy, Postgres, and our
JSON contract are all `snake_case` natively — nothing to configure, nothing to remember. The
frontend's `types/api.ts` mirrors the wire format exactly, so no translation layer exists anywhere
in the system.

### Pydantic models are defined twice — on purpose

Both services define their own Pydantic models mirroring `docs/API_CONTRACT.md`. A shared package
would mean packaging setup, version pinning, and a coordinated rebuild across two App Services for
a handful of small classes. **The contract file is the source of truth; the models are its
implementations.** When the contract changes, both sides change.

---

## TypeScript Style

- `"strict": true` in `tsconfig.json`. Non-negotiable.
- **No `any`.** Use `unknown` and narrow. If you're stuck, `// TODO(name): tighten` and move on.
- Explicit return types on exported functions. Inference is fine internally.
- **Named exports**, not default — better refactoring and autocomplete. (Next.js `page.tsx` and
  `layout.tsx` files are the exception; the framework requires default exports there.)
- `type` for unions and aliases · `interface` for object shapes that might extend.
- API types live in `frontend/types/api.ts`, hand-mirrored from `docs/API_CONTRACT.md` — nowhere
  else. One source of truth.
- `async/await` over `.then()` chains.
- No barrel files (`index.ts` re-exports) — they hurt tree-shaking and cause circular imports.

---

## Python Style — both services

- **Python 3.11+.** Type hints on every function signature — they're what makes FastAPI generate
  the OpenAPI docs and what makes review possible.
- Pydantic v2 for every request/response model. Never hand-roll a dict for an API payload.
- `async def` for anything doing I/O — HTTP calls, database queries, model calls.
- FastAPI dependency injection for shared concerns (DB session, current user, settings). Don't
  reach for globals.
- Config via a Pydantic `Settings` class reading the environment. **Never `os.getenv()` scattered
  through the codebase** — one place, validated at startup, fails loudly on a missing key.
- `ruff` for lint and format if it's set up; don't argue about style in review.
- Keep routers thin: parse, delegate to a service, return. Business logic lives in `services/`.

---

## Do / Don't

### ✅ Do

- **Build against the mock first.** The contract in `docs/API_CONTRACT.md` is frozen at kickoff —
  Nipuna builds against mock JSON on day one, Manujaya stubs the endpoints, Lakshitha stubs
  `/rag/*`. Nobody waits.
- Commit `.env.example` with every key and dummy values, so a teammate can start in 2 minutes.
- Keep secrets in `.env` locally and in App Service config in Azure. Never in code, never in a doc.
- Small, frequent commits. Push at least once an hour so the team can see progress.
- Add a row to the **Decisions Log** in `docs/PROJECT.md` when you make a call that affects others.
- Update your row in `docs/TASKS.md` when status changes — it's how we avoid duplicate work.
- Return the standard error envelope from every endpoint: `{ "error": { "code", "message" } }`.
- **Cite by corpus record ID.** Every factual claim resolves to a real `INC-*` / `FAU-*` / `WS-*`
  record. A claim that can't name its record is a bug, not a style issue.
- **Wire each layer's feature flag before you build the layer**, so a half-finished layer defaults
  off. The layers and their flags are in `SOLUTION.md` §10.

### ❌ Don't

- **Don't commit `.env`.** Verify `.gitignore` covers it *before* the first commit. We're on
  Azure AI Search F0, which is API-key-only — a leaked key is a live key.
- **Don't change `docs/API_CONTRACT.md` alone.** It's the contract between three people. Propose
  the change in the channel, get a 👍, then edit.
- **Don't change `docs/UI_SPEC.md`'s screen behaviour alone** — it drives Nipuna's build and
  Manujaya's endpoints. *Visual* design is Nipuna's call and needs no sign-off.
- Don't edit another person's folder without telling them.
- Don't call the agent service from the frontend. Everything goes through the backend — one
  origin, one auth surface, one CORS config.
- Don't add a dependency to a shared config (Docker, CI, `.gitignore`) without a heads-up.
- Don't rename a public API field once the frontend is consuming it. Add the new one, migrate, remove.
- Don't push directly to `main` after integration starts — PR into `main`, one reviewer.
- **Don't let a later layer edit an earlier layer's code.** Layer 5's orchestrator *calls* Layer 1's
  retriever; it never modifies it. This is what keeps the 45-mark core safe (`SOLUTION.md` §15, risk 14).
- **Don't import real-world facts into an answer.** The corpus is fictional and internally
  consistent. Earth marine biology is a hallucination here even when it's true on Earth.
- **Don't remove an SSE event type from the trace schema.** New step types are additive only —
  three people build against that schema simultaneously.

---

## Quick Reference

```bash
# frontend
cd frontend && npm install && npm run dev              # → localhost:3000

# backend
cd backend && python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 5000              # → localhost:5000

# agent
cd agent && python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000              # → localhost:8000

# migrations (backend)
alembic revision --autogenerate -m "description"
alembic upgrade head

# seed the Pandora corpus into Azure AI Search (agent) — run once, before any query works
python -m app.ingestion.seed_corpus --source "../Pandora_RAG_Knowledge_2026 (1).pdf"
```

Both Python services expose auto-generated API docs at `/docs` while running — the fastest way to
check a payload shape without reading code.

| Doc | What it answers |
|---|---|
| **`SOLUTION.md`** | **Why is it built this way? The design source of truth — start at §2.1, §4, §10.** |
| `PANDORA_RAG_HACKATHON_2026.md` | What did the judges actually ask for? *(read-only — never edit)* |
| `Pandora_RAG_Knowledge_2026.md` | What's in the corpus? Reference copy for verifying chunk boundaries. |
| `docs/PROJECT.md` | What are we building, and what's out of scope? |
| `docs/UI_SPEC.md` | What does each screen do and contain? |
| `docs/API_CONTRACT.md` | What exactly does this endpoint return? |
| `docs/ARCHITECTURE.md` | How do the pieces connect? |
| `docs/TASKS.md` | Who's doing what right now? |
| `docs/TECH_STACK.md` | Why did we pick this, and what are its limits? |

---

## The five things that win this

Memorise these. Every rubric category traces to one of them (`SOLUTION.md` §2.2).

| # | Thing | Why it scores |
|---|---|---|
| 1 | **Record-aware chunking** — one corpus record = one chunk, never split, never merged | The corpus's §15.2 rule 3 explicitly forbids merging two species. Fixed-size splitting guarantees that exact error. |
| 2 | **GroundingGate** — the corpus's own 8 published grounding rules, executed as a validator | Not our idea of "grounded" — the graders' published checklist, ticking green on screen |
| 3 | **The honest refusal** — thin evidence prints the brief's mandated sentence, never a guess | The 20-mark Accuracy criterion asks for exactly this, and most teams bolt it on last |
| 4 | **Conflict presentation** — `FN-A` / `FN-B` / `LAB-C` shown side by side, no cause declared | §14.3 of the corpus is a planted trap with a stated expected answer. We match it line for line. |
| 5 | **The Situation Report** — priority · species · causes · actions · sources · confidence | The format *is* the real-world value. An incident lead can execute from it. |

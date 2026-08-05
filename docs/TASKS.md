# TASKS.md — Task Board

**Update your own rows.** Status: `todo` · `doing` · `done`. It's how we avoid duplicate work.

**Legend:** 🔴 blocks someone else — do it first · 🟡 on the critical path · 🟢 independent

---

## ⚡ Day 0 — Unblockers (before anything else)

Nothing else starts cleanly until these are done. Two of them block all three other people.

| Task | Owner | Status | Blockers |
|---|---|---|---|
| 🔴 Create GitHub repo, add `.gitignore` (**`.env`, `bin/`, `obj/`, `__pycache__/`, `.venv/`, `node_modules/`, `.next/`**) and push **before any secret exists** | Malindu | todo | — |
| 🔴 Provision Azure: AI Foundry (deploy `gpt-4o-mini` + `text-embedding-3-small`), AI Search **F0**, PostgreSQL Flexible Server | Malindu | todo | Azure subscription access |
| 🔴 Create Supabase project, grab URL + anon key + JWT secret | Malindu | todo | — |
| 🔴 Write `.env.example` with every key name and dummy values; share real values via a **private** channel — never a commit | Malindu | todo | Azure + Supabase provisioned |
| 🔴 Freeze `docs/API_CONTRACT.md` — all four read it, everyone 👍 in the channel | All | todo | — |
| 🟡 Agree folder structure and create the four empty folders with a README each | All | todo | Repo exists |

---

## 🧠 Lakshitha (P1) — RAG pipeline + AI agent · `agent/`

| Task | Owner | Status | Blockers |
|---|---|---|---|
| 🔴 **Stub `/rag/ingest`, `/rag/query`, `/agent/run`, `/health` returning the exact §2 payloads** — unblocks Manujaya immediately | Lakshitha | todo | API contract frozen |
| 🟡 FastAPI scaffold: `app/{routers,chains,agents,ingestion,models}/`, `requirements.txt`, Uvicorn entrypoint | Lakshitha | todo | Folder structure |
| 🟡 Verify Azure AI Foundry connectivity — one embedding call + one `gpt-4o-mini` call | Lakshitha | todo | Azure provisioned |
| 🟡 Create the Azure AI Search index: `content`, `content_vector` (1536-d, HNSW, cosine), `document_id`, `page`, `section`, `chunk_id` | Lakshitha | todo | AI Search provisioned |
| 🟡 Text extraction: PDF → DOCX → CSV → TXT, retaining page numbers | Lakshitha | todo | Scaffold |
| 🟡 Chunking: ~800 tokens, ~120 overlap, split on headings/sections first | Lakshitha | todo | Extraction |
| 🟡 Embedding + batched upsert into AI Search (`text-embedding-3-small`) | Lakshitha | todo | Index + chunking |
| 🟡 Wire real `/rag/ingest` behind the stub | Lakshitha | todo | Embedding pipeline |
| 🟡 Hybrid retrieval — vector + BM25, fused, `top_k=6` | Lakshitha | todo | Index populated |
| 🟡 Grounded generation prompt: context-only, `[n]` citation markers, refuse when evidence is thin | Lakshitha | todo | Retrieval |
| 🟡 Wire real `/rag/query` behind the stub | Lakshitha | todo | Retrieval + generation |
| 🔥 **Agent action chain** — classify action-worthiness, build `flag_invoice` / `draft_email` / `create_task` | Lakshitha | todo | `/rag/query` working |
| 🔥 Wire real `/agent/run` — must return `suggested_action: null` on non-action queries | Lakshitha | todo | Action chain |
| 🟢 Pydantic `Settings` for env config — validated at startup, no scattered `os.getenv()` | Lakshitha | todo | Scaffold |
| 🟢 Confidence scoring + `has_sufficient_evidence` logic | Lakshitha | todo | Generation working |
| 🟢 LLM-based reranker over top-N candidates (**F0 has no semantic ranker**) — only if retrieval quality needs it | Lakshitha | todo | Retrieval working |
| 🟢 Tune chunk size / `top_k` against the real demo dataset | Lakshitha | todo | `[FILL AT KICKOFF]` dataset |

---

## 🎨 Nipuna (P2) — UI/UX + frontend · `frontend/`

| Task | Owner | Status | Blockers |
|---|---|---|---|
> **Seven routes to build.** Full screen-by-screen requirements in `docs/UI_SPEC.md` — it
> specifies *what* each screen does. **Everything visual is your call**: colour, type, spacing,
> components, iconography. Push back on the spec if it fights good design.
>
> **Build order:** `/app` → `/app/documents` → `/app/actions` → auth pages → `/` → `/app/history`.

**Setup & foundations**

| Task | Owner | Status | Blockers |
|---|---|---|---|
| 🔴 **Create JSON fixtures from §1.1 and §1.4 — build the entire UI against them.** Do not wait for the backend. | Nipuna | todo | API contract frozen |
| 🟡 Scaffold Next.js (App Router) with v0; `tsconfig` `strict: true`; folders `app/ components/ lib/ hooks/ types/` | Nipuna | todo | Folder structure |
| 🟡 `frontend/types/api.ts` — hand-mirror every §1 shape. One source of truth. | Nipuna | todo | API contract frozen |
| 🟡 Pick the styling approach and set up the design foundation — **your call entirely** | Nipuna | todo | Scaffold |
| 🔴 **App shell + auth guard in `app/app/layout.tsx`** — nav (Ask · Documents · Actions · History), account menu, redirect-to-`/login`. One guard, not one per page. | Nipuna | todo | Scaffold |
| 🟡 Pending-action count badge in nav — updates after approve/reject without a reload | Nipuna | todo | App shell |

**`/app` — Ask workspace ★ the demo screen**

| Task | Owner | Status | Blockers |
|---|---|---|---|
| 🟡 Question input — multi-line, Enter to submit, Shift+Enter for newline, example questions when empty | Nipuna | todo | Fixtures |
| 🔥 **Answer with inline citation markers** — `[n]` interactive, activating one highlights its source card. **Must be keyboard-activatable, not hover-only** (hover doesn't exist on touch). | Nipuna | todo | Fixtures |
| 🔥 Source cards — document name, page, excerpt, relevance score. **Visible alongside the answer, not behind a tab.** | Nipuna | todo | Fixtures |
| 🔥 **Agent action card** — title, rationale, payload rendered per type, **Approve / Edit / Reject**. `draft_email` shows full editable body. Must read as *proposed, not done*. | Nipuna | todo | Fixtures |
| 🔥 **Handle `suggested_action: null` as the default path** — most answers have no action | Nipuna | todo | Fixtures |
| 🟡 Confidence indicator with its stated reason — **not colour alone** | Nipuna | todo | Fixtures |
| 🔥 Insufficient-evidence state — **honest limitation, not an error**. No red, no warning icon. | Nipuna | todo | Fixtures |
| 🔴 First-run empty state → links to `/app/documents`. **The most likely place to lose a new user.** | Nipuna | todo | Fixtures |
| 🟡 Thinking state — visible progress, input disabled, no double-submit | Nipuna | todo | Fixtures |

**`/app/documents` — Document library**

| Task | Owner | Status | Blockers |
|---|---|---|---|
| 🟡 Upload — drag-and-drop **plus** click-to-browse fallback; states types and 10 MB limit up front | Nipuna | todo | Fixtures |
| 🟡 Document list — name, type, size, status, page/chunk counts, delete | Nipuna | todo | Fixtures |
| 🔥 **Status updates without manual refresh** — poll `GET /api/v1/documents/{id}` while pending/indexing | Nipuna | todo | Fixtures |
| 🟡 Client-side type/size validation before upload starts | Nipuna | todo | Upload |
| 🟡 Empty state, failed-row error message, delete confirmation | Nipuna | todo | List |

**`/app/actions` — Agent action inbox**

| Task | Owner | Status | Blockers |
|---|---|---|---|
| 🔥 Action list — type, title, rationale, status, citations, full payload per type | Nipuna | todo | Fixtures |
| 🔥 Approve / Edit / Reject controls; **`draft_email` body editable before approval** | Nipuna | todo | Action list |
| 🟡 Status + type filters | Nipuna | todo | Action list |
| 🟡 Handle `409 action_already_resolved` — refresh the item, don't error out | Nipuna | todo | Action list |
| 🟡 Empty state explaining where actions come from | Nipuna | todo | Action list |

**Public pages**

| Task | Owner | Status | Blockers |
|---|---|---|---|
| 🟡 `/login` + `/signup` — Supabase Auth, session handling, JWT on every request, no double-submit | Nipuna | todo | Supabase keys |
| 🟡 **`/` landing page** — hero, the problem, three things it does, how it works, worked example, CTA, footer | Nipuna | todo | Scaffold |
| 🔥 Landing-page worked example — real question + cited answer + proposed action. **Highest-value region on the page.** | Nipuna + Lakshitha | todo | Demo dataset |
| 🟢 `/app/history` — past questions and answers. **Cut this first if time is short.** | Nipuna | todo | Core screens done |

**Integration & polish**

| Task | Owner | Status | Blockers |
|---|---|---|---|
| 🔥 Swap fixtures for the real backend base URL | Nipuna | todo | Manujaya's stubs live |
| 🟡 Responsive pass — 360px / 768px / 1280px. **Nothing hidden on mobile; it re-flows.** | Nipuna | todo | Core screens done |
| 🟡 Accessibility pass — keyboard reachability, focus order, labels, colour never the sole signal | Nipuna | todo | Core screens done |
| 🟢 Error + toast handling for the §Error-envelope codes | Nipuna | todo | Core screens done |
| 🟢 Visual polish pass | Nipuna | todo | Core screens done |

---

## ⚙️ Manujaya (P3) — Backend · `backend/`

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
| 🟡 Alembic init + first migration, applied to Azure PostgreSQL | Manujaya | doing | Migration `0001` written and verified against the Postgres dialect; **not yet applied — Postgres not provisioned** |
| 🟡 Supabase JWT validation dependency (`python-jose`) — signature + expiry, extract user ID | Manujaya | doing | Code done; unverified against a real token — needs `SUPABASE_JWT_SECRET` |
| 🟡 `httpx` agent client — `X-Internal-Key`, **30 s** query / **60 s** ingest timeouts | Manujaya | done | Wired; live call untested until Lakshitha's stubs are up |
| 🟡 `POST /api/v1/documents` — validate type + size, persist, return `202`, dispatch to `/rag/ingest` async | Manujaya | done | — |
| 🟡 `GET/DELETE /api/v1/documents` — **delete must remove Postgres row AND AI Search vectors** | Manujaya | doing | **Part 2 has no delete endpoint.** Proposed `DELETE /rag/documents/{id}` — needs Lakshitha + a contract edit. Gateway calls it and logs when it's absent. |
| 🔥 `POST /api/v1/ask` — orchestrate `/rag/query` → `/agent/run`, join `document_name` from Postgres, assemble the response | Manujaya | done | — |
| 🔥 `POST` + `PATCH /api/v1/agent-actions` — persist, approve/reject/complete, set `resolved_at` | Manujaya | done | — |
| 🟡 `GET /api/v1/agent-actions` with status/type filters and paging | Manujaya | done | — |
| 🟡 Standard error envelope on every non-2xx via an exception handler + the documented `code` values | Manujaya | done | — |
| 🟡 `GET /health` for the Azure App Service probe | Manujaya | done | — |
| 🟢 `422 no_documents_indexed` guard before any LLM call | Manujaya | done | — |
| 🟢 Request/response logging for demo debugging | Manujaya | done | — |
| 🟢 21 contract tests (SQLite + stub agent, no network) + `ruff` clean | Manujaya | done | — |

---

## ☁️ Malindu (P4) — Deployment + cloud infra · `infra/`

| Task | Owner | Status | Blockers |
|---|---|---|---|
| 🔴 *(All four Day-0 unblockers above are Malindu's)* | Malindu | todo | — |
| 🟡 Create the two Azure App Services (backend + agent) and the Static Web App | Malindu | todo | Azure access |
| 🟡 App Service configuration — every env var set; **no secrets in code or docs** | Malindu | todo | App Services created |
| 🟡 GitHub Actions: build + deploy backend on push to `main` | Malindu | todo | App Service + backend scaffold |
| 🟡 GitHub Actions: build + deploy agent service — **same Python workflow pattern as the backend**, so write it once and copy | Malindu | todo | App Service + agent scaffold |
| 🟡 GitHub Actions: build + deploy frontend to Static Web Apps | Malindu | todo | SWA + frontend scaffold |
| 🟡 Azure health-check probes → backend `/health` and agent `/health` | Malindu | todo | Both deployed |
| 🟡 Networking: agent App Service reachable by the backend, **not publicly routable** | Malindu | todo | Both deployed |
| 🟡 Postgres firewall rules — Azure services + team dev IPs | Malindu | todo | Postgres provisioned |
| 🔥 **End-to-end smoke test on deployed infra** — upload → ask → approve an action | Malindu | todo | All three services deployed |
| 🟢 `README.md`: setup, env vars, run-locally, deploy | Malindu | todo | Everything running |
| 🟢 Architecture diagram export for the submission | Malindu | todo | `docs/ARCHITECTURE.md` |
| 🟢 **Record a backup demo video** once the flow works end to end | Malindu | todo | Smoke test passing |

---

## 🤝 Integration & Demo — everyone

| Task | Owner | Status | Blockers |
|---|---|---|---|
| 🔥 Integration checkpoint 1 — frontend hits the real backend stubs | Nipuna + Manujaya | todo | Both scaffolds up |
| 🔥 Integration checkpoint 2 — backend hits the real agent service | Manujaya + Lakshitha | todo | Agent endpoints real |
| 🔥 **Full flow working locally** — upload → index → ask → cited answer → action → approve | All | todo | Checkpoints 1 + 2 |
| 🔥 Full flow working on deployed Azure | All | todo | Local flow + deploys |
| 🟡 Load the demo dataset and rehearse three questions | All | todo | `[FILL AT KICKOFF]` dataset |
| 🟡 Rehearse the pitch against a timer | All | todo | Flow working |
| 🟢 Final polish pass — copy, empty states, obvious bugs | All | todo | Flow working |

---

## Notes

- **The three 🔴 stub tasks are the highest-leverage work in this file.** Three people can build
  in parallel from hour one instead of waiting in a chain.
- `[FILL AT KICKOFF]` items are unknowns from the brief — fill them the moment it drops.
- If you're blocked, put the blocker in the **Blockers** column and say so in the channel. Don't
  sit on it.

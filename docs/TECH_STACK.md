# TECH_STACK.md

Every technology we use, why we picked it, and where it bites.

---

## Frontend — Nipuna

| Technology | Why |
|---|---|
| **Next.js (App Router)** | React with file-based routing for our seven routes, plus layouts — the auth guard and app shell live in one `layout.tsx` instead of being repeated per page |
| **v0** | Generates a working scaffold in minutes; hours of UI time back for the parts judges actually see |
| **TypeScript** (`strict: true`) | The API contract becomes compile-time enforced — a renamed field fails the build, not the demo |
| **React** | Team already knows it |

> **Styling and component library are Nipuna's call** — Tailwind, CSS Modules, a component kit,
> whatever ships fastest at the quality bar they want. `docs/UI_SPEC.md` specifies what each
> screen must *do*; how it looks is deliberately left open.

---

## Backend — Manujaya

| Technology | Why |
|---|---|
| **Python 3.11+** | Same language as the agent service — one runtime to install, one set of idioms, and either person can read the other's code in a pinch |
| **FastAPI** | Async, fast, and **auto-generates OpenAPI docs at `/docs`** — Nipuna can inspect a live payload shape without reading Python |
| **Pydantic v2** | Request/response validation straight from type hints; models mirror `API_CONTRACT.md` one-to-one |
| **SQLAlchemy 2.0** | Mature async ORM with typed models |
| **Alembic** | Migrations — schema changes without hand-written SQL |
| **psycopg** (async) | The Postgres driver SQLAlchemy uses |
| **python-jose** | Verify the Supabase JWT signature at the gateway so no downstream service handles auth |
| **httpx** | Async HTTP client for calling the agent service, with real timeout support |
| **Uvicorn** | ASGI server |

> ✅ **Nothing to configure for casing.** Python, Pydantic, SQLAlchemy, Postgres, and our JSON
> contract are all `snake_case` natively. One convention across the entire system, set up by
> doing nothing.

---

## RAG + Agent — Lakshitha

| Technology | Why |
|---|---|
| **Python** | Where the AI ecosystem lives; every RAG library targets it first |
| **FastAPI** | Async, fast, auto-generated OpenAPI docs — the backend team can see the contract live |
| **LangChain** | Retrieval chains, agent tooling, and Azure integrations already built — we compose rather than write a RAG pipeline from scratch |
| **Uvicorn** | ASGI server FastAPI expects |
| **Pydantic** | Request/response validation; models mirror the backend's one-to-one |

---

## AI Models — Azure AI Foundry

| Model | Role | Why |
|---|---|---|
| **`text-embedding-3-small`** | Embeddings (1536-d) | ~5× cheaper and ~2× faster to index than `-3-large`; the recall difference is negligible on a hackathon corpus |
| **`gpt-4o-mini`** | Generation | Fast, cheap, strong at grounded extraction — and **shares a client, endpoint, and key with the embedding model** |

### The model decision — settled

**OpenAI models on Azure AI Foundry. Decided; not revisiting mid-hackathon.**

Both models share **one client, one endpoint, and one API key** — LangChain wires them up with
`AzureChatOpenAI` + `AzureOpenAIEmbeddings` against the same deployment. That's a single
integration, a single credential in `.env`, and a single thing to debug at 2am.

```
AZURE_OPENAI_ENDPOINT            ──┐
AZURE_OPENAI_API_KEY             ──┼── one Foundry resource, two deployments
AZURE_OPENAI_CHAT_DEPLOYMENT     ──┤   · gpt-4o-mini
AZURE_OPENAI_EMBEDDING_DEPLOYMENT──┘   · text-embedding-3-small
```

Everything stays on Azure and bills to one place, which matters if we're on credits.

> **The embedding model must never change after documents are indexed.** Vectors written by
> `text-embedding-3-small` are only comparable to query vectors from the same model. Swapping it
> means re-indexing every document — silently degraded retrieval otherwise, with no error to
> tell you.

---

## Vector Store — Azure AI Search (Free **F0** tier)

| Aspect | Detail |
|---|---|
| Why | Managed vector + keyword hybrid search with no infrastructure to run |
| Index | `content`, `content_vector` (1536-d, HNSW, cosine), `document_id`, `chunk_id`, `page`, `section` |
| Retrieval | Vector + BM25 fused, `top_k = 6` |

### ⚠️ Three F0 constraints to know before you design around them

**1. No semantic reranker.** That's a Basic-tier-and-above feature. If we need reranking, it's an
extra `gpt-4o-mini` call scoring the top-N candidates. **Do not architect around the built-in
ranker** — it isn't there.

**2. No managed identity → API keys only.** Already flagged in the stack table. This makes
`.env` hygiene load-bearing: a leaked key is a live key. `.gitignore` must cover `.env` **before
the first commit** — it's the first task in `docs/TASKS.md`.

**3. Hard limits:** 3 indexes · 50 MB total storage · 3 replicas/partitions. Fine for a hackathon
corpus of 20–50 documents. Worth knowing before anyone plans per-user indexes.

**Why hybrid rather than pure vector:** business documents are full of exact tokens embeddings
handle badly — invoice numbers (`INV-4471`), supplier names, amounts. BM25 nails those instantly.
Conversely *"which suppliers raised prices?"* shares no keywords with *"unit cost adjustment
effective July"* — that's the vector leg. Neither alone is sufficient.

---

## App Database — Azure Database for PostgreSQL

| Aspect | Detail |
|---|---|
| Why | Relational store for application state; managed, and SQLAlchemy + Alembic work cleanly with it |
| Tables | `documents`, `answers`, `agent_actions`, `conversations` |
| Owner | Backend only — the agent service never touches it |

**The split:** Postgres holds *what the user did*; Azure AI Search holds *what the AI retrieves*.
Keeping the agent service free of the app database means it can be restarted or redeployed
without risking user data.

> ⚠️ **Deletion crosses both stores.** `DELETE /api/v1/documents/{id}` must remove the Postgres
> row **and** the AI Search vectors. Orphaned vectors mean citing documents the user deleted.

---

## Auth — Supabase Auth

| Aspect | Detail |
|---|---|
| Why | Working email/password auth in ~15 minutes, with JWTs any backend can verify. Rolling our own would cost half a day for zero demo value. |
| Flow | Frontend signs in → JWT → `Authorization: Bearer` on every request → backend validates signature + expiry |
| Note | **The only piece outside Azure.** Accepted trade: the time saved is worth more than stack purity. |

---

## Deployment — Malindu

| Technology | Why |
|---|---|
| **Azure App Service** ×2 | Backend and agent service. Git-based deploy, health probes, env-var config. Agent service is **not publicly routable**. |
| **Azure Static Web Apps** | Purpose-built for Next.js; free tier, global CDN, GitHub-integrated |
| **GitHub Actions** | Push-to-deploy for all three services |
| **Bicep / az CLI** | Reproducible provisioning — recreate the stack if a resource is misconfigured |

---

## Repo

| Technology | Why |
|---|---|
| **GitHub** | Source of truth, PR review, CI/CD trigger, and the submission artifact |
| **`.gitignore`** | **`.env` covered before the first commit** — non-negotiable given API-key-only auth |
| **`.env.example`** | Every key name with dummy values, committed. A teammate goes from clone to running in two minutes. |

---

## Environment Variables

Full list lives in `.env.example`. Names here so everyone uses the same ones.

| Variable | Used by |
|---|---|
| `AZURE_OPENAI_ENDPOINT` | agent |
| `AZURE_OPENAI_API_KEY` | agent |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | agent |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | agent |
| `AZURE_SEARCH_ENDPOINT` | agent |
| `AZURE_SEARCH_API_KEY` | agent |
| `AZURE_SEARCH_INDEX_NAME` | agent |
| `AGENT_SERVICE_URL` | backend |
| `AGENT_SERVICE_KEY` | backend + agent (shared secret, `X-Internal-Key`) |
| `POSTGRES_CONNECTION_STRING` | backend |
| `SUPABASE_URL` | backend + frontend |
| `SUPABASE_ANON_KEY` | frontend |
| `SUPABASE_JWT_SECRET` | backend |
| `NEXT_PUBLIC_API_BASE_URL` | frontend |

**Anything prefixed `NEXT_PUBLIC_` is visible in the browser.** Never put a key behind that prefix.

---

## Prebuilt Components — disclose in the submission

Most hackathons require this, and it's easy to forget.

| Prebuilt | Custom-built by us |
|---|---|
| Azure AI Foundry models (`gpt-4o-mini`, `text-embedding-3-small`) | Chunking strategy, retrieval pipeline, prompts |
| Azure AI Search (index + hybrid query engine) | Index schema, agent action chain |
| LangChain framework | All chain composition and agent logic |
| Supabase Auth | Every API endpoint |
| Next.js, FastAPI, SQLAlchemy, Alembic | Entire frontend, API, and data model |
| v0 (initial UI scaffold) | Citation chips, action approval UX, all screens |

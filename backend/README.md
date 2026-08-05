# backend/ — FastAPI gateway

**Owner:** Manujaya (P3)
**Implements:** `docs/API_CONTRACT.md` **Part 1** (the public API)
**Talks to:** the browser (in), Postgres (owns), the agent service (out)

The browser only ever talks to this service. One origin, one auth surface, one
place secrets live. The agent service isn't publicly routable.

---

## Run it

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env          # then fill it in

python run.py                   # Windows  → http://localhost:5000/docs
uvicorn app.main:app --reload --port 5000   # Linux / Azure
```

> **Windows devs: use `run.py`.** psycopg's async mode cannot run on Windows'
> default `ProactorEventLoop`, and `uvicorn app.main:app` builds that loop before
> it imports the app — too late for the app to fix it. `run.py` sets the selector
> policy first, then starts uvicorn with reload. Symptom if you skip it:
> `InterfaceError: Psycopg cannot use the 'ProactorEventLoop'` on every query.

### Day-0 mode — nothing provisioned yet

Two switches in `.env` let the gateway run before Supabase, Postgres credentials,
or `agent/` exist:

| Setting | Effect |
|---|---|
| `AUTH_DISABLED=true` | Skip JWT verification, run every request as a fixed dev user |
| `AGENT_STUB_MODE=true` | Serve the contract's own example payloads instead of calling `agent/` |

Both log a loud warning at startup. **Neither goes anywhere near App Service config.**

With stub mode on, `POST /api/v1/ask` returns the §1.1 example — including the
`flag_invoice` suggested action for the *"which invoices are overdue"* question,
and the insufficient-evidence shape for anything unrelated. That's Nipuna's
integration target without waiting on retrieval.

### Migrations

```bash
alembic upgrade head
alembic revision --autogenerate -m "description"
```

The URL comes from `POSTGRES_CONNECTION_STRING` via `Settings` — `alembic.ini`
never holds a credential.

### Tests

```bash
pytest            # 21 contract tests, SQLite + stub agent, no network
ruff check .
```

---

## Layout

```
app/
  api/         routers — one file per resource, thin: parse, delegate, return
  core/        config · security (JWT) · errors · logging · dependencies
  db/          SQLAlchemy models, engine, session
  schemas/     Pydantic models mirroring the contract
  services/    business logic + the agent HTTP client
alembic/       migrations
tests/         contract conformance
run.py         local dev entrypoint (Windows)
```

## Endpoints

| Method | Path | Contract |
|---|---|---|
| `POST` | `/api/v1/ask` | §1.1 |
| `GET` `POST` | `/api/v1/documents` | §1.3 |
| `GET` `DELETE` | `/api/v1/documents/{id}` | §1.3 |
| `GET` `POST` | `/api/v1/agent-actions` | §1.4, §1.5 |
| `GET` `PATCH` | `/api/v1/agent-actions/{id}` | §1.6 |
| `GET` | `/health` | App Service probe (not versioned, no auth) |

Live shapes: **http://localhost:5000/docs**.

Every non-2xx returns the envelope — `{"error": {"code", "message", "details"}}` —
with the `code` values enumerated in the contract. Nothing escapes it: the
handlers in `app/core/errors.py` cover `AppError`, FastAPI validation errors,
`HTTPException`, and anything unhandled.

## How `/ask` is orchestrated

1. Verify the Supabase JWT, extract the user id.
2. **Guard:** the user must have ≥1 `indexed` document, else `422
   no_documents_indexed` — before any LLM call, so no tokens are wasted.
3. Resolve or create the conversation; load the **last turn only** for coreference.
4. `POST /rag/query` on the agent service — 30 s timeout, `504` on expiry.
5. Join `document_name` onto every citation from Postgres. The agent service
   returns `document_id` only and stays free of app-DB coupling.
6. `POST /agent/run` for the action proposal. Skipped when there's no grounded
   evidence, and a failure here degrades to `suggested_action: null` — a good
   cited answer shouldn't become a 502 because the action step had a bad minute.
7. Persist the answer row (the audit trail), return the §1.1 shape.

## Decisions taken while building this

| Decision | Why |
|---|---|
| Enums are `VARCHAR` + `CHECK`, not Postgres `ENUM` types | Adding a value later is a no-op instead of an `ALTER TYPE` that can't run inside a transaction |
| An unknown `conversation_id` starts a conversation under that id rather than 404ing | The client already holds the id; a 404 mid-typing is a worse failure than an empty history |
| A citation pointing at a missing document keeps its slot, named `(document unavailable)` | Dropping it would break the `[n]` markers already written into the answer text |
| Action citations are **copied** onto the action, not referenced | The audit trail has to survive the source document being deleted |
| `POST /agent-actions` snapshots *all* citations from `source_answer_id` | The §1.5 request body carries no `supporting_citations`, so the gateway can't narrow it without changing the frozen contract |
| A document owned by another user returns `404`, not `403` | Never confirm the existence of someone else's data |
| `/health` always returns `200`, with reachability in the body | A slow dependency shouldn't get the container recycled |
| Content type falls back to the file extension | Browsers send `application/octet-stream` for `.csv`/`.docx` often enough to lose real uploads |

## ⚠️ Open contract question — for the channel

**`DELETE /api/v1/documents/{id}` must remove the Azure AI Search vectors as well
as the Postgres row** (`ARCHITECTURE.md` § Where State Lives). But
`API_CONTRACT.md` **Part 2 has no delete endpoint** — only `/rag/ingest`,
`/rag/query`, `/agent/run`, `/health`. The gateway holds no AI Search credentials
by design, so it can't do the cleanup itself.

**Proposed:** add `DELETE /rag/documents/{document_id}` → `204` to Part 2.
Lakshitha to confirm, then the contract gets the edit with the usual 👍.

Until then `delete_document_vectors()` calls that path, treats `404/405/501` as
"not implemented yet", **logs a warning**, and lets the Postgres delete succeed —
so deletion works today, with orphaned vectors as the known, logged cost.

## Not built here

Retrieval, chunking, embeddings, prompts, and the action-classification chain all
live in `agent/`. This service never touches Azure AI Search or Azure AI Foundry.

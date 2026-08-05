"""Contract conformance — the shapes in docs/API_CONTRACT.md Part 1.

These run against the stub agent, so they check the gateway's own behaviour:
response shape, the error envelope, the guards, and the approval gate.
"""

from urllib.parse import quote

import pytest

pytestmark = pytest.mark.asyncio


# --- health ------------------------------------------------------------------


async def test_health_reports_dependencies(client):
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database_reachable"] is True
    assert body["agent_service_reachable"] is True


# --- auth --------------------------------------------------------------------


async def test_missing_token_returns_the_error_envelope(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "auth_disabled", False)
    response = await client.post("/api/v1/ask", json={"question": "anything"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


async def test_invalid_token_is_rejected(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "auth_disabled", False)
    monkeypatch.setattr(settings, "supabase_jwt_secret", "test-secret")
    response = await client.post(
        "/api/v1/ask",
        json={"question": "anything"},
        headers={"Authorization": "Bearer not-a-real-jwt"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


# --- §1.1 ask ----------------------------------------------------------------


INCIDENT_QUESTION = (
    "The water near Awa Reef has turned turquoise and the fish are leaving the area."
)
OFF_CORPUS_QUESTION = "What were the quarterly earnings of the Sydney branch?"


async def test_ask_without_an_indexed_corpus_is_422(client):
    response = await client.post("/api/v1/ask", json={"question": INCIDENT_QUESTION})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "corpus_not_indexed"


async def test_ask_returns_the_contract_shape(client, indexed_document):
    response = await client.post(
        "/api/v1/ask", json={"question": INCIDENT_QUESTION, "role_lens": "guardian"}
    )
    assert response.status_code == 200
    body = response.json()

    assert set(body) == {
        "answer_id",
        "conversation_id",
        "situation_report",
        "insufficient_evidence",
        "citations",
        "has_sufficient_evidence",
        "llm_call_count",
        "latency_ms",
    }
    assert body["has_sufficient_evidence"] is True
    assert body["insufficient_evidence"] is None
    # ≤ 8, hard cap.
    assert body["llm_call_count"] <= 8

    report = body["situation_report"]
    assert set(report) == {
        "priority",
        "affected_region_ids",
        "assembly_mode",
        "sections",
        "confidence",
        "conflicts",
        "was_partial",
    }
    # `class`, not `class_` — the alias has to survive serialization.
    assert report["priority"]["class"] == "W3"
    # An uncited severity would be an ungrounded model opinion.
    assert report["priority"]["citation"] is not None
    assert report["affected_region_ids"] == ["REG-01"]
    # The agent says "medium"; §1.1 says "moderate".
    assert report["confidence"]["level"] == "moderate"
    assert report["confidence"]["groundedness"] == 96


async def test_ask_sections_carry_only_the_three_content_sections_in_order(
    client, indexed_document
):
    body = (await client.post("/api/v1/ask", json={"question": INCIDENT_QUESTION})).json()
    sections = body["situation_report"]["sections"]

    assert [s["section_type"] for s in sections] == [
        "affected_species",
        "likely_causes",
        "recommended_actions",
    ]
    assert [s["display_order"] for s in sections] == [2, 3, 4]
    assert sections[0]["owning_agent"] == "marine_life_protector"
    # Markers are record IDs, not integers — the model cannot invent a plausible [7].
    assert "[FAU-001 p.11]" in sections[0]["content"]


async def test_ask_presents_conflicts_without_declaring_a_cause(client, indexed_document):
    body = (await client.post("/api/v1/ask", json={"question": INCIDENT_QUESTION})).json()
    conflict = body["situation_report"]["conflicts"][0]

    assert conflict["record_ids"] == ["FN-A", "FN-B", "LAB-C"]
    # The agent service calls it `nature`; §1.1 calls it `conflict_nature`.
    assert "incompatible causes" in conflict["conflict_nature"]
    assert [p["record_id"] for p in conflict["positions"]] == ["FN-A", "FN-B", "LAB-C"]
    # Every position names what limits it, and none is picked as the winner.
    assert all(p["reliability_limitation"] for p in conflict["positions"])


async def test_ask_citations_carry_record_ids_and_a_joined_document_name(
    client, indexed_document
):
    body = (await client.post("/api/v1/ask", json={"question": INCIDENT_QUESTION})).json()
    citation = body["citations"][0]

    assert set(citation) == {
        "marker",
        "document_id",
        "document_name",
        "chunk_id",
        "record_id",
        "record_type",
        "title",
        "chapter",
        "section",
        "page",
        "region_id",
        "excerpt",
        "relevance_score",
        "rerank_score",
        "evidence_quality",
        "risk_level",
        "record_date",
        "section_types",
    }
    assert citation["record_id"] == "INC-001"
    # The corpus's own taxonomy, carried verbatim.
    assert citation["evidence_quality"] == "provisional_interpretation"
    # document_name is joined on by the gateway; the agent service never sends it.
    assert citation["document_name"] == "Pandora_RAG_Knowledge_2026.pdf"


async def test_ask_handles_insufficient_evidence_as_a_200(client, indexed_document):
    response = await client.post("/api/v1/ask", json={"question": OFF_CORPUS_QUESTION})
    assert response.status_code == 200
    body = response.json()

    assert body["has_sufficient_evidence"] is False
    assert body["citations"] == []
    assert body["situation_report"]["confidence"]["level"] == "insufficient"
    assert body["situation_report"]["priority"]["class"] == "informational"

    refusal = body["insufficient_evidence"]
    # The brief's mandated sentence, verbatim. Not reworded, not truncated.
    assert refusal["message"] == (
        "The available Pandora knowledge base does not contain sufficient "
        "evidence to answer this question."
    )
    assert refusal["banner"].endswith("Recommend Field Investigation")
    assert refusal["what_would_resolve"]


async def test_ask_fills_empty_reason_on_every_unfilled_section(client, indexed_document):
    body = (await client.post("/api/v1/ask", json={"question": OFF_CORPUS_QUESTION})).json()
    unfilled = [s for s in body["situation_report"]["sections"] if s["status"] != "filled"]

    assert unfilled
    assert all(s["empty_reason"] for s in unfilled)


async def test_ask_reuses_the_conversation_id(client, indexed_document):
    first = (await client.post("/api/v1/ask", json={"question": INCIDENT_QUESTION})).json()
    second = await client.post(
        "/api/v1/ask",
        json={
            "question": "Which species are most at risk there?",
            "conversation_id": first["conversation_id"],
        },
    )
    assert second.status_code == 200
    assert second.json()["conversation_id"] == first["conversation_id"]


async def test_blank_question_returns_invalid_request(client):
    response = await client.post("/api/v1/ask", json={"question": "   "})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


# --- §1.2 the orchestration trace --------------------------------------------


async def _collect_stream(client, query: str) -> list[dict]:  # noqa: ANN001
    """Read an SSE response into a list of parsed events."""
    import json

    events: list[dict] = []
    async with client.stream("GET", f"/api/v1/ask/stream?{query}") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        # Buffering an event stream defeats the endpoint; §1.2 says so in bold.
        assert response.headers.get("x-accel-buffering") == "no"

        async for line in response.aiter_lines():
            if line.startswith("data:"):
                events.append(json.loads(line[5:].strip()))
    return events


async def test_stream_emits_the_trace_then_the_full_answer(client, indexed_document):
    events = await _collect_stream(client, f"question={quote(INCIDENT_QUESTION)}")

    step_types = [e["step_type"] for e in events]
    assert step_types[0] == "query.received"
    # The triage banner and the map light up before any section fills.
    assert step_types.index("priority.classified") < step_types.index("section.filling")
    assert "map.zone_lit" in step_types
    # Three specialists ignite together, then fill.
    assert step_types.count("section.filling") == 3
    assert step_types.count("section.completed") == 3
    assert "conflict.detected" in step_types
    assert "validation.result" in step_types

    # Monotonic, and terminal exactly once, at the end.
    sequence = [e["sequence_number"] for e in events]
    assert sequence == sorted(sequence)
    assert step_types.count("answer.completed") == 1
    assert step_types[-1] == "answer.completed"


async def test_stream_terminal_event_carries_the_whole_section_1_1_body(
    client, indexed_document
):
    events = await _collect_stream(client, f"question={quote(INCIDENT_QUESTION)}")
    payload = events[-1]["payload"]

    # A client can use this endpoint alone and never call POST /api/v1/ask.
    assert set(payload) == {
        "answer_id",
        "conversation_id",
        "situation_report",
        "insufficient_evidence",
        "citations",
        "has_sufficient_evidence",
        "llm_call_count",
        "latency_ms",
    }
    assert payload["situation_report"]["priority"]["class"] == "W3"
    # document_name is the gateway's join — proof this went through the mapper.
    assert payload["citations"][0]["document_name"] == "Pandora_RAG_Knowledge_2026.pdf"


async def test_stream_persists_the_report_and_its_trace(client, indexed_document, engine):
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models import Answer

    events = await _collect_stream(client, f"question={quote(INCIDENT_QUESTION)}")
    answer_id = events[-1]["payload"]["answer_id"]

    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with factory() as session:
        row = (await session.execute(select(Answer))).scalars().one()

    assert str(row.id) == answer_id
    assert row.situation_report["priority"]["class"] == "W3"
    # The trace is persisted for replay (§1.5).
    assert len(row.agent_steps) == len(events)
    assert row.agent_steps[0]["step_type"] == "query.received"


async def test_stream_refusal_is_a_normal_terminal_event(client, indexed_document):
    events = await _collect_stream(client, f"question={quote(OFF_CORPUS_QUESTION)}")
    payload = events[-1]["payload"]

    assert events[-1]["step_type"] == "answer.completed"
    assert payload["has_sufficient_evidence"] is False
    assert payload["insufficient_evidence"]["message"].startswith(
        "The available Pandora knowledge base"
    )


async def test_stream_does_not_buffer(engine, indexed_document, user_id, settings, monkeypatch):
    """§1.2's one bolded rule: events reach the client as they arrive.

    A buffering gateway looks identical to a working one until you time it —
    the whole trace lands at the end, and three orbs igniting at once becomes a
    single flash after five seconds.

    Timed against the generator, not through `client`: httpx's `ASGITransport`
    collects the whole body before returning, so an end-to-end timing here would
    prove nothing either way.
    """
    import time

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.schemas.ask import AskRequest
    from app.services import ask_stream as ask_stream_service
    from app.services.agent_client import AgentClient

    monkeypatch.setattr(settings, "stub_stream_delay_ms", 25)
    agent = AgentClient(settings)
    await agent.start()
    request = AskRequest(question=INCIDENT_QUESTION)

    async with async_sessionmaker(bind=engine, expire_on_commit=False)() as session:
        context = await ask_stream_service.prepare(session, user_id, request)
        await session.commit()

    started = time.perf_counter()
    arrivals = [
        time.perf_counter() - started
        async for _ in ask_stream_service.stream(agent, user_id, request, context)
    ]

    assert len(arrivals) > 10
    # The first event lands long before the last — nothing is held back.
    assert arrivals[0] < arrivals[-1] / 2


async def test_stream_without_an_indexed_corpus_is_422_not_an_event(client):
    response = await client.get(f"/api/v1/ask/stream?question={quote(INCIDENT_QUESTION)}")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "corpus_not_indexed"


async def test_stream_requires_a_token_when_auth_is_on(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "auth_disabled", False)
    response = await client.get(f"/api/v1/ask/stream?question={quote(INCIDENT_QUESTION)}")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


# --- §1.3 documents ----------------------------------------------------------


async def test_document_list_shape(client, indexed_document):
    response = await client.get("/api/v1/documents")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["limit"] == 50
    assert body["offset"] == 0
    assert set(body["documents"][0]) == {
        "id",
        "file_name",
        "content_type",
        "size_bytes",
        "page_count",
        "chunk_count",
        "status",
        "error_message",
        "uploaded_at",
        "indexed_at",
    }
    # ISO 8601 UTC with a trailing Z, per the contract.
    assert body["documents"][0]["uploaded_at"].endswith("Z")


async def test_upload_returns_202_pending_then_indexes(client):
    response = await client.post(
        "/api/v1/documents",
        files={"file": ("expenses-q2.csv", b"id,date,amount\n1,2026-07-01,100\n", "text/csv")},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "pending"
    assert body["chunk_count"] is None

    # The background ingest ran against the stub agent.
    polled = await client.get(f"/api/v1/documents/{body['id']}")
    assert polled.json()["status"] == "indexed"
    assert polled.json()["chunk_count"] == 23


async def test_upload_rejects_an_unsupported_type(client):
    response = await client.post(
        "/api/v1/documents",
        files={"file": ("photo.png", b"\x89PNG\r\n", "image/png")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_file_type"


async def test_upload_rejects_an_oversized_file(client, settings, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_bytes", 10)
    response = await client.post(
        "/api/v1/documents",
        files={"file": ("big.txt", b"x" * 100, "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "file_too_large"


async def test_unknown_document_is_404(client):
    response = await client.get("/api/v1/documents/3f2a0000-0000-4000-8000-000000000000")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "document_not_found"


async def test_delete_document_returns_204(client, indexed_document):
    response = await client.delete(f"/api/v1/documents/{indexed_document.id}")
    assert response.status_code == 204
    assert (await client.get(f"/api/v1/documents/{indexed_document.id}")).status_code == 404


# --- §1.4–1.6 agent actions --------------------------------------------------


ACTION_BODY = {
    "type": "flag_invoice",
    "title": "Flag invoice #4471 as overdue",
    "rationale": "32 days overdue and past the 30-day threshold where the 2% late fee applies.",
    "payload": {
        "invoice_number": "INV-4471",
        "supplier": "Silverline Supplies",
        "amount": 120000.00,
        "currency": "LKR",
        "due_date": "2026-07-04",
        "days_overdue": 32,
    },
}


async def test_create_action_persists_it_as_proposed(client, indexed_document):
    ask = (await client.post("/api/v1/ask", json={"question": INCIDENT_QUESTION})).json()

    response = await client.post(
        "/api/v1/agent-actions", json={**ACTION_BODY, "source_answer_id": ask["answer_id"]}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "proposed"
    assert body["resolved_at"] is None
    # Evidence is snapshotted from the source answer.
    assert body["citations"][0]["document_name"] == "Pandora_RAG_Knowledge_2026.pdf"


async def test_create_action_rejects_a_malformed_payload(client):
    response = await client.post(
        "/api/v1/agent-actions",
        json={**ACTION_BODY, "payload": {"invoice_number": "INV-4471"}},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


async def test_resolve_action_sets_resolved_at(client):
    created = (await client.post("/api/v1/agent-actions", json=ACTION_BODY)).json()
    response = await client.patch(
        f"/api/v1/agent-actions/{created['id']}",
        json={"status": "approved", "note": "Confirmed by phone."},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert response.json()["resolved_at"] is not None


async def test_resolving_twice_is_409(client):
    created = (await client.post("/api/v1/agent-actions", json=ACTION_BODY)).json()
    await client.patch(f"/api/v1/agent-actions/{created['id']}", json={"status": "approved"})
    response = await client.patch(
        f"/api/v1/agent-actions/{created['id']}", json={"status": "rejected"}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "action_already_resolved"


async def test_edited_payload_replaces_the_stored_one(client):
    draft = {
        "type": "draft_email",
        "title": "Payment reminder for INV-4471",
        "rationale": "32 days overdue.",
        "payload": {
            "to": "accounts@silverline.lk",
            "subject": "Overdue invoice INV-4471 — payment reminder",
            "body": "Dear Silverline Supplies,",
        },
    }
    created = (await client.post("/api/v1/agent-actions", json=draft)).json()
    edited = {**draft["payload"], "body": "Dear Silverline, please settle INV-4471."}
    response = await client.patch(
        f"/api/v1/agent-actions/{created['id']}", json={"status": "approved", "payload": edited}
    )
    assert response.status_code == 200
    assert response.json()["payload"]["body"] == "Dear Silverline, please settle INV-4471."


async def test_action_filters(client):
    await client.post("/api/v1/agent-actions", json=ACTION_BODY)
    proposed = await client.get("/api/v1/agent-actions?status=proposed")
    assert proposed.json()["total"] == 1
    approved = await client.get("/api/v1/agent-actions?status=approved")
    assert approved.json()["total"] == 0
    wrong_type = await client.get("/api/v1/agent-actions?type=create_task")
    assert wrong_type.json()["total"] == 0


async def test_unknown_action_is_404(client):
    response = await client.patch(
        "/api/v1/agent-actions/3f2a0000-0000-4000-8000-000000000000",
        json={"status": "approved"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "action_not_found"

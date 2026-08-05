"""Contract conformance — the shapes in docs/API_CONTRACT.md Part 1.

These run against the stub agent, so they check the gateway's own behaviour:
response shape, the error envelope, the guards, and the approval gate.
"""

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


async def test_ask_without_indexed_documents_is_422(client):
    response = await client.post("/api/v1/ask", json={"question": "Which invoices are overdue?"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "no_documents_indexed"


async def test_ask_returns_the_contract_shape(client, indexed_document):
    response = await client.post(
        "/api/v1/ask",
        json={"question": "Which invoices are overdue and who do I need to chase?"},
    )
    assert response.status_code == 200
    body = response.json()

    assert set(body) == {
        "answer_id",
        "conversation_id",
        "answer",
        "citations",
        "suggested_action",
        "confidence",
        "has_sufficient_evidence",
        "latency_ms",
    }
    assert body["confidence"] == "high"
    assert body["has_sufficient_evidence"] is True

    citation = body["citations"][0]
    assert set(citation) == {
        "marker",
        "document_id",
        "document_name",
        "page",
        "section",
        "excerpt",
        "relevance_score",
    }
    # document_name is joined on by the gateway; the agent service never sends it.
    assert citation["document_name"] == "invoices-july-2026.pdf"

    action = body["suggested_action"]
    assert action["type"] == "flag_invoice"
    assert action["supporting_citations"] == [1, 3]


async def test_ask_handles_insufficient_evidence_as_a_200(client, indexed_document):
    response = await client.post(
        "/api/v1/ask", json={"question": "What were our 2025 tax filings?"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["has_sufficient_evidence"] is False
    assert body["confidence"] == "insufficient"
    assert body["citations"] == []
    assert body["suggested_action"] is None


async def test_ask_reuses_the_conversation_id(client, indexed_document):
    first = (
        await client.post("/api/v1/ask", json={"question": "Which invoices are overdue?"})
    ).json()
    second = await client.post(
        "/api/v1/ask",
        json={
            "question": "And which supplier is worst?",
            "conversation_id": first["conversation_id"],
        },
    )
    assert second.json()["conversation_id"] == first["conversation_id"]


async def test_blank_question_returns_invalid_request(client):
    response = await client.post("/api/v1/ask", json={"question": "   "})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


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
    ask = (
        await client.post("/api/v1/ask", json={"question": "Which invoices are overdue?"})
    ).json()

    response = await client.post(
        "/api/v1/agent-actions", json={**ACTION_BODY, "source_answer_id": ask["answer_id"]}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "proposed"
    assert body["resolved_at"] is None
    # Evidence is snapshotted from the source answer.
    assert body["citations"][0]["document_name"] == "invoices-july-2026.pdf"


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

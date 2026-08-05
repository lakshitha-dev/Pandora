"""The streaming path against a *real* SSE server, not the stub.

`AGENT_STUB_MODE` replays a fixture list and never touches the wire, so these
tests stand up a fake agent service that frames its events exactly the way
`agent/`'s does — `sse_starlette` over `POST /agent/sitrep`, keep-alive comments
and all — and point the gateway's httpx client at it.

That covers what the stub cannot: SSE parsing, and the two shapes the terminal
event arrives in.
"""

import json

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from sse_starlette.sse import EventSourceResponse

from app.main import create_app

pytestmark = pytest.mark.asyncio

SITREP_BODY = {
    "situation_report": {
        "priority_class": "W2",
        "priority_label": "ALERT",
        "priority_reason": "Discolouration reported without species impact.",
        "priority_citation": "§4.5 Water Incident Classification",
        "priority_page": 12,
        "affected_region_ids": ["REG-01"],
        "assembly_mode": "sitrep",
        "confidence_level": "medium",
        "confidence_reason": "Moderate — 2 sources",
        "was_partial": False,
        "sections": [
            {
                "section_type": "likely_causes",
                "status": "filled",
                "empty_reason": None,
                "content": "Sediment plume documented [INC-001 p.40].",
                "claim_count": 1,
                "supported_claim_count": 1,
                "owning_agent": "incident_investigator",
                "duration_ms": 2100,
                "display_order": 3,
            }
        ],
    },
    "citations": [
        {
            "marker": 1,
            "document_id": "1a2b3c4d-2222-4e5f-9a8b-7c6d5e4f3a2b",
            "chunk_id": "chunk-0031",
            "record_id": "INC-001",
            "record_type": "incident",
            "title": "Turquoise Water Event",
            "chapter": "12 · Environmental Threats",
            "section": "Plausible causes",
            "page": 40,
            "region_id": "REG-01",
            "excerpt": "Plausible causes include mineral sediment...",
            "relevance_score": 0.9,
            "rerank_score": 9.0,
            "evidence_quality": "provisional_interpretation",
            "risk_level": "high",
            "record_date": None,
        }
    ],
    "grounding": {"groundedness": 91, "rules": [], "unsupported_sentences": []},
    "conflicts": [],
    "has_sufficient_evidence": True,
    "insufficient_evidence": None,
    "llm_call_count": 5,
    "duration_ms": 4100,
    "top_rerank_score": 9.0,
}

# The trace, minus the terminal event — the tests choose that per scenario.
TRACE_STEPS = [
    ("query.received", {"question": "the water near Awa Reef"}),
    ("priority.classified", {"class": "W2", "label": "ALERT"}),
    ("section.filling", {"section_type": "likely_causes"}),
    ("section.completed", {"section_type": "likely_causes", "claim_count": 1}),
    ("validation.result", {"groundedness": 91}),
]


def build_fake_agent(terminal_payload: dict) -> FastAPI:
    """An agent service that streams like the real one and answers JSON like it too."""
    app = FastAPI()

    @app.post("/agent/sitrep")
    async def sitrep(request: Request):  # noqa: ANN202
        if "text/event-stream" not in request.headers.get("accept", "").lower():
            return SITREP_BODY

        async def events():  # noqa: ANN202
            for sequence, (step_type, payload) in enumerate(TRACE_STEPS, start=1):
                yield {
                    "event": step_type,
                    "data": json.dumps(
                        {
                            "step_type": step_type,
                            "sequence_number": sequence,
                            "duration_ms": sequence * 100,
                            "payload": payload,
                        }
                    ),
                }
            yield {
                "event": "answer.completed",
                "data": json.dumps(
                    {
                        "step_type": "answer.completed",
                        "sequence_number": len(TRACE_STEPS) + 1,
                        "duration_ms": 4100,
                        "payload": terminal_payload,
                    }
                ),
            }

        return EventSourceResponse(events())

    return app


@pytest_asyncio.fixture
async def wired_client(engine, settings, monkeypatch, request):  # noqa: ANN001, ANN201
    """The gateway, with its agent client pointed at a fake agent over ASGI."""
    terminal_payload = request.param
    monkeypatch.setattr(settings, "agent_stub_mode", False)

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http_client:
        async with app.router.lifespan_context(app):
            app.state.agent_client._client = httpx.AsyncClient(
                transport=ASGITransport(app=build_fake_agent(terminal_payload)),
                base_url="http://agent",
            )
            yield http_client


async def collect(client, question: str) -> list[dict]:  # noqa: ANN001
    events: list[dict] = []
    async with client.stream("GET", "/api/v1/ask/stream", params={"question": question}) as r:
        assert r.status_code == 200
        async for line in r.aiter_lines():
            if line.startswith("data:"):
                events.append(json.loads(line[5:].strip()))
    return events


# The §1.2-conformant shape: the terminal event carries the whole §2.3 body.
CONFORMANT_TERMINAL = {**SITREP_BODY, "llm_call_count": 5, "latency_ms": 4100}
# What agent/ emits today: counts only.
COUNTS_ONLY_TERMINAL = {
    "llm_call_count": 5,
    "latency_ms": 4100,
    "citation_count": 1,
    "has_sufficient_evidence": True,
    "assembly_mode": "sitrep",
    "was_partial": False,
}


@pytest.mark.parametrize("wired_client", [CONFORMANT_TERMINAL], indirect=True)
async def test_frames_off_the_wire_are_parsed_and_forwarded(wired_client, indexed_document):
    events = await collect(wired_client, "the water near Awa Reef has turned turquoise")

    assert [e["step_type"] for e in events[:-1]] == [step for step, _ in TRACE_STEPS]
    assert events[0]["payload"]["question"] == "the water near Awa Reef"
    assert events[-1]["step_type"] == "answer.completed"

    payload = events[-1]["payload"]
    assert payload["situation_report"]["priority"]["class"] == "W2"
    assert payload["situation_report"]["confidence"]["level"] == "moderate"
    assert payload["citations"][0]["document_name"] == "Pandora_RAG_Knowledge_2026.pdf"


@pytest.mark.parametrize("wired_client", [COUNTS_ONLY_TERMINAL], indirect=True)
async def test_terminal_event_without_a_body_falls_back_to_a_json_call(
    wired_client, indexed_document
):
    """agent/ sends counts only today. The gateway still owes the client §1.1."""
    events = await collect(wired_client, "the water near Awa Reef has turned turquoise")
    payload = events[-1]["payload"]

    assert events[-1]["step_type"] == "answer.completed"
    assert payload["situation_report"]["priority"]["class"] == "W2"
    assert payload["has_sufficient_evidence"] is True
    assert payload["answer_id"]


@pytest.mark.parametrize("wired_client", [CONFORMANT_TERMINAL], indirect=True)
async def test_stream_persists_what_it_streamed(wired_client, indexed_document, engine):
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.db.models import Answer

    events = await collect(wired_client, "the water near Awa Reef has turned turquoise")

    async with async_sessionmaker(bind=engine, expire_on_commit=False)() as session:
        row = (await session.execute(select(Answer))).scalars().one()

    assert str(row.id) == events[-1]["payload"]["answer_id"]
    assert row.priority_class == "W2"
    assert [step["step_type"] for step in row.agent_steps] == [
        *(step for step, _ in TRACE_STEPS),
        "answer.completed",
    ]

"""Agent action shapes (API_CONTRACT §1.2, §1.4–1.6).

The three action types are fixed — see docs/PROJECT.md § Out of scope. Payloads
are validated per type so a malformed one fails at the boundary with a 400 rather
than rendering as a broken card in the inbox. Extra keys are allowed, so the
agent service can add a field without breaking the gateway.
"""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.schemas.common import ActionCitation, ActionStatus, ActionType, UtcDatetime


class _Payload(BaseModel):
    model_config = ConfigDict(extra="allow")


class FlagInvoicePayload(_Payload):
    invoice_number: str
    supplier: str
    amount: float
    currency: str
    due_date: str
    days_overdue: int


class DraftEmailPayload(_Payload):
    to: str
    subject: str
    body: str
    related_document_id: UUID | None = None


class CreateTaskPayload(_Payload):
    title: str
    description: str
    due_date: str | None = None
    priority: Literal["low", "medium", "high"]


PAYLOAD_MODELS: dict[str, type[_Payload]] = {
    "flag_invoice": FlagInvoicePayload,
    "draft_email": DraftEmailPayload,
    "create_task": CreateTaskPayload,
}


def validate_payload(action_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Check a payload against its type. Returns the payload unchanged on success."""
    model = PAYLOAD_MODELS.get(action_type)
    if model is None:
        raise ValueError(f"unknown action type: {action_type}")
    try:
        model.model_validate(payload)
    except ValidationError as exc:
        missing = ", ".join(".".join(str(p) for p in e["loc"]) for e in exc.errors())
        raise ValueError(f"payload is not a valid {action_type} payload: {missing}") from exc
    return payload


class AgentActionCreate(BaseModel):
    """§1.5 — the user accepted a suggested action."""

    type: ActionType
    title: str = Field(min_length=1, max_length=512)
    rationale: str = Field(min_length=1)
    payload: dict[str, Any]
    source_answer_id: UUID | None = None

    @field_validator("payload")
    @classmethod
    def _payload_shape(cls, value: dict[str, Any], info) -> dict[str, Any]:  # noqa: ANN001
        action_type = info.data.get("type")
        if action_type is None:  # `type` already failed; don't pile on.
            return value
        return validate_payload(action_type, value)


class AgentActionUpdate(BaseModel):
    """§1.6 — resolve an action. A non-null payload replaces the stored one."""

    status: Literal["approved", "rejected", "completed"]
    note: str | None = None
    payload: dict[str, Any] | None = None


class AgentActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: ActionType
    title: str
    rationale: str
    payload: dict[str, Any]
    status: ActionStatus
    source_answer_id: UUID | None = None
    citations: list[ActionCitation] = Field(default_factory=list)
    created_at: UtcDatetime
    resolved_at: UtcDatetime | None = None


class AgentActionListResponse(BaseModel):
    actions: list[AgentActionOut]
    total: int
    limit: int
    offset: int

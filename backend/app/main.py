from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlmodel import select

from app.db import create_db_and_tables, get_session
from app.models import AuditLogEntry, Batch, OutcomeStatus, RecoveryAttempt, RecoveryEvent
from app.services.actions import ARTIFACT_ACTIONS

app = FastAPI(title="Revenue Recovery Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()


class AttemptOut(BaseModel):
    attempt_number: int
    action_type: str
    rule_fired: str
    outcome_status: str
    outcome_reason: Optional[str] = None
    backoff_seconds_used: int
    real_notification_sent: bool
    notification_channels: Optional[str] = None
    created_at: datetime


class AuditOut(BaseModel):
    actor: str
    step_type: str
    message: str
    created_at: datetime


class EventOut(BaseModel):
    id: int
    batch_id: int
    customer_name: str
    customer_phone: str
    amount_inr: float
    source_type: str
    error_code: Optional[str] = None
    error_reason: Optional[str] = None
    root_cause_category: str
    status: str
    attempt_count: int
    is_genuine: bool
    message_sent: bool
    message_failed: bool
    real_notification_sent: bool
    recovered_amount_inr: float
    created_at: datetime
    attempts: list[AttemptOut]
    audit: list[AuditOut]


class BatchOut(BaseModel):
    id: int
    name: str
    started_at: datetime
    total_events: int
    total_amount_at_risk_inr: float
    total_recovered_inr: float


def _event_to_out(session, event: RecoveryEvent) -> EventOut:
    attempts = session.exec(
        select(RecoveryAttempt)
        .where(RecoveryAttempt.event_id == event.id)
        .order_by(RecoveryAttempt.attempt_number)
    ).all()
    audit_entries = session.exec(
        select(AuditLogEntry).where(AuditLogEntry.event_id == event.id).order_by(AuditLogEntry.created_at)
    ).all()

    link_attempts = [a for a in attempts if a.action_type in ARTIFACT_ACTIONS]
    message_failed = any(a.outcome_status == OutcomeStatus.ERROR for a in link_attempts)
    message_sent = any(a.outcome_status != OutcomeStatus.ERROR for a in link_attempts)
    real_notification_sent = any(a.real_notification_sent for a in attempts)

    return EventOut(
        id=event.id,
        batch_id=event.batch_id,
        customer_name=event.customer_name,
        customer_phone=event.customer_phone,
        amount_inr=event.amount_paise / 100,
        source_type=event.source_type,
        error_code=event.original_error_code,
        error_reason=event.original_error_reason,
        root_cause_category=event.root_cause_category,
        status=event.status,
        attempt_count=event.attempt_count,
        is_genuine=event.is_genuine,
        message_sent=message_sent,
        message_failed=message_failed,
        real_notification_sent=real_notification_sent,
        recovered_amount_inr=event.recovered_amount_paise / 100,
        created_at=event.created_at,
        attempts=[
            AttemptOut(
                attempt_number=a.attempt_number,
                action_type=a.action_type,
                rule_fired=a.rule_fired,
                outcome_status=a.outcome_status,
                outcome_reason=a.outcome_reason,
                backoff_seconds_used=a.backoff_seconds_used,
                real_notification_sent=a.real_notification_sent,
                notification_channels=a.notification_channels,
                created_at=a.created_at,
            )
            for a in attempts
        ],
        audit=[
            AuditOut(actor=e.actor, step_type=e.step_type, message=e.message, created_at=e.created_at)
            for e in audit_entries
        ],
    )


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/batches", response_model=list[BatchOut])
def list_batches() -> list[BatchOut]:
    session = get_session()
    batches = session.exec(select(Batch).order_by(Batch.id.desc())).all()

    out = []
    for b in batches:
        events = session.exec(select(RecoveryEvent).where(RecoveryEvent.batch_id == b.id)).all()
        recovered_paise = sum(e.recovered_amount_paise for e in events)
        at_risk_paise = sum(e.amount_paise for e in events)
        out.append(BatchOut(
            id=b.id,
            name=b.name,
            started_at=b.started_at,
            total_events=len(events),
            total_amount_at_risk_inr=at_risk_paise / 100,
            total_recovered_inr=recovered_paise / 100,
        ))
    return out


@app.get("/api/batches/{batch_id}/events", response_model=list[EventOut])
def list_events(batch_id: int) -> list[EventOut]:
    session = get_session()
    events = session.exec(
        select(RecoveryEvent).where(RecoveryEvent.batch_id == batch_id).order_by(RecoveryEvent.id)
    ).all()
    return [_event_to_out(session, e) for e in events]


@app.get("/api/events/{event_id}", response_model=EventOut)
def get_event(event_id: int) -> EventOut:
    session = get_session()
    event = session.get(RecoveryEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="event not found")
    return _event_to_out(session, event)

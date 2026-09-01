from datetime import datetime
from enum import StrEnum
from typing import Optional

from sqlmodel import Field, SQLModel


class SourceType(StrEnum):
    SUBSCRIPTION_CHARGE = "subscription_charge"
    PAYMENT_LINK = "payment_link"
    ORDER_CHECKOUT = "order_checkout"


class EventStatus(StrEnum):
    NEW = "new"
    DIAGNOSING = "diagnosing"
    RETRY_SCHEDULED = "retry_scheduled"
    ESCALATED = "escalated"
    RECOVERED = "recovered"
    UNRECOVERABLE = "unrecoverable"


TERMINAL_STATUSES = {EventStatus.ESCALATED, EventStatus.RECOVERED, EventStatus.UNRECOVERABLE}


class ActionType(StrEnum):
    RETRY_CHARGE = "retry_charge"
    SEND_PAYMENT_LINK = "send_payment_link"
    RESEND_LINK = "resend_link"
    ESCALATE_HUMAN = "escalate_human"
    NO_ACTION_RISK_BLOCK = "no_action_risk_block"


class OutcomeStatus(StrEnum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    ERROR = "error"


class Actor(StrEnum):
    RULE_ENGINE = "rule_engine"
    LLM = "llm"
    SYSTEM = "system"
    RAZORPAY_WEBHOOK = "razorpay_webhook"


class StepType(StrEnum):
    DIAGNOSIS = "diagnosis"
    DECISION = "decision"
    ACTION = "action"
    LLM_EXPLANATION = "llm_explanation"
    CUSTOMER_MESSAGE = "customer_message"
    STOP_RULE_TRIGGERED = "stop_rule_triggered"


class Batch(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_events: int = 0
    total_amount_at_risk_paise: int = 0
    total_recovered_paise: int = 0
    notes: Optional[str] = None


class RecoveryEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: int = Field(foreign_key="batch.id")

    source_type: SourceType
    razorpay_entity_id: str
    razorpay_payment_id: Optional[str] = None

    customer_name: str
    customer_email: str
    customer_phone: str

    amount_paise: int
    currency: str = "INR"

    original_error_code: Optional[str] = None
    original_error_reason: Optional[str] = None
    root_cause_category: str = "UNMAPPED"

    status: EventStatus = EventStatus.NEW
    attempt_count: int = 0
    next_action_at: Optional[datetime] = None

    is_genuine: bool = True

    recovered_amount_paise: int = 0
    recovered_at: Optional[datetime] = None

    created_at: datetime
    updated_at: datetime


class RecoveryAttempt(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: int = Field(foreign_key="recoveryevent.id")

    attempt_number: int
    action_type: ActionType
    rule_fired: str

    razorpay_action_ref: Optional[str] = None

    outcome_status: OutcomeStatus = OutcomeStatus.PENDING
    outcome_code: Optional[str] = None
    outcome_reason: Optional[str] = None

    backoff_seconds_used: int = 0
    real_notification_sent: bool = False

    created_at: datetime
    resolved_at: Optional[datetime] = None


class AuditLogEntry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: int = Field(foreign_key="recoveryevent.id")
    attempt_id: Optional[int] = Field(default=None, foreign_key="recoveryattempt.id")

    actor: Actor
    step_type: StepType
    message: str
    payload_json: str = "{}"

    created_at: datetime

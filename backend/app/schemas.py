from pydantic import BaseModel


class CategoryBreakdown(BaseModel):
    category: str
    total_events: int
    recovered_events: int
    recovery_rate_pct: float
    amount_at_risk_paise: int
    amount_recovered_paise: int


class BatchSummary(BaseModel):
    batch_id: int
    batch_name: str
    total_events: int
    genuine_events: int
    simulated_events: int
    total_amount_at_risk_paise: int
    total_recovered_paise: int
    overall_recovery_rate_pct: float
    escalated_count: int
    unrecoverable_count: int
    by_category: list[CategoryBreakdown]

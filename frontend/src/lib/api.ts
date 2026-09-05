export const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000"

export interface Attempt {
  attempt_number: number
  action_type: string
  rule_fired: string
  outcome_status: string
  outcome_reason: string | null
  backoff_seconds_used: number
  real_notification_sent: boolean
  notification_channels: string | null
  created_at: string
}

export interface AuditEntry {
  actor: string
  step_type: string
  message: string
  created_at: string
}

export interface RecoveryEvent {
  id: number
  batch_id: number
  customer_name: string
  customer_phone: string
  amount_inr: number
  source_type: string
  error_code: string | null
  error_reason: string | null
  root_cause_category: string
  status: string
  attempt_count: number
  is_genuine: boolean
  message_sent: boolean
  message_failed: boolean
  real_notification_sent: boolean
  recovered_amount_inr: number
  created_at: string
  attempts: Attempt[]
  audit: AuditEntry[]
}

export interface Batch {
  id: number
  name: string
  started_at: string
  total_events: number
  total_amount_at_risk_inr: number
  total_recovered_inr: number
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) {
    throw new Error(`${path} failed: ${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

export function fetchBatches(): Promise<Batch[]> {
  return getJson<Batch[]>("/api/batches")
}

export function fetchEvents(batchId: number): Promise<RecoveryEvent[]> {
  return getJson<RecoveryEvent[]>(`/api/batches/${batchId}/events`)
}

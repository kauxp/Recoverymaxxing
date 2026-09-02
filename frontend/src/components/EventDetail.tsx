import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { CategoryBadge, MessageBadge, StatusBadge } from "@/components/StatusBadge"
import { SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import type { RecoveryEvent } from "@/lib/api"
import { formatDateTime, formatInr, titleCase } from "@/lib/format"

export function EventDetail({ event }: { event: RecoveryEvent }) {
  return (
    <>
      <SheetHeader>
        <SheetTitle>{event.customer_name}</SheetTitle>
        <SheetDescription>
          Event #{event.id} &middot; {event.customer_phone} &middot; {formatDateTime(event.created_at)}
        </SheetDescription>
      </SheetHeader>

      <div className="flex flex-col gap-5 overflow-y-auto px-4 pb-6">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={event.status} />
          <CategoryBadge category={event.root_cause_category} />
          <MessageBadge sent={event.message_sent} real={event.real_notification_sent} />
          {!event.is_genuine && <Badge variant="outline">Simulated data</Badge>}
        </div>

        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <div className="text-muted-foreground">Amount at risk</div>
            <div className="font-medium">{formatInr(event.amount_inr)}</div>
          </div>
          <div>
            <div className="text-muted-foreground">Recovered</div>
            <div className="font-medium">{formatInr(event.recovered_amount_inr)}</div>
          </div>
        </div>

        <div>
          <h3 className="mb-1 text-sm font-medium">What failed</h3>
          <p className="text-sm text-muted-foreground">
            {event.error_reason ? titleCase(event.error_reason) : "Unknown"}
            {event.error_code ? ` (code: ${event.error_code})` : " (no Razorpay error code — a status state)"}
          </p>
        </div>

        <Separator />

        <div>
          <h3 className="mb-2 text-sm font-medium">Solution attempted ({event.attempts.length} attempt{event.attempts.length === 1 ? "" : "s"})</h3>
          <div className="flex flex-col gap-2">
            {event.attempts.map((a) => (
              <div key={a.attempt_number} className="rounded-lg border border-border p-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="font-medium">#{a.attempt_number} {titleCase(a.action_type)}</span>
                  <Badge variant={a.outcome_status === "success" ? "default" : a.outcome_status === "error" ? "destructive" : "secondary"}>
                    {titleCase(a.outcome_status)}
                  </Badge>
                </div>
                <div className="mt-1 text-xs text-muted-foreground">rule: {a.rule_fired}</div>
                {a.outcome_reason && <div className="mt-1 text-xs text-muted-foreground">{a.outcome_reason}</div>}
                {a.real_notification_sent && (
                  <div className="mt-1 text-xs font-medium text-sky-600">Real SMS/WhatsApp sent via Razorpay</div>
                )}
              </div>
            ))}
          </div>
        </div>

        <Separator />

        <div>
          <h3 className="mb-2 text-sm font-medium">Full reasoning trail</h3>
          <div className="flex flex-col gap-3 border-l border-border pl-3">
            {event.audit.map((entry, i) => (
              <div key={i}>
                <div className="text-xs text-muted-foreground">
                  {formatDateTime(entry.created_at)} &middot; {titleCase(entry.actor)} &middot; {titleCase(entry.step_type)}
                </div>
                <div className="text-sm">{entry.message}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  )
}

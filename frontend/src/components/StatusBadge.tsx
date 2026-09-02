import { Badge } from "@/components/ui/badge"
import { titleCase } from "@/lib/format"

const STATUS_VARIANT: Record<string, "default" | "secondary" | "destructive" | "outline"> = {
  recovered: "default",
  escalated: "secondary",
  unrecoverable: "destructive",
  retry_scheduled: "outline",
  new: "outline",
  diagnosing: "outline",
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <Badge variant={STATUS_VARIANT[status] ?? "outline"} className={status === "recovered" ? "bg-emerald-600 text-white" : undefined}>
      {titleCase(status)}
    </Badge>
  )
}

export function CategoryBadge({ category }: { category: string }) {
  return <Badge variant="outline">{titleCase(category)}</Badge>
}

export function MessageBadge({ sent, real }: { sent: boolean; real: boolean }) {
  if (!sent) {
    return <Badge variant="outline">No message</Badge>
  }
  return (
    <Badge variant={real ? "default" : "secondary"} className={real ? "bg-sky-600 text-white" : undefined}>
      {real ? "Sent (real)" : "Sent (simulated)"}
    </Badge>
  )
}

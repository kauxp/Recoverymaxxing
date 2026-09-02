import { useEffect, useMemo, useState } from "react"
import { Card, CardContent } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent } from "@/components/ui/sheet"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { CategoryBadge, MessageBadge, StatusBadge } from "@/components/StatusBadge"
import { EventDetail } from "@/components/EventDetail"
import { fetchBatches, fetchEvents, type Batch, type RecoveryEvent } from "@/lib/api"
import { formatInr, titleCase } from "@/lib/format"

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardContent className="px-4">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="mt-1 text-xl font-semibold">{value}</div>
      </CardContent>
    </Card>
  )
}

function App() {
  const [batches, setBatches] = useState<Batch[]>([])
  const [batchId, setBatchId] = useState<number | null>(null)
  const [events, setEvents] = useState<RecoveryEvent[]>([])
  const [selectedEvent, setSelectedEvent] = useState<RecoveryEvent | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchBatches()
      .then((data) => {
        setBatches(data)
        if (data.length > 0) setBatchId(data[0].id)
        setLoading(false)
      })
      .catch((err) => {
        setError(String(err))
        setLoading(false)
      })
  }, [])

  useEffect(() => {
    if (batchId === null) return
    fetchEvents(batchId)
      .then(setEvents)
      .catch((err) => setError(String(err)))
  }, [batchId])

  const totals = useMemo(() => {
    const atRisk = events.reduce((sum, e) => sum + e.amount_inr, 0)
    const recovered = events.reduce((sum, e) => sum + e.recovered_amount_inr, 0)
    const rate = atRisk > 0 ? (recovered / atRisk) * 100 : 0
    return { atRisk, recovered, rate }
  }, [events])

  if (loading) {
    return <div className="p-10 text-sm text-muted-foreground">Loading…</div>
  }

  if (error) {
    return (
      <div className="p-10 text-sm text-destructive">
        Could not reach the API at {import.meta.env.VITE_API_URL ?? "http://localhost:8000"}. Is the backend running? ({error})
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background p-6 md:p-10">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Revenue Recovery Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            What failed, why, what we did about it, and whether a message actually went out.
          </p>
        </div>
        {batches.length > 0 && (
          <Select value={batchId ? String(batchId) : undefined} onValueChange={(v) => setBatchId(Number(v))}>
            <SelectTrigger className="w-64">
              <SelectValue placeholder="Select a batch">
                {(value: string | null) => {
                  const batch = batches.find((b) => String(b.id) === value)
                  return batch ? `${batch.name} (#${batch.id}, ${batch.total_events} events)` : "Select a batch"
                }}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              {batches.map((b) => (
                <SelectItem key={b.id} value={String(b.id)}>
                  {b.name} (#{b.id}, {b.total_events} events)
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </header>

      {batches.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No batches yet — run <code>python scripts/run_batch.py</code> or{" "}
          <code>python scripts/evaluate_scenarios.py</code> in the backend first.
        </p>
      ) : (
        <>
          <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
            <StatCard label="Events" value={String(events.length)} />
            <StatCard label="At risk" value={formatInr(totals.atRisk)} />
            <StatCard label="Recovered" value={formatInr(totals.recovered)} />
            <StatCard label="Recovery rate" value={`${totals.rate.toFixed(1)}%`} />
          </div>

          <Card>
            <CardContent className="px-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Customer</TableHead>
                    <TableHead>Failure reason</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Attempts</TableHead>
                    <TableHead>Message</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                    <TableHead className="text-right">Recovered</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {events.map((e) => (
                    <TableRow key={e.id} className="cursor-pointer" onClick={() => setSelectedEvent(e)}>
                      <TableCell className="font-medium">{e.customer_name}</TableCell>
                      <TableCell className="text-muted-foreground">
                        {e.error_reason ? titleCase(e.error_reason) : "—"}
                      </TableCell>
                      <TableCell>
                        <CategoryBadge category={e.root_cause_category} />
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={e.status} />
                      </TableCell>
                      <TableCell>{e.attempt_count}</TableCell>
                      <TableCell>
                        <MessageBadge sent={e.message_sent} real={e.real_notification_sent} />
                      </TableCell>
                      <TableCell className="text-right">{formatInr(e.amount_inr)}</TableCell>
                      <TableCell className="text-right">{formatInr(e.recovered_amount_inr)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}

      <Sheet open={selectedEvent !== null} onOpenChange={(open) => !open && setSelectedEvent(null)}>
        <SheetContent className="overflow-y-auto sm:max-w-lg">
          {selectedEvent && <EventDetail event={selectedEvent} />}
        </SheetContent>
      </Sheet>
    </div>
  )
}

export default App

"use client"

import { useQuery } from "@tanstack/react-query"
import { apiClient, type ShipmentTokenUsage } from "@/lib/api-client"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
  ShieldCheck,
  FileSearch,
  Cpu,
  Zap,
  Hash,
  RefreshCw,
  TrendingUp,
  ChevronDown,
  ChevronUp,
  BarChart3,
} from "lucide-react"
import { useState, useMemo } from "react"
import { formatDistanceToNow } from "date-fns"
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts"

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return n.toLocaleString()
}

/** Returns a generic label for a model — hides vendor/model specifics. */
function maskedLabel(index: number): string {
  return index === 0 ? "AI Engine" : `AI Engine ${index + 1}`
}

const STEP_COLORS: Record<string, string> = {
  step2: "#6366f1",
  step6: "#10b981",
  vendor_validation: "#6366f1",
  boe_validation: "#10b981",
}

const STEP_LABELS: Record<string, string> = {
  step2: "Step 2 — Vendor",
  step6: "Step 6 — BOE",
  vendor_validation: "Step 2 — Vendor",
  boe_validation: "Step 6 — BOE",
}

const MODEL_COLORS = [
  "#6366f1", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4",
]

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatCard({
  label,
  value,
  sub,
  icon: Icon,
  color,
  loading,
}: {
  label: string
  value: string
  sub: string
  icon: React.ElementType
  color: string
  loading: boolean
}) {
  return (
    <Card className="p-6 hover:shadow-lg transition-shadow">
      <div className="flex items-start justify-between mb-4">
        <div>
          <p className="text-sm text-muted-foreground mb-1">{label}</p>
          <p className="text-3xl font-bold text-foreground">
            {loading ? <span className="animate-pulse text-muted-foreground">—</span> : value}
          </p>
        </div>
        <div className={`p-2 rounded-lg ${color}`}>
          <Icon className="w-6 h-6" />
        </div>
      </div>
      <p className="text-sm text-muted-foreground">{sub}</p>
    </Card>
  )
}

// Expandable row for the per-shipment token table
function ShipmentRow({
  s,
  idx,
  modelIndexMap,
}: {
  s: ShipmentTokenUsage
  idx: number
  modelIndexMap: Map<string, number>
}) {
  const [open, setOpen] = useState(false)
  const hasModels = s.by_model && s.by_model.length > 0

  return (
    <>
      <tr
        className={`border-b border-border hover:bg-muted/40 transition-colors cursor-pointer ${
          idx % 2 === 0 ? "bg-background" : "bg-muted/10"
        }`}
        onClick={() => hasModels && setOpen((v) => !v)}
      >
        {/* Step badge */}
        <td className="px-4 py-3 whitespace-nowrap">
          <Badge
            className="text-xs font-semibold"
            style={{
              background: STEP_COLORS[s.validation_type ?? s.step] + "22",
              color: STEP_COLORS[s.validation_type ?? s.step],
              border: `1px solid ${STEP_COLORS[s.validation_type ?? s.step]}44`,
            }}
          >
            {STEP_LABELS[s.validation_type ?? s.step] ?? s.step}
          </Badge>
        </td>

        {/* Shipment ID */}
        <td className="px-4 py-3 font-mono text-xs text-foreground max-w-[140px] truncate">
          {s.shipment_id}
        </td>

        {/* Docs processed */}
        <td className="px-4 py-3 text-center text-sm text-foreground">
          {s.documents_processed}
        </td>

        {/* Total tokens */}
        <td className="px-4 py-3 text-right text-sm font-medium text-foreground">
          {fmt(s.total_tokens)}
        </td>

        {/* Input tokens */}
        <td className="px-4 py-3 text-right text-sm text-muted-foreground">
          {fmt(s.input_tokens)}
        </td>

        {/* Output tokens */}
        <td className="px-4 py-3 text-right text-sm text-muted-foreground">
          {fmt(s.output_tokens)}
        </td>

        {/* AI calls */}
        <td className="px-4 py-3 text-right text-sm text-muted-foreground">
          {s.call_count}
        </td>

        {/* Date */}
        <td className="px-4 py-3 text-right text-xs text-muted-foreground whitespace-nowrap">
          {s.created_at
            ? formatDistanceToNow(new Date(s.created_at), { addSuffix: true })
            : "—"}
        </td>

        {/* Expand chevron */}
        <td className="px-4 py-3 text-center text-muted-foreground">
          {hasModels ? (
            open ? <ChevronUp className="w-4 h-4 inline" /> : <ChevronDown className="w-4 h-4 inline" />
          ) : null}
        </td>
      </tr>

      {/* Expanded model breakdown */}
      {open && hasModels && (
        <tr className="bg-muted/20">
          <td colSpan={9} className="px-6 py-3">
            <p className="text-xs font-semibold text-muted-foreground mb-2 uppercase tracking-wider">
              Engine breakdown
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-muted-foreground">
                    <th className="text-left pb-1 pr-4">Engine</th>
                    <th className="text-right pb-1 pr-4">Calls</th>
                    <th className="text-right pb-1 pr-4">Input</th>
                    <th className="text-right pb-1">Output</th>
                  </tr>
                </thead>
                <tbody>
                  {s.by_model.map((m, mi) => {
                    const key = `${m.provider}/${m.model}`
                    const idx = modelIndexMap.get(key) ?? mi
                    return (
                      <tr key={mi} className="border-t border-border/50">
                        <td className="py-1 pr-4">{maskedLabel(idx)}</td>
                        <td className="py-1 pr-4 text-right">{m.calls}</td>
                        <td className="py-1 pr-4 text-right">{fmt(m.input_tokens)}</td>
                        <td className="py-1 text-right">{fmt(m.output_tokens)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

// ---------------------------------------------------------------------------
// Main dashboard component
// ---------------------------------------------------------------------------

export default function PipelineDashboard() {
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["pipeline-stats"],
    queryFn: () => apiClient.getPipelineStats(),
    refetchInterval: 60_000,
    staleTime: 30_000,
  })

  // Stable index map: provider/model → index (used for consistent masking)
  const modelIndexMap = useMemo(() => {
    const map = new Map<string, number>()
    ;(data?.by_model ?? []).forEach((m, i) => {
      map.set(`${m.provider}/${m.model}`, i)
    })
    return map
  }, [data?.by_model])

  const stats = [
    {
      label: "Step 2 Shipments",
      value: data?.step2_shipments?.toLocaleString() ?? "—",
      sub: "Vendor document validations",
      icon: ShieldCheck,
      color: "bg-indigo-100 text-indigo-600 dark:bg-indigo-900/30 dark:text-indigo-400",
    },
    {
      label: "Step 6 Shipments",
      value: data?.step6_shipments?.toLocaleString() ?? "—",
      sub: "BOE cross-verifications",
      icon: FileSearch,
      color: "bg-emerald-100 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400",
    },
    {
      label: "Total Tokens",
      value: data ? fmt(data.total_tokens) : "—",
      sub: `${fmt(data?.total_input_tokens ?? 0)} in · ${fmt(data?.total_output_tokens ?? 0)} out`,
      icon: Cpu,
      color: "bg-violet-100 text-violet-600 dark:bg-violet-900/30 dark:text-violet-400",
    },
  ]

  // Bar chart data — tokens by engine (model names masked)
  const modelChartData = (data?.by_model ?? []).map((m, i) => ({
    name: maskedLabel(i),
    input: m.input_tokens,
    output: m.output_tokens,
    color: MODEL_COLORS[i % MODEL_COLORS.length],
  }))

  return (
    <div className="p-8 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-bold text-foreground mb-1">Pipeline Dashboard</h1>
          <p className="text-muted-foreground">
            Processing statistics and AI token usage across all shipments
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="flex items-center gap-2 px-4 py-2 text-sm rounded-lg border border-border hover:bg-muted transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${isFetching ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 text-destructive px-4 py-3 text-sm">
          Failed to load pipeline stats. Make sure the API is running.
        </div>
      )}

      {/* KPI cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {stats.map((s) => (
          <StatCard key={s.label} {...s} loading={isLoading} />
        ))}
      </div>

      {/* Charts + summary row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Token usage by engine — bar chart */}
        <Card className="p-6 lg:col-span-2">
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 className="w-5 h-5 text-muted-foreground" />
            <h2 className="text-lg font-semibold text-foreground">Token Usage by Engine</h2>
          </div>
          {isLoading ? (
            <div className="h-48 flex items-center justify-center text-muted-foreground text-sm animate-pulse">
              Loading chart…
            </div>
          ) : modelChartData.length === 0 ? (
            <div className="h-48 flex items-center justify-center text-muted-foreground text-sm">
              No data yet — run a shipment through Step 2 or Step 6
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={modelChartData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={(v) => fmt(v)} tick={{ fontSize: 11 }} width={55} />
                <Tooltip
                  formatter={(value: number, name: string) => [fmt(value), name === "input" ? "Input tokens" : "Output tokens"]}
                  contentStyle={{ fontSize: 12 }}
                />
                <Bar dataKey="input" name="input" stackId="a" radius={[0, 0, 2, 2]}>
                  {modelChartData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} fillOpacity={0.75} />
                  ))}
                </Bar>
                <Bar dataKey="output" name="output" stackId="a" radius={[2, 2, 0, 0]}>
                  {modelChartData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>

        {/* Pipeline breakdown summary */}
        <Card className="p-6">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-5 h-5 text-muted-foreground" />
            <h2 className="text-lg font-semibold text-foreground">Pipeline Breakdown</h2>
          </div>
          <div className="space-y-4">
            {/* Step 2 */}
            <div className="flex items-center justify-between py-3 border-b border-border">
              <div className="flex items-center gap-2">
                <span
                  className="w-3 h-3 rounded-full flex-shrink-0"
                  style={{ background: STEP_COLORS.vendor_validation }}
                />
                <div>
                  <p className="text-sm font-medium text-foreground">Step 2 — Vendor Docs</p>
                  <p className="text-xs text-muted-foreground">
                    {isLoading ? "…" : data?.step2_shipments ?? 0} shipments
                  </p>
                </div>
              </div>
              <span className="text-sm font-semibold text-foreground">
                {isLoading ? "—" : fmt(
                  (data?.shipments ?? [])
                    .filter((s) => (s.validation_type ?? s.step) === "vendor_validation" || s.step === "step2")
                    .reduce((a, s) => a + s.total_tokens, 0)
                )}
              </span>
            </div>

            {/* Step 6 */}
            <div className="flex items-center justify-between py-3 border-b border-border">
              <div className="flex items-center gap-2">
                <span
                  className="w-3 h-3 rounded-full flex-shrink-0"
                  style={{ background: STEP_COLORS.boe_validation }}
                />
                <div>
                  <p className="text-sm font-medium text-foreground">Step 6 — BOE Verify</p>
                  <p className="text-xs text-muted-foreground">
                    {isLoading ? "…" : data?.step6_shipments ?? 0} shipments
                  </p>
                </div>
              </div>
              <span className="text-sm font-semibold text-foreground">
                {isLoading ? "—" : fmt(
                  (data?.shipments ?? [])
                    .filter((s) => (s.validation_type ?? s.step) === "boe_validation" || s.step === "step6")
                    .reduce((a, s) => a + s.total_tokens, 0)
                )}
              </span>
            </div>

            {/* Avg per shipment */}
            <div className="flex items-center justify-between py-3">
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-amber-500 flex-shrink-0" />
                <div>
                  <p className="text-sm font-medium text-foreground">Avg per shipment</p>
                  <p className="text-xs text-muted-foreground">tokens</p>
                </div>
              </div>
              <span className="text-sm font-semibold text-foreground">
                {isLoading || !data
                  ? "—"
                  : data.shipments.length === 0
                  ? "—"
                  : fmt(Math.round(data.total_tokens / data.shipments.length))}
              </span>
            </div>
          </div>
        </Card>
      </div>

      {/* Per-shipment token usage table */}
      <Card className="overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div className="flex items-center gap-2">
            <Hash className="w-5 h-5 text-muted-foreground" />
            <h2 className="text-lg font-semibold text-foreground">Token Usage per Shipment</h2>
          </div>
          <span className="text-sm text-muted-foreground">
            {isLoading ? "—" : `${data?.shipments?.length ?? 0} shipments`}
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-muted/50 text-muted-foreground text-xs uppercase tracking-wider">
                <th className="px-4 py-3 text-left">Step</th>
                <th className="px-4 py-3 text-left">Shipment ID</th>
                <th className="px-4 py-3 text-center">Docs</th>
                <th className="px-4 py-3 text-right">Total Tokens</th>
                <th className="px-4 py-3 text-right">Input</th>
                <th className="px-4 py-3 text-right">Output</th>
                <th className="px-4 py-3 text-right">AI Calls</th>
                <th className="px-4 py-3 text-right">Age</th>
                <th className="px-4 py-3 text-center w-8"></th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i} className="border-b border-border">
                    {Array.from({ length: 9 }).map((_, j) => (
                      <td key={j} className="px-4 py-3">
                        <div className="h-4 bg-muted animate-pulse rounded" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : (data?.shipments ?? []).length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-6 py-12 text-center text-muted-foreground">
                    No shipments processed yet. Run a shipment through Step 2 or Step 6 to see token usage here.
                  </td>
                </tr>
              ) : (
                (data?.shipments ?? []).map((s, i) => (
                  <ShipmentRow
                    key={`${s.shipment_id}-${s.validation_type ?? s.step}`}
                    s={s}
                    idx={i}
                    modelIndexMap={modelIndexMap}
                  />
                ))
              )}
            </tbody>

            {/* Footer totals row */}
            {!isLoading && (data?.shipments ?? []).length > 0 && (
              <tfoot>
                <tr className="bg-muted/30 font-semibold text-foreground border-t-2 border-border">
                  <td className="px-4 py-3 text-xs uppercase text-muted-foreground" colSpan={3}>
                    Total
                  </td>
                  <td className="px-4 py-3 text-right">{fmt(data?.total_tokens ?? 0)}</td>
                  <td className="px-4 py-3 text-right text-muted-foreground">
                    {fmt(data?.total_input_tokens ?? 0)}
                  </td>
                  <td className="px-4 py-3 text-right text-muted-foreground">
                    {fmt(data?.total_output_tokens ?? 0)}
                  </td>
                  <td className="px-4 py-3 text-right text-muted-foreground">
                    {data?.total_llm_calls ?? 0}
                  </td>
                  <td colSpan={2} />
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      </Card>
    </div>
  )
}

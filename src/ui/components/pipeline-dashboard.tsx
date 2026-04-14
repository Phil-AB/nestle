"use client"

import { useQuery } from "@tanstack/react-query"
import { apiClient, type DashboardStatsResponse } from "@/lib/api-client"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
  Package,
  FileStack,
  ShieldCheck,
  FileSearch,
  ArrowRight,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Loader2,
} from "lucide-react"
import Link from "next/link"
import { formatDistanceToNow } from "date-fns"

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatCard({
  label,
  value,
  sub,
  icon: Icon,
  accent,
  loading,
}: {
  label: string
  value: string | number
  sub: string
  icon: React.ElementType
  accent: string
  loading: boolean
}) {
  return (
    <Card className="p-6 hover:shadow-md transition-shadow border-border/60">
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <p className="text-sm font-medium text-muted-foreground">{label}</p>
          <p className="text-3xl font-bold tracking-tight text-foreground">
            {loading ? (
              <Loader2 className="w-7 h-7 animate-spin text-muted-foreground" />
            ) : (
              value
            )}
          </p>
        </div>
        <div
          className="p-2.5 rounded-xl"
          style={{ background: accent + "18", color: accent }}
        >
          <Icon className="w-6 h-6" />
        </div>
      </div>
      <p className="text-xs text-muted-foreground mt-3">{sub}</p>
    </Card>
  )
}

function ProgressBar({
  value,
  max,
  color,
  label,
}: {
  value: number
  max: number
  color: string
  label: string
}) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-sm">
        <span className="text-foreground font-medium">{label}</span>
        <span className="text-muted-foreground tabular-nums">
          {value.toLocaleString()}
        </span>
      </div>
      <div className="h-2 rounded-full bg-muted overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
    </div>
  )
}

const BRAND = "#63513D"
const BRAND_LIGHT = "#8B7355"

const DOC_TYPE_COLORS: Record<string, string> = {
  invoice: "#63513D",
  packing_list: "#558B5E",
  bill_of_lading: "#5B7BA5",
  bill_of_entry: "#A0785A",
  airway_bill: "#7B6BA5",
  certificate_of_origin: "#8B6B5A",
}

const DOC_TYPE_LABELS: Record<string, string> = {
  invoice: "Invoices",
  packing_list: "Packing Lists",
  bill_of_lading: "Bills of Lading",
  bill_of_entry: "Bills of Entry",
  airway_bill: "Airway Bills",
  certificate_of_origin: "Certificates of Origin",
}

// ---------------------------------------------------------------------------
// Main dashboard
// ---------------------------------------------------------------------------

export default function PipelineDashboard() {
  const { data, isLoading, error, refetch, isFetching } =
    useQuery<DashboardStatsResponse>({
      queryKey: ["dashboard-stats"],
      queryFn: () => apiClient.getDashboardStats(),
      refetchInterval: 60_000,
      staleTime: 30_000,
    })

  const totalDocs = data?.total_documents ?? 0
  const docsComplete = data?.documents_by_status?.complete ?? 0
  const docsFailed = data?.documents_by_status?.failed ?? 0

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground tracking-tight">
            Dashboard
          </h1>
          <p className="text-muted-foreground mt-1">
            Shipment processing and document extraction overview
          </p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg border border-border hover:bg-muted transition-colors disabled:opacity-50"
        >
          {isFetching ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Clock className="w-4 h-4" />
          )}
          Refresh
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 text-destructive px-4 py-3 text-sm">
          Failed to load dashboard stats. Make sure the API is running.
        </div>
      )}

      {/* KPI cards row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <StatCard
          label="Total Shipments"
          value={data?.total_shipments ?? 0}
          sub={`${data?.shipments_by_status?.pending ?? 0} pending`}
          icon={Package}
          accent={BRAND}
          loading={isLoading}
        />
        <StatCard
          label="Documents Processed"
          value={totalDocs}
          sub={`${docsComplete} extracted, ${docsFailed} failed`}
          icon={FileStack}
          accent="#558B5E"
          loading={isLoading}
        />
        <StatCard
          label="Step 2 — Vendor"
          value={data?.pipeline?.step2_validated ?? 0}
          sub="Vendor document validations"
          icon={ShieldCheck}
          accent="#5B7BA5"
          loading={isLoading}
        />
        <StatCard
          label="Step 6 — BOE"
          value={data?.pipeline?.step6_validated ?? 0}
          sub="BOE cross-verifications"
          icon={FileSearch}
          accent="#A0785A"
          loading={isLoading}
        />
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Document breakdown */}
        <Card className="p-6 lg:col-span-3 border-border/60">
          <h2 className="text-lg font-semibold text-foreground mb-5">
            Documents by Type
          </h2>
          {isLoading ? (
            <div className="space-y-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <div
                  key={i}
                  className="h-10 bg-muted animate-pulse rounded-lg"
                />
              ))}
            </div>
          ) : totalDocs === 0 ? (
            <p className="text-muted-foreground text-sm py-8 text-center">
              No documents processed yet
            </p>
          ) : (
            <div className="space-y-4">
              {Object.entries(data?.documents_by_type ?? {})
                .sort(([, a], [, b]) => b - a)
                .map(([type, count]) => (
                  <ProgressBar
                    key={type}
                    value={count}
                    max={totalDocs}
                    color={
                      DOC_TYPE_COLORS[type] ??
                      BRAND_LIGHT
                    }
                    label={
                      DOC_TYPE_LABELS[type] ?? type.replace(/_/g, " ")
                    }
                  />
                ))}
            </div>
          )}
        </Card>

        {/* Extraction status */}
        <Card className="p-6 lg:col-span-2 border-border/60">
          <h2 className="text-lg font-semibold text-foreground mb-5">
            Extraction Status
          </h2>
          {isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <div
                  key={i}
                  className="h-8 bg-muted animate-pulse rounded-lg"
                />
              ))}
            </div>
          ) : (
            <div className="space-y-3">
              {Object.entries(data?.documents_by_status ?? {})
                .sort(([, a], [, b]) => b - a)
                .map(([status, count]) => {
                  const isOk = status === "complete"
                  const isErr = status === "failed"
                  return (
                    <div
                      key={status}
                      className="flex items-center justify-between py-2.5 px-3 rounded-lg bg-muted/50"
                    >
                      <div className="flex items-center gap-2.5">
                        {isOk ? (
                          <CheckCircle2 className="w-4 h-4 text-green-600" />
                        ) : isErr ? (
                          <AlertTriangle className="w-4 h-4 text-destructive" />
                        ) : (
                          <Clock className="w-4 h-4 text-amber-500" />
                        )}
                        <span className="text-sm font-medium capitalize text-foreground">
                          {status}
                        </span>
                      </div>
                      <Badge
                        variant="secondary"
                        className="tabular-nums text-xs"
                      >
                        {count.toLocaleString()}
                      </Badge>
                    </div>
                  )
                })}

              {/* Success rate */}
              {totalDocs > 0 && (
                <div className="pt-3 mt-2 border-t border-border">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">
                      Success rate
                    </span>
                    <span className="text-sm font-semibold text-foreground tabular-nums">
                      {((docsComplete / totalDocs) * 100).toFixed(1)}%
                    </span>
                  </div>
                </div>
              )}
            </div>
          )}
        </Card>
      </div>

      {/* Recent shipments */}
      <Card className="border-border/60 overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 className="text-lg font-semibold text-foreground">
            Recent Shipments
          </h2>
          <Badge variant="secondary" className="text-xs">
            {isLoading
              ? "..."
              : `${data?.recent_shipments?.length ?? 0} recent`}
          </Badge>
        </div>

        <div className="divide-y divide-border">
          {isLoading ? (
            Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="px-6 py-4">
                <div className="h-4 bg-muted animate-pulse rounded w-1/3" />
                <div className="h-3 bg-muted animate-pulse rounded w-1/4 mt-2" />
              </div>
            ))
          ) : (data?.recent_shipments ?? []).length === 0 ? (
            <div className="px-6 py-12 text-center text-muted-foreground text-sm">
              No shipments yet. Upload vendor documents to get started.
            </div>
          ) : (
            (data?.recent_shipments ?? []).map((s) => (
              <div
                key={s.id}
                className="px-6 py-3.5 flex items-center justify-between hover:bg-muted/30 transition-colors"
              >
                <div className="flex items-center gap-4">
                  <div
                    className="w-2 h-2 rounded-full flex-shrink-0"
                    style={{
                      background:
                        s.status === "validated"
                          ? "#558B5E"
                          : s.status === "errors"
                          ? "#DC2626"
                          : BRAND_LIGHT,
                    }}
                  />
                  <div>
                    <p className="text-sm font-medium text-foreground font-mono">
                      {s.shipment_number}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {s.supplier_name ?? "No supplier"}
                      {s.created_at && (
                        <>
                          {" "}
                          &middot;{" "}
                          {formatDistanceToNow(new Date(s.created_at), {
                            addSuffix: true,
                          })}
                        </>
                      )}
                    </p>
                  </div>
                </div>
                <Badge
                  variant={s.status === "validated" ? "default" : "secondary"}
                  className="text-xs capitalize"
                >
                  {s.status}
                </Badge>
              </div>
            ))
          )}
        </div>
      </Card>

      {/* Quick actions */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Link
          href="/validation/vendor-docs"
          className="group flex items-center justify-between p-5 rounded-xl border border-border/60 hover:border-primary/30 hover:shadow-sm transition-all bg-card"
        >
          <div className="flex items-center gap-4">
            <div
              className="p-2.5 rounded-xl"
              style={{ background: "#5B7BA518", color: "#5B7BA5" }}
            >
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <p className="text-sm font-semibold text-foreground">
                Vendor Validation
              </p>
              <p className="text-xs text-muted-foreground">
                Step 2 — Upload &amp; validate supplier documents
              </p>
            </div>
          </div>
          <ArrowRight className="w-4 h-4 text-muted-foreground group-hover:text-foreground group-hover:translate-x-1 transition-all" />
        </Link>

        <Link
          href="/validation/boe"
          className="group flex items-center justify-between p-5 rounded-xl border border-border/60 hover:border-primary/30 hover:shadow-sm transition-all bg-card"
        >
          <div className="flex items-center gap-4">
            <div
              className="p-2.5 rounded-xl"
              style={{ background: "#A0785A18", color: "#A0785A" }}
            >
              <FileSearch className="w-5 h-5" />
            </div>
            <div>
              <p className="text-sm font-semibold text-foreground">
                BOE Validation
              </p>
              <p className="text-xs text-muted-foreground">
                Step 6 — Cross-verify Bill of Entry
              </p>
            </div>
          </div>
          <ArrowRight className="w-4 h-4 text-muted-foreground group-hover:text-foreground group-hover:translate-x-1 transition-all" />
        </Link>
      </div>
    </div>
  )
}

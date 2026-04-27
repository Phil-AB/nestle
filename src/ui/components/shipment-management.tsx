"use client"

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { useRouter } from "next/navigation"
import { apiClient } from "@/lib/api-client"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import {
  Package,
  Truck,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Search,
  ChevronRight,
  Loader2,
} from "lucide-react"
import { formatDistanceToNow } from "date-fns"

const BRAND = "#63513D"
const BRAND_LIGHT = "#8B7355"

type StatusFilter = "all" | "pending" | "validated" | "errors"

function statusIcon(status: string) {
  if (status === "validated") return <CheckCircle2 className="w-4 h-4 text-green-600" />
  if (status === "errors") return <AlertTriangle className="w-4 h-4 text-destructive" />
  return <Clock className="w-4 h-4 text-amber-500" />
}

function statusDot(status: string) {
  const color =
    status === "validated" ? "#558B5E" : status === "errors" ? "#DC2626" : BRAND_LIGHT
  return <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: color }} />
}

export default function ShipmentManagement() {
  const router = useRouter()
  const [search, setSearch] = useState("")
  const [filterStatus, setFilterStatus] = useState<StatusFilter>("all")

  const { data, isLoading, error } = useQuery({
    queryKey: ["shipments-list"],
    queryFn: () => apiClient.listShipments(200),
    staleTime: 30_000,
    refetchInterval: 60_000,
  })

  const shipments = data?.shipments ?? []

  const filtered = shipments.filter(s => {
    const matchSearch =
      s.shipment_number.toLowerCase().includes(search.toLowerCase()) ||
      (s.supplier_name ?? "").toLowerCase().includes(search.toLowerCase()) ||
      (s.consignee_name ?? "").toLowerCase().includes(search.toLowerCase())
    const matchStatus = filterStatus === "all" || s.status === filterStatus
    return matchSearch && matchStatus
  })

  const counts = {
    total: shipments.length,
    pending: shipments.filter(s => s.status === "pending").length,
    validated: shipments.filter(s => s.status === "validated").length,
    errors: shipments.filter(s => s.status === "errors").length,
  }

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-foreground tracking-tight">Shipments</h1>
        <p className="text-muted-foreground mt-1">All shipments and their processing status.</p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          { label: "Total", value: counts.total, color: "text-foreground" },
          { label: "Pending", value: counts.pending, color: "text-amber-600" },
          { label: "Validated", value: counts.validated, color: "text-green-600" },
          { label: "Errors", value: counts.errors, color: "text-destructive" },
        ].map(c => (
          <Card key={c.label} className="p-4 border-border/60">
            <p className="text-xs text-muted-foreground mb-1">{c.label}</p>
            <p className={`text-2xl font-bold ${c.color}`}>
              {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : c.value}
            </p>
          </Card>
        ))}
      </div>

      {/* Search + filter */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="Search by shipment number, supplier, or consignee…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <div className="flex gap-2">
          {(["all", "pending", "validated", "errors"] as StatusFilter[]).map(s => (
            <button
              key={s}
              onClick={() => setFilterStatus(s)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium capitalize transition-colors ${
                filterStatus === s
                  ? "text-primary-foreground"
                  : "bg-muted text-foreground hover:bg-border"
              }`}
              style={filterStatus === s ? { background: BRAND } : undefined}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 text-destructive px-4 py-3 text-sm">
          Failed to load shipments. Make sure the API is running.
        </div>
      )}

      {/* List */}
      <Card className="border-border/60 overflow-hidden">
        <div className="divide-y divide-border">
          {isLoading ? (
            Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="px-6 py-4 space-y-2">
                <div className="h-4 bg-muted animate-pulse rounded w-1/4" />
                <div className="h-3 bg-muted animate-pulse rounded w-1/3" />
              </div>
            ))
          ) : filtered.length === 0 ? (
            <div className="px-6 py-16 text-center">
              <Package className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">
                {shipments.length === 0
                  ? "No shipments yet. Upload vendor documents to get started."
                  : "No shipments match your search."}
              </p>
            </div>
          ) : (
            filtered.map(s => (
              <button
                key={s.shipment_id}
                onClick={() => router.push(`/shipments/${s.shipment_id}`)}
                className="w-full px-6 py-4 flex items-center gap-4 hover:bg-muted/30 transition-colors text-left"
              >
                {statusDot(s.status)}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold font-mono text-foreground truncate">
                    {s.shipment_number}
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5 truncate">
                    {[s.supplier_name, s.consignee_name].filter(Boolean).join(" → ") || "No parties"}
                    {s.created_at && (
                      <> &middot; {formatDistanceToNow(new Date(s.created_at), { addSuffix: true })}</>
                    )}
                  </p>
                </div>
                <div className="flex items-center gap-3 flex-shrink-0">
                  {s.vendor_docs_count > 0 && (
                    <span className="text-xs text-muted-foreground hidden sm:block">
                      {s.vendor_docs_count} doc{s.vendor_docs_count !== 1 ? "s" : ""}
                    </span>
                  )}
                  <Badge
                    variant={s.status === "validated" ? "default" : "secondary"}
                    className="text-xs capitalize"
                  >
                    {s.status}
                  </Badge>
                  <ChevronRight className="w-4 h-4 text-muted-foreground" />
                </div>
              </button>
            ))
          )}
        </div>
      </Card>
    </div>
  )
}

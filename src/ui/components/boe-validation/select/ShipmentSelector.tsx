"use client"

import { useState, useEffect } from "react"
import { Input } from "@/components/ui/input"
import { Loader, Search, Package, Check } from "lucide-react"
import { apiClient } from "@/lib/api-client"
import type { Shipment } from "../lib/types"

interface ShipmentSelectorProps {
  selected: Shipment | null
  onSelect: (s: Shipment) => void
}

export function ShipmentSelector({
  selected,
  onSelect,
}: ShipmentSelectorProps) {
  const [shipments, setShipments] = useState<Shipment[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState("")
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    apiClient
      .listShipments(100)
      .then((res) => setShipments(res.shipments ?? []))
      .catch(() => setLoadError("Failed to load shipments"))
      .finally(() => setLoading(false))
  }, [])

  const filtered = shipments.filter(
    (s) =>
      s.shipment_number.toLowerCase().includes(search.toLowerCase()) ||
      (s.supplier_name ?? "").toLowerCase().includes(search.toLowerCase()) ||
      (s.consignee_name ?? "").toLowerCase().includes(search.toLowerCase())
  )

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
        <Loader className="w-4 h-4 animate-spin" />
        Loading shipments…
      </div>
    )
  }

  if (loadError) {
    return <p className="text-sm text-destructive py-2">{loadError}</p>
  }

  return (
    <div className="space-y-3">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search shipments…"
          className="pl-8 text-sm h-8"
        />
      </div>

      {filtered.length === 0 && (
        <p className="text-xs text-muted-foreground text-center py-4">
          {shipments.length === 0
            ? "No shipments found. Run Step 2 (Vendor Document Validation) first."
            : "No shipments match your search."}
        </p>
      )}

      <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
        {filtered.map((s) => {
          const isSelected = selected?.shipment_id === s.shipment_id
          return (
            <button
              key={s.shipment_id}
              onClick={() => onSelect(s)}
              className={`w-full flex items-center gap-3 p-3 rounded-lg border text-left transition-colors ${
                isSelected
                  ? "border-primary bg-primary/5"
                  : "border-border hover:border-primary/40 hover:bg-muted/30"
              }`}
            >
              <Package
                className={`w-4 h-4 flex-shrink-0 ${
                  isSelected ? "text-primary" : "text-muted-foreground"
                }`}
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <p className="text-sm font-semibold text-foreground truncate">
                    {s.shipment_number}
                  </p>
                  {(s.boe_version ?? 0) > 0 && (
                    <span className="text-[10px] font-bold px-1 py-0.5 rounded bg-primary/10 text-primary flex-shrink-0">
                      v{s.boe_version}
                    </span>
                  )}
                </div>
                <p className="text-xs text-muted-foreground truncate">
                  {s.supplier_name ?? "—"} → {s.consignee_name ?? "—"}
                </p>
              </div>
              <div className="flex-shrink-0 text-right">
                <span className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
                  {s.vendor_docs_count} doc{s.vendor_docs_count !== 1 ? "s" : ""}
                </span>
                {s.status && (
                  <p className="text-[10px] text-muted-foreground mt-0.5 capitalize">{s.status}</p>
                )}
              </div>
              {isSelected && <Check className="w-4 h-4 text-primary flex-shrink-0" />}
            </button>
          )
        })}
      </div>
    </div>
  )
}

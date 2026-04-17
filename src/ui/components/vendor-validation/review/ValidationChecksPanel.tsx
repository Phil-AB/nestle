"use client"

import { useState } from "react"
import { Card } from "@/components/ui/card"
import {
  ShieldCheck,
  CheckCircle,
  AlertCircle,
  ChevronDown,
  ChevronUp,
} from "lucide-react"
import { ConfidenceBadge } from "../shared/ConfidenceBadge"
import { formatValue } from "../lib/utils"

interface ValidationChecksPanelProps {
  results: any[]
}

export function ValidationChecksPanel({ results }: ValidationChecksPanelProps) {
  const [open, setOpen] = useState(false)
  const [filter, setFilter] = useState<"all" | "passed" | "failed">("failed")

  const filtered = results.filter((r) => {
    if (filter === "passed") return r.passed
    if (filter === "failed") return !r.passed
    return true
  })
  const passed = results.filter((r) => r.passed).length
  const failed = results.filter((r) => !r.passed).length

  return (
    <Card className="overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-muted/30 transition-colors text-left"
        onClick={() => setOpen(!open)}
      >
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-muted-foreground" />
          <span className="font-semibold text-sm text-foreground">All Validation Checks</span>
          <span className="text-[10px] font-mono text-muted-foreground">{results.length} total</span>
          <span className="text-[10px] text-green-600 font-semibold">{passed} passed</span>
          {failed > 0 && <span className="text-[10px] text-destructive font-semibold">{failed} failed</span>}
        </div>
        {open ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
      </button>

      {open && (
        <>
          <div className="px-4 py-2 border-t border-border flex items-center gap-1 bg-muted/20">
            {(["all", "passed", "failed"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`text-[10px] font-bold uppercase tracking-wide px-2 py-1 rounded transition-colors ${
                  filter === f ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {f === "all" ? `All (${results.length})` : f === "passed" ? `Passed (${passed})` : `Failed (${failed})`}
              </button>
            ))}
          </div>

          <div className="divide-y divide-border">
            {filtered.map((r, i) => (
              <div key={i} className={`flex items-start gap-3 px-4 py-2.5 ${!r.passed ? "bg-red-50/30 dark:bg-red-900/5" : ""}`}>
                <div className="flex-shrink-0 mt-0.5">
                  {r.passed ? (
                    <CheckCircle className="w-3.5 h-3.5 text-green-500" />
                  ) : (
                    <AlertCircle className="w-3.5 h-3.5 text-destructive" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-semibold text-foreground font-mono">
                      {r.field_name ?? r.validator_name}
                    </span>
                    {r.severity && r.severity === "critical" && (
                      <span className="text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">
                        {r.severity}
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-muted-foreground mt-0.5 leading-relaxed">{r.message}</p>
                  {!r.passed && (r.source_value !== undefined || r.target_value !== undefined) && (
                    <div className="flex gap-3 mt-1.5 flex-wrap">
                      {r.source_value !== undefined && (
                        <span className="text-[10px] font-mono bg-muted/60 px-1.5 py-0.5 rounded">
                          Got: {formatValue(r.source_value).slice(0, 120)}
                        </span>
                      )}
                      {r.target_value !== undefined && r.target_value !== null && (
                        <span className="text-[10px] font-mono bg-muted/60 px-1.5 py-0.5 rounded">
                          Expected: {formatValue(r.target_value).slice(0, 120)}
                        </span>
                      )}
                    </div>
                  )}
                </div>
                {typeof r.confidence === "number" && (
                  <ConfidenceBadge score={r.confidence} />
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </Card>
  )
}

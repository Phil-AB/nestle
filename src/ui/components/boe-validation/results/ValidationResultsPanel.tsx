"use client"

import { useState } from "react"
import { Card } from "@/components/ui/card"
import {
  ShieldCheck,
  CheckCircle,
  AlertCircle,
} from "lucide-react"
import { ConfidenceBadge, SeverityBadge } from "../shared/ConfidenceBadge"
import { formatValue } from "../lib/utils"

interface ValidationResultsPanelProps {
  results: any[]
}

export function ValidationResultsPanel({ results }: ValidationResultsPanelProps) {
  const [showAll, setShowAll] = useState(false)
  const [filter, setFilter] = useState<"all" | "passed" | "failed">("all")

  const filtered = results.filter((r) => {
    if (filter === "passed") return r.passed
    if (filter === "failed") return !r.passed
    return true
  })

  const displayed = showAll ? filtered : filtered.slice(0, 15)
  const passed = results.filter((r) => r.passed).length
  const failed = results.filter((r) => !r.passed).length

  return (
    <Card className="overflow-hidden">
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-muted-foreground" />
          <span className="font-semibold text-sm text-foreground">Validation Checks</span>
          <span className="text-[10px] font-mono text-muted-foreground">{results.length} total</span>
        </div>
        <div className="flex items-center gap-1">
          {(["all", "passed", "failed"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`text-[10px] font-bold uppercase tracking-wide px-2 py-1 rounded transition-colors ${
                filter === f
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {f === "all"
                ? `All (${results.length})`
                : f === "passed"
                ? `Passed (${passed})`
                : `Failed (${failed})`}
            </button>
          ))}
        </div>
      </div>

      <div className="divide-y divide-border">
        {displayed.map((result, i) => (
          <div
            key={i}
            className={`flex items-start gap-3 px-4 py-2.5 ${
              !result.passed ? "bg-red-50/30 dark:bg-red-900/5" : ""
            }`}
          >
            <div className="flex-shrink-0 mt-0.5">
              {result.passed ? (
                <CheckCircle className="w-3.5 h-3.5 text-green-500" />
              ) : (
                <AlertCircle className="w-3.5 h-3.5 text-destructive" />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs font-semibold text-foreground font-mono">
                  {result.field_name ?? result.validator_name}
                </span>
                <SeverityBadge severity={result.severity ?? "info"} />
              </div>
              <p className="text-[11px] text-muted-foreground mt-0.5 leading-relaxed">
                {result.message}
              </p>
              {!result.passed &&
                (result.source_value !== undefined || result.target_value !== undefined) && (
                  <div className="flex gap-3 mt-1.5 flex-wrap">
                    {result.source_value !== undefined && (
                      <span className="text-[10px] font-mono bg-muted/60 px-1.5 py-0.5 rounded text-foreground">
                        Got: {formatValue(result.source_value).slice(0, 120)}
                      </span>
                    )}
                    {result.target_value !== undefined && result.target_value !== null && (
                      <span className="text-[10px] font-mono bg-muted/60 px-1.5 py-0.5 rounded text-foreground">
                        Expected: {formatValue(result.target_value).slice(0, 120)}
                      </span>
                    )}
                  </div>
                )}
            </div>
            {typeof result.confidence === "number" && (
              <div className="flex-shrink-0 mt-0.5">
                <ConfidenceBadge score={result.confidence} />
              </div>
            )}
          </div>
        ))}
      </div>

      {filtered.length > 15 && (
        <div className="px-4 py-3 border-t border-border text-center">
          <button
            onClick={() => setShowAll(!showAll)}
            className="text-xs text-primary hover:underline font-medium"
          >
            {showAll ? "Show less" : `Show ${filtered.length - 15} more checks`}
          </button>
        </div>
      )}

      {filtered.length === 0 && (
        <div className="px-4 py-8 text-center text-xs text-muted-foreground">
          No results to show
        </div>
      )}
    </Card>
  )
}

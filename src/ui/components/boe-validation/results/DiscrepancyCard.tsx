"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  CheckCircle,
  X,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
} from "lucide-react"
import { SeverityBadge } from "../shared/ConfidenceBadge"
import type { ValidationDiscrepancy } from "../lib/types"
import { formatValue } from "../lib/utils"

interface DiscrepancyCardProps {
  disc: ValidationDiscrepancy
  confirmed: boolean | null
  onToggle: (id: string, value: boolean) => void
}

export function DiscrepancyCard({
  disc,
  confirmed,
  onToggle,
}: DiscrepancyCardProps) {
  const [expanded, setExpanded] = useState(true)
  const severityClass =
    disc.severity === "critical"
      ? "border-destructive/40 bg-destructive/5"
      : disc.severity === "major"
      ? "border-amber-400/40 bg-amber-50/30 dark:bg-amber-900/10"
      : "border-border bg-muted/20"

  return (
    <div className={`rounded-lg border p-4 ${severityClass}`}>
      <div
        className="flex items-start gap-3 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <AlertTriangle
          className={`w-4 h-4 mt-0.5 flex-shrink-0 ${
            disc.severity === "critical" ? "text-destructive" : "text-amber-500"
          }`}
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-sm text-foreground">
              {disc.field_name ?? disc.field ?? "—"}
            </span>
            <SeverityBadge severity={disc.severity} />
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            {disc.message ?? disc.description}
          </p>
        </div>
        {expanded ? (
          <ChevronUp className="w-4 h-4 text-muted-foreground flex-shrink-0" />
        ) : (
          <ChevronDown className="w-4 h-4 text-muted-foreground flex-shrink-0" />
        )}
      </div>

      {expanded && (
        <div className="mt-3 pl-7 space-y-3">
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="p-2 bg-card rounded border border-border">
              <p className="text-muted-foreground mb-0.5 text-[10px]">
                {disc.source_document ?? "Source"}
              </p>
              <p className="font-mono font-medium text-foreground truncate" title={formatValue(disc.source_value)}>
                {formatValue(disc.source_value)}
              </p>
            </div>
            <div className="p-2 bg-card rounded border border-border">
              <p className="text-muted-foreground mb-0.5 text-[10px]">
                {disc.target_document ?? "Expected"}
              </p>
              <p className="font-mono font-medium text-foreground truncate" title={formatValue(disc.target_value)}>
                {formatValue(disc.target_value)}
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant={confirmed === true ? "default" : "outline"}
              className={`text-xs flex-1 ${
                confirmed === true ? "bg-green-600 hover:bg-green-700 text-white" : ""
              }`}
              onClick={() => onToggle(disc.id, true)}
            >
              <CheckCircle className="w-3 h-3 mr-1.5" />
              Accept
            </Button>
            <Button
              size="sm"
              variant={confirmed === false ? "destructive" : "outline"}
              className="text-xs flex-1"
              onClick={() => onToggle(disc.id, false)}
            >
              <X className="w-3 h-3 mr-1.5" />
              Reject
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

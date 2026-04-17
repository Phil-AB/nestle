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

  return (
    <div className="rounded-lg border border-border bg-muted/20 p-4">
      <div className="flex items-start gap-3 cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0 text-amber-500" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-sm text-foreground">
              {disc.field_name ?? disc.field ?? "—"}
            </span>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">{disc.message ?? disc.description}</p>
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
              <p className="text-muted-foreground mb-0.5">{disc.source_document}</p>
              <p className="font-medium text-foreground truncate" title={formatValue(disc.source_value)}>{formatValue(disc.source_value)}</p>
            </div>
            <div className="p-2 bg-card rounded border border-border">
              <p className="text-muted-foreground mb-0.5">{disc.target_document}</p>
              <p className="font-medium text-foreground truncate" title={formatValue(disc.target_value)}>{formatValue(disc.target_value)}</p>
            </div>
          </div>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant={confirmed === true ? "default" : "outline"}
              className={`text-xs flex-1 ${confirmed === true ? "bg-green-600 hover:bg-green-700 text-white" : ""}`}
              onClick={() => onToggle(disc.id, true)}
            >
              <CheckCircle className="w-3 h-3 mr-1.5" />
              Accept Discrepancy
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

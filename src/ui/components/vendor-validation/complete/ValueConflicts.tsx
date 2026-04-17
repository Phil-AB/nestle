"use client"

import { Card } from "@/components/ui/card"
import { AlertTriangle, FileText } from "lucide-react"
import { DOC_LABEL } from "../lib/constants"
import { formatValue } from "../lib/utils"
import type { ValidationDiscrepancy } from "../lib/types"

// A "plain dict" means { doc_type: value } — not a scalar,
// not a {value, confidence} wrapper, not an array.
const isPlainDict = (v: any): v is Record<string, any> =>
  v !== null && v !== undefined &&
  typeof v === "object" && !Array.isArray(v) &&
  !("value" in v)

// Expand a value into per-document card entries.
const expandSide = (
  val: any,
  docName: string | null | undefined,
  role: "source" | "target" | "peer"
): { docKey: string; label: string; value: string; role: typeof role }[] => {
  if (val === null || val === undefined) return []
  if (isPlainDict(val)) {
    return Object.entries(val).map(([doc, v]) => ({
      docKey: doc,
      label: DOC_LABEL[doc] ?? doc.replace(/_/g, " "),
      value: formatValue(v),
      role,
    }))
  }
  // Scalar value — label with doc name if known, else "Expected Value"
  return [{
    docKey: docName ?? role,
    label: docName ? (DOC_LABEL[docName] ?? docName.replace(/_/g, " ")) : "Expected Value",
    value: formatValue(val),
    role,
  }]
}

interface ValueConflictsProps {
  mismatches: ValidationDiscrepancy[]
}

export function ValueConflicts({ mismatches }: ValueConflictsProps) {
  return (
    <Card className="overflow-hidden">
      <div className="px-5 py-3.5 border-b border-border flex items-center gap-2 bg-amber-50/40 dark:bg-amber-900/10">
        <AlertTriangle className="w-4 h-4 text-amber-500 flex-shrink-0" />
        <h3 className="font-semibold text-sm text-foreground">Value Conflicts</h3>
        <span className="text-[11px] text-muted-foreground ml-1">
          {mismatches.length} field{mismatches.length !== 1 ? "s" : ""} with conflicting values across documents
        </span>
      </div>
      <div className="divide-y divide-border/50">
        {mismatches.map((d) => {
          // Build flat card list:
          // • Pure n-way: source_value is dict, target_value absent → all peers
          // • Mixed/pairwise: expand each side; source entries = reference, target = conflict
          const isPureNWay = isPlainDict(d.source_value) && (d.target_value === null || d.target_value === undefined)

          const cards: { docKey: string; label: string; value: string; role: "source" | "target" | "peer" }[] =
            isPureNWay
              ? expandSide(d.source_value, null, "peer")
              : [
                  ...expandSide(d.source_value, d.source_document, "source"),
                  ...expandSide(d.target_value, d.target_document, "target"),
                ]

          return (
            <div key={d.id} className="px-5 py-4">
              <div className="flex items-start gap-2 mb-1">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-500 flex-shrink-0 mt-0.5" />
                <p className="text-sm font-semibold text-foreground">
                  {(d.field_name ?? d.field ?? "—").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                </p>
              </div>
              {d.message && <p className="text-xs text-muted-foreground mb-2 leading-relaxed pl-5">{d.message}</p>}
              <div className="grid gap-3 mt-3" style={{ gridTemplateColumns: `repeat(${Math.min(cards.length, 3)}, 1fr)` }}>
                {cards.map(({ docKey, label, value, role }) => (
                  <div
                    key={docKey}
                    className={`rounded-lg border-2 overflow-hidden ${
                      role === "source"
                        ? "border-amber-400 dark:border-amber-700"
                        : role === "target"
                        ? "border-amber-400 dark:border-amber-600"
                        : "border-border"
                    }`}
                  >
                    {/* Card header — document name is the primary identity */}
                    <div
                      className={`px-4 py-2.5 border-b flex items-center justify-between gap-3 ${
                        role === "source"
                          ? "bg-amber-50 dark:bg-amber-900/25 border-amber-200 dark:border-amber-700"
                          : role === "target"
                          ? "bg-amber-50 dark:bg-amber-900/25 border-amber-200 dark:border-amber-700"
                          : "bg-muted/40 border-border"
                      }`}
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <FileText
                          className={`w-3.5 h-3.5 flex-shrink-0 ${
                            role === "source"
                              ? "text-amber-600 dark:text-amber-500"
                              : role === "target"
                              ? "text-amber-500 dark:text-amber-400"
                              : "text-muted-foreground"
                          }`}
                        />
                        <p
                          className={`text-[12px] font-bold truncate ${
                            role === "source"
                              ? "text-amber-900 dark:text-amber-300"
                              : role === "target"
                              ? "text-amber-800 dark:text-amber-300"
                              : "text-foreground"
                          }`}
                        >
                          {label}
                        </p>
                      </div>
                      {role !== "peer" && (
                        <span
                          className={`text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded flex-shrink-0 ${
                            role === "source"
                              ? "bg-amber-100 dark:bg-amber-900/50 text-amber-800 dark:text-amber-300"
                              : "bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300"
                          }`}
                        >
                          {role === "source" ? "Source" : "Conflict"}
                        </span>
                      )}
                    </div>
                    {/* Card body — extracted value */}
                    <div className="px-4 py-3 bg-background">
                      <code className="text-sm font-mono text-foreground break-all leading-relaxed">{value}</code>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </Card>
  )
}

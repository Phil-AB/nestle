"use client"

import { Card } from "@/components/ui/card"
import {
  ClipboardCheck,
  CheckCircle,
  AlertTriangle,
  X,
  FileText,
  Info,
} from "lucide-react"
import { BOE_CHECKLIST, GRA_TRANSPORT_CODES } from "../lib/constants"
import type { ExtractedDocumentMeta, ValidationDiscrepancy, BOEChecklistEntry } from "../lib/types"
import { unwrap } from "../lib/utils"

interface BOEChecklistProps {
  extractedBOE: ExtractedDocumentMeta
  validationResults: any[]
  discrepancies: ValidationDiscrepancy[]
}

export function BOEChecklist({
  extractedBOE,
  validationResults,
  discrepancies,
}: BOEChecklistProps) {
  const fields = extractedBOE.fields ?? {}

  const resolveVal = (fieldNames: string[]): string | null => {
    for (const f of fieldNames) {
      const v = fields[f]
      if (v == null) continue
      const s = unwrap(v).trim()
      if (s) return s
    }
    return null
  }

  const valLookup = validationResults.reduce((acc: Record<string, any>, r: any) => {
    const f = r.field_name ?? ""
    if (f && !acc[f]) acc[f] = r
    return acc
  }, {} as Record<string, any>)

  const backendStatus = (entry: BOEChecklistEntry): "passed" | "failed" | null => {
    for (const f of entry.backendFields) {
      const r = valLookup[f]
      if (r !== undefined) return r.passed ? "passed" : "failed"
    }
    return null
  }

  // Returns the N/A reason message when a backend result explicitly marks a field
  // as not applicable (e.g. ETLS for CPC codes that don't require it)
  const notApplicableReason = (entry: BOEChecklistEntry): string | null => {
    for (const f of entry.backendFields) {
      const r = valLookup[f]
      if (r?.passed === true && r?.metadata?.not_applicable === true) {
        return r.metadata.reason ?? r.message ?? "Not applicable"
      }
    }
    return null
  }

  // Translate known GRA ICUMS transport codes to human-readable labels
  const translateVal = (entry: BOEChecklistEntry, raw: string | null): string | null => {
    if (!raw) return raw
    if (entry.id === "mode_of_shipment") {
      const label = GRA_TRANSPORT_CODES[raw.trim()]
      return label ? `${label} (${raw})` : raw
    }
    return raw
  }

  const discLookup = discrepancies.reduce((acc: Record<string, ValidationDiscrepancy>, d) => {
    const f = d.field_name ?? (d as any).field ?? ""
    if (f && !acc[f]) acc[f] = d
    return acc
  }, {} as Record<string, ValidationDiscrepancy>)

  const hasDisc = (entry: BOEChecklistEntry): boolean =>
    entry.backendFields.some((f) => !!discLookup[f]) ||
    entry.fieldNames.some((f) => !!discLookup[f])

  return (
    <Card className="overflow-hidden">
      <div className="px-5 py-3.5 border-b border-border flex items-center gap-3 bg-muted/20">
        <ClipboardCheck className="w-4 h-4 text-muted-foreground flex-shrink-0" />
        <h3 className="font-semibold text-foreground text-sm">BOE Checklist</h3>
        <span className="text-[11px] text-muted-foreground">{BOE_CHECKLIST.length} checks</span>
        <div className="flex items-center gap-3 ml-auto text-[11px] text-muted-foreground">
          <span className="flex items-center gap-1"><CheckCircle className="w-3 h-3 text-green-500" /> Present</span>
          <span className="flex items-center gap-1"><AlertTriangle className="w-3 h-3 text-amber-500" /> Conflict</span>
          <span className="flex items-center gap-1"><X className="w-3 h-3 text-destructive" /> Missing</span>
          <span className="flex items-center gap-1"><Info className="w-3 h-3 text-muted-foreground" /> N/A</span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr className="border-b-2 border-border bg-muted/30">
              <th className="sticky left-0 z-10 bg-muted/30 text-center px-3 py-2.5 text-[11px] font-bold uppercase tracking-widest text-muted-foreground border-r border-border w-10 select-none">#</th>
              <th className="sticky left-10 z-10 bg-muted/30 text-left px-4 py-2.5 text-[11px] font-bold uppercase tracking-widest text-muted-foreground border-r border-border min-w-[190px]">Checklist Item</th>
              <th className="text-left px-4 py-2.5 text-[11px] font-bold uppercase tracking-wide text-muted-foreground min-w-[320px]">
                <div className="flex items-center gap-1.5">
                  <FileText className="w-3 h-3" />
                  Bill of Entry
                </div>
              </th>
            </tr>
          </thead>
          <tbody>
            {BOE_CHECKLIST.map((entry, i) => {
              const rawVal = resolveVal(entry.fieldNames)
              const val = translateVal(entry, rawVal)
              const isEmpty = !rawVal || rawVal.trim() === ""
              const status = backendStatus(entry)
              const naReason = notApplicableReason(entry)
              const isNotApplicable = !!naReason && isEmpty
              const isConflict = hasDisc(entry) && !isEmpty
              const isMissing = !isNotApplicable && (status === "failed" || (status === null && isEmpty))
              const rowHasIssue = isMissing || isConflict
              const rowBg = rowHasIssue ? "bg-red-50/30 dark:bg-red-900/5" : i % 2 === 1 ? "bg-muted/10" : ""
              const stickyBg = rowHasIssue ? "bg-red-50/60 dark:bg-red-900/10" : i % 2 === 1 ? "bg-muted/20" : "bg-background"

              return (
                <tr key={entry.id} className={`border-b border-border/40 last:border-b-0 ${rowBg}`}>
                  <td className={`sticky left-0 z-10 text-center px-3 py-2 text-[11px] font-mono text-muted-foreground border-r border-border w-10 select-none ${stickyBg}`}>{i + 1}</td>
                  <td className={`sticky left-10 z-10 px-4 py-2.5 text-[12px] font-semibold border-r border-border whitespace-nowrap text-foreground ${stickyBg}`}>
                    {entry.label}
                  </td>
                  <td className="px-4 py-2.5 align-middle">
                    {isNotApplicable ? (
                      <span className="flex items-start gap-1.5 text-[12px] text-muted-foreground" title={naReason ?? undefined}>
                        <Info className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
                        <span className="leading-snug">N/A<span className="ml-1 text-[11px] opacity-70">— {naReason}</span></span>
                      </span>
                    ) : isMissing && !isConflict ? (
                      <span className="flex items-center gap-1.5 text-[12px] text-destructive font-medium">
                        <X className="w-3.5 h-3.5 flex-shrink-0" />
                        Missing
                      </span>
                    ) : isConflict ? (
                      <span className="flex items-start gap-1.5 text-[12px] text-amber-700 dark:text-amber-400">
                        <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
                        <span className="font-mono break-all leading-snug">{val}</span>
                      </span>
                    ) : (
                      <span className="flex items-start gap-1.5 text-[12px] text-foreground">
                        <CheckCircle className="w-3.5 h-3.5 text-green-500 flex-shrink-0 mt-0.5" />
                        <span className="font-mono break-all leading-snug">{val}</span>
                      </span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

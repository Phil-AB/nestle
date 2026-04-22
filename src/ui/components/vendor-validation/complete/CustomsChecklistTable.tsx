"use client"

import { Card } from "@/components/ui/card"
import {
  ClipboardCheck,
  CheckCircle,
  AlertTriangle,
  X,
  FileText,
} from "lucide-react"
import { RedactedBadge } from "../shared/ConfidenceBadge"
import { unwrap } from "../lib/utils"
import { DOC_LABEL, DOC_ORDER, CHECKLIST } from "../lib/constants"
import type { ExtractedDocumentMeta, ValidationDiscrepancy, ChecklistEntry } from "../lib/types"

interface CustomsChecklistTableProps {
  extractedDocuments: Record<string, ExtractedDocumentMeta>
  discrepancies: ValidationDiscrepancy[]
  validationResults: any[]
}

export function CustomsChecklistTable({
  extractedDocuments,
  discrepancies,
  validationResults,
}: CustomsChecklistTableProps) {
  const docs = Object.keys(extractedDocuments).sort(
    (a, b) => DOC_ORDER.indexOf(a) - DOC_ORDER.indexOf(b)
  )

  // Discrepancy lookup: "doc::field" -> discrepancy
  const discLookup = (discrepancies ?? []).reduce((acc, d) => {
    const key = `${d.source_document ?? ""}::${d.field_name ?? d.field ?? ""}`
    acc[key] = d
    return acc
  }, {} as Record<string, ValidationDiscrepancy>)

  // Backend validation result lookup: "doc::fieldName" → result object.
  const valResultLookup = (validationResults ?? []).reduce((acc: Record<string, any>, r: any) => {
    const doc = r.source_document ?? ""
    const field = r.field_name ?? ""
    if (doc && field) {
      const key = `${doc}::${field}`
      if (!acc[key]) acc[key] = r
    }
    return acc
  }, {} as Record<string, any>)

  /**
   * Look up backend validation status for a checklist entry on a specific doc.
   */
  const backendStatus = (
    entry: ChecklistEntry, doc: string
  ): { status: "passed" | "failed" | null; backendVal: string | null } => {
    for (const fieldName of entry.backendFields) {
      const r = valResultLookup[`${doc}::${fieldName}`]
      if (r !== undefined) {
        let bv: string | null = null
        const sv = r.source_value
        if (sv !== null && sv !== undefined) {
          if (typeof sv === "object" && !Array.isArray(sv) && "value" in sv) {
            bv = sv.value != null ? String(sv.value) : null
          } else if (typeof sv === "object" && !Array.isArray(sv)) {
            const v = sv[doc]
            bv = v != null ? String(unwrap(v)) : null
          } else {
            bv = String(sv)
          }
        }
        return { status: r.passed ? "passed" : "failed", backendVal: bv }
      }
    }
    return { status: null, backendVal: null }
  }

  // Incoterm rule check
  const incotermRuleResult = (validationResults ?? []).find(
    (r) => (r.field_name === "freight_insurance" || r.validator_name === "incoterm_validator") && r.passed
  )
  const incotermRulePassed = !!incotermRuleResult
  const incotermCode = (() => {
    const raw: string =
      incotermRuleResult?.source_value ??
      incotermRuleResult?.metadata?.incoterm ??
      ""
    const m = String(raw).match(/\b([A-Z]{3})\b/)
    return m ? m[1] : null
  })()

  const _DESC_FIELD_IDS = new Set(["description", "goods_description", "product_description", "article_description", "description_of_goods", "kind_of_packages_description_of_goods"])
  const _CONTAINER_IDS  = new Set(["container_count", "container_numbers", "container_no", "container_nos"])
  const _QTY_FIELD_IDS  = new Set(["quantity", "total_units", "total_sent_units", "total_packages", "totals", "total_qty"])
  const _DESC_SKIP = new Set(["CONTAINER SAID TO CONTAIN", ""])

  const resolveVal = (spec: string | string[], data: Record<string, any>, items?: any[]): string | null => {
    const specs = Array.isArray(spec) ? spec : [spec]
    const parts = specs.map((f) => { const v = data[f]; return v != null ? unwrap(v) : null }).filter(Boolean)
    if (parts.length) {
      const unique = [...new Set(parts.map((p) => (p as string).trim()))].filter(Boolean)
      return unique.join(" / ")
    }
    if (!items || !items.length) return null

    // Fallback 1: product description from line-item rows.
    if (specs.some((s) => _DESC_FIELD_IDS.has(s))) {
      for (const item of items) {
        if (!item || typeof item !== "object") continue
        for (const k of ["description", "goods_description", "product_description", "article_description", "description_of_goods", "kind_of_packages_description_of_goods"]) {
          const raw = (item as Record<string, any>)[k]
          if (raw == null) continue
          const v = unwrap(raw)
          if (v && !_DESC_SKIP.has(v.trim().toUpperCase()))
            return v.trim()
        }
      }
    }

    // Fallback 2b: quantity / total packages from items[] rows (prefer the largest value = totals row).
    if (specs.some((s) => _QTY_FIELD_IDS.has(s))) {
      // Normalize European thousands format: "7.560" (dot + 3 digits) → "7560"
      const normalizeQty = (s: string): { num: number; display: string } => {
        const t = s.trim()
        // European thousands: digits followed by one or more ".NNN" groups, no decimal part
        if (/^\d{1,3}(\.\d{3})+$/.test(t)) {
          const stripped = t.replace(/\./g, "")
          return { num: parseInt(stripped, 10), display: stripped }
        }
        const num = parseFloat(t.replace(/[^0-9.]/g, ""))
        return { num, display: t }
      }

      let best: string | null = null
      let bestNum = -Infinity
      for (const item of items) {
        if (!item || typeof item !== "object") continue
        for (const k of ["quantity", "total_packages", "total_units", "total_sent_units", "total_qty"]) {
          const raw = (item as Record<string, any>)[k]
          if (raw == null) continue
          const v = unwrap(raw)
          if (!v) continue
          const { num, display } = normalizeQty(String(v))
          if (!isNaN(num) && num > bestNum) { bestNum = num; best = display }
        }
      }
      if (best) return best
    }

    // Fallback 3: container count / numbers from items[] rows.
    if (specs.some((s) => _CONTAINER_IDS.has(s))) {
      const seen = new Set<string>()
      for (const item of items) {
        if (!item || typeof item !== "object") continue
        for (const k of ["container_no", "container_number", "container_nos"]) {
          const raw = (item as Record<string, any>)[k]
          if (!raw) continue
          const v = unwrap(raw)
          if (v && v.trim()) { seen.add(v.trim()); break }
        }
      }
      if (seen.size) {
        const unique = Array.from(seen)
        return `${unique.length} / ${unique.join(", ")}`
      }
    }

    return null
  }

  const entryHasDisc = (entry: ChecklistEntry, doc: string): boolean => {
    const spec = entry.docFields[doc]
    if (!spec) return false
    return (Array.isArray(spec) ? spec : [spec]).some((f) => !!discLookup[`${doc}::${f}`])
  }

  const isFieldRedacted = (spec: string | string[], data: Record<string, any>): boolean => {
    const specs = Array.isArray(spec) ? spec : [spec]
    for (const f of specs) {
      const v = data[f]
      if (v != null && typeof v === "object" && v.redacted === true) return true
    }
    return false
  }

  return (
    <Card className="overflow-hidden">
      <div className="px-5 py-3.5 border-b border-border flex items-center gap-3 bg-muted/20">
        <ClipboardCheck className="w-4 h-4 text-muted-foreground flex-shrink-0" />
        <h3 className="font-semibold text-foreground text-sm">Ghana Customs Checklist</h3>
        <span className="text-[11px] text-muted-foreground">
          {CHECKLIST.length} checks
        </span>
        <div className="flex items-center gap-3 ml-auto text-[11px] text-muted-foreground">
          <span className="flex items-center gap-1"><CheckCircle className="w-3 h-3 text-green-500" /> Present</span>
          <span className="flex items-center gap-1"><AlertTriangle className="w-3 h-3 text-amber-500" /> Conflict</span>
          <span className="flex items-center gap-1"><X className="w-3 h-3 text-destructive" /> Missing</span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr className="border-b-2 border-border bg-muted/30">
              <th className="sticky left-0 z-10 bg-muted/30 text-center px-3 py-2.5 text-[11px] font-bold uppercase tracking-widest text-muted-foreground border-r border-border w-10 select-none">#</th>
              <th className="sticky left-10 z-10 bg-muted/30 text-left px-4 py-2.5 text-[11px] font-bold uppercase tracking-widest text-muted-foreground border-r border-border min-w-[190px]">Checklist Item</th>
              {docs.map((doc) => (
                <th key={doc} className="text-left px-4 py-2.5 text-[11px] font-bold uppercase tracking-wide text-muted-foreground min-w-[240px] border-r border-border/40 last:border-r-0">
                  <div className="flex items-center gap-1.5">
                    <FileText className="w-3 h-3" />
                    {DOC_LABEL[doc] ?? doc.replace(/_/g, " ")}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {CHECKLIST.map((entry, i) => {
              const rowHasIssue = docs.some(
                (doc) => backendStatus(entry, doc).status === "failed" || entryHasDisc(entry, doc)
              )
              const rowBg = rowHasIssue ? "bg-red-50/30 dark:bg-red-900/5" : i % 2 === 1 ? "bg-muted/10" : ""
              const stickyBg = rowHasIssue ? "bg-red-50/60 dark:bg-red-900/10" : i % 2 === 1 ? "bg-muted/20" : "bg-background"

              return (
                <tr key={entry.id} className={`border-b border-border/40 last:border-b-0 ${rowBg}`}>
                  <td className={`sticky left-0 z-10 text-center px-3 py-2 text-[11px] font-mono text-muted-foreground border-r border-border w-10 select-none ${stickyBg}`}>{i + 1}</td>
                  <td className={`sticky left-10 z-10 px-4 py-2.5 text-[12px] font-semibold border-r border-border whitespace-nowrap text-foreground ${stickyBg}`}>
                    {entry.label}
                  </td>

                  {docs.map((doc) => {
                    const { status: bStatus, backendVal } = backendStatus(entry, doc)

                    if (bStatus === null && !entry.docFields[doc]) {
                      return <td key={doc} className="px-4 py-2.5 border-r border-border/30 last:border-r-0"><span className="text-muted-foreground/25 font-mono text-sm">—</span></td>
                    }

                    const spec = entry.docFields[doc]
                    const docData  = extractedDocuments[doc]?.fields ?? {}
                    const docItems = extractedDocuments[doc]?.items  ?? []
                    const resolvedVal = spec ? resolveVal(spec, docData, docItems) : null
                    const val = (resolvedVal && resolvedVal.trim()) ? resolvedVal : (backendVal ?? null)
                    const isEmpty = !val || val.trim() === ""
                    const isRedactedField = !!spec && isFieldRedacted(spec, docData)
                    const wasRedacted = !isEmpty && isRedactedField

                    const isConflict = entryHasDisc(entry, doc) && !isEmpty
                    const isMissing = bStatus === "failed" || (bStatus === null && isEmpty)

                    // Insurance/freight: absent is correct when incoterm rule passed
                    if ((entry.id === "insurance" || entry.id === "freight") && isEmpty && incotermRulePassed) {
                      const label = incotermCode
                        ? `${incotermCode} — not required`
                        : "Not required by incoterm"
                      return (
                        <td key={doc} className="px-4 py-2.5 border-r border-border/30 last:border-r-0">
                          <span className="flex items-center gap-1.5 text-[12px] text-green-600 dark:text-green-400">
                            <CheckCircle className="w-3.5 h-3.5 flex-shrink-0" />
                            <span className="font-mono">{label}</span>
                          </span>
                        </td>
                      )
                    }

                    if (isEmpty && isRedactedField) {
                      return (
                        <td key={doc} className="px-4 py-2.5 border-r border-border/30 last:border-r-0">
                          <span className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
                            <RedactedBadge />
                          </span>
                        </td>
                      )
                    }

                    return (
                      <td key={doc} className="px-4 py-2.5 align-middle border-r border-border/30 last:border-r-0">
                        {isMissing && !isConflict ? (
                          <span className="flex items-center gap-1.5 text-[12px] text-destructive font-medium">
                            <X className="w-3.5 h-3.5 flex-shrink-0" />
                            Missing
                          </span>
                        ) : isConflict ? (
                          <span className="flex items-start gap-1.5 text-[12px] text-amber-700 dark:text-amber-400">
                            <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
                            <span className="font-mono break-all leading-snug">
                              {val}
                              {wasRedacted && <span className="ml-1.5 px-1 py-0.5 rounded text-[10px] font-semibold bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">Redacted</span>}
                            </span>
                          </span>
                        ) : (
                          <span className="flex items-start gap-1.5 text-[12px] text-foreground">
                            <CheckCircle className="w-3.5 h-3.5 text-green-500 flex-shrink-0 mt-0.5" />
                            <span className="font-mono break-all leading-snug">
                              {val}
                              {wasRedacted && <span className="ml-1.5 px-1 py-0.5 rounded text-[10px] font-semibold bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">Redacted</span>}
                            </span>
                          </span>
                        )}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

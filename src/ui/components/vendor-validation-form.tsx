"use client"

import React, { useState, useEffect, useRef, useCallback } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  FileUp,
  Loader,
  CheckCircle,
  AlertCircle,
  AlertTriangle,
  X,
  ChevronDown,
  ChevronUp,
  ClipboardCheck,
  Settings2,
  Pencil,
  Check,
  Save,
  FileText,
  ShieldCheck,
  Copy,
  ArrowRight,
} from "lucide-react"
import {
  apiClient,
  type ValidationDiscrepancy,
  type VendorValidationResponse,
  type ExtractedDocumentMeta,
  type ExtractedTable,
} from "@/lib/api-client"

// ─── Document Slot Definition ─────────────────────────────────────────────────

interface DocSlot {
  key: "invoice" | "packing_list" | "bill_of_lading" | "freight_manifest" | "certificate_of_origin"
  label: string
  required: boolean
  description: string
}

const DOC_SLOTS: DocSlot[] = [
  {
    key: "invoice",
    label: "Commercial Invoice",
    required: true,
    description: "Supplier's invoice showing goods, quantities, and values",
  },
  {
    key: "packing_list",
    label: "Packing List",
    required: true,
    description: "Itemised list of goods shipped with weights and dimensions",
  },
  {
    key: "bill_of_lading",
    label: "Bill of Lading",
    required: false,
    description: "Carrier's receipt — confirms shipment details, containers, and routing",
  },
  {
    key: "freight_manifest",
    label: "Freight Manifest",
    required: false,
    description: "Full cargo manifest from the freight forwarder",
  },
  {
    key: "certificate_of_origin",
    label: "Certificate of Origin",
    required: false,
    description: "Certifies the country of manufacture for customs purposes",
  },
]

const DOC_LABEL: Record<string, string> = {
  invoice: "Commercial Invoice",
  packing_list: "Packing List",
  bill_of_lading: "Bill of Lading",
  freight_manifest: "Freight Manifest",
  certificate_of_origin: "Certificate of Origin",
}

// Short names used in conflict badges — scannable at a glance
const DOC_SHORT: Record<string, string> = {
  invoice: "Invoice",
  packing_list: "Packing List",
  bill_of_lading: "BOL",
  freight_manifest: "Manifest",
  certificate_of_origin: "Cert of Origin",
}

function autoShipmentNumber() {
  const now = new Date()
  const ymd = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}${String(now.getDate()).padStart(2, "0")}`
  const rand = Math.random().toString(36).slice(2, 6).toUpperCase()
  return `SHP-${ymd}-${rand}`
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Unwrap {value: ..., source: ...} envelopes or return raw value */
function unwrap(v: any): string {
  if (v === null || v === undefined) return ""
  if (typeof v === "object" && "value" in v) return String(v.value ?? "")
  if (Array.isArray(v)) return v.map((item) => unwrap(item)).join(", ")
  if (typeof v === "object") return JSON.stringify(v)
  return String(v)
}

/**
 * Format a discrepancy source_value / target_value for display.
 * Handles plain dicts (n-way matcher, shipper validator), {value} envelopes, arrays, and primitives.
 */
function formatValue(v: any): string {
  if (v === null || v === undefined) return "—"
  if (typeof v === "object" && !Array.isArray(v) && "value" in v) {
    return String(v.value ?? "—")
  }
  if (Array.isArray(v)) {
    return v.map((item) => formatValue(item)).join(", ")
  }
  if (typeof v === "object") {
    return Object.entries(v)
      .map(([doc, val]) => `${doc.replace(/_/g, " ")}: ${val}`)
      .join(" · ")
  }
  return String(v)
}

/**
 * Derive a 0-1 confidence score from a raw field value.
 * - Fields wrapped with {source: "ai_enhancement"} → 0.92
 * - Direct plain values (from Claude open-mode pass) → 0.85
 * - Fields with explicit confidence metadata → use that
 */
function deriveConfidence(v: any): number {
  if (v === null || v === undefined) return 0
  if (typeof v === "object") {
    if (typeof v.confidence === "number") return Math.min(1, v.confidence)
    if (v.source === "ai_enhancement") return 0.92
    if (v.source === "direct") return 0.95
    return 0.85
  }
  // Plain scalar — came straight from the model
  return 0.85
}

function ConfidenceBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const color =
    pct >= 90
      ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
      : pct >= 70
      ? "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
      : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
  return (
    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded font-mono ${color}`}>
      {pct}%
    </span>
  )
}

/** Returns true when a raw field value carries Claude's redaction flag */
function isRedacted(v: any): boolean {
  return typeof v === "object" && v !== null && !Array.isArray(v) && v.redacted === true
}

function RedactedBadge() {
  return (
    <span className="text-[10px] font-bold px-1.5 py-0.5 rounded font-mono uppercase tracking-wide bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400">
      redacted
    </span>
  )
}

// ─── FileSlot ─────────────────────────────────────────────────────────────────

function FileSlot({
  slot,
  file,
  onSelect,
  onRemove,
}: {
  slot: DocSlot
  file: File | null
  onSelect: (file: File) => void
  onRemove: () => void
}) {
  const inputId = `file-slot-${slot.key}`
  return (
    <div className="flex items-start gap-4 p-4 rounded-lg border border-border bg-muted/30">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="font-semibold text-foreground text-sm">{slot.label}</span>
          {slot.required ? (
            <span className="text-[10px] font-bold uppercase tracking-wide text-destructive">Required</span>
          ) : (
            <span className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">Optional</span>
          )}
        </div>
        <p className="text-xs text-muted-foreground mb-3">{slot.description}</p>

        {file ? (
          <div className="flex items-center gap-3 p-2 bg-primary/5 border border-primary/20 rounded-lg">
            <FileUp className="w-4 h-4 text-primary flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-foreground truncate">{file.name}</p>
              <p className="text-xs text-muted-foreground">{(file.size / 1024).toFixed(1)} KB</p>
            </div>
            <button
              onClick={onRemove}
              className="text-muted-foreground hover:text-destructive transition-colors flex-shrink-0"
              aria-label="Remove file"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <>
            <input
              id={inputId}
              type="file"
              accept=".pdf,.doc,.docx,.jpg,.jpeg,.png"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) onSelect(f)
                e.target.value = ""
              }}
            />
            <Button
              variant="outline"
              size="sm"
              onClick={() => document.getElementById(inputId)?.click()}
              className="text-xs"
            >
              <FileUp className="w-3 h-3 mr-1.5" />
              Select File
            </Button>
          </>
        )}
      </div>
    </div>
  )
}

// ─── DiscrepancyCard ──────────────────────────────────────────────────────────

function DiscrepancyCard({
  disc,
  confirmed,
  onToggle,
}: {
  disc: ValidationDiscrepancy
  confirmed: boolean | null
  onToggle: (id: string, value: boolean) => void
}) {
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

// ─── ExtractedTablesSection ───────────────────────────────────────────────────
// Renders supplementary tables (tax tables, freight tables, etc.) that Claude
// returns separately from items — shown below the items table in both the
// field-review (editable) and review-reference (read-only) panels.
//
// tableEdits shape: { [tblIdx]: { [rowIdx]: { [colIdx]: editedValue } } }

function ExtractedTablesSection({
  tables,
  editable = false,
  tableEdits,
  onCellChange,
}: {
  tables: ExtractedTable[]
  editable?: boolean
  tableEdits?: Record<number, Record<number, Record<number, string>>>
  onCellChange?: (tblIdx: number, rowIdx: number, colIdx: number, val: string) => void
}) {
  if (!tables || tables.length === 0) return null

  return (
    <div className="mt-3 pt-3 border-t border-border space-y-3">
      <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
        Additional Tables — {tables.length} table{tables.length !== 1 ? "s" : ""}
        {editable && (
          <span className="ml-2 normal-case font-normal text-muted-foreground/70">
            (hover a cell to edit)
          </span>
        )}
      </p>
      {tables.map((tbl, tblIdx) => {
        // Normalise: support {headers, rows} and {columns, data} shapes
        const headers: string[] = tbl.headers ?? tbl.columns ?? []
        const rows: any[][] = tbl.rows ?? tbl.data ?? []
        const title = tbl.title ?? tbl.name ?? `Table ${tblIdx + 1}`

        if (headers.length === 0 && rows.length === 0) return null

        return (
          <div key={tblIdx} className="rounded border border-border overflow-hidden">
            {title && (
              <div className="px-3 py-1.5 bg-muted/40 border-b border-border">
                <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">
                  {title}
                </span>
              </div>
            )}
            <div className="overflow-x-auto">
              <table className="w-full text-xs border-collapse">
                {headers.length > 0 && (
                  <thead>
                    <tr className="bg-muted/30">
                      {headers.map((h, hi) => (
                        <th
                          key={hi}
                          className="text-left px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground border-b border-border whitespace-nowrap"
                        >
                          {String(h).replace(/_/g, " ")}
                        </th>
                      ))}
                    </tr>
                  </thead>
                )}
                <tbody>
                  {rows.map((row, ri) => {
                    const cells: any[] = Array.isArray(row)
                      ? row
                      : headers.map((h) => (row as any)[h])
                    return (
                      <tr key={ri} className="border-b border-border last:border-b-0 hover:bg-muted/20">
                        {cells.map((cell, ci) => {
                          if (editable) {
                            const editedVal = tableEdits?.[tblIdx]?.[ri]?.[ci]
                            const rawStr = cell === null || cell === undefined ? "" : String(cell)
                            const isEdited = editedVal !== undefined && editedVal !== rawStr
                            return (
                              <EditableItemCell
                                key={ci}
                                raw={rawStr}
                                edited={editedVal}
                                isEdited={isEdited}
                                confidence={1}
                                readOnly={false}
                                onChange={onCellChange ? (v) => onCellChange(tblIdx, ri, ci, v) : undefined}
                              />
                            )
                          }
                          return (
                            <td key={ci} className="px-2 py-1.5 font-mono text-foreground whitespace-nowrap">
                              {cell === null || cell === undefined ? (
                                <span className="text-muted-foreground italic">—</span>
                              ) : (
                                String(cell)
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
          </div>
        )
      })}
    </div>
  )
}

// ─── ExtractedDocsReference ───────────────────────────────────────────────────
// Read-only collapsible panels — one per document — shown on the review step
// so reviewers can cross-reference extracted values while handling discrepancies.

const DOC_FIELD_GROUPS: Record<string, string[]> = {
  invoice: ["invoice_number", "invoice_date", "total_invoice_value", "total_fob_value", "currency", "incoterm", "shipper_name", "consignee_name", "payment_terms"],
  packing_list: ["invoice_number", "net_weight", "gross_weight", "quantity", "unit_of_measure", "shipper_name", "consignee_name", "hs_code"],
  bill_of_lading: ["bl_number", "vessel_name", "port_of_loading", "port_of_discharge", "shipper_name", "consignee_name", "container_numbers", "incoterm"],
  freight_manifest: ["bl_number", "vessel_name", "shipper_name", "consignee_name", "gross_weight", "net_weight"],
  certificate_of_origin: ["origin", "country_of_origin", "shipper_name", "consignee_name", "hs_code", "product_description"],
}

const DOC_DISPLAY_LABEL: Record<string, string> = {
  invoice: "Commercial Invoice",
  packing_list: "Packing List",
  bill_of_lading: "Bill of Lading",
  freight_manifest: "Freight Manifest",
  certificate_of_origin: "Certificate of Origin",
}

function ExtractedDocRefPanel({
  docType,
  docMeta,
}: {
  docType: string
  docMeta: ExtractedDocumentMeta
}) {
  const [open, setOpen] = useState(false)
  const fields = docMeta.fields ?? {}
  const priorityKeys = DOC_FIELD_GROUPS[docType] ?? []
  const allKeys = Object.keys(fields).filter((k) => k !== "items" && !k.startsWith("_"))
  // Show priority keys first, then any remaining ones
  const ordered = [
    ...priorityKeys.filter((k) => k in fields),
    ...allKeys.filter((k) => !priorityKeys.includes(k)),
  ]

  return (
    <Card className="overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-muted/30 transition-colors text-left"
        onClick={() => setOpen(!open)}
      >
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-muted-foreground" />
          <span className="font-semibold text-sm text-foreground">
            {DOC_DISPLAY_LABEL[docType] ?? docType}
          </span>
          <span className="text-[10px] font-mono text-muted-foreground">{allKeys.length} fields</span>
        </div>
        {open ? (
          <ChevronUp className="w-4 h-4 text-muted-foreground" />
        ) : (
          <ChevronDown className="w-4 h-4 text-muted-foreground" />
        )}
      </button>

      {open && (
        <div className="border-t border-border px-4 py-3">
          <div className="grid grid-cols-2 gap-x-6 gap-y-2">
            {ordered.map((key) => {
              const raw = fields[key]
              const redacted = isRedacted(raw)
              const val = unwrap(raw)
              const conf = deriveConfidence(raw)
              const label = key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
              return (
                <div key={key} className="flex items-start gap-2 min-w-0">
                  <div className="flex-1 min-w-0">
                    <p className="text-[10px] text-muted-foreground font-mono leading-none mb-0.5">
                      {label}
                    </p>
                    <p className="text-xs font-mono text-foreground truncate" title={val || "—"}>
                      {redacted
                        ? <span className="text-slate-400 dark:text-slate-500 italic">—</span>
                        : val || <span className="text-muted-foreground italic">—</span>
                      }
                    </p>
                  </div>
                  {redacted ? <RedactedBadge /> : <ConfidenceBadge score={conf} />}
                </div>
              )
            })}
          </div>

          {docMeta.items && docMeta.items.length > 0 && (
            <EditableLineItemsTable items={docMeta.items} readOnly />
          )}

          {docMeta.tables && docMeta.tables.length > 0 && (
            <ExtractedTablesSection tables={docMeta.tables} />
          )}
        </div>
      )}
    </Card>
  )
}

function ExtractedDocsReference({
  extractedDocuments,
}: {
  extractedDocuments: Record<string, ExtractedDocumentMeta>
}) {
  const [open, setOpen] = useState(false)
  const docCount = Object.keys(extractedDocuments).length

  return (
    <div className="space-y-2">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        <FileText className="w-3.5 h-3.5" />
        <span className="font-medium">
          {open ? "Hide" : "Show"} extracted document fields ({docCount} doc{docCount !== 1 ? "s" : ""})
        </span>
        {open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        <span className="italic">— reference while reviewing discrepancies</span>
      </button>

      {open && (
        <div className="space-y-2">
          {Object.entries(extractedDocuments).map(([docType, docMeta]) => (
            <ExtractedDocRefPanel key={docType} docType={docType} docMeta={docMeta} />
          ))}
        </div>
      )}
    </div>
  )
}

// ─── ValidationChecksPanel ────────────────────────────────────────────────────
// Compact collapsible check list for the review step.

function ValidationChecksPanel({ results }: { results: any[] }) {
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

// ─── EditableFieldRow ─────────────────────────────────────────────────────────

function EditableFieldRow({
  fieldKey,
  rawValue,
  editedValue,
  onChange,
}: {
  fieldKey: string
  rawValue: any
  editedValue: string | undefined
  onChange: (key: string, val: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState("")
  const inputRef = useRef<HTMLInputElement>(null)
  const redacted = isRedacted(rawValue)
  const confidence = deriveConfidence(rawValue)
  const displayValue = editedValue !== undefined ? editedValue : unwrap(rawValue)
  const isEdited = editedValue !== undefined && editedValue !== unwrap(rawValue)

  const startEdit = () => {
    if (redacted) return
    setDraft(displayValue)
    setEditing(true)
    setTimeout(() => inputRef.current?.focus(), 0)
  }

  const commitEdit = () => {
    onChange(fieldKey, draft)
    setEditing(false)
  }

  const cancelEdit = () => {
    setEditing(false)
  }

  // Format field key for display
  const label = fieldKey.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())

  return (
    <div className={`flex items-center gap-3 py-2.5 border-b border-border last:border-b-0 group ${isEdited ? "bg-amber-50/40 dark:bg-amber-900/10" : ""}`}>
      {/* Field name */}
      <div className="w-48 flex-shrink-0">
        <span className="text-xs font-medium text-muted-foreground font-mono">{label}</span>
        {isEdited && (
          <span className="ml-1.5 text-[9px] font-bold uppercase text-amber-600 dark:text-amber-400">edited</span>
        )}
      </div>

      {/* Value / Editor */}
      <div className="flex-1 min-w-0">
        {redacted ? (
          <span className="text-xs font-mono text-slate-400 dark:text-slate-500 italic select-none">—</span>
        ) : editing ? (
          <div className="flex items-center gap-2">
            <Input
              ref={inputRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") commitEdit()
                if (e.key === "Escape") cancelEdit()
              }}
              className="h-7 text-xs py-0 font-mono"
              autoComplete="off"
            />
            <button
              onClick={commitEdit}
              className="text-green-600 hover:text-green-700 flex-shrink-0"
              title="Save (Enter)"
            >
              <Check className="w-4 h-4" />
            </button>
            <button
              onClick={cancelEdit}
              className="text-muted-foreground hover:text-destructive flex-shrink-0"
              title="Cancel (Escape)"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-xs font-mono text-foreground truncate" title={displayValue}>
              {displayValue || <span className="text-muted-foreground italic">—</span>}
            </span>
            <button
              onClick={startEdit}
              className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-foreground flex-shrink-0"
              title="Edit field"
            >
              <Pencil className="w-3 h-3" />
            </button>
          </div>
        )}
      </div>

      {/* Confidence or redacted badge */}
      <div className="flex-shrink-0">
        {redacted ? <RedactedBadge /> : <ConfidenceBadge score={confidence} />}
      </div>
    </div>
  )
}

// ─── EditableItemCell ─────────────────────────────────────────────────────────

function EditableItemCell({
  raw,
  edited,
  isEdited,
  confidence,
  readOnly,
  onChange,
}: {
  raw: any
  edited: string | undefined
  isEdited: boolean
  confidence: number
  readOnly?: boolean
  onChange?: (value: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState("")
  const inputRef = useRef<HTMLInputElement>(null)
  const cellRedacted = isRedacted(raw)
  const displayValue = edited !== undefined ? edited : unwrap(raw)

  const startEdit = () => {
    if (readOnly || !onChange || cellRedacted) return
    setDraft(displayValue)
    setEditing(true)
    setTimeout(() => inputRef.current?.focus(), 0)
  }

  const commit = () => {
    onChange?.(draft)
    setEditing(false)
  }

  const cancel = () => setEditing(false)

  // Redacted cell — no value, no editing, just the badge
  if (cellRedacted) {
    return (
      <td className="px-2 py-1.5 font-mono">
        <RedactedBadge />
      </td>
    )
  }

  return (
    <td className={`px-2 py-1.5 font-mono group relative ${isEdited ? "bg-amber-50/40 dark:bg-amber-900/10" : ""}`}>
      {editing ? (
        <div className="flex items-center gap-1">
          <input
            ref={inputRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") commit()
              if (e.key === "Escape") cancel()
            }}
            className="h-6 text-xs py-0 font-mono bg-background border border-border rounded px-1 w-full min-w-[60px]"
            autoComplete="off"
          />
          <button onClick={commit} className="text-green-600 hover:text-green-700 flex-shrink-0">
            <Check className="w-3 h-3" />
          </button>
          <button onClick={cancel} className="text-muted-foreground hover:text-destructive flex-shrink-0">
            <X className="w-2.5 h-2.5" />
          </button>
        </div>
      ) : (
        <div className="flex items-center gap-1.5 min-w-0">
          <span
            className={`truncate text-xs ${displayValue ? "text-foreground" : "text-muted-foreground italic"}`}
            title={displayValue || "—"}
          >
            {displayValue || "—"}
          </span>
          {isEdited && (
            <span className="text-[8px] font-bold uppercase text-amber-600 dark:text-amber-400 flex-shrink-0">
              edited
            </span>
          )}
          <ConfidenceBadge score={confidence} />
          {!readOnly && onChange && (
            <button
              onClick={startEdit}
              className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-foreground flex-shrink-0 ml-auto"
              title="Edit cell"
            >
              <Pencil className="w-2.5 h-2.5" />
            </button>
          )}
        </div>
      )}
    </td>
  )
}

// ─── EditableLineItemsTable ───────────────────────────────────────────────────

const SKIP_ITEM_COLS = new Set([
  "_row_index", "_table_index", "column_index", "column_number",
  "row_index", "table_block_index", "table_bbox",
  "normalized_header", "original_header", "original_page",
])

/** Renders line items as a proper table with per-cell confidence and optional editing */
function EditableLineItemsTable({
  items,
  edits,
  onCellChange,
  readOnly,
}: {
  items: Array<Record<string, any>>
  edits?: Record<number, Record<string, string>>
  onCellChange?: (rowIndex: number, column: string, value: string) => void
  readOnly?: boolean
}) {
  if (!items || items.length === 0) return null

  // Derive column order from all rows, skipping internal metadata keys
  const seen = new Set<string>()
  const columns: string[] = []
  for (const row of items) {
    for (const k of Object.keys(row)) {
      if (!SKIP_ITEM_COLS.has(k) && !k.startsWith("_") && !seen.has(k)) {
        seen.add(k)
        columns.push(k)
      }
    }
  }

  return (
    <div className="mt-3 pt-3 border-t border-border">
      <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground mb-2">
        Line Items — {items.length} row{items.length !== 1 ? "s" : ""}
        {!readOnly && (
          <span className="ml-2 normal-case font-normal text-muted-foreground/70">
            (hover a cell to edit)
          </span>
        )}
      </p>
      <div className="overflow-x-auto rounded border border-border">
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr className="bg-muted/60">
              <th className="text-left px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground border-b border-border w-7">#</th>
              {columns.map((col) => (
                <th
                  key={col}
                  className="text-left px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground border-b border-border whitespace-nowrap"
                >
                  {col.replace(/_/g, " ")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map((row, rowIdx) => (
              <tr key={rowIdx} className="border-b border-border last:border-b-0 hover:bg-muted/20 transition-colors">
                <td className="px-2 py-1.5 text-[10px] text-muted-foreground font-mono">{rowIdx + 1}</td>
                {columns.map((col) => {
                  const raw = row[col]
                  const editedRow = edits?.[rowIdx]
                  const edited = editedRow?.[col]
                  const isEdited = edited !== undefined && edited !== unwrap(raw)
                  const conf = deriveConfidence(raw)
                  return (
                    <EditableItemCell
                      key={col}
                      raw={raw}
                      edited={edited}
                      isEdited={isEdited}
                      confidence={conf}
                      readOnly={readOnly}
                      onChange={onCellChange ? (v) => onCellChange(rowIdx, col, v) : undefined}
                    />
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ─── DocumentFieldPanel ───────────────────────────────────────────────────────

/** Shows all extracted fields for one document with confidence + editing */
function DocumentFieldPanel({
  docType,
  docMeta,
  edits,
  itemEdits,
  tableEdits,
  onFieldChange,
  onItemChange,
  onTableCellChange,
}: {
  docType: string
  docMeta: ExtractedDocumentMeta
  edits: Record<string, string>
  itemEdits: Record<number, Record<string, string>>
  tableEdits: Record<number, Record<number, Record<number, string>>>
  onFieldChange: (docType: string, key: string, val: string) => void
  onItemChange: (docType: string, rowIndex: number, column: string, val: string) => void
  onTableCellChange: (docType: string, tblIdx: number, rowIdx: number, colIdx: number, val: string) => void
}) {
  const [collapsed, setCollapsed] = useState(false)

  // Filter out internal/meta keys and items array
  const fieldEntries = Object.entries(docMeta.fields).filter(
    ([k]) => k !== "items" && !k.startsWith("_")
  )

  const editedCount = Object.keys(edits).length

  return (
    <Card className="overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-4 py-3 border-b border-border hover:bg-muted/30 transition-colors text-left"
        onClick={() => setCollapsed(!collapsed)}
      >
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm text-foreground">
            {DOC_LABEL[docType] ?? docType}
          </span>
          <span className="text-[10px] text-muted-foreground font-mono">
            {fieldEntries.length} fields
          </span>
          {editedCount > 0 && (
            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
              {editedCount} edited
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-muted-foreground uppercase font-semibold tracking-wide">
            Confidence
          </span>
          {collapsed ? (
            <ChevronDown className="w-4 h-4 text-muted-foreground" />
          ) : (
            <ChevronUp className="w-4 h-4 text-muted-foreground" />
          )}
        </div>
      </button>

      {!collapsed && (
        <div className="px-4 py-1">
          {fieldEntries.length === 0 ? (
            <p className="text-xs text-muted-foreground py-4 text-center">No fields extracted</p>
          ) : (
            fieldEntries.map(([key, rawVal]) => (
              <EditableFieldRow
                key={key}
                fieldKey={key}
                rawValue={rawVal}
                editedValue={edits[key]}
                onChange={(k, v) => onFieldChange(docType, k, v)}
              />
            ))
          )}

          {/* Line items — editable table */}
          {docMeta.items && docMeta.items.length > 0 && (
            <EditableLineItemsTable
              items={docMeta.items}
              edits={itemEdits}
              onCellChange={(rowIdx, col, val) => onItemChange(docType, rowIdx, col, val)}
            />
          )}

          {/* Supplementary tables — editable */}
          {docMeta.tables && docMeta.tables.length > 0 && (
            <ExtractedTablesSection
              tables={docMeta.tables}
              editable
              tableEdits={tableEdits}
              onCellChange={(tblIdx, rowIdx, colIdx, val) =>
                onTableCellChange(docType, tblIdx, rowIdx, colIdx, val)
              }
            />
          )}
        </div>
      )}
    </Card>
  )
}

// ─── Main Component ───────────────────────────────────────────────────────────

type Step = "upload" | "processing" | "field_review" | "review" | "complete"

export default function VendorValidationForm() {
  const [step, setStep] = useState<Step>("upload")

  // Optional shipment details
  const [showShipmentDetails, setShowShipmentDetails] = useState(false)
  const [shipmentNumber, setShipmentNumber] = useState("")
  const [supplierName, setSupplierName] = useState("")
  const [consigneeName, setConsigneeName] = useState("")
  const [incoterm, setIncoterm] = useState("")
  const [transportMode, setTransportMode] = useState("")

  // Files
  const [files, setFiles] = useState<Record<DocSlot["key"], File | null>>({
    invoice: null,
    packing_list: null,
    bill_of_lading: null,
    freight_manifest: null,
    certificate_of_origin: null,
  })

  // Extraction results (field review step)
  const [extractedDocuments, setExtractedDocuments] = useState<Record<string, ExtractedDocumentMeta> | null>(null)
  // Per-doc, per-field edits: { docType: { fieldKey: newValue } }
  const [fieldEdits, setFieldEdits] = useState<Record<string, Record<string, string>>>({})
  // Per-doc, per-row, per-column line item edits: { docType: { rowIndex: { column: newValue } } }
  const [lineItemEdits, setLineItemEdits] = useState<Record<string, Record<number, Record<string, string>>>>({})
  // Per-doc, per-table, per-row, per-col supplementary table edits: { docType: { tblIdx: { rowIdx: { colIdx: newValue } } } }
  const [tableEdits, setTableEdits] = useState<Record<string, Record<number, Record<number, Record<number, string>>>>>({})
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  // Validation results (stored from API — shown after field review)
  const [pendingResult, setPendingResult] = useState<VendorValidationResponse | null>(null)

  // Results
  const [shipmentId, setShipmentId] = useState<string | null>(null)
  const [generatedShipmentNumber, setGeneratedShipmentNumber] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [discrepancies, setDiscrepancies] = useState<ValidationDiscrepancy[]>([])
  const [validationResults, setValidationResults] = useState<any[]>([])
  const [finalStatus, setFinalStatus] = useState<string | null>(null)
  const [summary, setSummary] = useState<Record<string, any> | null>(null)
  const [confirmations, setConfirmations] = useState<Record<string, boolean | null>>({})

  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const elapsedRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Document viewer tab — shared across review + complete steps
  const [reviewView, setReviewView] = useState<"review" | "documents">("review")
  const [completeView, setCompleteView] = useState<"results" | "documents">("results")
  const [activeDocKey, setActiveDocKey] = useState<string | null>(null)
  // Blob URLs for uploaded files — created on demand, revoked on unmount
  const blobUrlsRef = useRef<Record<string, string>>({})
  const getDocBlobUrl = useCallback((key: string): string | null => {
    const file = files[key as keyof typeof files]
    if (!file) return null
    if (!blobUrlsRef.current[key]) {
      blobUrlsRef.current[key] = URL.createObjectURL(file)
    }
    return blobUrlsRef.current[key]
  }, [files])
  useEffect(() => {
    const urls = blobUrlsRef.current
    return () => { Object.values(urls).forEach(URL.revokeObjectURL) }
  }, [])

  useEffect(() => {
    if (submitting) {
      setElapsed(0)
      elapsedRef.current = setInterval(() => setElapsed((s) => s + 1), 1000)
    } else {
      if (elapsedRef.current) clearInterval(elapsedRef.current)
    }
    return () => { if (elapsedRef.current) clearInterval(elapsedRef.current) }
  }, [submitting])

  // ── Helpers ───────────────────────────────────────────────────────────────

  const setFile = (key: DocSlot["key"], file: File | null) =>
    setFiles((prev) => ({ ...prev, [key]: file }))

  const requiredFilled = files.invoice !== null && files.packing_list !== null

  const handleFieldChange = useCallback((docType: string, key: string, val: string) => {
    setFieldEdits((prev) => ({
      ...prev,
      [docType]: { ...(prev[docType] ?? {}), [key]: val },
    }))
  }, [])

  const handleLineItemChange = useCallback((docType: string, rowIndex: number, column: string, val: string) => {
    setLineItemEdits((prev) => ({
      ...prev,
      [docType]: {
        ...(prev[docType] ?? {}),
        [rowIndex]: { ...(prev[docType]?.[rowIndex] ?? {}), [column]: val },
      },
    }))
  }, [])

  const handleTableCellChange = useCallback((
    docType: string, tblIdx: number, rowIdx: number, colIdx: number, val: string
  ) => {
    setTableEdits((prev) => ({
      ...prev,
      [docType]: {
        ...(prev[docType] ?? {}),
        [tblIdx]: {
          ...(prev[docType]?.[tblIdx] ?? {}),
          [rowIdx]: { ...(prev[docType]?.[tblIdx]?.[rowIdx] ?? {}), [colIdx]: val },
        },
      },
    }))
  }, [])

  /** Apply the pending API result to component state and move to review/complete */
  const applyResult = (result: VendorValidationResponse) => {
    if (result.workflow_status === "awaiting_user" && result.discrepancies?.length) {
      setSessionId(result.session_id ?? null)
      setDiscrepancies(result.discrepancies)
      setValidationResults((result as any).validation_results ?? [])
      setSummary(result.summary ?? null)
      const initial: Record<string, boolean | null> = {}
      result.discrepancies.forEach((d) => { initial[d.id] = null })
      setConfirmations(initial)
      setStep("review")
    } else {
      setFinalStatus(result.final_status ?? null)
      setSummary(result.summary ?? null)
      setDiscrepancies(result.discrepancies ?? [])
      setValidationResults((result as any).validation_results ?? [])
      setStep("complete")
    }
  }

  // ── Submit ────────────────────────────────────────────────────────────────

  const handleValidate = async () => {
    setError(null)
    setSubmitting(true)
    setStep("processing")

    try {
      const number = shipmentNumber.trim() || autoShipmentNumber()
      setGeneratedShipmentNumber(number)

      const shipment = await apiClient.createShipment({
        shipment_number: number,
        supplier_name: supplierName.trim() || undefined as any,
        consignee_name: consigneeName.trim() || undefined as any,
        incoterm: incoterm.trim() || undefined,
        transport_mode: transportMode.trim() || undefined,
      })
      setShipmentId(shipment.shipment_id)

      const result: VendorValidationResponse = await apiClient.validateVendorDocs(
        shipment.shipment_id,
        {
          invoice: files.invoice ?? undefined,
          packing_list: files.packing_list ?? undefined,
          bill_of_lading: files.bill_of_lading ?? undefined,
          freight_manifest: files.freight_manifest ?? undefined,
          certificate_of_origin: files.certificate_of_origin ?? undefined,
        }
      )

      // Store full result for after the field review step
      setPendingResult(result)

      // If API returned extracted documents, show field review step
      if (result.extracted_documents && Object.keys(result.extracted_documents).length > 0) {
        setExtractedDocuments(result.extracted_documents)
        setFieldEdits({})
        setLineItemEdits({})
        setTableEdits({})
        setStep("field_review")
      } else {
        // No extracted documents returned — skip field review
        applyResult(result)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Validation failed. Please try again.")
      setStep("upload")
    } finally {
      setSubmitting(false)
    }
  }

  // ── Field Review Save ─────────────────────────────────────────────────────

  const handleSaveFields = async () => {
    if (!extractedDocuments) return
    setSaving(true)
    setSaveError(null)

    try {
      // Collect all doc types that have any edits
      const docTypes = new Set([
        ...Object.keys(fieldEdits),
        ...Object.keys(lineItemEdits),
        ...Object.keys(tableEdits),
      ])

      const savePromises = Array.from(docTypes)
        .filter((docType) => {
          const hasFieldEdits = Object.keys(fieldEdits[docType] ?? {}).length > 0
          const hasItemEdits = Object.keys(lineItemEdits[docType] ?? {}).length > 0
          const hasTableEdits = Object.keys(tableEdits[docType] ?? {}).length > 0
          return hasFieldEdits || hasItemEdits || hasTableEdits
        })
        .map((docType) => {
          const docId = extractedDocuments[docType]?.document_id
          if (!docId) return Promise.resolve()

          // Flatten item edits to [{row_index, column, value}]
          const itemUpdates = Object.entries(lineItemEdits[docType] ?? {}).flatMap(
            ([rowIdx, cols]) =>
              Object.entries(cols).map(([column, value]) => ({
                row_index: Number(rowIdx),
                column,
                value,
              }))
          )

          // Flatten table edits to [{table_index, row_index, col_index, value}]
          const tblUpdates = Object.entries(tableEdits[docType] ?? {}).flatMap(
            ([tblIdx, rows]) =>
              Object.entries(rows).flatMap(([rowIdx, cols]) =>
                Object.entries(cols).map(([colIdx, value]) => ({
                  table_index: Number(tblIdx),
                  row_index: Number(rowIdx),
                  col_index: Number(colIdx),
                  value,
                }))
              )
          )

          return apiClient.updateDocumentFields(
            docId,
            fieldEdits[docType] ?? {},
            {
              updated_by: "field_review",
              update_reason: "User reviewed and corrected extracted fields before validation",
            },
            itemUpdates.length > 0 ? itemUpdates : undefined,
            tblUpdates.length > 0 ? tblUpdates : undefined
          )
        })

      await Promise.all(savePromises)

      // Proceed to show validation results
      if (pendingResult) {
        applyResult(pendingResult)
      }
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Failed to save field edits. Please try again.")
    } finally {
      setSaving(false)
    }
  }

  /** Skip editing and proceed directly to validation results */
  const handleSkipFieldReview = () => {
    if (pendingResult) applyResult(pendingResult)
  }

  // ── HITL Resume ───────────────────────────────────────────────────────────

  const handleResume = async () => {
    if (!sessionId) return
    setError(null)
    setSubmitting(true)
    setStep("processing")
    try {
      const payload = Object.entries(confirmations)
        .filter(([, v]) => v !== null)
        .map(([id, confirmed]) => ({ discrepancy_id: id, confirmed: confirmed as boolean }))

      const result = await apiClient.resumeValidationSession(sessionId, payload)
      setFinalStatus((result as any).final_status ?? null)
      setSummary((result as any).summary ?? null)
      setStep("complete")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Resume failed. Please try again.")
      setStep("review")
    } finally {
      setSubmitting(false)
    }
  }

  // ── Reset ─────────────────────────────────────────────────────────────────

  const handleReset = () => {
    setStep("upload")
    setShipmentNumber("")
    setSupplierName("")
    setConsigneeName("")
    setIncoterm("")
    setTransportMode("")
    setShowShipmentDetails(false)
    setFiles({ invoice: null, packing_list: null, bill_of_lading: null, freight_manifest: null, certificate_of_origin: null })
    setShipmentId(null)
    setGeneratedShipmentNumber(null)
    setSessionId(null)
    setDiscrepancies([])
    setFinalStatus(null)
    setSummary(null)
    setConfirmations({})
    setError(null)
    setExtractedDocuments(null)
    setFieldEdits({})
    setLineItemEdits({})
    setTableEdits({})
    setPendingResult(null)
    setSaveError(null)
    setReviewView("review")
    setCompleteView("results")
    setActiveDocKey(null)
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────────────────────────────────────

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-foreground mb-2">Vendor Document Validation</h1>
        <p className="text-muted-foreground">
          Step 2 — Upload and cross-validate vendor documents before transmitting to the clearing agent.
        </p>
      </div>

      {/* Step indicator */}
      {step !== "upload" && (
        <div className="flex items-center gap-2 mb-6">
          {(["upload", "field_review", "review", "complete"] as const).map((s, i) => {
            const labels: Record<string, string> = {
              upload: "Upload",
              field_review: "Review Fields",
              review: "Discrepancies",
              complete: "Complete",
            }
            const stepOrder = ["upload", "field_review", "review", "complete"]
            const currentIdx = stepOrder.indexOf(step === "processing" ? "field_review" : step)
            const thisIdx = stepOrder.indexOf(s)
            const done = thisIdx < currentIdx
            const active = thisIdx === currentIdx
            return (
              <div key={s} className="flex items-center gap-2">
                <div className={`flex items-center gap-1.5 text-xs font-medium ${active ? "text-primary" : done ? "text-green-600 dark:text-green-400" : "text-muted-foreground"}`}>
                  <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold border-2 ${active ? "border-primary bg-primary text-primary-foreground" : done ? "border-green-500 bg-green-500 text-white" : "border-muted-foreground/30"}`}>
                    {done ? <Check className="w-3 h-3" /> : i + 1}
                  </div>
                  {labels[s]}
                </div>
                {i < 3 && <div className={`w-8 h-px ${done ? "bg-green-400" : "bg-border"}`} />}
              </div>
            )
          })}
        </div>
      )}

      {/* Error banner */}
      {error && (
        <Card className="p-4 border-l-4 border-destructive bg-destructive/5 mb-6">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-destructive mt-0.5 flex-shrink-0" />
            <div>
              <p className="font-semibold text-destructive text-sm">Error</p>
              <p className="text-sm text-destructive/80 mt-0.5">{error}</p>
            </div>
          </div>
        </Card>
      )}

      {/* ── Upload ──────────────────────────────────────────────────────────── */}
      {step === "upload" && (
        <div className="space-y-4">
          <Card className="overflow-hidden">
            <button
              className="w-full flex items-center justify-between p-4 hover:bg-muted/30 transition-colors text-left"
              onClick={() => setShowShipmentDetails(!showShipmentDetails)}
            >
              <div className="flex items-center gap-2">
                <Settings2 className="w-4 h-4 text-muted-foreground" />
                <span className="text-sm font-medium text-foreground">Shipment Details</span>
                <span className="text-xs text-muted-foreground">(optional)</span>
              </div>
              {showShipmentDetails ? (
                <ChevronUp className="w-4 h-4 text-muted-foreground" />
              ) : (
                <ChevronDown className="w-4 h-4 text-muted-foreground" />
              )}
            </button>

            {showShipmentDetails && (
              <div className="px-4 pb-4 border-t border-border pt-4 grid grid-cols-2 gap-4">
                <div className="col-span-2 md:col-span-1">
                  <Label htmlFor="shipment-number" className="text-xs font-medium text-muted-foreground">Shipment Number</Label>
                  <Input id="shipment-number" value={shipmentNumber} onChange={(e) => setShipmentNumber(e.target.value)} placeholder="Auto-generated if empty" className="mt-1 text-sm" />
                </div>
                <div className="col-span-2 md:col-span-1">
                  <Label htmlFor="incoterm" className="text-xs font-medium text-muted-foreground">Incoterm</Label>
                  <Input id="incoterm" value={incoterm} onChange={(e) => setIncoterm(e.target.value)} placeholder="e.g. CIF, FOB, DDP" className="mt-1 text-sm" />
                </div>
                <div className="col-span-2 md:col-span-1">
                  <Label htmlFor="supplier-name" className="text-xs font-medium text-muted-foreground">Supplier Name</Label>
                  <Input id="supplier-name" value={supplierName} onChange={(e) => setSupplierName(e.target.value)} placeholder="Extracted from invoice if empty" className="mt-1 text-sm" />
                </div>
                <div className="col-span-2 md:col-span-1">
                  <Label htmlFor="transport-mode" className="text-xs font-medium text-muted-foreground">Transport Mode</Label>
                  <Input id="transport-mode" value={transportMode} onChange={(e) => setTransportMode(e.target.value)} placeholder="e.g. Sea, Air, Road" className="mt-1 text-sm" />
                </div>
                <div className="col-span-2">
                  <Label htmlFor="consignee-name" className="text-xs font-medium text-muted-foreground">Consignee Name</Label>
                  <Input id="consignee-name" value={consigneeName} onChange={(e) => setConsigneeName(e.target.value)} placeholder="Extracted from invoice if empty" className="mt-1 text-sm" />
                </div>
              </div>
            )}
          </Card>

          <Card className="p-6 space-y-3">
            <h2 className="text-base font-semibold text-foreground mb-2">Documents</h2>
            {DOC_SLOTS.map((slot) => (
              <FileSlot
                key={slot.key}
                slot={slot}
                file={files[slot.key]}
                onSelect={(f) => setFile(slot.key, f)}
                onRemove={() => setFile(slot.key, null)}
              />
            ))}
          </Card>

          <div className="flex justify-end">
            <Button onClick={handleValidate} disabled={!requiredFilled || submitting} className="bg-primary hover:bg-primary/90">
              Validate Documents
            </Button>
          </div>
        </div>
      )}

      {/* ── Processing ───────────────────────────────────────────────────────── */}
      {step === "processing" && (
        <Card className="p-12 text-center">
          <div className="flex justify-center mb-6">
            <div className="p-4 bg-primary/10 rounded-lg">
              <Loader className="w-8 h-8 text-primary animate-spin" />
            </div>
          </div>
          <h2 className="text-2xl font-bold text-foreground mb-2">Extracting &amp; Validating</h2>
          <p className="text-muted-foreground">
            AI is extracting and cross-validating your documents. This typically takes 3–5 minutes.
          </p>
          <p className="text-sm text-muted-foreground mt-3 font-mono">
            {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, "0")} elapsed — please keep this tab open
          </p>
        </Card>
      )}

      {/* ── Field Review ──────────────────────────────────────────────────────── */}
      {step === "field_review" && extractedDocuments && (
        <div className="space-y-4">
          {/* Header banner */}
          <Card className="p-5 border-l-4 border-primary bg-primary/5">
            <div className="flex items-start gap-3">
              <ClipboardCheck className="w-5 h-5 text-primary mt-0.5 flex-shrink-0" />
              <div>
                <p className="font-semibold text-foreground">Review Extracted Fields</p>
                <p className="text-sm text-muted-foreground mt-0.5">
                  Check every extracted value before it is saved. Each field shows its AI confidence score.
                  Hover a row to edit it — press Enter to confirm or Escape to cancel.
                </p>
              </div>
            </div>
          </Card>

          {/* Confidence legend */}
          <div className="flex items-center gap-4 px-1">
            <span className="text-xs text-muted-foreground font-medium">Confidence:</span>
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">90%+</span>
              <span className="text-xs text-muted-foreground">High</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">70–89%</span>
              <span className="text-xs text-muted-foreground">Medium</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">&lt;70%</span>
              <span className="text-xs text-muted-foreground">Low — verify manually</span>
            </div>
          </div>

          {/* Document panels */}
          {Object.entries(extractedDocuments).map(([docType, docMeta]) => (
            <DocumentFieldPanel
              key={docType}
              docType={docType}
              docMeta={docMeta}
              edits={fieldEdits[docType] ?? {}}
              itemEdits={lineItemEdits[docType] ?? {}}
              tableEdits={tableEdits[docType] ?? {}}
              onFieldChange={handleFieldChange}
              onItemChange={handleLineItemChange}
              onTableCellChange={handleTableCellChange}
            />
          ))}

          {/* Save error */}
          {saveError && (
            <Card className="p-4 border-l-4 border-destructive bg-destructive/5">
              <div className="flex items-start gap-3">
                <AlertCircle className="w-4 h-4 text-destructive mt-0.5 flex-shrink-0" />
                <p className="text-sm text-destructive">{saveError}</p>
              </div>
            </Card>
          )}

          {/* Actions */}
          <div className="flex justify-between items-center pt-2">
            <Button variant="outline" onClick={() => setStep("upload")}>
              Re-upload Documents
            </Button>
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="sm" onClick={handleSkipFieldReview} className="text-xs text-muted-foreground">
                Skip Review
              </Button>
              <Button
                onClick={handleSaveFields}
                disabled={saving}
                className="bg-primary hover:bg-primary/90"
              >
                {saving ? (
                  <Loader className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Save className="w-4 h-4 mr-2" />
                )}
                Save &amp; Continue
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ── HITL Review ──────────────────────────────────────────────────────── */}
      {step === "review" && (
        <div className="space-y-4">

          {/* Tab bar */}
          {(() => {
            const uploadedDocs = Object.entries(files).filter(([, f]) => f !== null)
            const tabs = [
              { v: "review" as const, label: "Discrepancy Review", icon: ClipboardCheck },
              { v: "documents" as const, label: "View Original Documents", count: uploadedDocs.length, icon: FileText },
            ]
            return (
              <div className="flex justify-center py-1">
                <div className="flex items-center bg-muted/70 rounded-xl p-1 gap-0.5 border border-border/50 shadow-sm">
                  {tabs.map(({ v, label, icon: Icon, count }) => (
                    <button
                      key={v}
                      onClick={() => {
                        setReviewView(v)
                        if (v === "documents" && !activeDocKey) setActiveDocKey(uploadedDocs[0]?.[0] ?? null)
                      }}
                      className={`flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-medium transition-all duration-150 ${
                        reviewView === v
                          ? "bg-background text-foreground shadow-sm border border-border/60"
                          : "text-muted-foreground hover:text-foreground hover:bg-background/50"
                      }`}
                    >
                      <Icon className={`w-3.5 h-3.5 ${reviewView === v ? "text-primary" : ""}`} />
                      {label}
                      {count !== undefined && (
                        <span className={`text-[11px] font-bold px-1.5 py-0.5 rounded-md ${reviewView === v ? "bg-primary/10 text-primary" : "bg-muted-foreground/15 text-muted-foreground"}`}>
                          {count}
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            )
          })()}

          {/* Document viewer panel */}
          {reviewView === "documents" && (() => {
            const uploadedDocs = Object.entries(files).filter(([, f]) => f !== null) as [string, File][]
            const currentKey = activeDocKey ?? uploadedDocs[0]?.[0] ?? null
            const currentFile = currentKey ? files[currentKey as keyof typeof files] : null
            const blobUrl = currentKey ? getDocBlobUrl(currentKey) : null
            const isPdf = currentFile?.type === "application/pdf" || currentFile?.name?.toLowerCase().endsWith(".pdf")
            return (
              <div className="flex gap-4 h-[780px]">
                <div className="w-52 flex-shrink-0 flex flex-col gap-1">
                  <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground px-1 mb-1">Uploaded Files</p>
                  {uploadedDocs.map(([key, file]) => (
                    <button key={key} onClick={() => setActiveDocKey(key)}
                      className={`text-left px-3 py-2.5 rounded-lg border transition-colors ${currentKey === key ? "border-primary bg-primary/5 text-primary" : "border-border hover:bg-muted/50 text-foreground"}`}>
                      <div className="flex items-center gap-2">
                        <FileText className={`w-3.5 h-3.5 flex-shrink-0 ${currentKey === key ? "text-primary" : "text-muted-foreground"}`} />
                        <div className="min-w-0">
                          <p className="text-[12px] font-semibold truncate">{DOC_LABEL[key] ?? key.replace(/_/g, " ")}</p>
                          <p className="text-[10px] text-muted-foreground truncate mt-0.5" title={file.name}>{file.name}</p>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
                <div className="flex-1 min-w-0 rounded-lg border border-border overflow-hidden bg-muted/20">
                  {blobUrl && currentFile ? (
                    isPdf
                      ? <iframe key={currentKey} src={blobUrl} title={DOC_LABEL[currentKey!] ?? currentKey!} className="w-full h-full border-0" />
                      : <div className="w-full h-full flex items-center justify-center overflow-auto p-4">
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img key={currentKey} src={blobUrl} alt={DOC_LABEL[currentKey!] ?? currentKey!} className="max-w-full max-h-full object-contain rounded" />
                        </div>
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <p className="text-sm text-muted-foreground">Select a document to preview</p>
                    </div>
                  )}
                </div>
              </div>
            )
          })()}

          {/* Existing review content */}
          {reviewView === "review" && <>

          {/* Summary */}
          {summary && (
            <div className="grid grid-cols-4 gap-3">
              {[
                { label: "Total Checks", value: summary.total_checks ?? 0, color: "text-foreground" },
                { label: "Passed", value: summary.passed_checks ?? 0, color: "text-green-600" },
                { label: "Failed", value: summary.failed_checks ?? 0, color: (summary.failed_checks ?? 0) > 0 ? "text-destructive" : "text-muted-foreground" },
                { label: "Discrepancies", value: discrepancies.length, color: discrepancies.length > 0 ? "text-amber-500" : "text-muted-foreground" },
              ].map(({ label, value, color }) => (
                <Card key={label} className="p-3 text-center">
                  <p className="text-xs text-muted-foreground mb-1">{label}</p>
                  <p className={`text-xl font-bold ${color}`}>{value}</p>
                </Card>
              ))}
            </div>
          )}

          {/* Shipment + documents processed strip */}
          {(generatedShipmentNumber || shipmentNumber || summary?.documents_processed) && (
            <Card className="px-4 py-3">
              <div className="flex items-center gap-6 flex-wrap text-xs">
                {(generatedShipmentNumber || shipmentNumber) && (
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">Shipment:</span>
                    <span className="font-mono font-semibold text-foreground">
                      {shipmentNumber || generatedShipmentNumber}
                    </span>
                  </div>
                )}
                {summary?.documents_processed && (
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-muted-foreground">Documents:</span>
                    {(summary.documents_processed as string[]).map((doc) => (
                      <span key={doc} className="font-mono bg-muted px-1.5 py-0.5 rounded text-foreground capitalize">
                        {doc.replace(/_/g, " ")}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </Card>
          )}

          {/* Extracted documents reference — collapsed, one panel per doc */}
          {extractedDocuments && Object.keys(extractedDocuments).length > 0 && (
            <ExtractedDocsReference extractedDocuments={extractedDocuments} />
          )}

          <Card className="p-5 border-l-4 border-amber-400 bg-amber-50/30 dark:bg-amber-900/10">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-500 mt-0.5 flex-shrink-0" />
              <div>
                <p className="font-semibold text-foreground">Discrepancies Detected</p>
                <p className="text-sm text-muted-foreground mt-0.5">
                  {discrepancies.length} discrepanc{discrepancies.length !== 1 ? "ies" : "y"} found. Review
                  each one and choose to accept or reject before proceeding.
                </p>
              </div>
            </div>
          </Card>

          <div className="space-y-5">
            {Object.entries(
              discrepancies.reduce((acc, disc) => {
                const key = disc.source_document ?? "other"
                if (!acc[key]) acc[key] = []
                acc[key].push(disc)
                return acc
              }, {} as Record<string, ValidationDiscrepancy[]>)
            ).map(([docKey, discs]) => (
              <div key={docKey}>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">
                    {DOC_LABEL[docKey] ?? docKey.replace(/_/g, " ")}
                  </span>
                  <span className="text-[10px] font-mono text-muted-foreground/60">
                    {discs.length} issue{discs.length !== 1 ? "s" : ""}
                  </span>
                </div>
                <div className="space-y-2">
                  {discs.map((disc) => (
                    <DiscrepancyCard
                      key={disc.id}
                      disc={disc}
                      confirmed={confirmations[disc.id] ?? null}
                      onToggle={(id, val) => setConfirmations((prev) => ({ ...prev, [id]: val }))}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* Validation checks */}
          {validationResults && validationResults.length > 0 && (
            <ValidationChecksPanel results={validationResults} />
          )}

          </>}

          {/* Action footer — always visible */}
          <div className="flex justify-between pt-2">
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setStep("upload")}>
                Re-upload Documents
              </Button>
              {extractedDocuments && Object.keys(extractedDocuments).length > 0 && (
                <Button variant="outline" onClick={() => setStep("field_review")}>
                  <Pencil className="w-3.5 h-3.5 mr-1.5" />
                  Edit Fields
                </Button>
              )}
            </div>
            <Button
              onClick={handleResume}
              disabled={
                submitting ||
                discrepancies.some((d) => confirmations[d.id] === null)
              }
              className="bg-primary hover:bg-primary/90"
            >
              {submitting ? <Loader className="w-4 h-4 mr-2 animate-spin" /> : null}
              Submit Decisions
            </Button>
          </div>
        </div>
      )}

      {/* ── Complete ──────────────────────────────────────────────────────────── */}
      {step === "complete" && (
        <div className="space-y-5">

          {/* ── View switcher tab bar ── */}
          {(() => {
            const uploadedDocs = Object.entries(files).filter(([, f]) => f !== null)
            const tabs = [
              { v: "results" as const, label: "Validation Results", icon: ShieldCheck },
              { v: "documents" as const, label: "Documents", count: uploadedDocs.length, icon: FileText },
            ]
            return (
              <div className="flex justify-center py-1">
                <div className="flex items-center bg-muted/70 rounded-xl p-1 gap-0.5 border border-border/50 shadow-sm">
                  {tabs.map(({ v, label, icon: Icon, count }) => (
                    <button
                      key={v}
                      onClick={() => {
                        setCompleteView(v)
                        if (v === "documents" && !activeDocKey) setActiveDocKey(uploadedDocs[0]?.[0] ?? null)
                      }}
                      className={`flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-medium transition-all duration-150 ${
                        completeView === v
                          ? "bg-background text-foreground shadow-sm border border-border/60"
                          : "text-muted-foreground hover:text-foreground hover:bg-background/50"
                      }`}
                    >
                      <Icon className={`w-3.5 h-3.5 ${completeView === v ? "text-primary" : ""}`} />
                      {label}
                      {count !== undefined && (
                        <span className={`text-[11px] font-bold px-1.5 py-0.5 rounded-md ${completeView === v ? "bg-primary/10 text-primary" : "bg-muted-foreground/15 text-muted-foreground"}`}>
                          {count}
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            )
          })()}

          {/* ── Documents viewer ── */}
          {completeView === "documents" && (() => {
            const uploadedDocs = Object.entries(files).filter(([, f]) => f !== null) as [string, File][]
            const currentKey = activeDocKey ?? uploadedDocs[0]?.[0] ?? null
            const currentFile = currentKey ? files[currentKey as keyof typeof files] : null
            const blobUrl = currentKey ? getDocBlobUrl(currentKey) : null
            const isPdf = currentFile?.type === "application/pdf" || currentFile?.name?.toLowerCase().endsWith(".pdf")

            return (
              <div className="flex gap-4 h-[780px]">
                {/* Sidebar — document list */}
                <div className="w-52 flex-shrink-0 flex flex-col gap-1">
                  <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground px-1 mb-1">
                    Uploaded Files
                  </p>
                  {uploadedDocs.map(([key, file]) => (
                    <button
                      key={key}
                      onClick={() => setActiveDocKey(key)}
                      className={`text-left px-3 py-2.5 rounded-lg border transition-colors ${
                        currentKey === key
                          ? "border-primary bg-primary/5 text-primary"
                          : "border-border hover:bg-muted/50 text-foreground"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <FileText className={`w-3.5 h-3.5 flex-shrink-0 ${currentKey === key ? "text-primary" : "text-muted-foreground"}`} />
                        <div className="min-w-0">
                          <p className="text-[12px] font-semibold truncate">
                            {DOC_LABEL[key] ?? key.replace(/_/g, " ")}
                          </p>
                          <p className="text-[10px] text-muted-foreground truncate mt-0.5" title={file.name}>
                            {file.name}
                          </p>
                        </div>
                      </div>
                    </button>
                  ))}
                  {uploadedDocs.length === 0 && (
                    <p className="text-xs text-muted-foreground px-1">No files uploaded.</p>
                  )}
                </div>

                {/* Viewer pane */}
                <div className="flex-1 min-w-0 rounded-lg border border-border overflow-hidden bg-muted/20">
                  {blobUrl && currentFile ? (
                    isPdf ? (
                      <iframe
                        key={currentKey}
                        src={blobUrl}
                        title={DOC_LABEL[currentKey!] ?? currentKey!}
                        className="w-full h-full border-0"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center overflow-auto p-4">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          key={currentKey}
                          src={blobUrl}
                          alt={DOC_LABEL[currentKey!] ?? currentKey!}
                          className="max-w-full max-h-full object-contain rounded"
                        />
                      </div>
                    )
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <p className="text-sm text-muted-foreground">Select a document to preview</p>
                    </div>
                  )}
                </div>
              </div>
            )
          })()}

          {/* ── Validation results (default view) ── */}
          {completeView === "results" && <>

          {/* Status Banner */}
          <Card
            className={`p-5 border-l-4 ${
              finalStatus === "passed"
                ? "border-green-500 bg-green-50/30 dark:bg-green-900/10"
                : finalStatus === "failed"
                ? "border-destructive bg-destructive/5"
                : "border-amber-400 bg-amber-50/30 dark:bg-amber-900/10"
            }`}
          >
            <div className="flex items-start gap-4">
              <div
                className={`p-2.5 rounded-lg flex-shrink-0 ${
                  finalStatus === "passed"
                    ? "bg-green-100 dark:bg-green-900/30"
                    : finalStatus === "failed"
                    ? "bg-destructive/10"
                    : "bg-amber-100 dark:bg-amber-900/30"
                }`}
              >
                {finalStatus === "passed" ? (
                  <CheckCircle className="w-5 h-5 text-green-600" />
                ) : finalStatus === "failed" ? (
                  <AlertCircle className="w-5 h-5 text-destructive" />
                ) : (
                  <AlertTriangle className="w-5 h-5 text-amber-500" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <h2 className="text-lg font-bold text-foreground">
                  {finalStatus === "passed"
                    ? "Validation Passed"
                    : finalStatus === "failed"
                    ? "Validation Failed"
                    : "Requires Attention"}
                </h2>
                <p className="text-muted-foreground text-sm mt-0.5">
                  {finalStatus === "passed"
                    ? "All vendor documents are consistent. You may transmit to the clearing agent."
                    : finalStatus === "failed"
                    ? "Discrepancies remain unresolved. Please correct the documents and retry."
                    : "Some discrepancies were found. Review the details below before proceeding."}
                </p>
                {(generatedShipmentNumber || shipmentNumber) && (
                  <p className="text-xs text-muted-foreground mt-2 font-mono">
                    {shipmentNumber || generatedShipmentNumber}
                  </p>
                )}
              </div>
              {shipmentId && (
                <button
                  onClick={() => navigator.clipboard.writeText(shipmentId)}
                  className="flex-shrink-0 flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground px-2.5 py-1.5 rounded-md border border-border hover:bg-muted transition-colors"
                  title="Copy shipment ID"
                >
                  <Copy className="w-3 h-3" />
                  Copy ID
                </button>
              )}
            </div>
          </Card>

          {/* Stats row */}
          {summary && (
            <div className="grid grid-cols-4 gap-3">
              {[
                { label: "Total Checks", value: summary.total_checks ?? 0, color: "text-foreground" },
                { label: "Passed", value: summary.passed_checks ?? 0, color: "text-green-600 dark:text-green-400" },
                { label: "Failed", value: summary.failed_checks ?? 0, color: (summary.failed_checks ?? 0) > 0 ? "text-destructive" : "text-muted-foreground" },
                { label: "Discrepancies", value: summary.total_discrepancies ?? discrepancies.length, color: discrepancies.length > 0 ? "text-amber-500" : "text-muted-foreground" },
              ].map(({ label, value, color }) => (
                <Card key={label} className="p-3 text-center">
                  <p className={`text-2xl font-bold tabular-nums ${color}`}>{value}</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">{label}</p>
                </Card>
              ))}
            </div>
          )}

          {/* ── Ghana Customs Checklist Table ── */}
          {extractedDocuments && Object.keys(extractedDocuments).length > 0 && (() => {
            const DOC_ORDER = ["invoice", "packing_list", "bill_of_lading", "freight_manifest", "certificate_of_origin"]
            const docs = Object.keys(extractedDocuments).sort(
              (a, b) => DOC_ORDER.indexOf(a) - DOC_ORDER.indexOf(b)
            )

            // 17-item Ghana Customs checklist — derived from vendor_document_validation.yaml
            type ChecklistEntry = {
              id: string
              label: string
              docFields: Partial<Record<string, string | string[]>>
              boeOnly?: boolean
            }
            const CHECKLIST: ChecklistEntry[] = [
              // ── Vendor documents (Step 2) ──────────────────────────────────
              // docFields lists canonical name first, then every document-specific
              // label Claude may extract verbatim (exact label → snake_case).
              // Shipper is physically redacted on PL and BOL for all Nestlé Ghana supplier docs.
              // Only the invoice carries the full shipper block.
              { id: "shippers_address",  label: "Shipper's Name & Address",
                docFields: { invoice: ["shipper_name", "shipper_address"] } },
              { id: "consignee_address", label: "Consignee Name & Address",
                docFields: { invoice: ["consignee_name", "consignee_address"], packing_list: ["consignee_name", "consignee_address", "bill_to_name", "bill_to_address"], bill_of_lading: ["consignee_name", "consignee_address"] } },
              // PO: invoice → "Your Order Number", BOL/PL → "Customer ref." / "CUSTOMER REF."
              { id: "po_number",         label: "PO / Reference No.",
                docFields: { invoice: ["po_number", "your_order_number", "customer_ref", "customer_reference"], packing_list: ["po_number", "customer_ref", "customer_reference"], bill_of_lading: ["po_number", "customer_ref", "customer_reference"] } },
              // Product description: in line-item table rows (items[]) — resolveVal handles items fallback
              { id: "product_desc",      label: "Product Description",
                docFields: { invoice: ["product_description", "description", "goods_description"], packing_list: ["product_description", "description", "goods_description"], bill_of_lading: ["product_description", "goods_description", "description"] } },
              // FOB: first matching amount field + currency.
              // total_excl_vat is the Vreugdenhil label (= FOB when VAT = 0).
              // total_fob_value / total_invoice_value are canonical fallbacks.
              // Do NOT include both total_excl_vat and total_incl_vat — they are
              // the same value when VAT = 0 and would show twice.
              { id: "fob_value",         label: "FOB Value & Currency",
                docFields: { invoice: ["total_excl_vat", "total_fob_value", "total_invoice_value", "currency"] } },
              // Incoterm: invoice → "Shipping Condition", packing list → "Delivery terms".
              // BOL has no formal incoterm field (states "Freight Collect" instead) — excluded.
              { id: "incoterm",          label: "Incoterm",
                docFields: { invoice: ["incoterm", "shipping_condition"], packing_list: ["incoterm", "delivery_terms"] } },
              { id: "insurance",         label: "Insurance",                 docFields: { invoice: "insurance_value" } },
              { id: "freight",           label: "Freight",                   docFields: { invoice: "freight_value" } },
              // Net weight: invoice → "Total Net Weight", BOL → "NETT WEIGHT", PL → "Total sent Net weight"
              { id: "net_weight",        label: "Net Weight",
                docFields: { invoice: ["net_weight", "total_net_weight"], packing_list: ["net_weight", "total_sent_net_weight"], bill_of_lading: ["net_weight", "nett_weight"] } },
              // Gross weight: invoice → "Total Gross Weight", BOL → "GROSS WEIGHT", PL → "Total sent Gross weight"
              { id: "gross_weight",      label: "Gross Weight",
                docFields: { invoice: ["gross_weight", "total_gross_weight"], packing_list: ["gross_weight", "total_sent_gross_weight"], bill_of_lading: ["gross_weight"] } },
              { id: "country_of_origin", label: "Country of Origin",         docFields: { certificate_of_origin: "country_of_origin" } },
              // Quantity: invoice → "Total Units", BOL → "TOTALS" (page-2 totals block), PL → "Total sent Units"
              { id: "quantity",          label: "Quantity",
                docFields: { invoice: ["quantity", "total_units"], packing_list: ["quantity", "total_sent_units"], bill_of_lading: ["quantity", "total_units", "totals"] } },
              { id: "container_count",   label: "Number of Containers",      docFields: { packing_list: ["container_count", "container_numbers"], bill_of_lading: ["container_count", "container_numbers"] } },
              // ── BOE only (Step 6) ──────────────────────────────────────────
              { id: "declarant_name",    label: "Declarant Name",            docFields: {}, boeOnly: true },
              { id: "declarant_address", label: "Declarant Address",         docFields: {}, boeOnly: true },
              { id: "hs_code",           label: "H.S. Code",                 docFields: {}, boeOnly: true },
              { id: "import_duty",       label: "Import Duty",               docFields: {}, boeOnly: true },
              { id: "vat_nhil",          label: "VAT/NHIL",                  docFields: {}, boeOnly: true },
              { id: "cpc",               label: "CPC",                       docFields: {}, boeOnly: true },
            ]

            // Discrepancy lookup: "doc::field" -> discrepancy
            const discLookup = (discrepancies ?? []).reduce((acc, d) => {
              const key = `${d.source_document ?? ""}::${d.field_name ?? d.field ?? ""}`
              acc[key] = d
              return acc
            }, {} as Record<string, ValidationDiscrepancy>)

            // Incoterm rule check — absence of insurance/freight is correct for FCA
            const incotermRulePassed = (validationResults ?? []).some(
              (r) => (r.field_name === "freight_insurance" || r.validator_name === "incoterm_validator") && r.passed
            )

            const mismatches = (discrepancies ?? []).filter(
              (d) => !(d.source_value === null && d.target_value === null)
            )

            // Resolve single or multi-field spec from extracted doc data.
            // Falls back to items[] for two special cases:
            //   1. Description fields — Claude places product descriptions in line-item rows.
            //   2. container_count / container_numbers — PL has no top-level count field;
            //      derive from items[] when absent.
            const _DESC_FIELD_IDS = new Set(["description", "goods_description", "product_description", "article_description"])
            const _CONTAINER_IDS  = new Set(["container_count", "container_numbers", "container_no", "container_nos"])
            const _DESC_SKIP = new Set(["CONTAINER SAID TO CONTAIN", ""])
            const resolveVal = (spec: string | string[], data: Record<string, any>, items?: any[]): string | null => {
              const specs = Array.isArray(spec) ? spec : [spec]
              const parts = specs.map((f) => { const v = data[f]; return v != null ? unwrap(v) : null }).filter(Boolean)
              if (parts.length) return parts.join(" / ")
              if (!items || !items.length) return null

              // Fallback 1: product description from line-item rows.
              // Use unwrap() so both plain strings and {value, confidence} objects work.
              if (specs.some((s) => _DESC_FIELD_IDS.has(s))) {
                for (const item of items) {
                  if (!item || typeof item !== "object") continue
                  for (const k of ["description", "goods_description", "product_description", "article_description"]) {
                    const raw = (item as Record<string, any>)[k]
                    if (raw == null) continue
                    const v = unwrap(raw)
                    if (v && !_DESC_SKIP.has(v.trim().toUpperCase()))
                      return v.trim()
                  }
                }
              }

              // Fallback 2: container count / numbers from items[] rows.
              // Packing list has no top-level container_count; extract container_no from each row.
              // Each container may have multiple batch rows — deduplicate with a Set.
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

            return (
              <>
                <Card className="overflow-hidden">
                  <div className="px-5 py-3.5 border-b border-border flex items-center gap-3 bg-muted/20">
                    <ClipboardCheck className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                    <h3 className="font-semibold text-foreground text-sm">Ghana Customs Checklist</h3>
                    <span className="text-[11px] text-muted-foreground">
                      {CHECKLIST.filter((c) => !c.boeOnly).length} vendor doc checks · {CHECKLIST.filter((c) => c.boeOnly).length} deferred to BOE (Step 6)
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
                          const isFirstBoe = entry.boeOnly && !CHECKLIST[i - 1]?.boeOnly
                          const rowHasIssue = !entry.boeOnly && docs.some((doc) => entryHasDisc(entry, doc))
                          const rowBg = entry.boeOnly ? "bg-muted/5" : rowHasIssue ? "bg-red-50/30 dark:bg-red-900/5" : i % 2 === 1 ? "bg-muted/10" : ""
                          const stickyBg = entry.boeOnly ? "bg-muted/10" : rowHasIssue ? "bg-red-50/60 dark:bg-red-900/10" : i % 2 === 1 ? "bg-muted/20" : "bg-background"

                          return (
                            <React.Fragment key={entry.id}>
                              {isFirstBoe && (
                                <tr className="border-b border-border">
                                  <td colSpan={2 + docs.length} className="sticky left-0 px-4 py-1.5 bg-muted/40 text-[11px] font-semibold text-muted-foreground uppercase tracking-widest select-none">
                                    BOE Validation — Step 6
                                  </td>
                                </tr>
                              )}
                            <tr className={`border-b border-border/40 last:border-b-0 ${rowBg}`}>
                              <td className={`sticky left-0 z-10 text-center px-3 py-2 text-[11px] font-mono text-muted-foreground border-r border-border w-10 select-none ${stickyBg}`}>{i + 1}</td>
                              <td className={`sticky left-10 z-10 px-4 py-2.5 text-[12px] font-semibold border-r border-border whitespace-nowrap ${stickyBg} ${entry.boeOnly ? "text-muted-foreground/60" : "text-foreground"}`}>
                                {entry.label}
                              </td>

                              {docs.map((doc) => {
                                if (entry.boeOnly) {
                                  return <td key={doc} className="px-4 py-2.5 border-r border-border/30 last:border-r-0"><span className="text-muted-foreground/25 font-mono text-sm">—</span></td>
                                }

                                const spec = entry.docFields[doc]
                                if (!spec) {
                                  return <td key={doc} className="px-4 py-2.5 border-r border-border/30 last:border-r-0"><span className="text-muted-foreground/25 font-mono text-sm">—</span></td>
                                }

                                const docData  = extractedDocuments[doc]?.fields ?? {}
                                const docItems = extractedDocuments[doc]?.items  ?? []
                                const val = resolveVal(spec, docData, docItems)
                                const isEmpty = !val || val.trim() === ""
                                const isConflict = entryHasDisc(entry, doc) && !isEmpty
                                const isMissing = isEmpty

                                // Insurance/freight: absent is correct for FCA
                                if ((entry.id === "insurance" || entry.id === "freight") && isEmpty && incotermRulePassed) {
                                  return (
                                    <td key={doc} className="px-4 py-2.5 border-r border-border/30 last:border-r-0">
                                      <span className="flex items-center gap-1.5 text-[12px] text-green-600 dark:text-green-400">
                                        <CheckCircle className="w-3.5 h-3.5 flex-shrink-0" />
                                        <span className="font-mono">Compliant</span>
                                      </span>
                                    </td>
                                  )
                                }

                                return (
                                  <td key={doc} className="px-4 py-2.5 align-middle border-r border-border/30 last:border-r-0">
                                    {isMissing ? (
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
                                )
                              })}
                            </tr>
                            </React.Fragment>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                </Card>

                {/* Value conflict details */}
                {mismatches.length > 0 && (
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
                        // A "plain dict" means { doc_type: value } — not a scalar,
                        // not a {value, confidence} wrapper, not an array.
                        const isPlainDict = (v: any): v is Record<string, any> =>
                          v !== null && v !== undefined &&
                          typeof v === "object" && !Array.isArray(v) &&
                          !("value" in v)

                        // Expand a value into per-document card entries.
                        // If val is a plain dict → one card per doc key.
                        // If val is scalar and we know the doc → one card.
                        // If val is scalar and doc is unknown → skip (can't label it).
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
                                      ? "border-blue-400 dark:border-blue-600"
                                      : role === "target"
                                      ? "border-amber-400 dark:border-amber-600"
                                      : "border-border"
                                  }`}
                                >
                                  {/* Card header — document name is the primary identity */}
                                  <div
                                    className={`px-4 py-2.5 border-b flex items-center justify-between gap-3 ${
                                      role === "source"
                                        ? "bg-blue-50 dark:bg-blue-900/25 border-blue-200 dark:border-blue-700"
                                        : role === "target"
                                        ? "bg-amber-50 dark:bg-amber-900/25 border-amber-200 dark:border-amber-700"
                                        : "bg-muted/40 border-border"
                                    }`}
                                  >
                                    <div className="flex items-center gap-2 min-w-0">
                                      <FileText
                                        className={`w-3.5 h-3.5 flex-shrink-0 ${
                                          role === "source"
                                            ? "text-blue-500 dark:text-blue-400"
                                            : role === "target"
                                            ? "text-amber-500 dark:text-amber-400"
                                            : "text-muted-foreground"
                                        }`}
                                      />
                                      <p
                                        className={`text-[12px] font-bold truncate ${
                                          role === "source"
                                            ? "text-blue-800 dark:text-blue-300"
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
                                            ? "bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300"
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
                )}
              </>
            )
          })()}

          {/* Checks Run — reuse collapsible panel (starts collapsed, failed-only view) */}
          {validationResults && validationResults.length > 0 && (
            <ValidationChecksPanel results={validationResults} />
          )}

          {/* Workflow Notes */}
          {summary?.messages && summary.messages.length > 0 && (
            <Card className="p-4">
              <h3 className="font-semibold text-sm text-foreground mb-2">Workflow Notes</h3>
              <ul className="space-y-1">
                {summary.messages.map((msg: string, i: number) => (
                  <li key={i} className="text-xs text-muted-foreground flex gap-2">
                    <span className="text-muted-foreground/40">•</span>
                    <span>{msg}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {/* close completeView === "results" fragment */}
          </>}

          {/* ── Action footer ── always visible regardless of active tab ── */}
          <Card className="p-5 space-y-3">
            {finalStatus !== "failed" ? (
              <a href={`/validation/boe${shipmentId ? `?shipment_id=${shipmentId}` : ""}`} className="block">
                <Button className="w-full bg-primary hover:bg-primary/90">
                  Proceed to Step 6 — BOE Validation
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </a>
            ) : (
              <Button className="w-full" variant="destructive" onClick={handleReset}>
                Fix Documents &amp; Retry
              </Button>
            )}

            <div className="flex gap-2">
              {extractedDocuments && Object.keys(extractedDocuments).length > 0 && (
                <Button variant="outline" onClick={() => setStep("field_review")} className="flex-1 text-sm">
                  <Pencil className="w-3.5 h-3.5 mr-1.5" />
                  Edit Extracted Fields
                </Button>
              )}
              <Button variant="outline" onClick={handleReset} className="flex-1 text-sm">
                New Validation
              </Button>
            </div>
          </Card>

        </div>
      )}
    </div>
  )
}

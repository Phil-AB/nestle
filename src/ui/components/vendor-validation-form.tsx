"use client"

import { useState, useEffect, useRef, useCallback } from "react"
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
  if (typeof v === "object") return JSON.stringify(v)
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
  const severityClass =
    disc.severity === "critical"
      ? "border-destructive/40 bg-destructive/5"
      : disc.severity === "major"
      ? "border-amber-400/40 bg-amber-50/30 dark:bg-amber-900/10"
      : "border-border bg-muted/20"

  return (
    <div className={`rounded-lg border p-4 ${severityClass}`}>
      <div className="flex items-start gap-3 cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <AlertTriangle
          className={`w-4 h-4 mt-0.5 flex-shrink-0 ${
            disc.severity === "critical" ? "text-destructive" : "text-amber-500"
          }`}
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-sm text-foreground">
              {disc.field_name ?? disc.field ?? "—"}
            </span>
            <span
              className={`text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded ${
                disc.severity === "critical"
                  ? "bg-destructive/10 text-destructive"
                  : "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
              }`}
            >
              {disc.severity}
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
              <p className="font-medium text-foreground truncate">{String(disc.source_value ?? "—")}</p>
            </div>
            <div className="p-2 bg-card rounded border border-border">
              <p className="text-muted-foreground mb-0.5">{disc.target_document}</p>
              <p className="font-medium text-foreground truncate">{String(disc.target_value ?? "—")}</p>
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
                      {val || <span className="text-muted-foreground italic">—</span>}
                    </p>
                  </div>
                  <ConfidenceBadge score={conf} />
                </div>
              )
            })}
          </div>

          {docMeta.items && docMeta.items.length > 0 && (
            <div className="mt-3 pt-3 border-t border-border">
              <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground mb-2">
                Line Items ({docMeta.items.length})
              </p>
              <div className="space-y-1 max-h-28 overflow-y-auto">
                {docMeta.items.map((item, i) => (
                  <div key={i} className="text-[11px] font-mono text-muted-foreground bg-muted/40 rounded px-2 py-1 truncate">
                    {JSON.stringify(item, (_, v) =>
                      typeof v === "object" && v !== null && "value" in v ? v.value : v
                    ).slice(0, 200)}
                  </div>
                ))}
              </div>
            </div>
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
                    {r.severity && r.severity !== "info" && (
                      <span className={`text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded ${
                        r.severity === "critical" ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                        : r.severity === "major" ? "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
                        : "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
                      }`}>
                        {r.severity}
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-muted-foreground mt-0.5 leading-relaxed">{r.message}</p>
                  {!r.passed && (r.source_value !== undefined || r.target_value !== undefined) && (
                    <div className="flex gap-3 mt-1.5 flex-wrap">
                      {r.source_value !== undefined && (
                        <span className="text-[10px] font-mono bg-muted/60 px-1.5 py-0.5 rounded">
                          Got: {String(r.source_value).slice(0, 80)}
                        </span>
                      )}
                      {r.target_value !== undefined && r.target_value !== null && (
                        <span className="text-[10px] font-mono bg-muted/60 px-1.5 py-0.5 rounded">
                          Expected: {String(r.target_value).slice(0, 80)}
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
  const confidence = deriveConfidence(rawValue)
  const displayValue = editedValue !== undefined ? editedValue : unwrap(rawValue)
  const isEdited = editedValue !== undefined && editedValue !== unwrap(rawValue)

  const startEdit = () => {
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
        {editing ? (
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

      {/* Confidence */}
      <div className="flex-shrink-0">
        <ConfidenceBadge score={confidence} />
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
  onFieldChange,
}: {
  docType: string
  docMeta: ExtractedDocumentMeta
  edits: Record<string, string>
  onFieldChange: (docType: string, key: string, val: string) => void
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

          {/* Line items summary */}
          {docMeta.items && docMeta.items.length > 0 && (
            <div className="py-2.5 border-t border-border mt-1">
              <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                Line Items — {docMeta.items.length} row{docMeta.items.length !== 1 ? "s" : ""}
              </span>
              <div className="mt-2 space-y-1.5 max-h-40 overflow-y-auto">
                {docMeta.items.slice(0, 10).map((item, i) => (
                  <div key={i} className="text-[11px] font-mono text-muted-foreground bg-muted/40 rounded px-2 py-1 truncate">
                    {JSON.stringify(item, (_, v) => (typeof v === "object" && v !== null && "value" in v ? v.value : v)).slice(0, 200)}
                  </div>
                ))}
                {docMeta.items.length > 10 && (
                  <p className="text-[10px] text-muted-foreground text-center">
                    + {docMeta.items.length - 10} more rows
                  </p>
                )}
              </div>
            </div>
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
      // Save edits for each document that has changes
      const savePromises = Object.entries(fieldEdits)
        .filter(([, edits]) => Object.keys(edits).length > 0)
        .map(([docType, edits]) => {
          const docId = extractedDocuments[docType]?.document_id
          if (!docId) return Promise.resolve()
          return apiClient.updateDocumentFields(docId, edits, {
            updated_by: "field_review",
            update_reason: "User reviewed and corrected extracted fields before validation",
          })
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
    setPendingResult(null)
    setSaveError(null)
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────────────────────────────────────

  return (
    <div className="p-8 max-w-3xl mx-auto">
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
              onFieldChange={handleFieldChange}
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

          <div className="space-y-3">
            {discrepancies.map((disc) => (
              <DiscrepancyCard
                key={disc.id}
                disc={disc}
                confirmed={confirmations[disc.id] ?? null}
                onToggle={(id, val) => setConfirmations((prev) => ({ ...prev, [id]: val }))}
              />
            ))}
          </div>

          {/* Validation checks */}
          {validationResults && validationResults.length > 0 && (
            <ValidationChecksPanel results={validationResults} />
          )}

          <div className="flex justify-between pt-2">
            <Button variant="outline" onClick={() => setStep("upload")}>
              Re-upload Documents
            </Button>
            <Button
              onClick={handleResume}
              disabled={
                submitting ||
                discrepancies
                  .filter((d) => d.severity === "critical")
                  .some((d) => confirmations[d.id] === null)
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
        <div className="space-y-4">
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
                    ? "Critical discrepancies remain unresolved. Please correct the documents and retry."
                    : "Some discrepancies were found. Review the details below before proceeding."}
                </p>
                {(generatedShipmentNumber || shipmentNumber) && (
                  <p className="text-xs text-muted-foreground mt-1.5">
                    Shipment: <code className="font-mono">{shipmentNumber || generatedShipmentNumber}</code>
                  </p>
                )}
              </div>
            </div>
          </Card>

          {summary && (
            <div className="grid grid-cols-4 gap-3">
              {[
                { label: "Total Checks", value: summary.total_checks ?? 0, color: "text-foreground" },
                { label: "Passed", value: summary.passed_checks ?? 0, color: "text-green-600" },
                { label: "Failed", value: summary.failed_checks ?? 0, color: "text-destructive" },
                { label: "Discrepancies", value: summary.total_discrepancies ?? 0, color: "text-amber-500" },
              ].map(({ label, value, color }) => (
                <Card key={label} className="p-3 text-center">
                  <p className={`text-2xl font-bold ${color}`}>{value}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{label}</p>
                </Card>
              ))}
            </div>
          )}

          {summary && (summary.critical > 0 || summary.major > 0 || summary.minor > 0) && (
            <div className="flex gap-3">
              {[
                { label: "Critical", count: summary.critical, bg: "bg-destructive/10", text: "text-destructive" },
                { label: "Major", count: summary.major, bg: "bg-amber-50 dark:bg-amber-900/20", text: "text-amber-600 dark:text-amber-400" },
                { label: "Minor", count: summary.minor, bg: "bg-blue-50 dark:bg-blue-900/20", text: "text-blue-600 dark:text-blue-400" },
              ]
                .filter((s) => s.count > 0)
                .map(({ label, count, bg, text }) => (
                  <span key={label} className={`text-xs font-semibold px-2.5 py-1 rounded-full ${bg} ${text}`}>
                    {count} {label}
                  </span>
                ))}
            </div>
          )}

          {validationResults && validationResults.length > 0 && (() => {
            const groups: Record<string, any[]> = {}
            for (const r of validationResults) {
              const key = r.validator_name ?? "other"
              if (!groups[key]) groups[key] = []
              groups[key].push(r)
            }
            const validatorLabel = (name: string) =>
              name.replace(/_validator$/, "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())

            return (
              <Card className="p-0 overflow-hidden">
                <div className="px-4 py-3 border-b border-border flex items-center gap-2">
                  <ClipboardCheck className="w-4 h-4 text-muted-foreground" />
                  <h3 className="font-semibold text-sm text-foreground">
                    Checks Run ({validationResults.length})
                  </h3>
                  <span className="ml-auto text-xs text-muted-foreground">
                    {validationResults.filter((r: any) => r.passed).length} passed ·{" "}
                    {validationResults.filter((r: any) => !r.passed).length} failed
                  </span>
                </div>

                {Object.entries(groups).map(([validatorName, checks]) => (
                  <div key={validatorName} className="border-b border-border last:border-b-0">
                    <div className="px-4 py-2 bg-muted/30 flex items-center gap-2">
                      <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                        {validatorLabel(validatorName)}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        ({checks.filter((r) => r.passed).length}/{checks.length})
                      </span>
                    </div>
                    <div className="divide-y divide-border">
                      {checks.map((r: any, idx: number) => (
                        <div key={idx} className="px-4 py-3">
                          <div className="flex items-start gap-3">
                            <div className="flex-shrink-0 mt-0.5">
                              {r.passed ? (
                                <CheckCircle className="w-4 h-4 text-green-500" />
                              ) : (
                                <AlertCircle className="w-4 h-4 text-destructive" />
                              )}
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="text-sm font-semibold text-foreground">
                                  {r.field_name ?? r.field ?? "—"}
                                </span>
                                {r.source_document && (
                                  <span className="text-[10px] font-mono text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                                    {r.source_document}
                                  </span>
                                )}
                              </div>
                              {r.message && (
                                <p className="text-xs text-muted-foreground mt-1">{r.message}</p>
                              )}
                              {r.passed && r.source_value !== null && r.source_value !== undefined && (
                                <div className="mt-1.5 flex items-center gap-1.5 text-xs">
                                  <span className="text-muted-foreground">Value:</span>
                                  <code className="font-mono text-foreground bg-muted px-1.5 py-0.5 rounded">
                                    {String(r.source_value)}
                                  </code>
                                  {r.target_value !== null && r.target_value !== undefined && (
                                    <>
                                      <span className="text-muted-foreground">→</span>
                                      <code className="font-mono text-foreground bg-muted px-1.5 py-0.5 rounded">
                                        {String(r.target_value)}
                                      </code>
                                    </>
                                  )}
                                </div>
                              )}
                              {!r.passed && (r.source_value !== null || r.target_value !== null) && (
                                <div className="mt-2 grid grid-cols-2 gap-2">
                                  <div className="p-2 bg-card rounded border border-border text-xs">
                                    <p className="text-muted-foreground mb-0.5 text-[10px] uppercase font-semibold">
                                      {r.source_document ?? "Source"}
                                    </p>
                                    <code className="font-mono text-foreground break-all">
                                      {r.source_value !== null && r.source_value !== undefined ? String(r.source_value) : "—"}
                                    </code>
                                  </div>
                                  {r.target_value !== null && r.target_value !== undefined && (
                                    <div className="p-2 bg-card rounded border border-border text-xs">
                                      <p className="text-muted-foreground mb-0.5 text-[10px] uppercase font-semibold">
                                        {r.target_document ?? "Target"}
                                      </p>
                                      <code className="font-mono text-foreground break-all">
                                        {String(r.target_value)}
                                      </code>
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                            <span
                              className={`text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded flex-shrink-0 ${
                                r.passed
                                  ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                                  : "bg-destructive/10 text-destructive"
                              }`}
                            >
                              {r.passed ? "PASS" : "FAIL"}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </Card>
            )
          })()}

          {discrepancies && discrepancies.length > 0 && (
            <Card className="p-0 overflow-hidden">
              <div className="px-4 py-3 border-b border-border flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-500" />
                <h3 className="font-semibold text-sm text-foreground">Discrepancies ({discrepancies.length})</h3>
              </div>
              <div className="divide-y divide-border">
                {discrepancies.map((d: ValidationDiscrepancy) => (
                  <div key={d.id} className="px-4 py-3 space-y-1.5">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-semibold text-foreground">{d.field_name ?? d.field ?? "—"}</span>
                      <span
                        className={`text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded ${
                          d.severity === "critical"
                            ? "bg-destructive/10 text-destructive"
                            : d.severity === "major"
                            ? "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
                            : "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
                        }`}
                      >
                        {d.severity}
                      </span>
                      {d.status && <span className="text-[10px] text-muted-foreground uppercase">{d.status}</span>}
                    </div>
                    {d.message && <p className="text-xs text-muted-foreground">{d.message}</p>}
                    {(d.source_value !== undefined || d.target_value !== undefined) && (
                      <div className="flex gap-4 text-xs mt-1">
                        {d.source_value !== undefined && (
                          <div>
                            <span className="text-muted-foreground">{d.source_document ?? "Source"}: </span>
                            <code className="font-mono text-foreground">{String(d.source_value)}</code>
                          </div>
                        )}
                        {d.target_value !== undefined && (
                          <div>
                            <span className="text-muted-foreground">{d.target_document ?? "Target"}: </span>
                            <code className="font-mono text-foreground">{String(d.target_value)}</code>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          )}

          {summary?.messages && summary.messages.length > 0 && (
            <Card className="p-4">
              <h3 className="font-semibold text-sm text-foreground mb-2">Workflow Notes</h3>
              <ul className="space-y-1">
                {summary.messages.map((msg: string, i: number) => (
                  <li key={i} className="text-xs text-muted-foreground flex gap-2">
                    <span className="text-muted-foreground/50">•</span>
                    <span>{msg}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          <Card className="p-4 space-y-3">
            {shipmentId && (
              <div className="flex items-center justify-between gap-3 p-3 bg-muted/40 rounded-lg border border-border">
                <div className="min-w-0">
                  <p className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground mb-0.5">Shipment ID</p>
                  <code className="text-sm font-mono text-foreground break-all">{shipmentId}</code>
                </div>
                <button
                  onClick={() => navigator.clipboard.writeText(shipmentId)}
                  className="flex-shrink-0 p-2 rounded-md hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
                  title="Copy shipment ID"
                >
                  <Copy className="w-4 h-4" />
                </button>
              </div>
            )}

            {finalStatus !== "failed" ? (
              <a href={`/validation/boe${shipmentId ? `?shipment_id=${shipmentId}` : ""}`}>
                <Button className="w-full bg-primary hover:bg-primary/90">
                  Proceed to Step 6 — BOE Validation
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </a>
            ) : (
              <Button variant="outline" onClick={handleReset} className="w-full">
                Fix Documents &amp; Retry
              </Button>
            )}
          </Card>

          <Button variant="outline" onClick={handleReset} className="w-full">
            New Validation
          </Button>
        </div>
      )}
    </div>
  )
}

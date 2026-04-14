"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
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
  Pencil,
  Check,
  Save,
  Search,
  Package,
  FileText,
  ShieldCheck,
  Eye,
} from "lucide-react"
import {
  apiClient,
  type ValidationDiscrepancy,
  type BOEValidationResponse,
  type ExtractedDocumentMeta,
} from "@/lib/api-client"

// ─── Helpers ──────────────────────────────────────────────────────────────────

function unwrap(v: any): string {
  if (v === null || v === undefined) return ""
  if (typeof v === "object" && "value" in v) return String(v.value ?? "")
  if (typeof v === "object") return JSON.stringify(v)
  return String(v)
}

/**
 * Format a discrepancy source_value / target_value for display.
 * Handles:
 *  - null / undefined → "—"
 *  - {value: ...} envelopes → unwrapped scalar
 *  - plain dicts (n-way matcher: {doc: val, ...}) → "doc1: val1 · doc2: val2"
 *  - arrays → joined with ", "
 *  - primitives → String()
 */
function formatValue(v: any): string {
  if (v === null || v === undefined) return "—"
  // Unwrap confidence envelope
  if (typeof v === "object" && !Array.isArray(v) && "value" in v) {
    return String(v.value ?? "—")
  }
  if (Array.isArray(v)) {
    return v.map((item) => formatValue(item)).join(", ")
  }
  if (typeof v === "object") {
    // e.g. {bill_of_entry: "1901.90", invoice: "1901.9"} from n-way matcher
    // or   {invoice: "Nestlé SA", bill_of_lading: "Nestle S.A."} from shipper validator
    return Object.entries(v)
      .map(([doc, val]) => `${doc.replace(/_/g, " ")}: ${val}`)
      .join(" · ")
  }
  return String(v)
}

function deriveConfidence(v: any): number {
  if (v === null || v === undefined) return 0
  if (typeof v === "object") {
    if (typeof v.confidence === "number") return Math.min(1, v.confidence)
    if (v.source === "ai_enhancement") return 0.92
    if (v.source === "direct") return 0.95
    return 0.85
  }
  return 0.85
}

/** Normalise a header or key string for fuzzy matching (snake_case, lowercase). */
function normKey(s: string): string {
  return String(s).toLowerCase().replace(/[\s\-/\\]+/g, "_").replace(/[^\w]/g, "").replace(/_+/g, "_")
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

function SeverityBadge({ severity }: { severity: string }) {
  const map: Record<string, string> = {
    critical: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
    major: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
    minor: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-500",
    info: "bg-muted text-muted-foreground",
  }
  return (
    <span
      className={`text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded ${
        map[severity] ?? map.info
      }`}
    >
      {severity}
    </span>
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
  const displayValue = edited !== undefined ? edited : unwrap(raw)

  const startEdit = () => {
    if (readOnly || !onChange) return
    setDraft(displayValue)
    setEditing(true)
    setTimeout(() => inputRef.current?.focus(), 0)
  }

  const commit = () => {
    onChange?.(draft)
    setEditing(false)
  }

  const cancel = () => setEditing(false)

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

// ─── RenderedBlocks (Table blocks from extraction) ─────────────────────────────

function RenderedBlocks({
  blocks,
  blockEdits,
  onCellChange,
}: {
  blocks?: Array<{ type: string; content: any }>
  blockEdits?: Record<number, Record<string, string>>
  onCellChange?: (tableIdx: number, rowIdx: number, colIdx: number, val: string) => void
}) {
  if (!blocks || blocks.length === 0) return null

  const tables = blocks.filter((b) => b.type === "Table" && b.content)
  if (tables.length === 0) return null

  return (
    <div className="mt-3 pt-3 border-t border-border space-y-3">
      <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground mb-1">
        Extracted Tables — {tables.length}
        {onCellChange && (
          <span className="ml-2 normal-case font-normal text-muted-foreground/70">
            (hover a cell to edit)
          </span>
        )}
      </p>
      {tables.map((block, tableIdx) => {
        const tbl = block.content
        const headers: string[] = (tbl.headers ?? []).map((h: any) => unwrap(h))
        const rows: any[][] = tbl.rows ?? tbl.data ?? []
        const title = tbl.title || `Table ${tableIdx + 1}`

        if (headers.length === 0 && rows.length === 0) return null

        return (
          <div key={tableIdx} className="overflow-x-auto rounded border border-border">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="bg-muted/60">
                  <th
                    colSpan={headers.length || 1}
                    className="text-left px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground border-b border-border"
                  >
                    {title}
                  </th>
                </tr>
                {headers.length > 0 && (
                  <tr className="bg-muted/40">
                    {headers.map((h, j) => (
                      <th
                        key={j}
                        className="text-left px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground border-b border-border whitespace-nowrap"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                )}
              </thead>
              <tbody>
                {rows.map((row, ri) => {
                  // Normalise row to array of cell values.
                  // Claude may return rows as arrays OR as objects keyed by column name.
                  let cells: any[]
                  if (Array.isArray(row)) {
                    cells = row
                  } else if (typeof row === "object" && row !== null) {
                    const rowObj = row as Record<string, any>
                    const rowKeys = Object.keys(rowObj)
                    cells = headers.length > 0
                      ? headers.map((h) => {
                          const nh = normKey(h)
                          if (h in rowObj) return rowObj[h]
                          const match = rowKeys.find(k => normKey(k) === nh)
                          return match ? rowObj[match] : null
                        })
                      : rowKeys.map(k => rowObj[k])
                  } else {
                    cells = [row]
                  }
                  return (
                    <tr
                      key={ri}
                      className={`border-b border-border last:border-b-0 hover:bg-muted/20 transition-colors ${ri % 2 === 0 ? "bg-background" : "bg-muted/10"}`}
                    >
                      {cells.map((cell, ci) => {
                        const cellKey = `${ri},${ci}`
                        const edited = blockEdits?.[tableIdx]?.[cellKey]
                        const isEdited = edited !== undefined && edited !== unwrap(cell)
                        return (
                          <EditableItemCell
                            key={ci}
                            raw={cell}
                            edited={edited}
                            isEdited={isEdited}
                            confidence={deriveConfidence(cell)}
                            readOnly={!onCellChange}
                            onChange={onCellChange ? (v) => onCellChange(tableIdx, ri, ci, v) : undefined}
                          />
                        )
                      })}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )
      })}
    </div>
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

  const cancelEdit = () => setEditing(false)

  const label = fieldKey.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())

  return (
    <div
      className={`flex items-center gap-3 py-2.5 border-b border-border last:border-b-0 group ${
        isEdited ? "bg-amber-50/40 dark:bg-amber-900/10" : ""
      }`}
    >
      <div className="w-52 flex-shrink-0">
        <span className="text-xs font-medium text-muted-foreground font-mono">{label}</span>
        {isEdited && (
          <span className="ml-1.5 text-[9px] font-bold uppercase text-amber-600 dark:text-amber-400">
            edited
          </span>
        )}
      </div>

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
              title="Save"
            >
              <Check className="w-4 h-4" />
            </button>
            <button
              onClick={cancelEdit}
              className="text-muted-foreground hover:text-destructive flex-shrink-0"
              title="Cancel"
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
              title="Edit"
            >
              <Pencil className="w-3 h-3" />
            </button>
          </div>
        )}
      </div>

      <div className="flex-shrink-0">
        <ConfidenceBadge score={confidence} />
      </div>
    </div>
  )
}

// ─── ExtractedFieldsReference ────────────────────────────────────────────────
// Read-only collapsible panel shown on the Results page so reviewers can
// cross-reference extracted BOE values while reviewing discrepancies.

const FIELD_GROUPS: Array<{ label: string; keys: string[] }> = [
  {
    label: "Identity",
    keys: ["boe_number", "invoice_number", "bl_number", "order_number", "po_number", "contract_number"],
  },
  {
    label: "Parties",
    keys: ["consignee_name", "consignee_address", "shipper_name", "shipper_address", "declarant_name", "declarant_reg_number"],
  },
  {
    label: "Goods",
    keys: ["hs_code", "product_description", "country_of_origin", "quantity", "net_weight", "gross_weight"],
  },
  {
    label: "Financials",
    keys: ["customs_value", "total_fob_value", "total_invoice_value", "freight_value", "insurance_value", "duty_rate", "duty_amount", "vat_rate", "vat_amount", "nhil_amount"],
  },
  {
    label: "Transport",
    keys: ["incoterm", "currency", "vessel_name", "port_of_loading", "port_of_discharge", "container_numbers", "mode_of_shipment"],
  },
  {
    label: "Customs",
    keys: ["customs_code", "customs_procedure", "cpc_code", "etls_approval"],
  },
]

function ExtractedFieldsReference({ docMeta }: { docMeta: ExtractedDocumentMeta }) {
  const [open, setOpen] = useState(false)

  const fields = docMeta.fields ?? {}
  const allKeys = Object.keys(fields).filter((k) => k !== "items" && !k.startsWith("_"))

  // Build grouped display — assign each key to the first matching group, rest go to "Other"
  const assigned = new Set<string>()
  const groups = FIELD_GROUPS.map((g) => {
    const present = g.keys.filter((k) => k in fields)
    present.forEach((k) => assigned.add(k))
    return { label: g.label, keys: present }
  }).filter((g) => g.keys.length > 0)

  const other = allKeys.filter((k) => !assigned.has(k))
  if (other.length > 0) groups.push({ label: "Other", keys: other })

  return (
    <Card className="overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-muted/30 transition-colors text-left"
        onClick={() => setOpen(!open)}
      >
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-muted-foreground" />
          <span className="font-semibold text-sm text-foreground">Extracted BOE Fields</span>
          <span className="text-[10px] font-mono text-muted-foreground">{allKeys.length} fields</span>
          <span className="text-[10px] text-muted-foreground italic">— reference while reviewing</span>
        </div>
        {open ? (
          <ChevronUp className="w-4 h-4 text-muted-foreground" />
        ) : (
          <ChevronDown className="w-4 h-4 text-muted-foreground" />
        )}
      </button>

      {open && (
        <div className="border-t border-border divide-y divide-border">
          {groups.map((group) => (
            <div key={group.label} className="px-4 py-3">
              <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground mb-2">
                {group.label}
              </p>
              <div className="grid grid-cols-2 gap-x-6 gap-y-1.5">
                {group.keys.map((key) => {
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
                        <p
                          className="text-xs font-mono text-foreground truncate"
                          title={val || "—"}
                        >
                          {val || <span className="text-muted-foreground italic">—</span>}
                        </p>
                      </div>
                      <ConfidenceBadge score={conf} />
                    </div>
                  )
                })}
              </div>
            </div>
          ))}

          {docMeta.items && docMeta.items.length > 0 && (
            <div className="px-4 py-3">
              <EditableLineItemsTable items={docMeta.items} readOnly />
            </div>
          )}

          {docMeta.blocks && docMeta.blocks.length > 0 && (
            <div className="px-4 py-3">
              <RenderedBlocks blocks={docMeta.blocks} />
            </div>
          )}
        </div>
      )}
    </Card>
  )
}

// ─── BOEFieldPanel ────────────────────────────────────────────────────────────

function BOEFieldPanel({
  docMeta,
  edits,
  itemEdits,
  blockEdits,
  onFieldChange,
  onItemChange,
  onBlockCellChange,
}: {
  docMeta: ExtractedDocumentMeta
  edits: Record<string, string>
  itemEdits: Record<number, Record<string, string>>
  blockEdits: Record<number, Record<string, string>>
  onFieldChange: (key: string, val: string) => void
  onItemChange: (rowIndex: number, column: string, val: string) => void
  onBlockCellChange: (tableIdx: number, rowIdx: number, colIdx: number, val: string) => void
}) {
  const [collapsed, setCollapsed] = useState(false)

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
          <FileText className="w-4 h-4 text-muted-foreground" />
          <span className="font-semibold text-sm text-foreground">Bill of Entry</span>
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
                onChange={onFieldChange}
              />
            ))
          )}

          {docMeta.items && docMeta.items.length > 0 && (
            <EditableLineItemsTable
              items={docMeta.items}
              edits={itemEdits}
              onCellChange={onItemChange}
            />
          )}

          {docMeta.blocks && docMeta.blocks.length > 0 && (
            <RenderedBlocks
              blocks={docMeta.blocks}
              blockEdits={blockEdits}
              onCellChange={onBlockCellChange}
            />
          )}
        </div>
      )}
    </Card>
  )
}

// ─── ValidationResultsPanel ───────────────────────────────────────────────────

function ValidationResultsPanel({ results }: { results: any[] }) {
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

// ─── ShipmentSelector ─────────────────────────────────────────────────────────

interface Shipment {
  shipment_id: string
  shipment_number: string
  supplier_name?: string
  consignee_name?: string
  status: string
  vendor_docs_count: number
  created_at?: string
}

function ShipmentSelector({
  selected,
  onSelect,
}: {
  selected: Shipment | null
  onSelect: (s: Shipment) => void
}) {
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
                <p className="text-sm font-semibold text-foreground truncate">
                  {s.shipment_number}
                </p>
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

// ─── Main Component ───────────────────────────────────────────────────────────

type Step = "select" | "processing" | "field_review" | "results" | "complete"

export default function BOEValidationForm() {
  const [step, setStep] = useState<Step>("select")

  // Shipment + file
  const [selectedShipment, setSelectedShipment] = useState<Shipment | null>(null)
  const [boeFile, setBoeFile] = useState<File | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Stashed full API result (used after field review)
  const [pendingResult, setPendingResult] = useState<BOEValidationResponse | null>(null)

  // Extracted BOE fields + edits
  const [extractedBOE, setExtractedBOE] = useState<ExtractedDocumentMeta | null>(null)
  const [fieldEdits, setFieldEdits] = useState<Record<string, string>>({})
  // Per-row, per-column line item edits: { rowIndex: { column: newValue } }
  const [lineItemEdits, setLineItemEdits] = useState<Record<number, Record<string, string>>>({})
  // Per-table, per-cell block edits: { tableIdx: { "rowIdx,colIdx": newValue } }
  const [blockEdits, setBlockEdits] = useState<Record<number, Record<string, string>>>({})
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  // Validation state
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [discrepancies, setDiscrepancies] = useState<ValidationDiscrepancy[]>([])
  const [confirmations, setConfirmations] = useState<Record<string, boolean | null>>({})
  const [validationResults, setValidationResults] = useState<any[]>([])
  const [finalStatus, setFinalStatus] = useState<string | null>(null)
  const [summary, setSummary] = useState<Record<string, any> | null>(null)

  // UI
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const elapsedRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Document viewer tabs — one per step that has content to review
  const [fieldReviewView, setFieldReviewView] = useState<"fields" | "document">("fields")
  const [resultsView, setResultsView] = useState<"results" | "document">("results")

  // Blob URL for the uploaded BOE file — created on demand, revoked on unmount
  const boeBlobUrlRef = useRef<string | null>(null)
  const getBOEBlobUrl = useCallback((): string | null => {
    if (!boeFile) return null
    if (!boeBlobUrlRef.current) {
      boeBlobUrlRef.current = URL.createObjectURL(boeFile)
    }
    return boeBlobUrlRef.current
  }, [boeFile])
  useEffect(() => {
    return () => {
      if (boeBlobUrlRef.current) {
        URL.revokeObjectURL(boeBlobUrlRef.current)
        boeBlobUrlRef.current = null
      }
    }
  }, [])

  useEffect(() => {
    if (submitting) {
      setElapsed(0)
      elapsedRef.current = setInterval(() => setElapsed((s) => s + 1), 1000)
    } else {
      if (elapsedRef.current) clearInterval(elapsedRef.current)
    }
    return () => {
      if (elapsedRef.current) clearInterval(elapsedRef.current)
    }
  }, [submitting])

  const handleFieldChange = useCallback((key: string, val: string) => {
    setFieldEdits((prev) => ({ ...prev, [key]: val }))
  }, [])

  const handleLineItemChange = useCallback((rowIndex: number, column: string, val: string) => {
    setLineItemEdits((prev) => ({
      ...prev,
      [rowIndex]: { ...(prev[rowIndex] ?? {}), [column]: val },
    }))
  }, [])

  const handleBlockCellChange = useCallback((tableIdx: number, rowIdx: number, colIdx: number, val: string) => {
    setBlockEdits((prev) => ({
      ...prev,
      [tableIdx]: { ...(prev[tableIdx] ?? {}), [`${rowIdx},${colIdx}`]: val },
    }))
  }, [])

  // ── Apply API result to state ─────────────────────────────────────────────

  const applyResult = useCallback((res: BOEValidationResponse) => {
    setValidationResults(res.validation_results ?? [])
    setSummary(res.summary ?? null)
    setFinalStatus(res.final_status ?? null)
    setDiscrepancies(res.discrepancies ?? [])
    setSessionId(res.session_id ?? null)

    const hitlDiscs = [...(res.discrepancies ?? []), ...(res.critical_discrepancies ?? [])].filter(
      (d) => d.severity === "critical" || d.severity === "major"
    )

    if (hitlDiscs.length > 0) {
      const initial: Record<string, boolean | null> = {}
      hitlDiscs.forEach((d) => {
        initial[d.id] = null
      })
      setConfirmations(initial)
    }

    setStep("results")
  }, [])

  // ── Submit ────────────────────────────────────────────────────────────────

  const handleValidate = async () => {
    if (!selectedShipment || !boeFile) return
    setError(null)
    setSubmitting(true)
    setStep("processing")

    try {
      const res = await apiClient.validateBOE(selectedShipment.shipment_id, boeFile)

      if (res.extracted_boe && Object.keys(res.extracted_boe.fields ?? {}).length > 0) {
        setExtractedBOE(res.extracted_boe)
        setFieldEdits({})
        setLineItemEdits({})
        setBlockEdits({})
        setPendingResult(res)
        setStep("field_review")
      } else {
        applyResult(res)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "BOE validation failed. Please try again.")
      setStep("select")
    } finally {
      setSubmitting(false)
    }
  }

  // ── Save field edits ──────────────────────────────────────────────────────

  const handleSaveFields = async () => {
    if (!extractedBOE) return
    setSaving(true)
    setSaveError(null)

    try {
      const hasFieldEdits = Object.keys(fieldEdits).length > 0
      const hasItemEdits = Object.keys(lineItemEdits).length > 0
      const hasBlockEdits = Object.keys(blockEdits).length > 0

      if ((hasFieldEdits || hasItemEdits || hasBlockEdits) && extractedBOE.document_id) {
        // Flatten line item edits to [{row_index, column, value}]
        const itemUpdates = Object.entries(lineItemEdits).flatMap(([rowIdx, cols]) =>
          Object.entries(cols).map(([column, value]) => ({
            row_index: Number(rowIdx),
            column,
            value,
          }))
        )

        // Apply block edits back into the blocks structure
        const updatedBlocks = hasBlockEdits && extractedBOE.blocks
          ? extractedBOE.blocks.map((block, ti) => {
              const tableEdits = blockEdits[ti]
              if (!tableEdits || block.type !== "Table") return block
              const tbl = { ...block.content }
              const rows = (tbl.rows ?? tbl.data ?? []).map((row: any[], ri: number) => {
                const arr = Array.isArray(row) ? [...row] : [row]
                Object.entries(tableEdits).forEach(([key, val]) => {
                  const [r, c] = key.split(",").map(Number)
                  if (r === ri && c < arr.length) arr[c] = val
                })
                return arr
              })
              return { ...block, content: { ...tbl, rows } }
            })
          : extractedBOE.blocks

        await apiClient.updateDocumentFields(
          extractedBOE.document_id,
          fieldEdits,
          {
            updated_by: "field_review",
            update_reason: "User reviewed and corrected extracted BOE fields",
            blocks: updatedBlocks,
          },
          itemUpdates.length > 0 ? itemUpdates : undefined
        )
      }
      if (pendingResult) applyResult(pendingResult)
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Failed to save edits. Please try again.")
    } finally {
      setSaving(false)
    }
  }

  // ── HITL Resume ───────────────────────────────────────────────────────────

  const handleResume = async () => {
    if (!sessionId) {
      // No session to resume — just mark complete
      setStep("complete")
      return
    }
    setError(null)
    setSubmitting(true)

    try {
      const payload = Object.entries(confirmations)
        .filter(([, v]) => v !== null)
        .map(([id, confirmed]) => ({ discrepancy_id: id, confirmed: confirmed as boolean }))

      const res = await apiClient.resumeValidationSession(sessionId, payload)
      setFinalStatus((res as any).final_status ?? finalStatus)
      setSummary((res as any).summary ?? summary)
      setValidationResults((res as any).validation_results ?? validationResults)
      setStep("complete")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Resume failed. Please try again.")
    } finally {
      setSubmitting(false)
    }
  }

  // ── Reset ─────────────────────────────────────────────────────────────────

  const handleReset = () => {
    setStep("select")
    setSelectedShipment(null)
    setBoeFile(null)
    setPendingResult(null)
    setExtractedBOE(null)
    setFieldEdits({})
    setLineItemEdits({})
    setBlockEdits({})
    setSessionId(null)
    setDiscrepancies([])
    setConfirmations({})
    setValidationResults([])
    setFinalStatus(null)
    setSummary(null)
    setError(null)
    setSaveError(null)
    setFieldReviewView("fields")
    setResultsView("results")
    if (boeBlobUrlRef.current) {
      URL.revokeObjectURL(boeBlobUrlRef.current)
      boeBlobUrlRef.current = null
    }
  }

  // ─── Step indicator ────────────────────────────────────────────────────────

  const INDICATOR_STEPS: Array<{ key: Step; label: string }> = [
    { key: "select", label: "Select" },
    { key: "field_review", label: "Review Fields" },
    { key: "results", label: "Results" },
    { key: "complete", label: "Complete" },
  ]
  const stepOrder: Step[] = ["select", "field_review", "results", "complete"]
  const currentIdx = stepOrder.indexOf(step === "processing" ? "field_review" : step)

  // ─────────────────────────────────────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────────────────────────────────────

  return (
    <div className="p-8 max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-foreground mb-2">BOE Validation</h1>
        <p className="text-muted-foreground">
          Step 6 — Cross-verify the Bill of Entry against stored vendor documents.
        </p>
      </div>

      {/* Step indicator */}
      {step !== "select" && (
        <div className="flex items-center gap-2 mb-6">
          {INDICATOR_STEPS.map(({ key, label }, i) => {
            const thisIdx = stepOrder.indexOf(key)
            const done = thisIdx < currentIdx
            const active = thisIdx === currentIdx
            return (
              <div key={key} className="flex items-center gap-2">
                <div
                  className={`flex items-center gap-1.5 text-xs font-medium ${
                    active
                      ? "text-primary"
                      : done
                      ? "text-green-600 dark:text-green-400"
                      : "text-muted-foreground"
                  }`}
                >
                  <div
                    className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold border-2 ${
                      active
                        ? "border-primary bg-primary text-primary-foreground"
                        : done
                        ? "border-green-500 bg-green-500 text-white"
                        : "border-muted-foreground/30"
                    }`}
                  >
                    {done ? <Check className="w-3 h-3" /> : i + 1}
                  </div>
                  {label}
                </div>
                {i < INDICATOR_STEPS.length - 1 && (
                  <div className={`w-8 h-px ${done ? "bg-green-400" : "bg-border"}`} />
                )}
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

      {/* ── Select ───────────────────────────────────────────────────────────── */}
      {step === "select" && (
        <div className="space-y-4">
          <Card className="p-5">
            <h2 className="text-sm font-semibold text-foreground mb-1">Select Shipment</h2>
            <p className="text-xs text-muted-foreground mb-4">
              Choose a shipment that completed Step 2 (vendor document validation).
            </p>
            <ShipmentSelector selected={selectedShipment} onSelect={setSelectedShipment} />
          </Card>

          <Card className="p-5">
            <h2 className="text-sm font-semibold text-foreground mb-1">Bill of Entry</h2>
            <p className="text-xs text-muted-foreground mb-4">
              Upload the BOE (customs declaration) PDF to validate against the vendor documents.
            </p>

            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.doc,.docx,.jpg,.jpeg,.png"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) setBoeFile(f)
                e.target.value = ""
              }}
            />

            {boeFile ? (
              <div className="flex items-center gap-3 p-3 bg-primary/5 border border-primary/20 rounded-lg">
                <FileUp className="w-4 h-4 text-primary flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-foreground truncate">{boeFile.name}</p>
                  <p className="text-xs text-muted-foreground">{(boeFile.size / 1024).toFixed(1)} KB</p>
                </div>
                <button
                  onClick={() => setBoeFile(null)}
                  className="text-muted-foreground hover:text-destructive transition-colors flex-shrink-0"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <Button
                variant="outline"
                size="sm"
                onClick={() => fileInputRef.current?.click()}
                className="text-xs"
              >
                <FileUp className="w-3 h-3 mr-1.5" />
                Select BOE File
              </Button>
            )}
          </Card>

          <div className="flex justify-end">
            <Button
              onClick={handleValidate}
              disabled={!selectedShipment || !boeFile || submitting}
              className="bg-primary hover:bg-primary/90"
            >
              Run BOE Validation
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
          <h2 className="text-2xl font-bold text-foreground mb-2">Processing BOE</h2>
          <p className="text-muted-foreground">
            Extracting fields and running cross-validation against vendor documents.
            This typically takes 2–4 minutes.
          </p>
          <p className="text-sm text-muted-foreground mt-3 font-mono">
            {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, "0")} elapsed — keep this tab open
          </p>
        </Card>
      )}

      {/* ── Field Review ─────────────────────────────────────────────────────── */}
      {step === "field_review" && extractedBOE && (
        <div className="space-y-4">

          {/* Tab bar */}
          <div className="flex justify-center py-1">
            <div className="flex items-center bg-muted/70 rounded-xl p-1 gap-0.5 border border-border/50 shadow-sm">
              {[
                { v: "fields" as const, label: "Review Fields", icon: ClipboardCheck },
                { v: "document" as const, label: "View BOE Document", icon: Eye },
              ].map(({ v, label, icon: Icon }) => (
                <button
                  key={v}
                  onClick={() => setFieldReviewView(v)}
                  className={`flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-medium transition-all duration-150 ${
                    fieldReviewView === v
                      ? "bg-background text-foreground shadow-sm border border-border/60"
                      : "text-muted-foreground hover:text-foreground hover:bg-background/50"
                  }`}
                >
                  <Icon className={`w-3.5 h-3.5 ${fieldReviewView === v ? "text-primary" : ""}`} />
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Document viewer panel */}
          {fieldReviewView === "document" && (() => {
            const blobUrl = getBOEBlobUrl()
            const isPdf = boeFile?.type === "application/pdf" || boeFile?.name?.toLowerCase().endsWith(".pdf")
            return (
              <div className="rounded-lg border border-border overflow-hidden bg-muted/20 h-[780px]">
                {blobUrl && boeFile ? (
                  isPdf ? (
                    <iframe
                      src={blobUrl}
                      title={boeFile.name}
                      className="w-full h-full border-0"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center overflow-auto p-4">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={blobUrl}
                        alt={boeFile.name}
                        className="max-w-full max-h-full object-contain rounded"
                      />
                    </div>
                  )
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <p className="text-sm text-muted-foreground">No BOE document available to preview.</p>
                  </div>
                )}
              </div>
            )
          })()}

          {/* Fields review panel */}
          {fieldReviewView === "fields" && <>

          <Card className="p-5 border-l-4 border-primary bg-primary/5">
            <div className="flex items-start gap-3">
              <ClipboardCheck className="w-5 h-5 text-primary mt-0.5 flex-shrink-0" />
              <div>
                <p className="font-semibold text-foreground">Review Extracted BOE Fields</p>
                <p className="text-sm text-muted-foreground mt-0.5">
                  Verify every extracted value before proceeding. Each field shows its AI
                  confidence score. Hover a row to edit — press Enter to confirm or Escape to
                  cancel. Switch to <strong>View BOE Document</strong> to cross-reference the original.
                </p>
              </div>
            </div>
          </Card>

          {/* Confidence legend */}
          <div className="flex items-center gap-4 px-1">
            <span className="text-xs text-muted-foreground font-medium">Confidence:</span>
            {[
              {
                label: "90%+",
                classes: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
                desc: "High",
              },
              {
                label: "70–89%",
                classes: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
                desc: "Medium",
              },
              {
                label: "<70%",
                classes: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
                desc: "Low — verify manually",
              },
            ].map(({ label, classes, desc }) => (
              <div key={label} className="flex items-center gap-1.5">
                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${classes}`}>
                  {label}
                </span>
                <span className="text-xs text-muted-foreground">{desc}</span>
              </div>
            ))}
          </div>

          <BOEFieldPanel
            docMeta={extractedBOE}
            edits={fieldEdits}
            itemEdits={lineItemEdits}
            blockEdits={blockEdits}
            onFieldChange={handleFieldChange}
            onItemChange={handleLineItemChange}
            onBlockCellChange={handleBlockCellChange}
          />

          {saveError && (
            <Card className="p-4 border-l-4 border-destructive bg-destructive/5">
              <div className="flex items-start gap-3">
                <AlertCircle className="w-4 h-4 text-destructive mt-0.5 flex-shrink-0" />
                <p className="text-sm text-destructive">{saveError}</p>
              </div>
            </Card>
          )}

          </>}

          <div className="flex justify-between items-center pt-2">
            <Button variant="outline" onClick={() => setStep("select")}>
              Re-upload BOE
            </Button>
            <div className="flex items-center gap-3">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  if (pendingResult) applyResult(pendingResult)
                }}
                className="text-xs text-muted-foreground"
              >
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

      {/* ── Results ──────────────────────────────────────────────────────────── */}
      {step === "results" && (
        <div className="space-y-4">

          {/* Tab bar */}
          <div className="flex justify-center py-1">
            <div className="flex items-center bg-muted/70 rounded-xl p-1 gap-0.5 border border-border/50 shadow-sm">
              {[
                { v: "results" as const, label: "Validation Results", icon: ShieldCheck },
                { v: "document" as const, label: "View BOE Document", icon: Eye },
              ].map(({ v, label, icon: Icon }) => (
                <button
                  key={v}
                  onClick={() => setResultsView(v)}
                  className={`flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-medium transition-all duration-150 ${
                    resultsView === v
                      ? "bg-background text-foreground shadow-sm border border-border/60"
                      : "text-muted-foreground hover:text-foreground hover:bg-background/50"
                  }`}
                >
                  <Icon className={`w-3.5 h-3.5 ${resultsView === v ? "text-primary" : ""}`} />
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Document viewer panel */}
          {resultsView === "document" && (() => {
            const blobUrl = getBOEBlobUrl()
            const isPdf = boeFile?.type === "application/pdf" || boeFile?.name?.toLowerCase().endsWith(".pdf")
            return (
              <div className="rounded-lg border border-border overflow-hidden bg-muted/20 h-[780px]">
                {blobUrl && boeFile ? (
                  isPdf ? (
                    <iframe
                      src={blobUrl}
                      title={boeFile.name}
                      className="w-full h-full border-0"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center overflow-auto p-4">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={blobUrl}
                        alt={boeFile.name}
                        className="max-w-full max-h-full object-contain rounded"
                      />
                    </div>
                  )
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <p className="text-sm text-muted-foreground">No BOE document available to preview.</p>
                  </div>
                )}
              </div>
            )
          })()}

          {/* Validation results content */}
          {resultsView === "results" && <>

          {/* Summary stats */}
          {summary && (
            <div className="grid grid-cols-4 gap-3">
              {[
                { label: "Total Checks", value: summary.total_checks ?? 0, color: "text-foreground" },
                { label: "Passed", value: summary.passed_checks ?? 0, color: "text-green-600" },
                { label: "Failed", value: summary.failed_checks ?? 0, color: (summary.failed_checks ?? 0) > 0 ? "text-destructive" : "text-muted-foreground" },
                { label: "Critical", value: summary.critical ?? 0, color: (summary.critical ?? 0) > 0 ? "text-destructive" : "text-muted-foreground" },
              ].map(({ label, value, color }) => (
                <Card key={label} className="p-3 text-center">
                  <p className="text-xs text-muted-foreground mb-1">{label}</p>
                  <p className={`text-xl font-bold ${color}`}>{value}</p>
                </Card>
              ))}
            </div>
          )}

          {/* Shipment + document context strip */}
          {(selectedShipment || summary?.documents_processed) && (
            <Card className="px-4 py-3">
              <div className="flex items-center gap-6 flex-wrap text-xs">
                {selectedShipment && (
                  <div className="flex items-center gap-2">
                    <Package className="w-3.5 h-3.5 text-muted-foreground" />
                    <span className="text-muted-foreground">Shipment:</span>
                    <span className="font-mono font-semibold text-foreground">{selectedShipment.shipment_number}</span>
                    {selectedShipment.supplier_name && (
                      <span className="text-muted-foreground">· {selectedShipment.supplier_name}</span>
                    )}
                  </div>
                )}
                {summary?.documents_processed && (
                  <div className="flex items-center gap-2 flex-wrap">
                    <FileText className="w-3.5 h-3.5 text-muted-foreground" />
                    <span className="text-muted-foreground">Documents validated:</span>
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

          {/* Extracted BOE fields — collapsed by default for reference */}
          {extractedBOE && Object.keys(extractedBOE.fields ?? {}).length > 0 && (
            <ExtractedFieldsReference docMeta={extractedBOE} />
          )}

          {/* Discrepancy HITL */}
          {discrepancies.filter((d) => d.severity === "critical" || d.severity === "major").length > 0 && (
            <Card className="p-5 border-l-4 border-amber-400 bg-amber-50/30 dark:bg-amber-900/10">
              <div className="flex items-start gap-3 mb-4">
                <AlertTriangle className="w-5 h-5 text-amber-500 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="font-semibold text-foreground">Discrepancies Require Review</p>
                  <p className="text-sm text-muted-foreground mt-0.5">
                    Accept or reject each discrepancy before finalising the validation.
                  </p>
                </div>
              </div>
              <div className="space-y-3">
                {discrepancies
                  .filter((d) => d.severity === "critical" || d.severity === "major")
                  .map((disc) => (
                    <DiscrepancyCard
                      key={disc.id}
                      disc={disc}
                      confirmed={confirmations[disc.id] ?? null}
                      onToggle={(id, val) => setConfirmations((prev) => ({ ...prev, [id]: val }))}
                    />
                  ))}
              </div>
            </Card>
          )}

          {/* All validation checks */}
          {validationResults.length > 0 && (
            <ValidationResultsPanel results={validationResults} />
          )}

          </>}

          <div className="flex justify-between pt-2">
            <Button variant="outline" onClick={handleReset}>
              Validate Another BOE
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
              {submitting && <Loader className="w-4 h-4 mr-2 animate-spin" />}
              {discrepancies.filter((d) => d.severity === "critical" || d.severity === "major").length > 0
                ? "Submit Decisions"
                : "Confirm & Complete"}
            </Button>
          </div>
        </div>
      )}

      {/* ── Complete ─────────────────────────────────────────────────────────── */}
      {step === "complete" && (
        <div className="space-y-4">
          <Card
            className={`p-6 border-l-4 ${
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
                  <CheckCircle className="w-6 h-6 text-green-600" />
                ) : finalStatus === "failed" ? (
                  <AlertCircle className="w-6 h-6 text-destructive" />
                ) : (
                  <AlertTriangle className="w-6 h-6 text-amber-500" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <h2 className="text-xl font-bold text-foreground">
                  {finalStatus === "passed"
                    ? "BOE Validation Passed"
                    : finalStatus === "failed"
                    ? "BOE Validation Failed"
                    : "BOE Requires Attention"}
                </h2>
                {selectedShipment && (
                  <p className="text-sm text-muted-foreground mt-0.5">
                    Shipment:{" "}
                    <span className="font-mono font-medium">
                      {selectedShipment.shipment_number}
                    </span>
                  </p>
                )}
                {summary && (
                  <div className="flex items-center gap-4 mt-3 text-sm flex-wrap">
                    <span className="text-muted-foreground">
                      <span className="font-semibold text-green-600">
                        {summary.passed_checks}
                      </span>
                      /{summary.total_checks} checks passed
                    </span>
                    {(summary.major ?? 0) > 0 && (
                      <span className="text-amber-600 font-semibold">
                        {summary.major} major
                      </span>
                    )}
                    {(summary.critical ?? 0) > 0 && (
                      <span className="text-destructive font-semibold">
                        {summary.critical} critical
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          </Card>

          {/* Validation checks on complete screen */}
          {validationResults.length > 0 && (
            <ValidationResultsPanel results={validationResults} />
          )}

          <div className="flex justify-between pt-2">
            <Button variant="outline" onClick={handleReset}>
              Validate Another BOE
            </Button>
            {finalStatus === "passed" && (
              <Button className="bg-green-600 hover:bg-green-700 text-white">
                <CheckCircle className="w-4 h-4 mr-2" />
                Proceed to Clearance
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

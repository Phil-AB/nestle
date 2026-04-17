"use client"

import { useState } from "react"
import { Card } from "@/components/ui/card"
import { ChevronDown, ChevronUp } from "lucide-react"
import { EditableFieldRow } from "./EditableFieldRow"
import { EditableLineItemsTable } from "./EditableLineItemsTable"
import { ExtractedTablesSection } from "./ExtractedTablesSection"
import { DOC_LABEL } from "../lib/constants"
import type { ExtractedDocumentMeta } from "../lib/types"

interface DocumentFieldPanelProps {
  docType: string
  docMeta: ExtractedDocumentMeta
  edits: Record<string, string>
  itemEdits: Record<number, Record<string, string>>
  tableEdits: Record<number, Record<number, Record<number, string>>>
  onFieldChange: (docType: string, key: string, val: string) => void
  onItemChange: (docType: string, rowIndex: number, column: string, val: string) => void
  onTableCellChange: (docType: string, tblIdx: number, rowIdx: number, colIdx: number, val: string) => void
}

/** Shows all extracted fields for one document with confidence + editing */
export function DocumentFieldPanel({
  docType,
  docMeta,
  edits,
  itemEdits,
  tableEdits,
  onFieldChange,
  onItemChange,
  onTableCellChange,
}: DocumentFieldPanelProps) {
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

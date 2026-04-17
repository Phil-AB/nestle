"use client"

import { useState } from "react"
import { Card } from "@/components/ui/card"
import { ChevronDown, ChevronUp, FileText } from "lucide-react"
import { EditableFieldRow } from "./EditableFieldRow"
import { EditableLineItemsTable } from "./EditableLineItemsTable"
import { RenderedBlocks } from "./RenderedBlocks"
import type { ExtractedDocumentMeta } from "../lib/types"

interface BOEFieldPanelProps {
  docMeta: ExtractedDocumentMeta
  edits: Record<string, string>
  itemEdits: Record<number, Record<string, string>>
  blockEdits: Record<number, Record<string, string>>
  onFieldChange: (key: string, val: string) => void
  onItemChange: (rowIndex: number, column: string, val: string) => void
  onBlockCellChange: (tableIdx: number, rowIdx: number, colIdx: number, val: string) => void
}

export function BOEFieldPanel({
  docMeta,
  edits,
  itemEdits,
  blockEdits,
  onFieldChange,
  onItemChange,
  onBlockCellChange,
}: BOEFieldPanelProps) {
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

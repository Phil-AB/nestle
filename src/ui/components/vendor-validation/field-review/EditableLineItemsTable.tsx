"use client"

import { EditableItemCell } from "./EditableItemCell"
import { SKIP_ITEM_COLS } from "../lib/constants"
import { deriveConfidence, unwrap } from "../lib/utils"

interface EditableLineItemsTableProps {
  items: Array<Record<string, any>>
  edits?: Record<number, Record<string, string>>
  onCellChange?: (rowIndex: number, column: string, value: string) => void
  readOnly?: boolean
}

/** Renders line items as a proper table with per-cell confidence and optional editing */
export function EditableLineItemsTable({
  items,
  edits,
  onCellChange,
  readOnly,
}: EditableLineItemsTableProps) {
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

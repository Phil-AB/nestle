"use client"

import { EditableItemCell } from "./EditableItemCell"
import type { ExtractedTable } from "../lib/types"
import { unwrap, normKey, deriveConfidence } from "../lib/utils"

interface ExtractedTablesSectionProps {
  tables: ExtractedTable[]
  editable?: boolean
  tableEdits?: Record<number, Record<number, Record<number, string>>>
  onCellChange?: (tblIdx: number, rowIdx: number, colIdx: number, val: string) => void
}

export function ExtractedTablesSection({
  tables,
  editable = false,
  tableEdits,
  onCellChange,
}: ExtractedTablesSectionProps) {
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
        const headers: string[] = (tbl.headers ?? tbl.columns ?? []).map((h: any) => unwrap(h))
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
                          {h.replace(/_/g, " ")}
                        </th>
                      ))}
                    </tr>
                  </thead>
                )}
                <tbody>
                  {rows.map((row, ri) => {
                    // Normalise row to cell array — rows may be arrays or objects keyed by column name.
                    let cells: any[]
                    if (Array.isArray(row)) {
                      cells = row
                    } else if (typeof row === "object" && row !== null) {
                      const rowObj = row as Record<string, any>
                      const rowKeys = Object.keys(rowObj)
                      cells = headers.length > 0
                        ? headers.map((h) => {
                            if (h in rowObj) return rowObj[h]
                            const nh = normKey(h)
                            const match = rowKeys.find(k => normKey(k) === nh)
                            return match ? rowObj[match] : null
                          })
                        : rowKeys.map(k => rowObj[k])
                    } else {
                      cells = [row]
                    }
                    return (
                      <tr key={ri} className="border-b border-border last:border-b-0 hover:bg-muted/20">
                        {cells.map((cell, ci) => {
                          if (editable) {
                            const editedVal = tableEdits?.[tblIdx]?.[ri]?.[ci]
                            const rawStr = unwrap(cell)
                            const isEdited = editedVal !== undefined && editedVal !== rawStr
                            return (
                              <EditableItemCell
                                key={ci}
                                raw={cell}
                                edited={editedVal}
                                isEdited={isEdited}
                                confidence={deriveConfidence(cell)}
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
                                unwrap(cell)
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

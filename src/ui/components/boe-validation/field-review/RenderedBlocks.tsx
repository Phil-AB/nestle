"use client"

import { EditableItemCell } from "./EditableItemCell"
import { unwrap, normKey, deriveConfidence } from "../lib/utils"

interface RenderedBlocksProps {
  blocks?: Array<{ type: string; content: any }>
  blockEdits?: Record<number, Record<string, string>>
  onCellChange?: (tableIdx: number, rowIdx: number, colIdx: number, val: string) => void
}

export function RenderedBlocks({
  blocks,
  blockEdits,
  onCellChange,
}: RenderedBlocksProps) {
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

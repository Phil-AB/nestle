"use client"

import { useState, useRef } from "react"
import { Check, X, Pencil } from "lucide-react"
import { ConfidenceBadge } from "../shared/ConfidenceBadge"
import { unwrap } from "../lib/utils"

interface EditableItemCellProps {
  raw: any
  edited: string | undefined
  isEdited: boolean
  confidence: number
  readOnly?: boolean
  onChange?: (value: string) => void
}

export function EditableItemCell({
  raw,
  edited,
  isEdited,
  confidence,
  readOnly,
  onChange,
}: EditableItemCellProps) {
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

"use client"

import { useState, useRef } from "react"
import { Input } from "@/components/ui/input"
import { Check, X, Pencil } from "lucide-react"
import { ConfidenceBadge, RedactedBadge } from "../shared/ConfidenceBadge"
import { unwrap, deriveConfidence, isRedacted } from "../lib/utils"

interface EditableFieldRowProps {
  fieldKey: string
  rawValue: any
  editedValue: string | undefined
  onChange: (key: string, val: string) => void
}

export function EditableFieldRow({
  fieldKey,
  rawValue,
  editedValue,
  onChange,
}: EditableFieldRowProps) {
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

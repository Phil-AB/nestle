"use client"

import { FileUp, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { DocSlot } from "../lib/types"

interface FileSlotProps {
  slot: DocSlot
  file: File | null
  onSelect: (file: File) => void
  onRemove: () => void
}

export function FileSlot({ slot, file, onSelect, onRemove }: FileSlotProps) {
  const inputId = `file-slot-${slot.key}`
  return (
    <div className="flex items-start gap-4 p-4 rounded-lg border border-border bg-muted/30">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="font-semibold text-foreground text-sm">{slot.label}</span>
          {slot.required ? (
            <span className="text-[10px] font-bold uppercase tracking-wide text-destructive"></span>
          ) : (
            <span className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground"></span>
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

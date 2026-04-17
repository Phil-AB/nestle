"use client"

import { useState } from "react"
import { Card } from "@/components/ui/card"
import { FileText, ChevronDown, ChevronUp } from "lucide-react"
import { ConfidenceBadge } from "../shared/ConfidenceBadge"
import { EditableLineItemsTable } from "../field-review/EditableLineItemsTable"
import { RenderedBlocks } from "../field-review/RenderedBlocks"
import { FIELD_GROUPS } from "../lib/constants"
import { unwrap, deriveConfidence } from "../lib/utils"
import type { ExtractedDocumentMeta } from "../lib/types"

interface ExtractedFieldsReferenceProps {
  docMeta: ExtractedDocumentMeta
}

export function ExtractedFieldsReference({ docMeta }: ExtractedFieldsReferenceProps) {
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

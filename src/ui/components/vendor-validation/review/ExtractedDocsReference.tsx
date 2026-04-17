"use client"

import { useState } from "react"
import { Card } from "@/components/ui/card"
import { FileText, ChevronDown, ChevronUp } from "lucide-react"
import { ConfidenceBadge, RedactedBadge } from "../shared/ConfidenceBadge"
import { EditableLineItemsTable } from "../field-review/EditableLineItemsTable"
import { ExtractedTablesSection } from "../field-review/ExtractedTablesSection"
import { DOC_FIELD_GROUPS, DOC_DISPLAY_LABEL } from "../lib/constants"
import { unwrap, deriveConfidence, isRedacted } from "../lib/utils"
import type { ExtractedDocumentMeta } from "../lib/types"

function ExtractedDocRefPanel({
  docType,
  docMeta,
}: {
  docType: string
  docMeta: ExtractedDocumentMeta
}) {
  const [open, setOpen] = useState(false)
  const fields = docMeta.fields ?? {}
  const priorityKeys = DOC_FIELD_GROUPS[docType] ?? []
  const allKeys = Object.keys(fields).filter((k) => k !== "items" && !k.startsWith("_"))
  // Show priority keys first, then any remaining ones
  const ordered = [
    ...priorityKeys.filter((k) => k in fields),
    ...allKeys.filter((k) => !priorityKeys.includes(k)),
  ]

  return (
    <Card className="overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-muted/30 transition-colors text-left"
        onClick={() => setOpen(!open)}
      >
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-muted-foreground" />
          <span className="font-semibold text-sm text-foreground">
            {DOC_DISPLAY_LABEL[docType] ?? docType}
          </span>
          <span className="text-[10px] font-mono text-muted-foreground">{allKeys.length} fields</span>
        </div>
        {open ? (
          <ChevronUp className="w-4 h-4 text-muted-foreground" />
        ) : (
          <ChevronDown className="w-4 h-4 text-muted-foreground" />
        )}
      </button>

      {open && (
        <div className="border-t border-border px-4 py-3">
          <div className="grid grid-cols-2 gap-x-6 gap-y-2">
            {ordered.map((key) => {
              const raw = fields[key]
              const redacted = isRedacted(raw)
              const val = unwrap(raw)
              const conf = deriveConfidence(raw)
              const label = key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
              return (
                <div key={key} className="flex items-start gap-2 min-w-0">
                  <div className="flex-1 min-w-0">
                    <p className="text-[10px] text-muted-foreground font-mono leading-none mb-0.5">
                      {label}
                    </p>
                    <p className="text-xs font-mono text-foreground truncate" title={val || "—"}>
                      {redacted
                        ? <span className="text-slate-400 dark:text-slate-500 italic">—</span>
                        : val || <span className="text-muted-foreground italic">—</span>
                      }
                    </p>
                  </div>
                  {redacted ? <RedactedBadge /> : <ConfidenceBadge score={conf} />}
                </div>
              )
            })}
          </div>

          {docMeta.items && docMeta.items.length > 0 && (
            <EditableLineItemsTable items={docMeta.items} readOnly />
          )}

          {docMeta.tables && docMeta.tables.length > 0 && (
            <ExtractedTablesSection tables={docMeta.tables} />
          )}
        </div>
      )}
    </Card>
  )
}

interface ExtractedDocsReferenceProps {
  extractedDocuments: Record<string, ExtractedDocumentMeta>
}

export function ExtractedDocsReference({
  extractedDocuments,
}: ExtractedDocsReferenceProps) {
  const [open, setOpen] = useState(false)
  const docCount = Object.keys(extractedDocuments).length

  return (
    <div className="space-y-2">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        <FileText className="w-3.5 h-3.5" />
        <span className="font-medium">
          {open ? "Hide" : "Show"} extracted document fields ({docCount} doc{docCount !== 1 ? "s" : ""})
        </span>
        {open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        <span className="italic">— reference while reviewing discrepancies</span>
      </button>

      {open && (
        <div className="space-y-2">
          {Object.entries(extractedDocuments).map(([docType, docMeta]) => (
            <ExtractedDocRefPanel key={docType} docType={docType} docMeta={docMeta} />
          ))}
        </div>
      )}
    </div>
  )
}

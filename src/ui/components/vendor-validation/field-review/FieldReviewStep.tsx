"use client"

import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Loader, Save, ClipboardCheck, AlertCircle } from "lucide-react"
import { DocumentFieldPanel } from "./DocumentFieldPanel"
import type { ExtractedDocumentMeta, FieldEdits, LineItemEdits, TableEdits } from "../lib/types"

interface FieldReviewStepProps {
  extractedDocuments: Record<string, ExtractedDocumentMeta>
  fieldEdits: FieldEdits
  lineItemEdits: LineItemEdits
  tableEdits: TableEdits
  saving: boolean
  saveError: string | null
  onFieldChange: (docType: string, key: string, val: string) => void
  onItemChange: (docType: string, rowIndex: number, column: string, val: string) => void
  onTableCellChange: (docType: string, tblIdx: number, rowIdx: number, colIdx: number, val: string) => void
  onSave: () => void
  onSkip: () => void
  onReupload: () => void
}

export function FieldReviewStep({
  extractedDocuments,
  fieldEdits,
  lineItemEdits,
  tableEdits,
  saving,
  saveError,
  onFieldChange,
  onItemChange,
  onTableCellChange,
  onSave,
  onSkip,
  onReupload,
}: FieldReviewStepProps) {
  return (
    <div className="space-y-4">
      {/* Header banner */}
      <Card className="p-5 border-l-4 border-primary bg-primary/5">
        <div className="flex items-start gap-3">
          <ClipboardCheck className="w-5 h-5 text-primary mt-0.5 flex-shrink-0" />
          <div>
            <p className="font-semibold text-foreground">Review Extracted Fields</p>
            <p className="text-sm text-muted-foreground mt-0.5">
              Check every extracted value before it is saved. Each field shows its AI confidence score.
              Hover a row to edit it — press Enter to confirm or Escape to cancel.
            </p>
          </div>
        </div>
      </Card>

      {/* Confidence legend */}
      <div className="flex items-center gap-4 px-1">
        <span className="text-xs text-muted-foreground font-medium">Confidence:</span>
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">Confident</span>
          <span className="text-xs text-muted-foreground">80–100%</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">Partially Confident</span>
          <span className="text-xs text-muted-foreground">51–79%</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">Not Confident</span>
          <span className="text-xs text-muted-foreground">0–50% — verify manually</span>
        </div>
      </div>

      {/* Document panels */}
      {Object.entries(extractedDocuments).map(([docType, docMeta]) => (
        <DocumentFieldPanel
          key={docType}
          docType={docType}
          docMeta={docMeta}
          edits={fieldEdits[docType] ?? {}}
          itemEdits={lineItemEdits[docType] ?? {}}
          tableEdits={tableEdits[docType] ?? {}}
          onFieldChange={onFieldChange}
          onItemChange={onItemChange}
          onTableCellChange={onTableCellChange}
        />
      ))}

      {/* Save error */}
      {saveError && (
        <Card className="p-4 border-l-4 border-destructive bg-destructive/5">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-4 h-4 text-destructive mt-0.5 flex-shrink-0" />
            <p className="text-sm text-destructive">{saveError}</p>
          </div>
        </Card>
      )}

      {/* Actions */}
      <div className="flex justify-between items-center pt-2">
        <Button variant="outline" onClick={onReupload}>
          Re-upload Documents
        </Button>
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={onSkip} className="text-xs text-muted-foreground">
            Skip Review
          </Button>
          <Button
            onClick={onSave}
            disabled={saving}
            className="bg-primary hover:bg-primary/90"
          >
            {saving ? (
              <Loader className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Save className="w-4 h-4 mr-2" />
            )}
            Save &amp; Continue
          </Button>
        </div>
      </div>
    </div>
  )
}

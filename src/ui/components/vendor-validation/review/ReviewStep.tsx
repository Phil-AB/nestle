"use client"

import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  Loader,
  AlertTriangle,
  AlertCircle,
  ClipboardCheck,
  FileText,
  Pencil,
} from "lucide-react"
import { DiscrepancyCard } from "./DiscrepancyCard"
import { ExtractedDocsReference } from "./ExtractedDocsReference"
import { ValidationChecksPanel } from "./ValidationChecksPanel"
import { DocumentViewer } from "../shared/DocumentViewer"
import { TabBar } from "../shared/TabBar"
import { DOC_LABEL } from "../lib/constants"
import type {
  DocFiles,
  ValidationDiscrepancy,
  ExtractedDocumentMeta,
} from "../lib/types"

interface ReviewStepProps {
  files: DocFiles
  reviewView: "review" | "documents"
  setReviewView: (v: "review" | "documents") => void
  activeDocKey: string | null
  setActiveDocKey: (v: string | null) => void
  getDocBlobUrl: (key: string) => string | null
  summary: Record<string, any> | null
  generatedShipmentNumber: string | null
  shipmentNumber: string
  discrepancies: ValidationDiscrepancy[]
  confirmations: Record<string, boolean | null>
  validationResults: any[]
  extractedDocuments: Record<string, ExtractedDocumentMeta> | null
  submitting: boolean
  onResume: () => void
  onConfirmToggle: (id: string, value: boolean) => void
  onReupload: () => void
  onEditFields: () => void
}

export function ReviewStep({
  files,
  reviewView,
  setReviewView,
  activeDocKey,
  setActiveDocKey,
  getDocBlobUrl,
  summary,
  generatedShipmentNumber,
  shipmentNumber,
  discrepancies,
  confirmations,
  validationResults,
  extractedDocuments,
  submitting,
  onResume,
  onConfirmToggle,
  onReupload,
  onEditFields,
}: ReviewStepProps) {
  const uploadedDocs = Object.entries(files).filter(([, f]) => f !== null)

  return (
    <div className="space-y-4">
      {/* Tab bar */}
      <TabBar
        tabs={[
          { v: "review" as const, label: "Discrepancy Review", icon: ClipboardCheck },
          { v: "documents" as const, label: "View Original Documents", icon: FileText, count: uploadedDocs.length },
        ]}
        active={reviewView}
        onChange={(v) => {
          setReviewView(v)
          if (v === "documents" && !activeDocKey) setActiveDocKey(uploadedDocs[0]?.[0] ?? null)
        }}
      />

      {/* Document viewer panel */}
      {reviewView === "documents" && (
        <DocumentViewer
          files={files}
          activeDocKey={activeDocKey}
          setActiveDocKey={setActiveDocKey}
          getDocBlobUrl={getDocBlobUrl}
        />
      )}

      {/* Existing review content */}
      {reviewView === "review" && <>

      {/* Summary */}
      {summary && (
        <div className="grid grid-cols-4 gap-3">
          {[
            { label: "Total Checks", value: summary.total_checks ?? 0, color: "text-foreground" },
            { label: "Passed", value: summary.passed_checks ?? 0, color: "text-green-600" },
            { label: "Failed", value: summary.failed_checks ?? 0, color: (summary.failed_checks ?? 0) > 0 ? "text-destructive" : "text-muted-foreground" },
            { label: "Discrepancies", value: discrepancies.length, color: discrepancies.length > 0 ? "text-amber-500" : "text-muted-foreground" },
          ].map(({ label, value, color }) => (
            <Card key={label} className="p-3 text-center">
              <p className="text-xs text-muted-foreground mb-1">{label}</p>
              <p className={`text-xl font-bold ${color}`}>{value}</p>
            </Card>
          ))}
        </div>
      )}

      {/* Shipment + documents processed strip */}
      {(generatedShipmentNumber || shipmentNumber || summary?.documents_processed) && (
        <Card className="px-4 py-3">
          <div className="flex items-center gap-6 flex-wrap text-xs">
            {(generatedShipmentNumber || shipmentNumber) && (
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">Shipment:</span>
                <span className="font-mono font-semibold text-foreground">
                  {shipmentNumber || generatedShipmentNumber}
                </span>
              </div>
            )}
            {summary?.documents_processed && (
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-muted-foreground">Documents:</span>
                {(summary.documents_processed as string[]).map((doc) => (
                  <span key={doc} className="font-mono bg-muted px-1.5 py-0.5 rounded text-foreground capitalize">
                    {doc.replace(/_/g, " ")}
                  </span>
                ))}
              </div>
            )}
          </div>
        </Card>
      )}

      {/* Extracted documents reference — collapsed, one panel per doc */}
      {extractedDocuments && Object.keys(extractedDocuments).length > 0 && (
        <ExtractedDocsReference extractedDocuments={extractedDocuments} />
      )}

      <Card className="p-5 border-l-4 border-amber-400 bg-amber-50/30 dark:bg-amber-900/10">
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-500 mt-0.5 flex-shrink-0" />
          <div>
            <p className="font-semibold text-foreground">Discrepancies Detected</p>
            <p className="text-sm text-muted-foreground mt-0.5">
              {discrepancies.length} discrepanc{discrepancies.length !== 1 ? "ies" : "y"} found. Review
              each one and choose to accept or reject before proceeding.
            </p>
          </div>
        </div>
      </Card>

      <div className="space-y-5">
        {Object.entries(
          discrepancies.reduce((acc, disc) => {
            const key = disc.source_document ?? "other"
            if (!acc[key]) acc[key] = []
            acc[key].push(disc)
            return acc
          }, {} as Record<string, ValidationDiscrepancy[]>)
        ).map(([docKey, discs]) => (
          <div key={docKey}>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-bold uppercase tracking-widest text-muted-foreground">
                {DOC_LABEL[docKey] ?? docKey.replace(/_/g, " ")}
              </span>
              <span className="text-[10px] font-mono text-muted-foreground/60">
                {discs.length} issue{discs.length !== 1 ? "s" : ""}
              </span>
            </div>
            <div className="space-y-2">
              {discs.map((disc) => (
                <DiscrepancyCard
                  key={disc.id}
                  disc={disc}
                  confirmed={confirmations[disc.id] ?? null}
                  onToggle={onConfirmToggle}
                />
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Validation checks */}
      {validationResults && validationResults.length > 0 && (
        <ValidationChecksPanel results={validationResults} />
      )}

      </>}

      {/* Action footer — always visible */}
      <div className="flex justify-between pt-2">
        <div className="flex gap-2">
          <Button variant="outline" onClick={onReupload}>
            Re-upload Documents
          </Button>
          {extractedDocuments && Object.keys(extractedDocuments).length > 0 && (
            <Button variant="outline" onClick={onEditFields}>
              <Pencil className="w-3.5 h-3.5 mr-1.5" />
              Edit Fields
            </Button>
          )}
        </div>
        <Button
          onClick={onResume}
          disabled={
            submitting ||
            discrepancies.some((d) => confirmations[d.id] === null)
          }
          className="bg-primary hover:bg-primary/90"
        >
          {submitting ? <Loader className="w-4 h-4 mr-2 animate-spin" /> : null}
          Submit Decisions
        </Button>
      </div>
    </div>
  )
}

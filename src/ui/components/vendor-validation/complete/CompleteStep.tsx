"use client"

import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  Loader,
  CheckCircle,
  AlertCircle,
  AlertTriangle,
  FileText,
  ShieldCheck,
  Pencil,
  Copy,
  ArrowRight,
} from "lucide-react"
import { CustomsChecklistTable } from "./CustomsChecklistTable"
import { ValueConflicts } from "./ValueConflicts"
import { ValidationChecksPanel } from "../review/ValidationChecksPanel"
import { DocumentViewer } from "../shared/DocumentViewer"
import { TabBar } from "../shared/TabBar"
import type {
  DocFiles,
  ValidationDiscrepancy,
  ExtractedDocumentMeta,
} from "../lib/types"

interface CompleteStepProps {
  files: DocFiles
  completeView: "results" | "documents"
  setCompleteView: (v: "results" | "documents") => void
  activeDocKey: string | null
  setActiveDocKey: (v: string | null) => void
  getDocBlobUrl: (key: string) => string | null
  finalStatus: string | null
  summary: Record<string, any> | null
  generatedShipmentNumber: string | null
  shipmentNumber: string
  shipmentId: string | null
  discrepancies: ValidationDiscrepancy[]
  validationResults: any[]
  extractedDocuments: Record<string, ExtractedDocumentMeta> | null
  onReset: () => void
  onEditFields: () => void
}

export function CompleteStep({
  files,
  completeView,
  setCompleteView,
  activeDocKey,
  setActiveDocKey,
  getDocBlobUrl,
  finalStatus,
  summary,
  generatedShipmentNumber,
  shipmentNumber,
  shipmentId,
  discrepancies,
  validationResults,
  extractedDocuments,
  onReset,
  onEditFields,
}: CompleteStepProps) {
  const uploadedDocs = Object.entries(files).filter(([, f]) => f !== null)
  const mismatches = (discrepancies ?? []).filter(
    (d) => !(d.source_value === null && d.target_value === null)
  )

  return (
    <div className="space-y-5">
      {/* View switcher tab bar */}
      <TabBar
        tabs={[
          { v: "results" as const, label: "Validation Results", icon: ShieldCheck },
          { v: "documents" as const, label: "Documents", icon: FileText, count: uploadedDocs.length },
        ]}
        active={completeView}
        onChange={(v) => {
          setCompleteView(v)
          if (v === "documents" && !activeDocKey) setActiveDocKey(uploadedDocs[0]?.[0] ?? null)
        }}
      />

      {/* Documents viewer */}
      {completeView === "documents" && (
        <DocumentViewer
          files={files}
          activeDocKey={activeDocKey}
          setActiveDocKey={setActiveDocKey}
          getDocBlobUrl={getDocBlobUrl}
        />
      )}

      {/* Validation results (default view) */}
      {completeView === "results" && <>

      {/* Status Banner */}
      <Card
        className={`p-5 border-l-4 ${
          finalStatus === "passed"
            ? "border-green-500 bg-green-50/30 dark:bg-green-900/10"
            : finalStatus === "failed"
            ? "border-destructive bg-destructive/5"
            : "border-amber-400 bg-amber-50/30 dark:bg-amber-900/10"
        }`}
      >
        <div className="flex items-start gap-4">
          <div
            className={`p-2.5 rounded-lg flex-shrink-0 ${
              finalStatus === "passed"
                ? "bg-green-100 dark:bg-green-900/30"
                : finalStatus === "failed"
                ? "bg-destructive/10"
                : "bg-amber-100 dark:bg-amber-900/30"
            }`}
          >
            {finalStatus === "passed" ? (
              <CheckCircle className="w-5 h-5 text-green-600" />
            ) : finalStatus === "failed" ? (
              <AlertCircle className="w-5 h-5 text-destructive" />
            ) : (
              <AlertTriangle className="w-5 h-5 text-amber-500" />
            )}
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="text-lg font-bold text-foreground">
              {finalStatus === "passed"
                ? "Validation Passed"
                : finalStatus === "failed"
                ? "Validation Failed"
                : "Requires Attention"}
            </h2>
            <p className="text-muted-foreground text-sm mt-0.5">
              {finalStatus === "passed"
                ? "All vendor documents are consistent. You may transmit to the clearing agent."
                : finalStatus === "failed"
                ? "Discrepancies remain unresolved. Please correct the documents and retry."
                : "Some discrepancies were found. Review the details below before proceeding."}
            </p>
            {(generatedShipmentNumber || shipmentNumber) && (
              <p className="text-xs text-muted-foreground mt-2 font-mono">
                {shipmentNumber || generatedShipmentNumber}
              </p>
            )}
          </div>
          {shipmentId && (
            <button
              onClick={() => navigator.clipboard.writeText(shipmentId)}
              className="flex-shrink-0 flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground px-2.5 py-1.5 rounded-md border border-border hover:bg-muted transition-colors"
              title="Copy shipment ID"
            >
              <Copy className="w-3 h-3" />
              Copy ID
            </button>
          )}
        </div>
      </Card>

      {/* Stats row */}
      {summary && (
        <div className="grid grid-cols-4 gap-3">
          {[
            { label: "Total Checks", value: summary.total_checks ?? 0, color: "text-foreground" },
            { label: "Passed", value: summary.passed_checks ?? 0, color: "text-green-600 dark:text-green-400" },
            { label: "Failed", value: summary.failed_checks ?? 0, color: (summary.failed_checks ?? 0) > 0 ? "text-destructive" : "text-muted-foreground" },
            { label: "Discrepancies", value: summary.total_discrepancies ?? discrepancies.length, color: discrepancies.length > 0 ? "text-amber-500" : "text-muted-foreground" },
          ].map(({ label, value, color }) => (
            <Card key={label} className="p-3 text-center">
              <p className={`text-2xl font-bold tabular-nums ${color}`}>{value}</p>
              <p className="text-[11px] text-muted-foreground mt-0.5">{label}</p>
            </Card>
          ))}
        </div>
      )}

      {/* Ghana Customs Checklist Table */}
      {extractedDocuments && Object.keys(extractedDocuments).length > 0 && (
        <CustomsChecklistTable
          extractedDocuments={extractedDocuments}
          discrepancies={discrepancies}
          validationResults={validationResults}
        />
      )}

      {/* Value conflict details */}
      {mismatches.length > 0 && (
        <ValueConflicts mismatches={mismatches} />
      )}

      {/* Checks Run */}
      {validationResults && validationResults.length > 0 && (
        <ValidationChecksPanel results={validationResults} />
      )}

      {/* Workflow Notes */}
      {summary?.messages && summary.messages.length > 0 && (
        <Card className="p-4">
          <h3 className="font-semibold text-sm text-foreground mb-2">Workflow Notes</h3>
          <ul className="space-y-1">
            {summary.messages.map((msg: string, i: number) => (
              <li key={i} className="text-xs text-muted-foreground flex gap-2">
                <span className="text-muted-foreground/40">•</span>
                <span>{msg}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      </>}

      {/* Action footer — always visible */}
      <Card className="p-5 space-y-3">
        {finalStatus !== "failed" ? (
          <a href={`/validation/boe${shipmentId ? `?shipment_id=${shipmentId}` : ""}`} className="block">
            <Button className="w-full bg-primary hover:bg-primary/90">
              Proceed to Step 6 — BOE Validation
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </a>
        ) : (
          <Button className="w-full" variant="destructive" onClick={onReset}>
            Fix Documents &amp; Retry
          </Button>
        )}

        <div className="flex gap-2">
          {extractedDocuments && Object.keys(extractedDocuments).length > 0 && (
            <Button variant="outline" onClick={onEditFields} className="flex-1 text-sm">
              <Pencil className="w-3.5 h-3.5 mr-1.5" />
              Edit Extracted Fields
            </Button>
          )}
          <Button variant="outline" onClick={onReset} className="flex-1 text-sm">
            New Validation
          </Button>
        </div>
      </Card>
    </div>
  )
}

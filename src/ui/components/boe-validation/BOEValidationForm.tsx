"use client"

import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  FileUp,
  Loader,
  CheckCircle,
  AlertCircle,
  AlertTriangle,
  X,
  ClipboardCheck,
  Pencil,
  Save,
  Package,
  FileText,
  ShieldCheck,
  Eye,
} from "lucide-react"
import { StepIndicator } from "./shared/StepIndicator"
import { BOEDocumentViewer } from "./shared/BOEDocumentViewer"
import { ShipmentSelector } from "./select/ShipmentSelector"
import { BOEFieldPanel } from "./field-review/BOEFieldPanel"
import { BOEChecklist } from "./results/BOEChecklist"
import { ExtractedFieldsReference } from "./results/ExtractedFieldsReference"
import { DiscrepancyCard } from "./results/DiscrepancyCard"
import { ValidationResultsPanel } from "./results/ValidationResultsPanel"
import { useBOEValidation } from "./hooks/useBOEValidation"

export default function BOEValidationForm() {
  const v = useBOEValidation()

  return (
    <div className="p-8 max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-foreground mb-2">BOE Validation</h1>
        <p className="text-muted-foreground">
          Step 6 — Cross-verify the Bill of Entry against stored vendor documents.
        </p>
      </div>

      {/* Step indicator */}
      {v.step !== "select" && <StepIndicator step={v.step} />}

      {/* Error banner */}
      {v.error && (
        <Card className="p-4 border-l-4 border-destructive bg-destructive/5 mb-6">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-destructive mt-0.5 flex-shrink-0" />
            <div>
              <p className="font-semibold text-destructive text-sm">Error</p>
              <p className="text-sm text-destructive/80 mt-0.5">{v.error}</p>
            </div>
          </div>
        </Card>
      )}

      {/* Select */}
      {v.step === "select" && (
        <div className="space-y-4">
          <Card className="p-5">
            <h2 className="text-sm font-semibold text-foreground mb-1">Select Shipment</h2>
            <p className="text-xs text-muted-foreground mb-4">
              Choose a shipment that completed Step 2 (vendor document validation).
            </p>
            <ShipmentSelector selected={v.selectedShipment} onSelect={v.setSelectedShipment} />
          </Card>

          <Card className="p-5">
            <h2 className="text-sm font-semibold text-foreground mb-1">Bill of Entry</h2>
            <p className="text-xs text-muted-foreground mb-4">
              Upload the BOE (customs declaration) PDF to validate against the vendor documents.
            </p>

            <input
              ref={v.fileInputRef}
              type="file"
              accept=".pdf,.doc,.docx,.jpg,.jpeg,.png"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) v.setBoeFile(f)
                e.target.value = ""
              }}
            />

            {v.boeFile ? (
              <div className="flex items-center gap-3 p-3 bg-primary/5 border border-primary/20 rounded-lg">
                <FileUp className="w-4 h-4 text-primary flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-foreground truncate">{v.boeFile.name}</p>
                  <p className="text-xs text-muted-foreground">{(v.boeFile.size / 1024).toFixed(1)} KB</p>
                </div>
                <button
                  onClick={() => v.setBoeFile(null)}
                  className="text-muted-foreground hover:text-destructive transition-colors flex-shrink-0"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <Button
                variant="outline"
                size="sm"
                onClick={() => v.fileInputRef.current?.click()}
                className="text-xs"
              >
                <FileUp className="w-3 h-3 mr-1.5" />
                Select BOE File
              </Button>
            )}
          </Card>

          <div className="flex justify-end">
            <Button
              onClick={v.handleValidate}
              disabled={!v.selectedShipment || !v.boeFile || v.submitting}
              className="bg-primary hover:bg-primary/90"
            >
              Run BOE Validation
            </Button>
          </div>
        </div>
      )}

      {/* Processing */}
      {v.step === "processing" && (
        <Card className="p-12 text-center">
          <div className="flex justify-center mb-6">
            <div className="p-4 bg-primary/10 rounded-lg">
              <Loader className="w-8 h-8 text-primary animate-spin" />
            </div>
          </div>
          <h2 className="text-2xl font-bold text-foreground mb-2">Processing BOE</h2>
          <p className="text-muted-foreground">
            Extracting fields and running cross-validation against vendor documents.
            This usually takes ~ 2 minutes.
          </p>
          <p className="text-sm text-muted-foreground mt-3 font-mono">
            {Math.floor(v.elapsed / 60)}:{String(v.elapsed % 60).padStart(2, "0")} elapsed — keep this tab open
          </p>
        </Card>
      )}

      {/* Field Review */}
      {v.step === "field_review" && v.extractedBOE && (
        <div className="space-y-4">

          {/* Tab bar */}
          <div className="flex justify-center py-1">
            <div className="flex items-center bg-muted/70 rounded-xl p-1 gap-0.5 border border-border/50 shadow-sm">
              {[
                { v: "fields" as const, label: "Review Fields", icon: ClipboardCheck },
                { v: "document" as const, label: "View BOE Document", icon: Eye },
              ].map(({ v: tab, label, icon: Icon }) => (
                <button
                  key={tab}
                  onClick={() => v.setFieldReviewView(tab)}
                  className={`flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-medium transition-all duration-150 ${
                    v.fieldReviewView === tab
                      ? "bg-background text-foreground shadow-sm border border-border/60"
                      : "text-muted-foreground hover:text-foreground hover:bg-background/50"
                  }`}
                >
                  <Icon className={`w-3.5 h-3.5 ${v.fieldReviewView === tab ? "text-primary" : ""}`} />
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Document viewer */}
          {v.fieldReviewView === "document" && (
            <BOEDocumentViewer boeFile={v.boeFile} getBOEBlobUrl={v.getBOEBlobUrl} />
          )}

          {/* Fields review panel */}
          {v.fieldReviewView === "fields" && <>

          <Card className="p-5 border-l-4 border-primary bg-primary/5">
            <div className="flex items-start gap-3">
              <ClipboardCheck className="w-5 h-5 text-primary mt-0.5 flex-shrink-0" />
              <div>
                <p className="font-semibold text-foreground">Review Extracted BOE Fields</p>
                <p className="text-sm text-muted-foreground mt-0.5">
                  Verify every extracted value before proceeding. Each field shows its AI
                  confidence score. Hover a row to edit — press Enter to confirm or Escape to
                  cancel. Switch to <strong>View BOE Document</strong> to cross-reference the original.
                </p>
              </div>
            </div>
          </Card>

          {/* Confidence legend */}
          <div className="flex items-center gap-4 px-1">
            <span className="text-xs text-muted-foreground font-medium">Confidence:</span>
            {[
              {
                label: "Confident",
                classes: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
                desc: "80–100%",
              },
              {
                label: "Partially Confident",
                classes: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
                desc: "51–79%",
              },
              {
                label: "Not Confident",
                classes: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
                desc: "0–50% — verify manually",
              },
            ].map(({ label, classes, desc }) => (
              <div key={label} className="flex items-center gap-1.5">
                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${classes}`}>
                  {label}
                </span>
                <span className="text-xs text-muted-foreground">{desc}</span>
              </div>
            ))}
          </div>

          <BOEFieldPanel
            docMeta={v.extractedBOE}
            edits={v.fieldEdits}
            itemEdits={v.lineItemEdits}
            blockEdits={v.blockEdits}
            onFieldChange={v.handleFieldChange}
            onItemChange={v.handleLineItemChange}
            onBlockCellChange={v.handleBlockCellChange}
          />

          {v.saveError && (
            <Card className="p-4 border-l-4 border-destructive bg-destructive/5">
              <div className="flex items-start gap-3">
                <AlertCircle className="w-4 h-4 text-destructive mt-0.5 flex-shrink-0" />
                <p className="text-sm text-destructive">{v.saveError}</p>
              </div>
            </Card>
          )}

          </>}

          <div className="flex justify-between items-center pt-2">
            <Button variant="outline" onClick={() => v.setStep("select")}>
              Re-upload BOE
            </Button>
            <div className="flex items-center gap-3">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  if (v.pendingResult) v.applyResult(v.pendingResult)
                }}
                className="text-xs text-muted-foreground"
              >
                Skip Review
              </Button>
              <Button
                onClick={v.handleSaveFields}
                disabled={v.saving}
                className="bg-primary hover:bg-primary/90"
              >
                {v.saving ? (
                  <Loader className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Save className="w-4 h-4 mr-2" />
                )}
                Save &amp; Continue
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Results */}
      {v.step === "results" && (
        <div className="space-y-4">

          {/* Tab bar */}
          <div className="flex justify-center py-1">
            <div className="flex items-center bg-muted/70 rounded-xl p-1 gap-0.5 border border-border/50 shadow-sm">
              {[
                { v: "results" as const, label: "Validation Results", icon: ShieldCheck },
                { v: "document" as const, label: "View BOE Document", icon: Eye },
              ].map(({ v: tab, label, icon: Icon }) => (
                <button
                  key={tab}
                  onClick={() => v.setResultsView(tab)}
                  className={`flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-medium transition-all duration-150 ${
                    v.resultsView === tab
                      ? "bg-background text-foreground shadow-sm border border-border/60"
                      : "text-muted-foreground hover:text-foreground hover:bg-background/50"
                  }`}
                >
                  <Icon className={`w-3.5 h-3.5 ${v.resultsView === tab ? "text-primary" : ""}`} />
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Document viewer */}
          {v.resultsView === "document" && (
            <BOEDocumentViewer boeFile={v.boeFile} getBOEBlobUrl={v.getBOEBlobUrl} />
          )}

          {/* Validation results content */}
          {v.resultsView === "results" && <>

          {/* Summary stats */}
          {v.summary && (
            <div className="grid grid-cols-4 gap-3">
              {[
                { label: "Total Checks", value: v.summary.total_checks ?? 0, color: "text-foreground" },
                { label: "Passed", value: v.summary.passed_checks ?? 0, color: "text-green-600" },
                { label: "Failed", value: v.summary.failed_checks ?? 0, color: (v.summary.failed_checks ?? 0) > 0 ? "text-destructive" : "text-muted-foreground" },
                { label: "Discrepancies", value: v.summary.total_discrepancies ?? 0, color: (v.summary.total_discrepancies ?? 0) > 0 ? "text-destructive" : "text-muted-foreground" },
              ].map(({ label, value, color }) => (
                <Card key={label} className="p-3 text-center">
                  <p className="text-xs text-muted-foreground mb-1">{label}</p>
                  <p className={`text-xl font-bold ${color}`}>{value}</p>
                </Card>
              ))}
            </div>
          )}

          {/* Shipment + document context strip */}
          {(v.selectedShipment || v.summary?.documents_processed) && (
            <Card className="px-4 py-3">
              <div className="flex items-center gap-6 flex-wrap text-xs">
                {v.selectedShipment && (
                  <div className="flex items-center gap-2">
                    <Package className="w-3.5 h-3.5 text-muted-foreground" />
                    <span className="text-muted-foreground">Shipment:</span>
                    <span className="font-mono font-semibold text-foreground">{v.selectedShipment.shipment_number}</span>
                    {v.selectedShipment.supplier_name && (
                      <span className="text-muted-foreground">· {v.selectedShipment.supplier_name}</span>
                    )}
                  </div>
                )}
                {v.summary?.documents_processed && (
                  <div className="flex items-center gap-2 flex-wrap">
                    <FileText className="w-3.5 h-3.5 text-muted-foreground" />
                    <span className="text-muted-foreground">Documents validated:</span>
                    {(v.summary.documents_processed as string[]).map((doc) => (
                      <span key={doc} className="font-mono bg-muted px-1.5 py-0.5 rounded text-foreground capitalize">
                        {doc.replace(/_/g, " ")}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </Card>
          )}

          {/* BOE Checklist */}
          {v.extractedBOE && (
            <BOEChecklist
              extractedBOE={v.extractedBOE}
              validationResults={v.validationResults}
              discrepancies={v.discrepancies}
            />
          )}

          {/* Extracted BOE fields */}
          {v.extractedBOE && Object.keys(v.extractedBOE.fields ?? {}).length > 0 && (
            <ExtractedFieldsReference docMeta={v.extractedBOE} />
          )}

          {/* Discrepancy HITL */}
          {v.discrepancies.length > 0 && (
            <Card className="p-5 border-l-4 border-destructive bg-destructive/5">
              <div className="flex items-start gap-3 mb-4">
                <AlertTriangle className="w-5 h-5 text-destructive mt-0.5 flex-shrink-0" />
                <div>
                  <p className="font-semibold text-foreground">
                    {v.discrepancies.length} Discrepanc{v.discrepancies.length === 1 ? "y" : "ies"} Require Review
                  </p>
                  <p className="text-sm text-muted-foreground mt-0.5">
                    Accept or reject each discrepancy before finalising the validation.
                  </p>
                </div>
              </div>
              <div className="space-y-3">
                {v.discrepancies.map((disc) => (
                  <DiscrepancyCard
                    key={disc.id}
                    disc={disc}
                    confirmed={v.confirmations[disc.id] ?? null}
                    onToggle={(id, val) => v.setConfirmations((prev) => ({ ...prev, [id]: val }))}
                  />
                ))}
              </div>
            </Card>
          )}

          {/* All validation checks */}
          {v.validationResults.length > 0 && (
            <ValidationResultsPanel results={v.validationResults} />
          )}

          </>}

          <div className="flex justify-between pt-2">
            <div className="flex gap-2">
              <Button variant="outline" onClick={v.handleReset}>
                Validate Another BOE
              </Button>
              {v.extractedBOE && (
                <Button variant="outline" onClick={() => v.setStep("field_review")}>
                  <Pencil className="w-3.5 h-3.5 mr-1.5" />
                  Edit Fields
                </Button>
              )}
            </div>
            <Button
              onClick={v.handleResume}
              disabled={
                v.submitting ||
                v.discrepancies.some((d) => v.confirmations[d.id] === null || v.confirmations[d.id] === undefined)
              }
              className="bg-primary hover:bg-primary/90"
            >
              {v.submitting && <Loader className="w-4 h-4 mr-2 animate-spin" />}
              {v.discrepancies.length > 0 ? "Submit Decisions" : "Confirm & Complete"}
            </Button>
          </div>
        </div>
      )}

      {/* Complete */}
      {v.step === "complete" && (
        <div className="space-y-4">
          <Card
            className={`p-6 border-l-4 ${
              v.finalStatus === "passed"
                ? "border-green-500 bg-green-50/30 dark:bg-green-900/10"
                : v.finalStatus === "failed"
                ? "border-destructive bg-destructive/5"
                : "border-amber-400 bg-amber-50/30 dark:bg-amber-900/10"
            }`}
          >
            <div className="flex items-start gap-4">
              <div
                className={`p-2.5 rounded-lg flex-shrink-0 ${
                  v.finalStatus === "passed"
                    ? "bg-green-100 dark:bg-green-900/30"
                    : v.finalStatus === "failed"
                    ? "bg-destructive/10"
                    : "bg-amber-100 dark:bg-amber-900/30"
                }`}
              >
                {v.finalStatus === "passed" ? (
                  <CheckCircle className="w-6 h-6 text-green-600" />
                ) : v.finalStatus === "failed" ? (
                  <AlertCircle className="w-6 h-6 text-destructive" />
                ) : (
                  <AlertTriangle className="w-6 h-6 text-amber-500" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <h2 className="text-xl font-bold text-foreground">
                  {v.finalStatus === "passed"
                    ? "BOE Validation Passed"
                    : v.finalStatus === "failed"
                    ? "BOE Validation Failed"
                    : "BOE Requires Attention"}
                </h2>
                {v.selectedShipment && (
                  <p className="text-sm text-muted-foreground mt-0.5">
                    Shipment:{" "}
                    <span className="font-mono font-medium">
                      {v.selectedShipment.shipment_number}
                    </span>
                  </p>
                )}
                {v.summary && (
                  <div className="flex items-center gap-4 mt-3 text-sm flex-wrap">
                    <span className="text-muted-foreground">
                      <span className="font-semibold text-green-600">
                        {v.summary.passed_checks}
                      </span>
                      /{v.summary.total_checks} checks passed
                    </span>
                    {(v.summary.total_discrepancies ?? 0) > 0 && (
                      <span className="text-destructive font-semibold">
                        {v.summary.total_discrepancies} discrepanc{v.summary.total_discrepancies === 1 ? "y" : "ies"}
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          </Card>

          {/* Validation checks on complete screen */}
          {v.validationResults.length > 0 && (
            <ValidationResultsPanel results={v.validationResults} />
          )}

          <div className="flex justify-between pt-2">
            <Button variant="outline" onClick={v.handleReset}>
              Validate Another BOE
            </Button>
            {v.finalStatus === "passed" && (
              <Button className="bg-green-600 hover:bg-green-700 text-white">
                <CheckCircle className="w-4 h-4 mr-2" />
                Proceed to Clearance
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

"use client"

import { Card } from "@/components/ui/card"
import { Loader, AlertCircle } from "lucide-react"
import { StepIndicator } from "./shared/StepIndicator"
import { UploadStep } from "./upload/UploadStep"
import { FieldReviewStep } from "./field-review/FieldReviewStep"
import { ReviewStep } from "./review/ReviewStep"
import { CompleteStep } from "./complete/CompleteStep"
import { useVendorValidation } from "./hooks/useVendorValidation"

export default function VendorValidationForm() {
  const v = useVendorValidation()

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-foreground mb-2">Vendor Document Validation</h1>
        <p className="text-muted-foreground">
          Step 2 — Upload and cross-validate vendor documents before transmitting to the clearing agent.
        </p>
      </div>

      {/* Step indicator */}
      {v.step !== "upload" && (
        <StepIndicator step={v.step} />
      )}

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

      {/* Upload */}
      {v.step === "upload" && (
        <UploadStep
          uploadMode={v.uploadMode}
          setUploadMode={v.setUploadMode}
          bundleFile={v.bundleFile}
          setBundleFile={v.setBundleFile}
          bundleRequiredFilled={v.bundleRequiredFilled}
          onBundleValidate={v.handleBundleValidate}
          showShipmentDetails={v.showShipmentDetails}
          setShowShipmentDetails={v.setShowShipmentDetails}
          shipmentNumber={v.shipmentNumber}
          setShipmentNumber={v.setShipmentNumber}
          supplierName={v.supplierName}
          setSupplierName={v.setSupplierName}
          consigneeName={v.consigneeName}
          setConsigneeName={v.setConsigneeName}
          incoterm={v.incoterm}
          setIncoterm={v.setIncoterm}
          transportMode={v.transportMode}
          setTransportMode={v.setTransportMode}
          files={v.files}
          setFile={v.setFile}
          requiredFilled={v.requiredFilled}
          submitting={v.submitting}
          onValidate={v.handleValidate}
        />
      )}

      {/* Processing */}
      {v.step === "processing" && (
        <Card className="p-12 text-center">
          <div className="flex justify-center mb-6">
            <div className="p-4 bg-primary/10 rounded-lg">
              <Loader className="w-8 h-8 text-primary animate-spin" />
            </div>
          </div>
          <h2 className="text-2xl font-bold text-foreground mb-2">Extracting &amp; Validating</h2>
          <p className="text-muted-foreground">
            AI is extracting and cross-validating your documents. This should take about ~ 3 minutes.
          </p>
          <p className="text-sm text-muted-foreground mt-3 font-mono">
            {Math.floor(v.elapsed / 60)}:{String(v.elapsed % 60).padStart(2, "0")} elapsed — please keep this tab open
          </p>
        </Card>
      )}

      {/* Field Review */}
      {v.step === "field_review" && v.extractedDocuments && (
        <FieldReviewStep
          extractedDocuments={v.extractedDocuments}
          fieldEdits={v.fieldEdits}
          lineItemEdits={v.lineItemEdits}
          tableEdits={v.tableEdits}
          saving={v.saving}
          saveError={v.saveError}
          files={v.files}
          activeDocKey={v.activeDocKey}
          setActiveDocKey={v.setActiveDocKey}
          getDocBlobUrl={v.getDocBlobUrl}
          onFieldChange={v.handleFieldChange}
          onItemChange={v.handleLineItemChange}
          onTableCellChange={v.handleTableCellChange}
          onSave={v.handleSaveFields}
          onSkip={v.handleSkipFieldReview}
          onReupload={() => v.setStep("upload")}
        />
      )}

      {/* HITL Review */}
      {v.step === "review" && (
        <ReviewStep
          files={v.files}
          reviewView={v.reviewView}
          setReviewView={v.setReviewView}
          activeDocKey={v.activeDocKey}
          setActiveDocKey={v.setActiveDocKey}
          getDocBlobUrl={v.getDocBlobUrl}
          summary={v.summary}
          generatedShipmentNumber={v.generatedShipmentNumber}
          shipmentNumber={v.shipmentNumber}
          discrepancies={v.discrepancies}
          confirmations={v.confirmations}
          validationResults={v.validationResults}
          extractedDocuments={v.extractedDocuments}
          submitting={v.submitting}
          onResume={v.handleResume}
          onConfirmToggle={(id, value) => v.setConfirmations((prev) => ({ ...prev, [id]: value }))}
          onReupload={() => v.setStep("upload")}
          onEditFields={() => v.setStep("field_review")}
        />
      )}

      {/* Complete */}
      {v.step === "complete" && (
        <CompleteStep
          files={v.files}
          completeView={v.completeView}
          setCompleteView={v.setCompleteView}
          activeDocKey={v.activeDocKey}
          setActiveDocKey={v.setActiveDocKey}
          getDocBlobUrl={v.getDocBlobUrl}
          finalStatus={v.finalStatus}
          summary={v.summary}
          generatedShipmentNumber={v.generatedShipmentNumber}
          shipmentNumber={v.shipmentNumber}
          shipmentId={v.shipmentId}
          discrepancies={v.discrepancies}
          validationResults={v.validationResults}
          extractedDocuments={v.extractedDocuments}
          onReset={v.handleReset}
          onEditFields={() => v.setStep("field_review")}
        />
      )}
    </div>
  )
}

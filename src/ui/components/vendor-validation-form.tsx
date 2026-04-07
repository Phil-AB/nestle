"use client"

import { useState } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  FileUp,
  Loader,
  CheckCircle,
  AlertCircle,
  AlertTriangle,
  X,
  ChevronDown,
  ChevronUp,
  ClipboardCheck,
  Settings2,
} from "lucide-react"
import { apiClient, type ValidationDiscrepancy, type VendorValidationResponse } from "@/lib/api-client"

// ─── Document Slot Definition ─────────────────────────────────────────────────

interface DocSlot {
  key: "invoice" | "packing_list" | "freight_manifest" | "certificate_of_origin"
  label: string
  required: boolean
  description: string
}

const DOC_SLOTS: DocSlot[] = [
  {
    key: "invoice",
    label: "Commercial Invoice",
    required: true,
    description: "Main invoice from the supplier",
  },
  {
    key: "packing_list",
    label: "Packing List",
    required: true,
    description: "Itemised list of goods shipped",
  },
  {
    key: "freight_manifest",
    label: "Freight Manifest / Bill of Lading",
    required: false,
    description: "Carrier's document of goods transported",
  },
  {
    key: "certificate_of_origin",
    label: "Certificate of Origin",
    required: false,
    description: "Certifies the country of manufacture",
  },
]

function autoShipmentNumber() {
  const now = new Date()
  const ymd = `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}${String(now.getDate()).padStart(2, "0")}`
  const rand = Math.random().toString(36).slice(2, 6).toUpperCase()
  return `SHP-${ymd}-${rand}`
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function FileSlot({
  slot,
  file,
  onSelect,
  onRemove,
}: {
  slot: DocSlot
  file: File | null
  onSelect: (file: File) => void
  onRemove: () => void
}) {
  const inputId = `file-slot-${slot.key}`

  return (
    <div className="flex items-start gap-4 p-4 rounded-lg border border-border bg-muted/30">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="font-semibold text-foreground text-sm">{slot.label}</span>
          {slot.required ? (
            <span className="text-[10px] font-bold uppercase tracking-wide text-destructive">Required</span>
          ) : (
            <span className="text-[10px] font-bold uppercase tracking-wide text-muted-foreground">Optional</span>
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

function DiscrepancyCard({
  disc,
  confirmed,
  onToggle,
}: {
  disc: ValidationDiscrepancy
  confirmed: boolean | null
  onToggle: (id: string, value: boolean) => void
}) {
  const [expanded, setExpanded] = useState(true)
  const severityClass =
    disc.severity === "critical"
      ? "border-destructive/40 bg-destructive/5"
      : disc.severity === "major"
      ? "border-amber-400/40 bg-amber-50/30 dark:bg-amber-900/10"
      : "border-border bg-muted/20"

  return (
    <div className={`rounded-lg border p-4 ${severityClass}`}>
      <div
        className="flex items-start gap-3 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <AlertTriangle
          className={`w-4 h-4 mt-0.5 flex-shrink-0 ${
            disc.severity === "critical" ? "text-destructive" : "text-amber-500"
          }`}
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-sm text-foreground">{disc.field}</span>
            <span
              className={`text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded ${
                disc.severity === "critical"
                  ? "bg-destructive/10 text-destructive"
                  : "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
              }`}
            >
              {disc.severity}
            </span>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">{disc.description}</p>
        </div>
        {expanded ? (
          <ChevronUp className="w-4 h-4 text-muted-foreground flex-shrink-0" />
        ) : (
          <ChevronDown className="w-4 h-4 text-muted-foreground flex-shrink-0" />
        )}
      </div>

      {expanded && (
        <div className="mt-3 pl-7 space-y-3">
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="p-2 bg-card rounded border border-border">
              <p className="text-muted-foreground mb-0.5">{disc.source_document}</p>
              <p className="font-medium text-foreground truncate">{String(disc.source_value ?? "—")}</p>
            </div>
            <div className="p-2 bg-card rounded border border-border">
              <p className="text-muted-foreground mb-0.5">{disc.target_document}</p>
              <p className="font-medium text-foreground truncate">{String(disc.target_value ?? "—")}</p>
            </div>
          </div>

          <div className="flex gap-2">
            <Button
              size="sm"
              variant={confirmed === true ? "default" : "outline"}
              className={`text-xs flex-1 ${confirmed === true ? "bg-green-600 hover:bg-green-700 text-white" : ""}`}
              onClick={() => onToggle(disc.id, true)}
            >
              <CheckCircle className="w-3 h-3 mr-1.5" />
              Accept Discrepancy
            </Button>
            <Button
              size="sm"
              variant={confirmed === false ? "destructive" : "outline"}
              className="text-xs flex-1"
              onClick={() => onToggle(disc.id, false)}
            >
              <X className="w-3 h-3 mr-1.5" />
              Reject
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Main Component ───────────────────────────────────────────────────────────

type Step = "upload" | "processing" | "review" | "complete"

export default function VendorValidationForm() {
  const [step, setStep] = useState<Step>("upload")

  // Optional shipment details — collapsed by default
  const [showShipmentDetails, setShowShipmentDetails] = useState(false)
  const [shipmentNumber, setShipmentNumber] = useState("")
  const [supplierName, setSupplierName] = useState("")
  const [consigneeName, setConsigneeName] = useState("")
  const [incoterm, setIncoterm] = useState("")
  const [transportMode, setTransportMode] = useState("")

  // Files
  const [files, setFiles] = useState<Record<DocSlot["key"], File | null>>({
    invoice: null,
    packing_list: null,
    freight_manifest: null,
    certificate_of_origin: null,
  })

  // Results
  const [shipmentId, setShipmentId] = useState<string | null>(null)
  const [generatedShipmentNumber, setGeneratedShipmentNumber] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [discrepancies, setDiscrepancies] = useState<ValidationDiscrepancy[]>([])
  const [validationResults, setValidationResults] = useState<any[]>([])
  const [finalStatus, setFinalStatus] = useState<string | null>(null)
  const [summary, setSummary] = useState<Record<string, any> | null>(null)
  const [confirmations, setConfirmations] = useState<Record<string, boolean | null>>({})

  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  // ── Helpers ───────────────────────────────────────────────────────────────

  const setFile = (key: DocSlot["key"], file: File | null) =>
    setFiles((prev) => ({ ...prev, [key]: file }))

  const requiredFilled = files.invoice !== null && files.packing_list !== null

  // ── Submit ────────────────────────────────────────────────────────────────

  const handleValidate = async () => {
    setError(null)
    setSubmitting(true)
    setStep("processing")

    try {
      // Create shipment — use user-provided number or auto-generate
      const number = shipmentNumber.trim() || autoShipmentNumber()
      setGeneratedShipmentNumber(number)

      const shipment = await apiClient.createShipment({
        shipment_number: number,
        supplier_name: supplierName.trim() || undefined as any,
        consignee_name: consigneeName.trim() || undefined as any,
        incoterm: incoterm.trim() || undefined,
        transport_mode: transportMode.trim() || undefined,
      })
      setShipmentId(shipment.shipment_id)

      // Validate vendor docs
      const result: VendorValidationResponse = await apiClient.validateVendorDocs(
        shipment.shipment_id,
        {
          invoice: files.invoice ?? undefined,
          packing_list: files.packing_list ?? undefined,
          freight_manifest: files.freight_manifest ?? undefined,
          certificate_of_origin: files.certificate_of_origin ?? undefined,
        }
      )

      if (result.workflow_status === "awaiting_user" && result.discrepancies?.length) {
        setSessionId(result.session_id ?? null)
        setDiscrepancies(result.discrepancies)
        setValidationResults((result as any).validation_results ?? [])
        setSummary(result.summary ?? null)
        const initial: Record<string, boolean | null> = {}
        result.discrepancies.forEach((d) => { initial[d.id] = null })
        setConfirmations(initial)
        setStep("review")
      } else {
        setFinalStatus(result.final_status ?? null)
        setSummary(result.summary ?? null)
        setDiscrepancies(result.discrepancies ?? [])
        setValidationResults((result as any).validation_results ?? [])
        setStep("complete")
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Validation failed. Please try again.")
      setStep("upload")
    } finally {
      setSubmitting(false)
    }
  }

  // ── HITL Resume ───────────────────────────────────────────────────────────

  const handleResume = async () => {
    if (!sessionId) return
    setError(null)
    setSubmitting(true)
    setStep("processing")
    try {
      const payload = Object.entries(confirmations)
        .filter(([, v]) => v !== null)
        .map(([id, confirmed]) => ({ discrepancy_id: id, confirmed: confirmed as boolean }))

      const result = await apiClient.resumeValidationSession(sessionId, payload)
      setFinalStatus((result as any).final_status ?? null)
      setSummary((result as any).summary ?? null)
      setStep("complete")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Resume failed. Please try again.")
      setStep("review")
    } finally {
      setSubmitting(false)
    }
  }

  // ── Reset ─────────────────────────────────────────────────────────────────

  const handleReset = () => {
    setStep("upload")
    setShipmentNumber("")
    setSupplierName("")
    setConsigneeName("")
    setIncoterm("")
    setTransportMode("")
    setShowShipmentDetails(false)
    setFiles({ invoice: null, packing_list: null, freight_manifest: null, certificate_of_origin: null })
    setShipmentId(null)
    setGeneratedShipmentNumber(null)
    setSessionId(null)
    setDiscrepancies([])
    setFinalStatus(null)
    setSummary(null)
    setConfirmations({})
    setError(null)
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────────────────────────────────────

  return (
    <div className="p-8 max-w-3xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-foreground mb-2">Vendor Document Validation</h1>
        <p className="text-muted-foreground">
          Step 2 — Upload and cross-validate vendor documents before transmitting to the clearing agent.
        </p>
      </div>

      {/* Error banner */}
      {error && (
        <Card className="p-4 border-l-4 border-destructive bg-destructive/5 mb-6">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-destructive mt-0.5 flex-shrink-0" />
            <div>
              <p className="font-semibold text-destructive text-sm">Error</p>
              <p className="text-sm text-destructive/80 mt-0.5">{error}</p>
            </div>
          </div>
        </Card>
      )}

      {/* ── Upload ──────────────────────────────────────────────────────────── */}
      {step === "upload" && (
        <div className="space-y-4">
          {/* Optional shipment details toggle */}
          <Card className="overflow-hidden">
            <button
              className="w-full flex items-center justify-between p-4 hover:bg-muted/30 transition-colors text-left"
              onClick={() => setShowShipmentDetails(!showShipmentDetails)}
            >
              <div className="flex items-center gap-2">
                <Settings2 className="w-4 h-4 text-muted-foreground" />
                <span className="text-sm font-medium text-foreground">Shipment Details</span>
                <span className="text-xs text-muted-foreground">(optional)</span>
              </div>
              {showShipmentDetails ? (
                <ChevronUp className="w-4 h-4 text-muted-foreground" />
              ) : (
                <ChevronDown className="w-4 h-4 text-muted-foreground" />
              )}
            </button>

            {showShipmentDetails && (
              <div className="px-4 pb-4 border-t border-border pt-4 grid grid-cols-2 gap-4">
                <div className="col-span-2 md:col-span-1">
                  <Label htmlFor="shipment-number" className="text-xs font-medium text-muted-foreground">
                    Shipment Number
                  </Label>
                  <Input
                    id="shipment-number"
                    value={shipmentNumber}
                    onChange={(e) => setShipmentNumber(e.target.value)}
                    placeholder="Auto-generated if empty"
                    className="mt-1 text-sm"
                  />
                </div>
                <div className="col-span-2 md:col-span-1">
                  <Label htmlFor="incoterm" className="text-xs font-medium text-muted-foreground">
                    Incoterm
                  </Label>
                  <Input
                    id="incoterm"
                    value={incoterm}
                    onChange={(e) => setIncoterm(e.target.value)}
                    placeholder="e.g. CIF, FOB, DDP"
                    className="mt-1 text-sm"
                  />
                </div>
                <div className="col-span-2 md:col-span-1">
                  <Label htmlFor="supplier-name" className="text-xs font-medium text-muted-foreground">
                    Supplier Name
                  </Label>
                  <Input
                    id="supplier-name"
                    value={supplierName}
                    onChange={(e) => setSupplierName(e.target.value)}
                    placeholder="Extracted from invoice if empty"
                    className="mt-1 text-sm"
                  />
                </div>
                <div className="col-span-2 md:col-span-1">
                  <Label htmlFor="transport-mode" className="text-xs font-medium text-muted-foreground">
                    Transport Mode
                  </Label>
                  <Input
                    id="transport-mode"
                    value={transportMode}
                    onChange={(e) => setTransportMode(e.target.value)}
                    placeholder="e.g. Sea, Air, Road"
                    className="mt-1 text-sm"
                  />
                </div>
                <div className="col-span-2">
                  <Label htmlFor="consignee-name" className="text-xs font-medium text-muted-foreground">
                    Consignee Name
                  </Label>
                  <Input
                    id="consignee-name"
                    value={consigneeName}
                    onChange={(e) => setConsigneeName(e.target.value)}
                    placeholder="Extracted from invoice if empty"
                    className="mt-1 text-sm"
                  />
                </div>
              </div>
            )}
          </Card>

          {/* Document slots */}
          <Card className="p-6 space-y-3">
            <h2 className="text-base font-semibold text-foreground mb-2">Documents</h2>
            {DOC_SLOTS.map((slot) => (
              <FileSlot
                key={slot.key}
                slot={slot}
                file={files[slot.key]}
                onSelect={(f) => setFile(slot.key, f)}
                onRemove={() => setFile(slot.key, null)}
              />
            ))}
          </Card>

          <div className="flex justify-end">
            <Button
              onClick={handleValidate}
              disabled={!requiredFilled || submitting}
              className="bg-primary hover:bg-primary/90"
            >
              Validate Documents
            </Button>
          </div>
        </div>
      )}

      {/* ── Processing ───────────────────────────────────────────────────────── */}
      {step === "processing" && (
        <Card className="p-12 text-center">
          <div className="flex justify-center mb-6">
            <div className="p-4 bg-primary/10 rounded-lg">
              <Loader className="w-8 h-8 text-primary animate-spin" />
            </div>
          </div>
          <h2 className="text-2xl font-bold text-foreground mb-2">Extracting & Validating</h2>
          <p className="text-muted-foreground">
            Documents are being extracted and cross-validated. This may take up to 2 minutes...
          </p>
        </Card>
      )}

      {/* ── HITL Review ──────────────────────────────────────────────────────── */}
      {step === "review" && (
        <div className="space-y-4">
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

          <div className="space-y-3">
            {discrepancies.map((disc) => (
              <DiscrepancyCard
                key={disc.id}
                disc={disc}
                confirmed={confirmations[disc.id] ?? null}
                onToggle={(id, val) => setConfirmations((prev) => ({ ...prev, [id]: val }))}
              />
            ))}
          </div>

          <div className="flex justify-between pt-2">
            <Button variant="outline" onClick={() => setStep("upload")}>
              Re-upload Documents
            </Button>
            <Button
              onClick={handleResume}
              disabled={
                submitting ||
                discrepancies
                  .filter((d) => d.severity === "critical")
                  .some((d) => confirmations[d.id] === null)
              }
              className="bg-primary hover:bg-primary/90"
            >
              {submitting ? <Loader className="w-4 h-4 mr-2 animate-spin" /> : null}
              Submit Decisions
            </Button>
          </div>
        </div>
      )}

      {/* ── Complete ──────────────────────────────────────────────────────────── */}
      {step === "complete" && (
        <div className="space-y-4">
          {/* Status banner */}
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
                    ? "Critical discrepancies remain unresolved. Please correct the documents and retry."
                    : "Some discrepancies were found. Review the details below before proceeding."}
                </p>
                {(generatedShipmentNumber || shipmentNumber) && (
                  <p className="text-xs text-muted-foreground mt-1.5">
                    Shipment: <code className="font-mono">{shipmentNumber || generatedShipmentNumber}</code>
                  </p>
                )}
              </div>
            </div>
          </Card>

          {/* Stat cards */}
          {summary && (
            <div className="grid grid-cols-4 gap-3">
              {[
                { label: "Total Checks", value: summary.total_checks ?? 0, color: "text-foreground" },
                { label: "Passed", value: summary.passed_checks ?? 0, color: "text-green-600" },
                { label: "Failed", value: summary.failed_checks ?? 0, color: "text-destructive" },
                { label: "Discrepancies", value: summary.total_discrepancies ?? 0, color: "text-amber-500" },
              ].map(({ label, value, color }) => (
                <Card key={label} className="p-3 text-center">
                  <p className={`text-2xl font-bold ${color}`}>{value}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{label}</p>
                </Card>
              ))}
            </div>
          )}

          {/* Severity breakdown */}
          {summary && (summary.critical > 0 || summary.major > 0 || summary.minor > 0) && (
            <div className="flex gap-3">
              {[
                { label: "Critical", count: summary.critical, bg: "bg-destructive/10", text: "text-destructive" },
                { label: "Major", count: summary.major, bg: "bg-amber-50 dark:bg-amber-900/20", text: "text-amber-600 dark:text-amber-400" },
                { label: "Minor", count: summary.minor, bg: "bg-blue-50 dark:bg-blue-900/20", text: "text-blue-600 dark:text-blue-400" },
              ]
                .filter((s) => s.count > 0)
                .map(({ label, count, bg, text }) => (
                  <span key={label} className={`text-xs font-semibold px-2.5 py-1 rounded-full ${bg} ${text}`}>
                    {count} {label}
                  </span>
                ))}
            </div>
          )}

          {/* Checks breakdown table */}
          {validationResults && validationResults.length > 0 && (() => {
            // Group checks by validator name
            const groups: Record<string, any[]> = {}
            for (const r of validationResults) {
              const key = r.validator_name ?? "other"
              if (!groups[key]) groups[key] = []
              groups[key].push(r)
            }
            const validatorLabel = (name: string) =>
              name.replace(/_validator$/, "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())

            return (
              <Card className="p-0 overflow-hidden">
                <div className="px-4 py-3 border-b border-border flex items-center gap-2">
                  <ClipboardCheck className="w-4 h-4 text-muted-foreground" />
                  <h3 className="font-semibold text-sm text-foreground">
                    Checks Run ({validationResults.length})
                  </h3>
                  <span className="ml-auto text-xs text-muted-foreground">
                    {validationResults.filter((r: any) => r.passed).length} passed ·{" "}
                    {validationResults.filter((r: any) => !r.passed).length} failed
                  </span>
                </div>

                {Object.entries(groups).map(([validatorName, checks]) => (
                  <div key={validatorName} className="border-b border-border last:border-b-0">
                    {/* Validator group header */}
                    <div className="px-4 py-2 bg-muted/30 flex items-center gap-2">
                      <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                        {validatorLabel(validatorName)}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        ({checks.filter((r) => r.passed).length}/{checks.length})
                      </span>
                    </div>

                    <div className="divide-y divide-border">
                      {checks.map((r: any, idx: number) => (
                        <div key={idx} className="px-4 py-3">
                          <div className="flex items-start gap-3">
                            <div className="flex-shrink-0 mt-0.5">
                              {r.passed ? (
                                <CheckCircle className="w-4 h-4 text-green-500" />
                              ) : (
                                <AlertCircle className="w-4 h-4 text-destructive" />
                              )}
                            </div>
                            <div className="flex-1 min-w-0">
                              {/* Field name + document */}
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="text-sm font-semibold text-foreground">
                                  {r.field_name ?? r.field ?? "—"}
                                </span>
                                {r.source_document && (
                                  <span className="text-[10px] font-mono text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                                    {r.source_document}
                                  </span>
                                )}
                              </div>
                              {/* Message */}
                              {r.message && (
                                <p className="text-xs text-muted-foreground mt-1">{r.message}</p>
                              )}
                              {/* Values */}
                              {r.passed && r.source_value !== null && r.source_value !== undefined && (
                                <div className="mt-1.5 flex items-center gap-1.5 text-xs">
                                  <span className="text-muted-foreground">Value:</span>
                                  <code className="font-mono text-foreground bg-muted px-1.5 py-0.5 rounded">
                                    {String(r.source_value)}
                                  </code>
                                  {r.target_value !== null && r.target_value !== undefined && (
                                    <>
                                      <span className="text-muted-foreground">→</span>
                                      <code className="font-mono text-foreground bg-muted px-1.5 py-0.5 rounded">
                                        {String(r.target_value)}
                                      </code>
                                    </>
                                  )}
                                </div>
                              )}
                              {/* Failed: show source vs target comparison */}
                              {!r.passed && (r.source_value !== null || r.target_value !== null) && (
                                <div className="mt-2 grid grid-cols-2 gap-2">
                                  <div className="p-2 bg-card rounded border border-border text-xs">
                                    <p className="text-muted-foreground mb-0.5 text-[10px] uppercase font-semibold">
                                      {r.source_document ?? "Source"}
                                    </p>
                                    <code className="font-mono text-foreground break-all">
                                      {r.source_value !== null && r.source_value !== undefined
                                        ? String(r.source_value)
                                        : "—"}
                                    </code>
                                  </div>
                                  {r.target_value !== null && r.target_value !== undefined && (
                                    <div className="p-2 bg-card rounded border border-border text-xs">
                                      <p className="text-muted-foreground mb-0.5 text-[10px] uppercase font-semibold">
                                        {r.target_document ?? "Target"}
                                      </p>
                                      <code className="font-mono text-foreground break-all">
                                        {String(r.target_value)}
                                      </code>
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                            <span
                              className={`text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded flex-shrink-0 ${
                                r.passed
                                  ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                                  : "bg-destructive/10 text-destructive"
                              }`}
                            >
                              {r.passed ? "PASS" : "FAIL"}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </Card>
            )
          })()}

          {/* Discrepancy list */}
          {discrepancies && discrepancies.length > 0 && (
            <Card className="p-0 overflow-hidden">
              <div className="px-4 py-3 border-b border-border flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-500" />
                <h3 className="font-semibold text-sm text-foreground">Discrepancies ({discrepancies.length})</h3>
              </div>
              <div className="divide-y divide-border">
                {discrepancies.map((d: ValidationDiscrepancy) => (
                  <div key={d.id} className="px-4 py-3 space-y-1.5">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-semibold text-foreground">{d.field}</span>
                      <span
                        className={`text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded ${
                          d.severity === "critical"
                            ? "bg-destructive/10 text-destructive"
                            : d.severity === "major"
                            ? "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
                            : "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
                        }`}
                      >
                        {d.severity}
                      </span>
                      {d.status && (
                        <span className="text-[10px] text-muted-foreground uppercase">{d.status}</span>
                      )}
                    </div>
                    {d.message && (
                      <p className="text-xs text-muted-foreground">{d.message}</p>
                    )}
                    {(d.source_value !== undefined || d.target_value !== undefined) && (
                      <div className="flex gap-4 text-xs mt-1">
                        {d.source_value !== undefined && (
                          <div>
                            <span className="text-muted-foreground">{d.source_document ?? "Source"}: </span>
                            <code className="font-mono text-foreground">{String(d.source_value)}</code>
                          </div>
                        )}
                        {d.target_value !== undefined && (
                          <div>
                            <span className="text-muted-foreground">{d.target_document ?? "Target"}: </span>
                            <code className="font-mono text-foreground">{String(d.target_value)}</code>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Messages from workflow */}
          {summary?.messages && summary.messages.length > 0 && (
            <Card className="p-4">
              <h3 className="font-semibold text-sm text-foreground mb-2">Workflow Notes</h3>
              <ul className="space-y-1">
                {summary.messages.map((msg: string, i: number) => (
                  <li key={i} className="text-xs text-muted-foreground flex gap-2">
                    <span className="text-muted-foreground/50">•</span>
                    <span>{msg}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          <Button variant="outline" onClick={handleReset} className="w-full">
            New Validation
          </Button>
        </div>
      )}
    </div>
  )
}

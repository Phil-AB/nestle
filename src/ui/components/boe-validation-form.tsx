"use client"

import { useState, useEffect, useRef } from "react"
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
  FileSearch,
  RefreshCw,
} from "lucide-react"
import { useSearchParams } from "next/navigation"
import { apiClient, type ValidationDiscrepancy, type BOEValidationResponse } from "@/lib/api-client"

// ─── Shipment type ────────────────────────────────────────────────────────────

interface ShipmentOption {
  shipment_id: string
  shipment_number: string
  supplier_name?: string
  consignee_name?: string
  status: string
  vendor_docs_count: number
  created_at?: string
}

// ─── Discrepancy Review Card ──────────────────────────────────────────────────

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

  const fieldName = (disc as any).field_name ?? disc.field ?? "—"
  const message = (disc as any).message ?? disc.description

  return (
    <div className={`rounded-lg border p-4 ${severityClass}`}>
      <div className="flex items-start gap-3 cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <AlertTriangle
          className={`w-4 h-4 mt-0.5 flex-shrink-0 ${
            disc.severity === "critical" ? "text-destructive" : "text-amber-500"
          }`}
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-sm text-foreground">{fieldName}</span>
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
          {message && <p className="text-xs text-muted-foreground mt-0.5">{message}</p>}
        </div>
        {expanded ? (
          <ChevronUp className="w-4 h-4 text-muted-foreground flex-shrink-0" />
        ) : (
          <ChevronDown className="w-4 h-4 text-muted-foreground flex-shrink-0" />
        )}
      </div>

      {expanded && (
        <div className="mt-3 pl-7 space-y-3">
          {/* Source vs Target values */}
          {((disc as any).source_value !== undefined || (disc as any).target_value !== undefined) && (
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="p-2 bg-card rounded border border-border">
                <p className="text-muted-foreground mb-0.5 text-[10px] uppercase font-semibold">
                  {disc.source_document ?? "BOE"}
                </p>
                <code className="font-mono text-foreground break-all">
                  {String((disc as any).source_value ?? "—")}
                </code>
              </div>
              <div className="p-2 bg-card rounded border border-border">
                <p className="text-muted-foreground mb-0.5 text-[10px] uppercase font-semibold">
                  {disc.target_document ?? "Vendor Docs"}
                </p>
                <code className="font-mono text-foreground break-all">
                  {typeof (disc as any).target_value === "object" && (disc as any).target_value !== null
                    ? Object.entries((disc as any).target_value)
                        .map(([doc, val]) => `${doc}: ${val}`)
                        .join(", ")
                    : String((disc as any).target_value ?? "—")}
                </code>
              </div>
            </div>
          )}

          {/* Accept / Reject */}
          <div className="flex gap-2">
            <Button
              size="sm"
              variant={confirmed === true ? "default" : "outline"}
              className={`text-xs flex-1 ${confirmed === true ? "bg-green-600 hover:bg-green-700 text-white" : ""}`}
              onClick={() => onToggle(disc.id, true)}
            >
              <CheckCircle className="w-3 h-3 mr-1.5" />
              Accept
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

export default function BOEValidationForm() {
  const searchParams = useSearchParams()
  const prefilledShipmentId = searchParams.get("shipment_id") ?? ""

  const [step, setStep] = useState<Step>("upload")

  // Shipment selector
  const [shipments, setShipments] = useState<ShipmentOption[]>([])
  const [shipmentsLoading, setShipmentsLoading] = useState(false)
  const [shipmentsError, setShipmentsError] = useState<string | null>(null)
  const [selectedShipment, setSelectedShipment] = useState<ShipmentOption | null>(null)
  const [manualId, setManualId] = useState(prefilledShipmentId)

  // Inputs
  const [shipmentId, setShipmentId] = useState("")
  const [boeFile, setBoeFile] = useState<File | null>(null)

  // Results
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [discrepancies, setDiscrepancies] = useState<ValidationDiscrepancy[]>([])
  const [validationResults, setValidationResults] = useState<any[]>([])
  const [finalStatus, setFinalStatus] = useState<string | null>(null)
  const [summary, setSummary] = useState<Record<string, any> | null>(null)
  const [confirmations, setConfirmations] = useState<Record<string, boolean | null>>({})

  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const elapsedRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (submitting) {
      setElapsed(0)
      elapsedRef.current = setInterval(() => setElapsed((s) => s + 1), 1000)
    } else {
      if (elapsedRef.current) clearInterval(elapsedRef.current)
    }
    return () => { if (elapsedRef.current) clearInterval(elapsedRef.current) }
  }, [submitting])

  // Derive active shipment ID from selection or manual input
  const activeShipmentId = selectedShipment?.shipment_id ?? manualId.trim()

  const canSubmit = activeShipmentId.length > 0 && boeFile !== null

  // ── Fetch shipments on mount ──────────────────────────────────────────────

  const fetchShipments = async () => {
    setShipmentsLoading(true)
    setShipmentsError(null)
    try {
      const data = await apiClient.listShipments(50)
      setShipments(data.shipments)
      // Auto-select shipment if prefilled from vendor validation deep link
      if (prefilledShipmentId) {
        const match = data.shipments.find((s) => s.shipment_id === prefilledShipmentId)
        if (match) {
          setSelectedShipment(match)
          setManualId("")
        }
      }
    } catch (e) {
      setShipmentsError("Could not load shipments.")
    } finally {
      setShipmentsLoading(false)
    }
  }

  useEffect(() => { fetchShipments() }, [])

  // ── Submit ────────────────────────────────────────────────────────────────

  const handleValidate = async () => {
    setError(null)
    setSubmitting(true)
    setStep("processing")

    try {
      const result: BOEValidationResponse = await apiClient.validateBOE(
        activeShipmentId,
        boeFile!
      )

      const discs = result.discrepancies ?? []
      const vResults = (result as any).validation_results ?? []

      if (result.workflow_status === "awaiting_user" && discs.length > 0) {
        setSessionId(result.session_id ?? null)
        setDiscrepancies(discs)
        setValidationResults(vResults)
        setSummary(result.summary ?? null)
        const initial: Record<string, boolean | null> = {}
        discs.forEach((d) => { initial[d.id] = null })
        setConfirmations(initial)
        setStep("review")
      } else {
        setFinalStatus(result.final_status ?? null)
        setSummary(result.summary ?? null)
        setDiscrepancies(discs)
        setValidationResults(vResults)
        setStep("complete")
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "BOE validation failed. Please try again.")
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
      setDiscrepancies((result as any).discrepancies ?? discrepancies)
      setValidationResults((result as any).validation_results ?? validationResults)
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
    setSelectedShipment(null)
    setManualId("")
    setShipmentId("")
    setBoeFile(null)
    setSessionId(null)
    setDiscrepancies([])
    setValidationResults([])
    setFinalStatus(null)
    setSummary(null)
    setConfirmations({})
    setError(null)
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  const validatorLabel = (name: string) =>
    name.replace(/_validator$/, "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())

  // ─────────────────────────────────────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────────────────────────────────────

  return (
    <div className="p-8 max-w-3xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-foreground mb-2">BOE Validation</h1>
        <p className="text-muted-foreground">
          Step 6 — Cross-verify the Bill of Entry against stored vendor documents before customs filing.
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

      {/* ── Upload ────────────────────────────────────────────────────────────── */}
      {step === "upload" && (
        <div className="space-y-4">
          {/* Shipment selector */}
          <Card className="p-5 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <Label className="text-sm font-semibold text-foreground">
                  Shipment <span className="text-destructive">*</span>
                </Label>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Select a shipment from Step 2, or enter an ID manually.
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={fetchShipments}
                disabled={shipmentsLoading}
                className="text-xs text-muted-foreground"
              >
                <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${shipmentsLoading ? "animate-spin" : ""}`} />
                Refresh
              </Button>
            </div>

            {shipmentsError && (
              <p className="text-xs text-destructive">{shipmentsError}</p>
            )}

            {/* Shipment list */}
            {shipmentsLoading ? (
              <div className="flex items-center gap-2 py-4 text-xs text-muted-foreground">
                <Loader className="w-4 h-4 animate-spin" />
                Loading shipments...
              </div>
            ) : shipments.length > 0 ? (
              <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                {shipments.map((s) => {
                  const isSelected = selectedShipment?.shipment_id === s.shipment_id
                  const hasVendorDocs = s.vendor_docs_count > 0
                  return (
                    <button
                      key={s.shipment_id}
                      onClick={() => {
                        setSelectedShipment(isSelected ? null : s)
                        setManualId("")
                      }}
                      className={`w-full text-left p-3 rounded-lg border transition-colors ${
                        isSelected
                          ? "border-primary bg-primary/5"
                          : "border-border bg-muted/20 hover:bg-muted/40"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-sm font-semibold text-foreground truncate">
                              {s.shipment_number}
                            </span>
                            <span
                              className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${
                                hasVendorDocs
                                  ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                                  : "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
                              }`}
                            >
                              {hasVendorDocs ? `${s.vendor_docs_count} docs` : "no docs"}
                            </span>
                            {isSelected && (
                              <CheckCircle className="w-3.5 h-3.5 text-primary flex-shrink-0" />
                            )}
                          </div>
                          {(s.supplier_name || s.consignee_name) && (
                            <p className="text-xs text-muted-foreground mt-0.5 truncate">
                              {[s.supplier_name, s.consignee_name].filter(Boolean).join(" → ")}
                            </p>
                          )}
                        </div>
                        <span className="text-[10px] text-muted-foreground flex-shrink-0 mt-0.5">
                          {s.created_at ? new Date(s.created_at).toLocaleDateString() : ""}
                        </span>
                      </div>
                      <p className="text-[10px] font-mono text-muted-foreground/60 mt-1 truncate">
                        {s.shipment_id}
                      </p>
                    </button>
                  )
                })}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground py-2">No shipments found.</p>
            )}

            {/* Divider */}
            <div className="flex items-center gap-3">
              <div className="flex-1 h-px bg-border" />
              <span className="text-xs text-muted-foreground">or enter manually</span>
              <div className="flex-1 h-px bg-border" />
            </div>

            {/* Manual ID input */}
            <div>
              <Input
                value={manualId}
                onChange={(e) => {
                  setManualId(e.target.value)
                  if (e.target.value) setSelectedShipment(null)
                }}
                placeholder="Paste shipment ID..."
                className="font-mono text-sm"
                disabled={!!selectedShipment}
              />
            </div>

            {/* Active selection indicator */}
            {activeShipmentId && (
              <div className="flex items-center gap-2 p-2 bg-primary/5 border border-primary/20 rounded-lg">
                <CheckCircle className="w-3.5 h-3.5 text-primary flex-shrink-0" />
                <code className="text-xs font-mono text-foreground truncate">{activeShipmentId}</code>
              </div>
            )}
          </Card>

          {/* BOE upload */}
          <Card className="p-5">
            <h2 className="text-sm font-semibold text-foreground mb-1">
              Bill of Entry <span className="text-destructive">*</span>
            </h2>
            <p className="text-xs text-muted-foreground mb-4">
              The draft BOE from the clearing agent (GRA Ghana form, PDF)
            </p>

            {boeFile ? (
              <div className="flex items-center gap-3 p-3 bg-primary/5 border border-primary/20 rounded-lg">
                <FileUp className="w-4 h-4 text-primary flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-foreground truncate">{boeFile.name}</p>
                  <p className="text-xs text-muted-foreground">{(boeFile.size / 1024).toFixed(1)} KB</p>
                </div>
                <button
                  onClick={() => setBoeFile(null)}
                  className="text-muted-foreground hover:text-destructive transition-colors flex-shrink-0"
                  aria-label="Remove file"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <label
                htmlFor="boe-file-input"
                className="flex flex-col items-center justify-center gap-2 p-8 border-2 border-dashed border-border rounded-lg cursor-pointer hover:bg-muted/30 hover:border-primary/40 transition-colors"
              >
                <FileSearch className="w-8 h-8 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">
                  Click to select BOE PDF
                </span>
                <span className="text-xs text-muted-foreground/60">.pdf supported</span>
                <input
                  id="boe-file-input"
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png,.tiff"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0]
                    if (f) setBoeFile(f)
                    e.target.value = ""
                  }}
                />
              </label>
            )}
          </Card>

          <div className="flex justify-end">
            <Button
              onClick={handleValidate}
              disabled={!canSubmit || submitting}
              className="bg-primary hover:bg-primary/90"
            >
              <FileSearch className="w-4 h-4 mr-2" />
              Validate BOE
            </Button>
          </div>
        </div>
      )}

      {/* ── Processing ──────────────────────────────────────────────────────────── */}
      {step === "processing" && (
        <Card className="p-12 text-center">
          <div className="flex justify-center mb-6">
            <div className="p-4 bg-primary/10 rounded-lg">
              <Loader className="w-8 h-8 text-primary animate-spin" />
            </div>
          </div>
          <h2 className="text-2xl font-bold text-foreground mb-2">Extracting & Cross-Verifying</h2>
          <p className="text-muted-foreground">
            AI is extracting the BOE and cross-checking against stored vendor documents. This typically takes 3–5 minutes.
          </p>
          <p className="text-sm text-muted-foreground mt-3 font-mono">
            {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, "0")} elapsed — please keep this tab open
          </p>
        </Card>
      )}

      {/* ── HITL Review ─────────────────────────────────────────────────────────── */}
      {step === "review" && (
        <div className="space-y-4">
          {/* Summary bar */}
          {summary && (
            <div className="grid grid-cols-4 gap-3">
              {[
                { label: "Total Checks", value: summary.total_checks ?? 0, color: "text-foreground" },
                { label: "Passed", value: summary.passed_checks ?? 0, color: "text-green-600" },
                { label: "Failed", value: summary.failed_checks ?? 0, color: "text-destructive" },
                { label: "Discrepancies", value: summary.total_discrepancies ?? discrepancies.length, color: "text-amber-500" },
              ].map(({ label, value, color }) => (
                <Card key={label} className="p-3 text-center">
                  <p className={`text-2xl font-bold ${color}`}>{value}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{label}</p>
                </Card>
              ))}
            </div>
          )}

          <Card className="p-5 border-l-4 border-amber-400 bg-amber-50/30 dark:bg-amber-900/10">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-500 mt-0.5 flex-shrink-0" />
              <div>
                <p className="font-semibold text-foreground">Discrepancies Detected</p>
                <p className="text-sm text-muted-foreground mt-0.5">
                  {discrepancies.length} discrepanc{discrepancies.length !== 1 ? "ies" : "y"} found between the BOE
                  and vendor documents. Review each one and accept or reject before proceeding.
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
              Re-upload BOE
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
              {submitting && <Loader className="w-4 h-4 mr-2 animate-spin" />}
              Submit Decisions
            </Button>
          </div>
        </div>
      )}

      {/* ── Complete ────────────────────────────────────────────────────────────── */}
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
                    ? "BOE Validated — Cleared for Filing"
                    : finalStatus === "failed"
                    ? "BOE Validation Failed"
                    : "BOE Requires Attention"}
                </h2>
                <p className="text-muted-foreground text-sm mt-0.5">
                  {finalStatus === "passed"
                    ? "The BOE is consistent with all vendor documents. You may proceed to customs filing."
                    : finalStatus === "failed"
                    ? "Critical discrepancies remain. The BOE must be corrected before filing."
                    : "Some discrepancies were found. Review the details below before filing."}
                </p>
                <p className="text-xs text-muted-foreground mt-1.5 font-mono">
                  {selectedShipment?.shipment_number ?? activeShipmentId}
                </p>
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

          {/* Severity badges */}
          {summary && (summary.critical > 0 || summary.major > 0 || summary.minor > 0) && (
            <div className="flex gap-3 flex-wrap">
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

          {/* Checks breakdown */}
          {validationResults.length > 0 && (() => {
            const groups: Record<string, any[]> = {}
            for (const r of validationResults) {
              const key = r.validator_name ?? "other"
              if (!groups[key]) groups[key] = []
              groups[key].push(r)
            }

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
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="text-sm font-semibold text-foreground">
                                  {r.field_name ?? r.field ?? "—"}
                                </span>
                                {r.source_document && (
                                  <span className="text-[10px] font-mono text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                                    {r.source_document}
                                  </span>
                                )}
                                {r.target_document && (
                                  <span className="text-[10px] font-mono text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                                    → {r.target_document}
                                  </span>
                                )}
                              </div>
                              {r.message && (
                                <p className="text-xs text-muted-foreground mt-1">{r.message}</p>
                              )}
                              {r.passed && r.source_value !== null && r.source_value !== undefined && (
                                <div className="mt-1.5 flex items-center gap-1.5 text-xs flex-wrap">
                                  <span className="text-muted-foreground">Value:</span>
                                  <code className="font-mono text-foreground bg-muted px-1.5 py-0.5 rounded">
                                    {String(r.source_value)}
                                  </code>
                                  {r.target_value !== null && r.target_value !== undefined && (
                                    <>
                                      <span className="text-muted-foreground">→</span>
                                      <code className="font-mono text-foreground bg-muted px-1.5 py-0.5 rounded">
                                        {typeof r.target_value === "object"
                                          ? JSON.stringify(r.target_value)
                                          : String(r.target_value)}
                                      </code>
                                    </>
                                  )}
                                </div>
                              )}
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
                                        {typeof r.target_value === "object"
                                          ? JSON.stringify(r.target_value)
                                          : String(r.target_value)}
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

          {/* Remaining discrepancies (post-HITL) */}
          {discrepancies.length > 0 && (
            <Card className="p-0 overflow-hidden">
              <div className="px-4 py-3 border-b border-border flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-500" />
                <h3 className="font-semibold text-sm text-foreground">
                  Discrepancies ({discrepancies.length})
                </h3>
              </div>
              <div className="divide-y divide-border">
                {discrepancies.map((d: any) => (
                  <div key={d.id} className="px-4 py-3 space-y-1.5">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-semibold text-foreground">
                        {d.field_name ?? d.field ?? "—"}
                      </span>
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
                      {confirmations[d.id] === true && (
                        <span className="text-[10px] text-green-600 font-semibold uppercase">Accepted</span>
                      )}
                      {confirmations[d.id] === false && (
                        <span className="text-[10px] text-destructive font-semibold uppercase">Rejected</span>
                      )}
                    </div>
                    {(d.message ?? d.description) && (
                      <p className="text-xs text-muted-foreground">{d.message ?? d.description}</p>
                    )}
                    {(d.source_value !== undefined || d.target_value !== undefined) && (
                      <div className="flex gap-4 text-xs mt-1 flex-wrap">
                        {d.source_value !== undefined && (
                          <div>
                            <span className="text-muted-foreground">{d.source_document ?? "BOE"}: </span>
                            <code className="font-mono text-foreground">{String(d.source_value)}</code>
                          </div>
                        )}
                        {d.target_value !== undefined && (
                          <div>
                            <span className="text-muted-foreground">{d.target_document ?? "Vendor Docs"}: </span>
                            <code className="font-mono text-foreground">
                              {typeof d.target_value === "object"
                                ? Object.entries(d.target_value).map(([doc, val]) => `${doc}: ${val}`).join(", ")
                                : String(d.target_value)}
                            </code>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Workflow messages */}
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
            New BOE Validation
          </Button>
        </div>
      )}
    </div>
  )
}

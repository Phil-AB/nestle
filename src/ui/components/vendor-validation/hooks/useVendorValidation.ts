"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import {
  apiClient,
  type VendorValidationResponse,
  type ExtractedDocumentMeta,
  type ValidationDiscrepancy,
  type BundleValidationResponse,
} from "@/lib/api-client"
import { autoShipmentNumber } from "../lib/utils"
import type { Step, DocFiles, FieldEdits, LineItemEdits, TableEdits } from "../lib/types"

export function useVendorValidation() {
  const [step, setStep] = useState<Step>("upload")

  // Optional shipment details
  const [showShipmentDetails, setShowShipmentDetails] = useState(false)
  const [shipmentNumber, setShipmentNumber] = useState("")
  const [supplierName, setSupplierName] = useState("")
  const [consigneeName, setConsigneeName] = useState("")
  const [incoterm, setIncoterm] = useState("")
  const [transportMode, setTransportMode] = useState("")

  // Upload mode
  const [uploadMode, setUploadMode] = useState<"separate" | "bundle">("separate")
  const [bundleFile, setBundleFile] = useState<File | null>(null)

  // Files (separate mode)
  const [files, setFiles] = useState<DocFiles>({
    invoice: null,
    packing_list: null,
    bill_of_lading: null,
    freight_manifest: null,
    certificate_of_origin: null,
  })

  // Extraction results (field review step)
  const [extractedDocuments, setExtractedDocuments] = useState<Record<string, ExtractedDocumentMeta> | null>(null)
  const [fieldEdits, setFieldEdits] = useState<FieldEdits>({})
  const [lineItemEdits, setLineItemEdits] = useState<LineItemEdits>({})
  const [tableEdits, setTableEdits] = useState<TableEdits>({})
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  // Validation results (stored from API — shown after field review)
  const [pendingResult, setPendingResult] = useState<VendorValidationResponse | null>(null)

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
  const [elapsed, setElapsed] = useState(0)
  const elapsedRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Document viewer tab — shared across review + complete steps
  const [reviewView, setReviewView] = useState<"review" | "documents">("review")
  const [completeView, setCompleteView] = useState<"results" | "documents">("results")
  const [activeDocKey, setActiveDocKey] = useState<string | null>(null)
  // Blob URLs for uploaded files — created on demand, revoked on unmount
  const blobUrlsRef = useRef<Record<string, string>>({})
  const getDocBlobUrl = useCallback((key: string): string | null => {
    const file = files[key as keyof typeof files]
    if (!file) return null
    if (!blobUrlsRef.current[key]) {
      blobUrlsRef.current[key] = URL.createObjectURL(file)
    }
    return blobUrlsRef.current[key]
  }, [files])
  useEffect(() => {
    const urls = blobUrlsRef.current
    return () => { Object.values(urls).forEach(URL.revokeObjectURL) }
  }, [])

  useEffect(() => {
    if (submitting) {
      setElapsed(0)
      elapsedRef.current = setInterval(() => setElapsed((s) => s + 1), 1000)
    } else {
      if (elapsedRef.current) clearInterval(elapsedRef.current)
    }
    return () => { if (elapsedRef.current) clearInterval(elapsedRef.current) }
  }, [submitting])

  // ── Helpers ───────────────────────────────────────────────────────────────

  const setFile = (key: keyof DocFiles, file: File | null) =>
    setFiles((prev) => ({ ...prev, [key]: file }))

  const requiredFilled = files.invoice !== null && files.packing_list !== null
  const bundleRequiredFilled = bundleFile !== null

  const handleFieldChange = useCallback((docType: string, key: string, val: string) => {
    setFieldEdits((prev) => ({
      ...prev,
      [docType]: { ...(prev[docType] ?? {}), [key]: val },
    }))
  }, [])

  const handleLineItemChange = useCallback((docType: string, rowIndex: number, column: string, val: string) => {
    setLineItemEdits((prev) => ({
      ...prev,
      [docType]: {
        ...(prev[docType] ?? {}),
        [rowIndex]: { ...(prev[docType]?.[rowIndex] ?? {}), [column]: val },
      },
    }))
  }, [])

  const handleTableCellChange = useCallback((
    docType: string, tblIdx: number, rowIdx: number, colIdx: number, val: string
  ) => {
    setTableEdits((prev) => ({
      ...prev,
      [docType]: {
        ...(prev[docType] ?? {}),
        [tblIdx]: {
          ...(prev[docType]?.[tblIdx] ?? {}),
          [rowIdx]: { ...(prev[docType]?.[tblIdx]?.[rowIdx] ?? {}), [colIdx]: val },
        },
      },
    }))
  }, [])

  /** Apply the pending API result to component state and move to review/complete */
  const applyResult = (result: VendorValidationResponse) => {
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
  }

  // ── Submit ────────────────────────────────────────────────────────────────

  const handleValidate = async () => {
    setError(null)
    setSubmitting(true)
    setStep("processing")

    try {
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

      const result: VendorValidationResponse = await apiClient.validateVendorDocs(
        shipment.shipment_id,
        {
          invoice: files.invoice ?? undefined,
          packing_list: files.packing_list ?? undefined,
          bill_of_lading: files.bill_of_lading ?? undefined,
          freight_manifest: files.freight_manifest ?? undefined,
          certificate_of_origin: files.certificate_of_origin ?? undefined,
        }
      )

      // Store full result for after the field review step
      setPendingResult(result)

      // If API returned extracted documents, show field review step
      if (result.extracted_documents && Object.keys(result.extracted_documents).length > 0) {
        setExtractedDocuments(result.extracted_documents)
        setFieldEdits({})
        setLineItemEdits({})
        setTableEdits({})
        setStep("field_review")
      } else {
        // No extracted documents returned — skip field review
        applyResult(result)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Validation failed. Please try again.")
      setStep("upload")
    } finally {
      setSubmitting(false)
    }
  }

  // ── Bundle Submit ─────────────────────────────────────────────────────────

  const handleBundleValidate = async () => {
    if (!bundleFile) return
    setError(null)
    setSubmitting(true)
    setStep("processing")

    try {
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

      const result: BundleValidationResponse = await apiClient.validateBundle(
        shipment.shipment_id,
        bundleFile
      )

      setPendingResult(result as any)

      if (result.extracted_documents && Object.keys(result.extracted_documents).length > 0) {
        setExtractedDocuments(result.extracted_documents)
        setFieldEdits({})
        setLineItemEdits({})
        setTableEdits({})
        setStep("field_review")
      } else {
        applyResult(result as any)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Bundle validation failed. Please try again.")
      setStep("upload")
    } finally {
      setSubmitting(false)
    }
  }

  // ── Field Review Save ─────────────────────────────────────────────────────

  const handleSaveFields = async () => {
    if (!extractedDocuments) return
    setSaving(true)
    setSaveError(null)

    try {
      // Collect all doc types that have any edits
      const docTypes = new Set([
        ...Object.keys(fieldEdits),
        ...Object.keys(lineItemEdits),
        ...Object.keys(tableEdits),
      ])

      const savePromises = Array.from(docTypes)
        .filter((docType) => {
          const hasFieldEdits = Object.keys(fieldEdits[docType] ?? {}).length > 0
          const hasItemEdits = Object.keys(lineItemEdits[docType] ?? {}).length > 0
          const hasTableEdits = Object.keys(tableEdits[docType] ?? {}).length > 0
          return hasFieldEdits || hasItemEdits || hasTableEdits
        })
        .map((docType) => {
          const docId = extractedDocuments[docType]?.document_id
          if (!docId) return Promise.resolve()

          // Flatten item edits to [{row_index, column, value}]
          const itemUpdates = Object.entries(lineItemEdits[docType] ?? {}).flatMap(
            ([rowIdx, cols]) =>
              Object.entries(cols).map(([column, value]) => ({
                row_index: Number(rowIdx),
                column,
                value,
              }))
          )

          // Flatten table edits to [{table_index, row_index, col_index, value}]
          const tblUpdates = Object.entries(tableEdits[docType] ?? {}).flatMap(
            ([tblIdx, rows]) =>
              Object.entries(rows).flatMap(([rowIdx, cols]) =>
                Object.entries(cols).map(([colIdx, value]) => ({
                  table_index: Number(tblIdx),
                  row_index: Number(rowIdx),
                  col_index: Number(colIdx),
                  value,
                }))
              )
          )

          return apiClient.updateDocumentFields(
            docId,
            fieldEdits[docType] ?? {},
            {
              updated_by: "field_review",
              update_reason: "User reviewed and corrected extracted fields before validation",
            },
            itemUpdates.length > 0 ? itemUpdates : undefined,
            tblUpdates.length > 0 ? tblUpdates : undefined
          )
        })

      await Promise.all(savePromises)

      // Proceed to show validation results
      if (pendingResult) {
        applyResult(pendingResult)
      }
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Failed to save field edits. Please try again.")
    } finally {
      setSaving(false)
    }
  }

  /** Skip editing and proceed directly to validation results */
  const handleSkipFieldReview = () => {
    if (pendingResult) applyResult(pendingResult)
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
    setFiles({ invoice: null, packing_list: null, bill_of_lading: null, freight_manifest: null, certificate_of_origin: null })
    setUploadMode("separate")
    setBundleFile(null)
    setShipmentId(null)
    setGeneratedShipmentNumber(null)
    setSessionId(null)
    setDiscrepancies([])
    setFinalStatus(null)
    setSummary(null)
    setConfirmations({})
    setError(null)
    setExtractedDocuments(null)
    setFieldEdits({})
    setLineItemEdits({})
    setTableEdits({})
    setPendingResult(null)
    setSaveError(null)
    setReviewView("review")
    setCompleteView("results")
    setActiveDocKey(null)
  }

  return {
    // State
    step,
    uploadMode, setUploadMode,
    bundleFile, setBundleFile,
    showShipmentDetails, setShowShipmentDetails,
    shipmentNumber, setShipmentNumber,
    supplierName, setSupplierName,
    consigneeName, setConsigneeName,
    incoterm, setIncoterm,
    transportMode, setTransportMode,
    files,
    setFile,
    extractedDocuments,
    fieldEdits,
    lineItemEdits,
    tableEdits,
    saving,
    saveError,
    shipmentId,
    generatedShipmentNumber,
    sessionId,
    discrepancies,
    validationResults,
    finalStatus,
    summary,
    confirmations,
    error,
    submitting,
    elapsed,
    reviewView, setReviewView,
    completeView, setCompleteView,
    activeDocKey, setActiveDocKey,

    // Derived
    requiredFilled,
    bundleRequiredFilled,

    // Functions
    getDocBlobUrl,
    handleFieldChange,
    handleLineItemChange,
    handleTableCellChange,
    handleValidate,
    handleBundleValidate,
    handleSaveFields,
    handleSkipFieldReview,
    handleResume,
    handleReset,

    // Setters for step navigation
    setStep,
    setConfirmations,
  }
}

"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import {
  apiClient,
  type BOEValidationResponse,
  type ExtractedDocumentMeta,
  type ValidationDiscrepancy,
} from "@/lib/api-client"
import type { Step, Shipment } from "../lib/types"

export function useBOEValidation() {
  const [step, setStep] = useState<Step>("select")

  // Shipment + file
  const [selectedShipment, setSelectedShipment] = useState<Shipment | null>(null)
  const [boeFile, setBoeFile] = useState<File | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Stashed full API result (used after field review)
  const [pendingResult, setPendingResult] = useState<BOEValidationResponse | null>(null)

  // Extracted BOE fields + edits
  const [extractedBOE, setExtractedBOE] = useState<ExtractedDocumentMeta | null>(null)
  const [fieldEdits, setFieldEdits] = useState<Record<string, string>>({})
  const [lineItemEdits, setLineItemEdits] = useState<Record<number, Record<string, string>>>({})
  const [blockEdits, setBlockEdits] = useState<Record<number, Record<string, string>>>({})
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  // Validation state
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [discrepancies, setDiscrepancies] = useState<ValidationDiscrepancy[]>([])
  const [confirmations, setConfirmations] = useState<Record<string, boolean | null>>({})
  const [validationResults, setValidationResults] = useState<any[]>([])
  const [finalStatus, setFinalStatus] = useState<string | null>(null)
  const [summary, setSummary] = useState<Record<string, any> | null>(null)

  // UI
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const elapsedRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Document viewer tabs
  const [fieldReviewView, setFieldReviewView] = useState<"fields" | "document">("fields")
  const [resultsView, setResultsView] = useState<"results" | "document">("results")

  // Blob URL for the uploaded BOE file
  const boeBlobUrlRef = useRef<string | null>(null)
  const getBOEBlobUrl = useCallback((): string | null => {
    if (!boeFile) return null
    if (!boeBlobUrlRef.current) {
      boeBlobUrlRef.current = URL.createObjectURL(boeFile)
    }
    return boeBlobUrlRef.current
  }, [boeFile])
  useEffect(() => {
    return () => {
      if (boeBlobUrlRef.current) {
        URL.revokeObjectURL(boeBlobUrlRef.current)
        boeBlobUrlRef.current = null
      }
    }
  }, [])

  useEffect(() => {
    if (submitting) {
      setElapsed(0)
      elapsedRef.current = setInterval(() => setElapsed((s) => s + 1), 1000)
    } else {
      if (elapsedRef.current) clearInterval(elapsedRef.current)
    }
    return () => {
      if (elapsedRef.current) clearInterval(elapsedRef.current)
    }
  }, [submitting])

  const handleFieldChange = useCallback((key: string, val: string) => {
    setFieldEdits((prev) => ({ ...prev, [key]: val }))
  }, [])

  const handleLineItemChange = useCallback((rowIndex: number, column: string, val: string) => {
    setLineItemEdits((prev) => ({
      ...prev,
      [rowIndex]: { ...(prev[rowIndex] ?? {}), [column]: val },
    }))
  }, [])

  const handleBlockCellChange = useCallback((tableIdx: number, rowIdx: number, colIdx: number, val: string) => {
    setBlockEdits((prev) => ({
      ...prev,
      [tableIdx]: { ...(prev[tableIdx] ?? {}), [`${rowIdx},${colIdx}`]: val },
    }))
  }, [])

  // ── Apply API result to state ─────────────────────────────────────────────

  const applyResult = useCallback((res: BOEValidationResponse) => {
    setValidationResults(res.validation_results ?? [])
    setSummary(res.summary ?? null)
    setFinalStatus(res.final_status ?? null)
    setDiscrepancies(res.discrepancies ?? [])
    setSessionId(res.session_id ?? null)

    const hitlDiscs = [...(res.discrepancies ?? []), ...(res.critical_discrepancies ?? [])].filter(
      (d) => d.severity === "critical" || d.severity === "major"
    )

    if (hitlDiscs.length > 0) {
      const initial: Record<string, boolean | null> = {}
      hitlDiscs.forEach((d) => {
        initial[d.id] = null
      })
      setConfirmations(initial)
    }

    setStep("results")
  }, [])

  // ── Submit ────────────────────────────────────────────────────────────────

  const handleValidate = async () => {
    if (!selectedShipment || !boeFile) return
    setError(null)
    setSubmitting(true)
    setStep("processing")

    try {
      const res = await apiClient.validateBOE(selectedShipment.shipment_id, boeFile)

      if (res.extracted_boe && Object.keys(res.extracted_boe.fields ?? {}).length > 0) {
        setExtractedBOE(res.extracted_boe)
        setFieldEdits({})
        setLineItemEdits({})
        setBlockEdits({})
        setPendingResult(res)
        setStep("field_review")
      } else {
        applyResult(res)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "BOE validation failed. Please try again.")
      setStep("select")
    } finally {
      setSubmitting(false)
    }
  }

  // ── Save field edits ──────────────────────────────────────────────────────

  const handleSaveFields = async () => {
    if (!extractedBOE) return
    setSaving(true)
    setSaveError(null)

    try {
      const hasFieldEdits = Object.keys(fieldEdits).length > 0
      const hasItemEdits = Object.keys(lineItemEdits).length > 0
      const hasBlockEdits = Object.keys(blockEdits).length > 0

      if ((hasFieldEdits || hasItemEdits || hasBlockEdits) && extractedBOE.document_id) {
        const itemUpdates = Object.entries(lineItemEdits).flatMap(([rowIdx, cols]) =>
          Object.entries(cols).map(([column, value]) => ({
            row_index: Number(rowIdx),
            column,
            value,
          }))
        )

        const updatedBlocks = hasBlockEdits && extractedBOE.blocks
          ? extractedBOE.blocks.map((block, ti) => {
              const tableEdits = blockEdits[ti]
              if (!tableEdits || block.type !== "Table") return block
              const tbl = { ...block.content }
              const rows = (tbl.rows ?? tbl.data ?? []).map((row: any[], ri: number) => {
                const arr = Array.isArray(row) ? [...row] : [row]
                Object.entries(tableEdits).forEach(([key, val]) => {
                  const [r, c] = key.split(",").map(Number)
                  if (r === ri && c < arr.length) arr[c] = val
                })
                return arr
              })
              return { ...block, content: { ...tbl, rows } }
            })
          : extractedBOE.blocks

        await apiClient.updateDocumentFields(
          extractedBOE.document_id,
          fieldEdits,
          {
            updated_by: "field_review",
            update_reason: "User reviewed and corrected extracted BOE fields",
            blocks: updatedBlocks,
          },
          itemUpdates.length > 0 ? itemUpdates : undefined
        )
      }
      if (pendingResult) applyResult(pendingResult)
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Failed to save edits. Please try again.")
    } finally {
      setSaving(false)
    }
  }

  // ── HITL Resume ───────────────────────────────────────────────────────────

  const handleResume = async () => {
    if (!sessionId) {
      setStep("complete")
      return
    }
    setError(null)
    setSubmitting(true)

    try {
      const payload = Object.entries(confirmations)
        .filter(([, v]) => v !== null)
        .map(([id, confirmed]) => ({ discrepancy_id: id, confirmed: confirmed as boolean }))

      const res = await apiClient.resumeValidationSession(sessionId, payload)
      setFinalStatus((res as any).final_status ?? finalStatus)
      setSummary((res as any).summary ?? summary)
      setValidationResults((res as any).validation_results ?? validationResults)
      setStep("complete")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Resume failed. Please try again.")
    } finally {
      setSubmitting(false)
    }
  }

  // ── Reset ─────────────────────────────────────────────────────────────────

  const handleReset = () => {
    setStep("select")
    setSelectedShipment(null)
    setBoeFile(null)
    setPendingResult(null)
    setExtractedBOE(null)
    setFieldEdits({})
    setLineItemEdits({})
    setBlockEdits({})
    setSessionId(null)
    setDiscrepancies([])
    setConfirmations({})
    setValidationResults([])
    setFinalStatus(null)
    setSummary(null)
    setError(null)
    setSaveError(null)
    setFieldReviewView("fields")
    setResultsView("results")
    if (boeBlobUrlRef.current) {
      URL.revokeObjectURL(boeBlobUrlRef.current)
      boeBlobUrlRef.current = null
    }
  }

  return {
    // State
    step,
    selectedShipment, setSelectedShipment,
    boeFile, setBoeFile,
    fileInputRef,
    extractedBOE,
    fieldEdits,
    lineItemEdits,
    blockEdits,
    saving,
    saveError,
    pendingResult,
    sessionId,
    discrepancies,
    confirmations,
    validationResults,
    finalStatus,
    summary,
    error,
    submitting,
    elapsed,
    fieldReviewView, setFieldReviewView,
    resultsView, setResultsView,

    // Functions
    getBOEBlobUrl,
    handleFieldChange,
    handleLineItemChange,
    handleBlockCellChange,
    handleValidate,
    handleSaveFields,
    applyResult,
    handleResume,
    handleReset,

    // Setters
    setStep,
    setConfirmations,
  }
}

import type {
  ValidationDiscrepancy,
  BOEValidationResponse,
  ExtractedDocumentMeta,
} from "@/lib/api-client"

export type { ValidationDiscrepancy, BOEValidationResponse, ExtractedDocumentMeta }

export type Step = "select" | "processing" | "field_review" | "results" | "complete"

export interface Shipment {
  shipment_id: string
  shipment_number: string
  boe_number?: string
  boe_version?: number
  supplier_name?: string
  consignee_name?: string
  status: string
  vendor_docs_count: number
  created_at?: string
}

export type BOEChecklistEntry = {
  id: string
  label: string
  fieldNames: string[]
  backendFields: string[]
}

export type FieldGroups = Array<{ label: string; keys: string[] }>

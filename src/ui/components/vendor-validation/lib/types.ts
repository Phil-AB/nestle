import type {
  ValidationDiscrepancy,
  VendorValidationResponse,
  ExtractedDocumentMeta,
  ExtractedTable,
} from "@/lib/api-client"

export type {
  ValidationDiscrepancy,
  VendorValidationResponse,
  ExtractedDocumentMeta,
  ExtractedTable,
}

export interface DocSlot {
  key: "invoice" | "packing_list" | "bill_of_lading" | "freight_manifest" | "certificate_of_origin"
  label: string
  required: boolean
  description: string
}

export type Step = "upload" | "processing" | "field_review" | "review" | "complete"

export type ChecklistEntry = {
  id: string
  label: string
  docFields: Partial<Record<string, string | string[]>>
  backendFields: string[]
}

export type DocFiles = Record<DocSlot["key"], File | null>

export type FieldEdits = Record<string, Record<string, string>>
export type LineItemEdits = Record<string, Record<number, Record<string, string>>>
export type TableEdits = Record<string, Record<number, Record<number, Record<number, string>>>>

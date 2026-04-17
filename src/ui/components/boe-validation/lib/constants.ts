import type { BOEChecklistEntry, FieldGroups, Step } from "./types"

export const SKIP_ITEM_COLS = new Set([
  "_row_index", "_table_index", "column_index", "column_number",
  "row_index", "table_block_index", "table_bbox",
  "normalized_header", "original_header", "original_page",
])

export const BOE_CHECKLIST: BOEChecklistEntry[] = [
  { id: "declarant_name",    label: "Declarant Name",
    fieldNames: ["declarant_name", "declarant_representative"],
    backendFields: ["declarant_name"] },
  { id: "declarant_address", label: "Declarant Address",
    fieldNames: ["declarant_address", "declarant_representative_address"],
    backendFields: ["declarant_reg_number"] },
  { id: "hs_code",           label: "H.S. Code",
    fieldNames: ["hs_code", "hs_code_full", "commodity_code"],
    backendFields: ["hs_code"] },
  { id: "import_duty",       label: "Import Duty",
    fieldNames: ["duty_amount", "duty_rate"],
    backendFields: ["duty_amount"] },
  { id: "vat_nhil",          label: "VAT / NHIL",
    fieldNames: ["vat_amount", "nhil_amount"],
    backendFields: ["vat_amount", "nhil_amount"] },
  { id: "cpc",               label: "CPC",
    fieldNames: ["customs_code", "cpc"],
    backendFields: ["customs_code"] },
]

export const FIELD_GROUPS: FieldGroups = [
  {
    label: "Identity",
    keys: ["boe_number", "invoice_number", "bl_number", "order_number", "po_number", "contract_number"],
  },
  {
    label: "Parties",
    keys: ["consignee_name", "consignee_address", "shipper_name", "shipper_address", "declarant_name", "declarant_reg_number"],
  },
  {
    label: "Goods",
    keys: ["hs_code", "product_description", "country_of_origin", "quantity", "net_weight", "gross_weight"],
  },
  {
    label: "Financials",
    keys: ["customs_value", "total_fob_value", "total_invoice_value", "freight_value", "insurance_value", "duty_rate", "duty_amount", "vat_rate", "vat_amount", "nhil_amount"],
  },
  {
    label: "Transport",
    keys: ["incoterm", "currency", "vessel_name", "port_of_loading", "port_of_discharge", "container_numbers", "mode_of_shipment"],
  },
  {
    label: "Customs",
    keys: ["customs_code", "customs_procedure", "cpc_code", "etls_approval"],
  },
]

export const INDICATOR_STEPS: Array<{ key: Step; label: string }> = [
  { key: "select", label: "Select" },
  { key: "field_review", label: "Review Fields" },
  { key: "results", label: "Results" },
  { key: "complete", label: "Complete" },
]

export const STEP_ORDER: Step[] = ["select", "field_review", "results", "complete"]

import type { BOEChecklistEntry, FieldGroups, Step } from "./types"

export const SKIP_ITEM_COLS = new Set([
  "_row_index", "_table_index", "column_index", "column_number",
  "row_index", "table_block_index", "table_bbox",
  "normalized_header", "original_header", "original_page",
])

export const BOE_CHECKLIST: BOEChecklistEntry[] = [
  { id: "shipper_name",      label: "Shipper's Name & Address",
    fieldNames: ["shipper_name", "shipper_address"],
    backendFields: ["shipper_name"] },
  { id: "consignee_name",    label: "Consignee Name & Address",
    fieldNames: ["consignee_name", "consignee_address"],
    backendFields: ["consignee_name"] },
  { id: "declarant_name",    label: "Declarant Name",
    fieldNames: ["declarant_name", "declarant_representative"],
    backendFields: ["declarant_name"] },
  { id: "declarant_reg",     label: "Declarant Reg. No.",
    fieldNames: ["declarant_reg_number", "declarant_no"],
    backendFields: ["declarant_reg_number"] },
  { id: "hs_code",           label: "H.S. Code",
    fieldNames: ["hs_code_full", "hs_code", "commodity_code"],
    backendFields: ["hs_code"] },
  { id: "cpc",               label: "CPC Code",
    fieldNames: ["customs_code", "cpc"],
    backendFields: ["customs_code"] },
  { id: "import_duty_rate",  label: "Import Duty Rate",
    fieldNames: ["duty_rate"],
    backendFields: ["duty_rate"] },
  { id: "import_duty",       label: "Import Duty Amount",
    fieldNames: ["duty_amount"],
    backendFields: ["duty_amount"] },
  { id: "vat_nhil",          label: "VAT / NHIL",
    fieldNames: ["vat_amount", "nhil_amount"],
    backendFields: ["vat_amount", "nhil_amount"] },
  { id: "etls_approval",     label: "ETLS / Concession Ref.",
    fieldNames: ["etls_approval_number", "etls_approval"],
    backendFields: ["etls_approval_number"] },
  { id: "fob_value",         label: "FOB Value & Currency",
    fieldNames: ["total_fob_value", "fob_value", "currency"],
    backendFields: ["total_fob_value", "fob_boe_to_invoice"] },
  { id: "customs_value",     label: "Customs Value (CIF)",
    fieldNames: ["customs_value"],
    backendFields: ["customs_value"] },
  { id: "incoterm",          label: "Incoterm",
    fieldNames: ["incoterm", "shipping_condition"],
    backendFields: ["incoterm", "freight_insurance"] },
  { id: "insurance",         label: "Insurance",
    fieldNames: ["insurance_value"],
    backendFields: ["insurance_value", "freight_insurance"] },
  { id: "freight",           label: "Freight",
    fieldNames: ["freight_value"],
    backendFields: ["freight_value"] },
  { id: "gross_weight",      label: "Gross Weight",
    fieldNames: ["gross_weight"],
    backendFields: ["gross_weight", "gross_weight_packing_to_boe"] },
  { id: "net_weight",        label: "Net Weight",
    fieldNames: ["net_weight"],
    backendFields: ["net_weight"] },
  { id: "quantity",          label: "Quantity",
    fieldNames: ["quantity"],
    backendFields: ["quantity", "quantity_invoice_to_packing"] },
  { id: "country_of_origin", label: "Country of Origin",
    fieldNames: ["origin", "country_of_origin"],
    backendFields: ["origin", "country_of_origin"] },
  { id: "container_count",   label: "Number of Containers",
    fieldNames: ["container_count", "container_numbers"],
    backendFields: ["container_count"] },
  { id: "mode_of_shipment",  label: "Mode of Shipment",
    fieldNames: ["entry_exit_code", "mode_of_shipment"],
    backendFields: ["entry_exit_code", "mode_of_shipment"] },
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

export const GRA_TRANSPORT_CODES: Record<string, string> = {
  "10": "Sea",
  "20": "Rail",
  "30": "Road",
  "40": "Air",
  "50": "Post",
  "70": "Pipeline",
}

export const INDICATOR_STEPS: Array<{ key: Step; label: string }> = [
  { key: "select", label: "Select" },
  { key: "field_review", label: "Review Fields" },
  { key: "results", label: "Results" },
  { key: "complete", label: "Complete" },
]

export const STEP_ORDER: Step[] = ["select", "field_review", "results", "complete"]

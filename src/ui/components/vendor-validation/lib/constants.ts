import type { DocSlot, ChecklistEntry } from "./types"

export const DOC_SLOTS: DocSlot[] = [
  {
    key: "invoice",
    label: "Commercial Invoice",
    required: true,
    description: "Supplier's invoice showing goods, quantities, and values",
  },
  {
    key: "packing_list",
    label: "Packing List",
    required: true,
    description: "Itemised list of goods shipped with weights and dimensions",
  },
  {
    key: "bill_of_lading",
    label: "Bill of Lading",
    required: false,
    description: "Carrier's receipt — confirms shipment details, containers, and routing",
  },
  {
    key: "freight_manifest",
    label: "Freight Manifest",
    required: false,
    description: "Full cargo manifest from the freight forwarder",
  },
  {
    key: "certificate_of_origin",
    label: "Certificate of Origin",
    required: false,
    description: "Certifies the country of manufacture for customs purposes",
  },
]

export const DOC_LABEL: Record<string, string> = {
  invoice: "Commercial Invoice",
  packing_list: "Packing List",
  bill_of_lading: "Bill of Lading",
  freight_manifest: "Freight Manifest",
  certificate_of_origin: "Certificate of Origin",
}

export const DOC_SHORT: Record<string, string> = {
  invoice: "Invoice",
  packing_list: "Packing List",
  bill_of_lading: "BOL",
  freight_manifest: "Manifest",
  certificate_of_origin: "Cert of Origin",
}

export const DOC_FIELD_GROUPS: Record<string, string[]> = {
  invoice: ["invoice_number", "invoice_date", "total_invoice_value", "total_fob_value", "currency", "incoterm", "shipper_name", "consignee_name", "payment_terms"],
  packing_list: ["invoice_number", "net_weight", "gross_weight", "quantity", "unit_of_measure", "shipper_name", "consignee_name", "hs_code"],
  bill_of_lading: ["bl_number", "vessel_name", "port_of_loading", "port_of_discharge", "shipper_name", "consignee_name", "container_numbers", "incoterm"],
  freight_manifest: ["bl_number", "vessel_name", "shipper_name", "consignee_name", "gross_weight", "net_weight"],
  certificate_of_origin: ["origin", "country_of_origin", "shipper_name", "consignee_name", "hs_code", "product_description"],
}

export const DOC_DISPLAY_LABEL: Record<string, string> = {
  invoice: "Commercial Invoice",
  packing_list: "Packing List",
  bill_of_lading: "Bill of Lading",
  freight_manifest: "Freight Manifest",
  certificate_of_origin: "Certificate of Origin",
}

export const SKIP_ITEM_COLS = new Set([
  "_row_index", "_table_index", "column_index", "column_number",
  "row_index", "table_block_index", "table_bbox",
  "normalized_header", "original_header", "original_page",
])

export const DOC_ORDER = ["invoice", "packing_list", "bill_of_lading", "freight_manifest", "certificate_of_origin"]

export const CHECKLIST: ChecklistEntry[] = [
  { id: "shippers_address",  label: "Shipper's Name & Address",
    backendFields: ["shipper_name", "shipper_address"],
    docFields: { invoice: ["shipper_name", "shipper_address"], bill_of_lading: ["shipper_name", "shipper_address"] } },
  { id: "consignee_address", label: "Consignee Name & Address",
    backendFields: ["consignee_name", "consignee_address"],
    docFields: { invoice: ["consignee_name", "consignee_address"], packing_list: ["consignee_name", "consignee_address", "bill_to_name", "bill_to_address"], bill_of_lading: ["consignee_name", "consignee_address"] } },
  { id: "po_number",         label: "PO / Reference No.",
    backendFields: ["po_number"],
    docFields: { invoice: ["po_number", "your_order_number", "customer_ref", "customer_reference"], packing_list: ["po_number", "customer_ref", "customer_reference"], bill_of_lading: ["po_number", "customer_ref", "customer_reference"] } },
  { id: "product_desc",      label: "Product Description",
    backendFields: ["product_description"],
    docFields: { invoice: ["product_description", "description", "goods_description"], packing_list: ["product_description", "description", "goods_description", "description_of_goods"], bill_of_lading: ["product_description", "goods_description", "description", "kind_of_packages_description_of_goods"] } },
  { id: "hs_code",           label: "H.S. Code",
    backendFields: ["hs_code"],
    docFields: { invoice: ["hs_code"], packing_list: ["hs_code"], bill_of_lading: ["hs_code"] } },
  { id: "fob_value",         label: "FOB Value & Currency",
    backendFields: ["total_invoice_value", "total_fob_value", "currency"],
    docFields: { invoice: ["total_excl_vat", "total_fob_value", "total_invoice_value", "currency"] } },
  { id: "incoterm",          label: "Incoterm",
    backendFields: ["incoterm"],
    docFields: { invoice: ["incoterm", "shipping_condition"], packing_list: ["incoterm", "delivery_terms"] } },
  { id: "insurance",         label: "Insurance",
    backendFields: ["insurance_value", "freight_insurance"],
    docFields: { invoice: "insurance_value" } },
  { id: "freight",           label: "Freight",
    backendFields: ["freight_value", "freight_insurance"],
    docFields: { invoice: "freight_value" } },
  { id: "net_weight",        label: "Net Weight",
    backendFields: ["net_weight"],
    docFields: { invoice: ["net_weight", "total_net_weight"], packing_list: ["net_weight", "total_net_weight", "total_sent_net_weight"], bill_of_lading: ["net_weight", "nett_weight"] } },
  { id: "gross_weight",      label: "Gross Weight",
    backendFields: ["gross_weight"],
    docFields: { invoice: ["gross_weight", "total_gross_weight"], packing_list: ["gross_weight", "total_gross_weight", "total_sent_gross_weight"], bill_of_lading: ["gross_weight"] } },
  { id: "country_of_origin", label: "Country of Origin",
    backendFields: ["country_of_origin"],
    docFields: { certificate_of_origin: "country_of_origin" } },
  { id: "quantity",          label: "Quantity",
    backendFields: ["quantity"],
    docFields: { invoice: ["quantity", "total_units"], packing_list: ["quantity", "total_units", "total_sent_units"], bill_of_lading: ["quantity"] } },
  { id: "container_count",   label: "Number of Containers",
    backendFields: ["container_count", "container_numbers"],
    docFields: { packing_list: ["container_count", "container_numbers"], bill_of_lading: ["container_count", "container_numbers"] } },
]

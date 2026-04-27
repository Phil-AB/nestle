Step 2 — Vendor Document Validation: Checks
14 steps, well covered:

#	Check	Status
1	Invoice field completeness (invoice_number, shipper, consignee, incoterm, currency, value, weights, qty, PO refs)	✅
2	Packing list completeness (consignee, incoterm, weights, qty, containers, PO refs)	✅
3	BOL completeness (bl_number, consignee, containers, weights, qty, PO refs)	✅ optional
4	Consignee name match across invoice/PL/BOL (fuzzy, 0.75 threshold)	✅
5–7	Order number, contract number, PO number consistency (exact match, graceful skip if absent)	✅
8	Product description consistency (fuzzy — handles abbreviated vs full name)	✅
9	Incoterm consistency invoice ↔ PL (fuzzy)	✅
10	Incoterm freight/insurance rules (FCA → freight collect, not billed on invoice)	✅
11–12	Net + gross weight consistency invoice/PL/BOL (±1%)	✅
13	Quantity consistency invoice/PL/BOL (±0.5%)	✅
14	Container count + container IDs PL ↔ BOL	✅
15	Country of origin presence on COO (when uploaded)	✅ optional
Gaps in Step 2:

Freight manifest — accepted at upload, stored in DB, but no validation steps use it. If a freight manifest is uploaded alongside the invoice and PL, its weights, quantities, and container data are never cross-checked against the other documents.

COO completeness is shallow — only checks country_of_origin and consignee_name. A COO should also carry goods_description and ideally hs_code. If Nestle needs the COO for concessionary duty claims (master concession), hs_code on the COO needs to match the BOE.

Step 6 — BOE Cross-Verification: Checks
22 steps, mostly well covered:

#	Check	Status
1	Shipper + consignee name match BOE/invoice/BOL (fuzzy 0.8)	✅
2	Required fields on BOE (hs_code, gross_weight, qty, duty_rate)	✅
3	HS code 3-way match BOE/invoice/PL (when present, exact)	✅
4	HS code format (6–10 digit / XXXX.XX regex)	✅
5	Weight matching BOE/invoice/PL/BOL (±1%)	✅
6	Quantity invoice ↔ PL (±0.5%)	✅
7	Duty amount calculation: customs_value × duty_rate (±0.5%)	✅
8	Duty rate range (0–100%)	✅
9	CPC/customs code rules (40E68/40V02/40U01/40W01 amounts, exemptions)	✅
10	Mode of shipment (Section 21 code vs transport doc)	✅
11	Incoterm rules (freight/insurance compliance per incoterm)	✅
12	Declarant name + registration number present	✅
13	FOB value BOE ↔ invoice (±0.5%)	✅
14	Incoterm BOE ↔ invoice (extracts 3-letter code)	✅
15	Currency BOE ↔ invoice (exact)	✅
16	Country of origin present on BOE	✅
17	Container count BOE ↔ BOL	✅
18	ETLS approval number required for 40U01/40W01 (zero duty)	✅
19	Master Concession eligibility (HS codes vs 244-item list, expiry, ref number)	✅
20	VAT (15%) and NHIL (2.5%) calculations	✅
21	VAT deferment eligibility (40V02 HS codes vs URV 0014, 82 items)	✅
22	Insurance rate (0.875% sea, 1% air of C&F)	✅
Gaps in Step 6:

Invoice number cross-check (BOE ↔ invoice) — The GRA BOE has an invoice number field. The workflow doc lists "invoice number" as a field to verify. There is no step checking bill_of_entry.invoice_number matches invoice.invoice_number. This is a direct traceability check — if the BOE was built on the wrong invoice, this is the only catch.

CIF / customs value calculation check — The BOE customs_value is the CIF value (Cost + Insurance + Freight). It must equal FOB + freight + insurance. Currently we validate duty_amount and VAT/NHIL calculations but there's no step checking that customs_value = FOB + freight_value + insurance_value. An incorrect CIF flows into every subsequent calculation (duty, VAT, NHIL), so this is foundational.

GET Fund levy (Tax 88 = 2.5%) — Ghana BOEs carry three tax lines: VAT (15%), NHIL (Tax 47, 2.5%), and GET Fund Levy (Tax 88, 2.5%). The current vat_nhil_rate_check only verifies VAT and NHIL. GET Fund is charged on the same base as NHIL and appears as a separate line on the GRA BOE. It needs its own calculation check.

Summary of what to add:

Priority	Gap	Where
High	Invoice number BOE ↔ invoice cross-check	Step 6, new step after fob_value_crosscheck
High	CIF calculation: FOB + freight + insurance = customs_value	Step 6, new calculation step
Medium	GET Fund levy (Tax 88 = 2.5%) calculation check	Step 6, extend vat_nhil_rate_check
Low	Freight manifest validation (weight/qty/container cross-check)	Step 2, new optional steps
Want me to implement the three Step 6 gaps now? They're all config + possibly one validator change.


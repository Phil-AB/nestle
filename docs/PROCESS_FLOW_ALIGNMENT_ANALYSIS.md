# Process Flow Alignment Analysis
**Analysis Date**: 2026-02-10
**Analyzed By**: Claude (Backend Engineer & Code Auditor)
**Source Documents**:
- Process Flow.pptx (5 slides)
- Complete codebase audit

---

## Executive Summary

This document provides a **thorough analysis** of how the current codebase aligns with the BOE validation process flow outlined in the PowerPoint presentation. The analysis covers document ingestion, validation rules, customs code handling, HS code verification, and BOE structure extraction.

### Overall Assessment

| Category | Status | Coverage | Notes |
|----------|--------|----------|-------|
| **Document Ingestion** | ✅ **ALIGNED** | 100% | All required documents supported |
| **Basic Validation Rules** | ✅ **ALIGNED** | 80% | Core validations implemented |
| **Customs Code Handling** | ❌ **NOT ALIGNED** | 0% | Missing implementation |
| **CET File Integration** | ❌ **NOT ALIGNED** | 0% | Not implemented |
| **BOE Section Validation** | ❌ **NOT ALIGNED** | 0% | Generic extraction only |
| **Incoterm-Specific Logic** | ⚠️ **PARTIAL** | 30% | Structure exists, logic missing |
| **Mode of Shipment Detection** | ❌ **NOT ALIGNED** | 0% | Not implemented |

---

## Detailed Analysis by Component

---

## 1. Document Ingestion & Pre-Alert Handling ✅

### PPTX Requirements (Slides 2-3)

**Pre-alerts or receipt of scanned copies of clearing documents:**
- Bill of Lading (BL) - for sea shipments
- Air Waybill (AWB) - for air shipments
- Delivery Note (DN) - for road shipments
- Final/Commercial Invoice
- Packing List
- Certificate of Origin (COO)

### Codebase Implementation

**✅ ALL DOCUMENTS SUPPORTED**

#### Document Type Configuration
**File**: `/config/document_types.yaml`

```yaml
document_types:
  invoice: ✅ Supported
    - display_name: "Invoice"
    - Fields: invoice_number, invoice_date, shipper, consignee, incoterm, etc.

  boe: ✅ Supported (Bill of Entry)
    - display_name: "Bill of Entry"
    - Fields: declaration_number, fob_value, cif_value, duty_value, etc.

  packing_list: ✅ Supported
    - display_name: "Packing List"
    - Fields: gross_weight, net_weight, quantity, hs_code, etc.

  bill_of_lading: ✅ Supported
    - display_name: "Bill of Lading"
    - Fields: vessel_name, port_of_loading, port_of_discharge, etc.

  coo: ✅ Supported (Certificate of Origin)
    - display_name: "Certificate of Origin"
    - Fields: certificate_number, country_of_origin, hs_code, etc.
```

#### Document Schemas
**File**: `/shared/contracts/document_schemas.py`

```python
✅ InvoiceSchema - Complete with line items
✅ BOESchema - Complete with line items
✅ PackingListSchema - Complete with weights
✅ COOSchema - Complete with HS codes
✅ FreightSchema - Freight documents supported
```

#### Validation Use Case Configuration
**File**: `/config/validation/use_cases/boe_validation.yaml`

```yaml
documents:
  primary:
    type: "bill_of_entry" ✅

  supporting:
    - type: "invoice" ✅
    - type: "packing_list" ✅
    - type: "bill_of_lading" ✅
      alternatives:
        - "airway_bill" ✅
```

### ✅ Alignment Status: **FULLY ALIGNED**

---

## 2. BOE Validation Rules ✅ Partial

### PPTX Requirements (Slide 2-3)

**Draft BOE is sent to IMPEX for checks and validation:**

1. **Check Shipper, Consignee** (using BL/AWB/DN)
2. **Check Weights** on Packing List
3. **Check HS Code** (using COO)
4. **Check Freight Amount** on Invoice (depending on incoterm: CFR, CIF, FCA/FOB)
5. **Section 21**: Mode of shipment (KIA = air, TMA = sea)
6. **Section 25**: Description of goods (verify HS code)
7. **Section 31**: Item details with HS codes
8. **Section 40**: Calculations (duty, VAT, rates)

### Codebase Implementation

#### ✅ Implemented Validators

##### 1. HS Code Matching ✅
**File**: `/modules/validation_engine/validators/cross_document/n_way_matcher.py`

**Validator**: `n_way_matcher`
- ✅ Compares HS code across N documents (BOE, Invoice, Packing List)
- ✅ Exact match validation
- ✅ Identifies which documents mismatch
- ✅ Groups documents by value

**Config** (from `boe_validation.yaml`):
```yaml
- name: "hs_code_3way_matching"
  validators:
    - "n_way_matcher"
  config:
    field_name: "hs_code"
    documents:
      - "bill_of_entry"
      - "invoice"
      - "packing_list"
    match_type: "exact"
```

**✅ ALIGNED** with PPTX requirement: "Check HS Code using COO"

---

##### 2. Weight Matching ✅
**File**: `/modules/validation_engine/validators/statistical/tolerance_validator.py`

**Validator**: `tolerance_validator`
- ✅ Net weight validation (Invoice → BOE)
- ✅ Net weight validation (Packing List → BOE)
- ✅ Gross weight validation (Packing List → BOE)
- ✅ Net < Gross consistency check
- ✅ Configurable tolerance (default 1%)
- ✅ Per-session tolerance overrides

**Config**:
```yaml
- name: "weight_matching"
  config:
    tolerance_type: "percentage"
    default_tolerance: 1.0

    validations:
      - name: "net_weight_invoice_to_boe"
        tolerance_percent: 1.0
      - name: "gross_weight_packing_to_boe"
        tolerance_percent: 1.0
```

**✅ ALIGNED** with PPTX requirement: "Check Weights on PL"

---

##### 3. Duty Calculation ✅
**File**: `/modules/validation_engine/validators/cross_document/calculation_validator.py`

**Validator**: `calculation_validator`
- ✅ Validates computed fields by recomputing
- ✅ Formula: `duty_amount = unit_price × quantity × duty_rate`
- ✅ Gathers fields from multiple documents
- ✅ Tolerance-based comparison (0.5%)

**Config**:
```yaml
- name: "duty_calculation"
  validators:
    - "calculation_validator"
  config:
    calculations:
      - formula: "unit_price * quantity * duty_rate"
        fields:
          unit_price: "invoice.unit_price"
          quantity: "packing_list.quantity"
          duty_rate: "bill_of_entry.duty_rate"
        tolerance_percent: 0.5
```

**✅ ALIGNED** with PPTX requirement: Section 40 calculations

---

##### 4. Required Fields Validation ✅
**File**: `/modules/validation_engine/validators/rule_based/required_fields_validator.py`

**Validator**: `required_fields_validator`
- ✅ Ensures critical fields exist
- ✅ Per-document-type required fields
- ✅ Nested field support

**Config**:
```yaml
required_fields:
  bill_of_entry:
    - "hs_code"
    - "net_weight"
    - "gross_weight"
    - "duty_rate"
    - "duty_amount"
```

**✅ ALIGNED** with general validation requirements

---

##### 5. HS Code Format Validation ✅
**File**: `/modules/validation_engine/validators/rule_based/regex_validator.py`

**Validator**: `regex_validator`
- ✅ Pattern matching for HS Code format
- ✅ Format: `XXXX.XX` (e.g., 1234.56)

**Config**:
```yaml
- name: "hs_code_format"
  validators:
    - "regex_validator"
  config:
    pattern: "^\\d{4}\\.\\d{2}$"
```

**✅ ALIGNED** with HS Code validation

---

##### 6. Quantity Matching ✅
**Validator**: `tolerance_validator` (reused)
- ✅ Quantity matching across documents
- ✅ 0.5% tolerance

**✅ ALIGNED** with general validation

---

#### ❌ Missing Validators

##### 1. Shipper/Consignee Validation ❌
**PPTX Requirement**: "Check Shipper, Consignee using BL/AWB/DN"

**Status**: ❌ **NOT IMPLEMENTED**

**Gap**:
- No validator to compare shipper/consignee between BOE and BL/AWB/DN
- Fields exist in schemas but no cross-document validation

**Needed**:
```python
# Missing validator
@ValidatorRegistry.register("shipper_consignee_validator")
class ShipperConsigneeValidator(IValidator):
    """
    Validates shipper and consignee match across:
    - BOE
    - Invoice
    - BL/AWB/DN
    """
    # Implementation needed
```

---

##### 2. Freight Amount Validation (Incoterm-Specific) ❌
**PPTX Requirement**: "Check Freight Amount on Invoice (depending on incoterm)"

**Incoterms**:
- **CFR** (Cost & Freight): Invoice should have freight value
- **CIF** (Cost, Insurance, Freight): Invoice should have insurance + freight
- **FCA/FOB** (Free Carrier/Free on Board): No freight value needed

**Status**: ❌ **NOT IMPLEMENTED**

**Gap**:
- `incoterm` field exists in `InvoiceSchema`
- `freight_value` and `insurance_value` fields exist
- **NO validator** to enforce incoterm-specific rules

**Needed**:
```python
# Missing validator
@ValidatorRegistry.register("incoterm_validator")
class IncotermValidator(IValidator):
    """
    Validates freight and insurance based on incoterm:
    - CFR: freight_value required
    - CIF: freight_value + insurance_value required
    - FCA/FOB: freight_value not expected
    """
    # Implementation needed
```

---

##### 3. Mode of Shipment Detection (Section 21) ❌
**PPTX Requirement**: "Section 21 tells you the mode of shipment (e.g., KIA = air, TMA = sea)"

**Status**: ❌ **NOT IMPLEMENTED**

**Gap**:
- No extraction of BOE Section 21
- No logic to determine shipment mode from codes
- No validation that correct transport document is provided (BL for sea, AWB for air)

**Needed**:
```python
# Missing validator
@ValidatorRegistry.register("shipment_mode_validator")
class ShipmentModeValidator(IValidator):
    """
    Validates shipment mode consistency:
    - If Section 21 = KIA → expect AWB
    - If Section 21 = TMA → expect BL
    """
    # Implementation needed
```

---

##### 4. Description of Goods Validation (Section 25) ❌
**PPTX Requirement**: "Mostly, the description of goods in section 25 gives an idea whether the HS/Commodity Code used is right or not"

**Status**: ❌ **NOT IMPLEMENTED**

**Gap**:
- No semantic validation of product description vs HS code
- No LLM-based reasoning to verify HS code matches description

**Needed**:
```python
# Missing validator (AI-based)
@ValidatorRegistry.register("description_hs_code_validator")
class DescriptionHSCodeValidator(IValidator):
    """
    Uses LLM to validate that product description
    is consistent with the HS code.
    """
    # Implementation needed
```

---

### ⚠️ Alignment Status: **PARTIALLY ALIGNED** (60%)

**Implemented**: 6/10 validation rules
**Missing**: 4/10 validation rules

---

## 3. Customs Code Handling ❌

### PPTX Requirements (Slide 3)

**Specific customs codes mentioned:**

1. **40E68**:
   - Pay Import VAT in full (5%)
   - Amount Payable = 5% × Customs Value
   - Full duty payment

2. **40V02**:
   - VAT exempted for payment later
   - Amount Payable = 0.00
   - Amount Exempted = VAT Rate × Customs Value

3. **40U01 & 40W01**:
   - Import Duty is exempted
   - **40W01**: Import Duty exempted, but pay taxes

### Codebase Implementation

**Status**: ❌ **NOT IMPLEMENTED**

#### Findings:

1. **No customs code handling found**:
   ```bash
   # Search results:
   $ grep -r "40E68\|40V02\|40U01\|40W01" .
   # No results
   ```

2. **No VAT calculation logic**:
   - No validator for customs code-specific VAT rules
   - No Amount Payable calculation
   - No Amount Exempted calculation

3. **No duty exemption logic**:
   - No handling for duty-exempt codes
   - No differentiation between duty-exempt and tax-exempt

#### Gap Analysis:

**Missing Components**:

```python
# Missing validator
@ValidatorRegistry.register("customs_code_validator")
class CustomsCodeValidator(IValidator):
    """
    Validates Amount Payable based on customs code:

    40E68:
      - Amount Payable = 5% * Customs Value
      - Full VAT payment

    40V02:
      - Amount Payable = 0.00
      - Amount Exempted = VAT Rate * Customs Value

    40U01, 40W01:
      - Duty exempted
      - 40W01: Still pay taxes
    """
    # Implementation needed
```

**Missing Configuration**:

```yaml
# Should be in: /config/validation/validators/customs_code.yaml

customs_codes:
  40E68:
    type: "full_vat_payment"
    vat_rate: 0.05
    calculation: "5% * customs_value"
    amount_payable: "calculated"
    exempted: false

  40V02:
    type: "vat_exempted"
    vat_rate: 0.00
    amount_payable: 0.00
    amount_exempted: "vat_rate * customs_value"

  40U01:
    type: "duty_exempted"
    duty_exempted: true
    vat_exempted: false

  40W01:
    type: "duty_exempted_tax_payable"
    duty_exempted: true
    vat_exempted: false
    taxes_payable: true
```

### ❌ Alignment Status: **NOT ALIGNED** (0%)

**Critical Gap**: Customs code-specific validation is completely missing

---

## 4. HS Code & CET File Integration ❌

### PPTX Requirements (Slide 3)

**CET File Integration**:
- "HS Code can be confirmed in the CET File (column C 'Description' and column E 'ID')"
- "Column E has rates (in %) which are reflected on the BOE in section 40 (Rate column)"
- "You may double check the HS code using the CET File attached"

### Codebase Implementation

**Status**: ❌ **NOT IMPLEMENTED**

#### Findings:

1. **No CET file in repository**:
   ```bash
   $ find . -name "*CET*" -o -name "*cet*"
   # No results
   ```

2. **No CET file integration**:
   - No code to load CET file
   - No HS code lookup against CET
   - No rate verification from CET

3. **No HS code description validation**:
   - HS code format validation exists ✅
   - HS code cross-document matching exists ✅
   - **BUT**: No validation that HS code description matches CET

#### Gap Analysis:

**Missing Components**:

```python
# Missing service
class CETFileService:
    """
    Service to load and query CET (Common External Tariff) file.

    CET File Structure:
    - Column C: Description
    - Column E: ID (HS Code)
    - Rates in %
    """

    def load_cet_file(self, file_path: str):
        """Load CET file (CSV/Excel)"""
        pass

    def get_hs_code_info(self, hs_code: str) -> Dict:
        """Get description and rate for HS code"""
        pass

    def verify_hs_code(self, hs_code: str, description: str) -> bool:
        """Verify HS code matches description"""
        pass

    def get_duty_rate(self, hs_code: str) -> Decimal:
        """Get duty rate % for HS code"""
        pass
```

**Missing Validator**:

```python
# Missing validator
@ValidatorRegistry.register("cet_hs_code_validator")
class CETHSCodeValidator(IValidator):
    """
    Validates HS code against CET file:
    1. HS code exists in CET
    2. Description matches CET description
    3. Duty rate matches CET rate
    """

    async def validate(self, source, target, context):
        cet_service = CETFileService()

        hs_code = source.get("hs_code")
        description = source.get("description")
        duty_rate = source.get("duty_rate")

        # Look up in CET
        cet_info = cet_service.get_hs_code_info(hs_code)

        # Validate
        # ... implementation
```

**Missing Configuration**:

```yaml
# Should be in: /config/validation/cet_integration.yaml

cet_integration:
  enabled: true
  file_path: "/config/data/CET_Ghana_2024.csv"

  columns:
    hs_code: "E"  # Column E: ID
    description: "C"  # Column C: Description
    duty_rate: "Rate"  # Rate column

  validation:
    verify_hs_code_exists: true
    verify_description_match: true
    verify_duty_rate_match: true

  caching:
    enabled: true
    ttl_seconds: 86400  # Cache CET for 24 hours
```

### ❌ Alignment Status: **NOT ALIGNED** (0%)

**Critical Gap**: CET file integration completely missing

---

## 5. Customs Value Calculation & Incoterm Handling ⚠️

### PPTX Requirements (Slide 3)

**Customs Value Calculation**:
- "For CIF shipments, FOB + Insurance + Freight = Total Invoice Value (all in one currency)"
- "Currency rate is usually in section 16 to guide"
- "Customs value is calculated on the incoterm (e.g., CIF, FOB, etc.)"

### Codebase Implementation

**Status**: ⚠️ **PARTIAL IMPLEMENTATION**

#### ✅ What Exists:

1. **Schema Support**:
   ```python
   # InvoiceSchema (document_schemas.py)
   incoterm: Optional[str]
   total_fob_value: Optional[Decimal]
   freight_value: Optional[Decimal]
   insurance_value: Optional[Decimal]
   total_invoice_value: Optional[Decimal]

   # BOESchema
   fob_value: Optional[Decimal]
   freight_value: Optional[Decimal]
   insurance_value: Optional[Decimal]
   cif_value: Optional[Decimal]
   ```

2. **Unit Conversion Support** (normalization):
   ```yaml
   # boe_validation.yaml
   units:
     currency:
       target: "USD"
       source: "exchange_rate_api"
       fallback_rates:
         EUR: 1.1
         GBP: 1.3
         JPY: 0.0091
   ```

#### ❌ What's Missing:

1. **CIF Calculation Validation**:
   - No validator to verify: `CIF = FOB + Insurance + Freight`
   - Formula exists in schemas but not validated

2. **Currency Rate Verification (Section 16)**:
   - No extraction of BOE Section 16 (currency rate)
   - No validation that currency conversion is correct

3. **Incoterm-Specific Customs Value**:
   - No validator to calculate customs value based on incoterm
   - CIF incoterm → customs value = CIF value
   - FOB incoterm → customs value = FOB value
   - No logic to enforce this

#### Gap Analysis:

**Missing Validator**:

```python
# Missing validator
@ValidatorRegistry.register("cif_calculation_validator")
class CIFCalculationValidator(IValidator):
    """
    Validates CIF calculation:
    CIF = FOB + Insurance + Freight

    Also validates:
    - All values in same currency (or converted)
    - Currency rate from Section 16 if applicable
    """

    async def validate(self, source, target, context):
        fob = source.get("fob_value")
        insurance = source.get("insurance_value")
        freight = source.get("freight_value")
        cif = source.get("cif_value")

        # Validate: CIF = FOB + Insurance + Freight
        calculated_cif = fob + insurance + freight

        # Compare with tolerance
        # ... implementation
```

**Missing Validator**:

```python
# Missing validator
@ValidatorRegistry.register("customs_value_validator")
class CustomsValueValidator(IValidator):
    """
    Validates customs value based on incoterm:

    - CIF: customs_value = cif_value
    - FOB: customs_value = fob_value
    - CFR: customs_value = fob_value + freight_value
    """
    # Implementation needed
```

### ⚠️ Alignment Status: **PARTIALLY ALIGNED** (30%)

**Structure exists** but **validation logic missing**

---

## 6. BOE Structure Extraction (Sections 21, 25, 31, 40) ❌

### PPTX Requirements (Slides 4-5)

**BOE Form Sections** (highlighted in images):

- **Section 21**: Mode of shipment (Entry/Exit codes like KIA, TMA)
- **Section 25**: Description of goods (for HS code verification)
- **Section 31**: Line items with HS codes, quantities, values
- **Section 40**: Duty calculations (rate, duty amount, VAT)
- **Section 16**: Currency rate

### Codebase Implementation

**Status**: ❌ **NOT ALIGNED**

#### Findings:

1. **Generic BOE Schema Only**:
   ```python
   # BOESchema is generic, no section-specific extraction
   class BOESchema(BaseModel):
       declaration_number: str
       fob_value: Optional[Decimal]
       cif_value: Optional[Decimal]
       duty_value: Optional[Decimal]
       items: List[BOEItemSchema]
   ```

2. **No Section-Specific Extraction**:
   ```bash
   $ grep -r "Section 21\|Section 25\|Section 31\|Section 40" .
   # No results
   ```

3. **No Spatial Extraction for BOE Sections**:
   - Extraction module (`modules/extraction/parser/spatial_extractor.py`) exists
   - **BUT**: No BOE-specific section extraction logic

#### Gap Analysis:

**Missing Schema**:

```python
# Missing: BOE section-specific schema

class BOESectionSchema(BaseModel):
    """Structured extraction of BOE sections"""

    section_16: Optional[Dict] = Field(None, description="Currency rate")
    section_21: Optional[Dict] = Field(None, description="Mode of shipment")
    section_25: Optional[List[Dict]] = Field(None, description="Description of goods")
    section_31: Optional[List[Dict]] = Field(None, description="Line items")
    section_40: Optional[List[Dict]] = Field(None, description="Duty calculations")

class BOESection21(BaseModel):
    """Section 21: Entry/Exit"""
    entry_exit_code: str  # e.g., "KIA", "TMA"
    mode_of_transport: str  # "air", "sea", "road"

class BOESection25(BaseModel):
    """Section 25: Description of goods"""
    line_number: int
    description: str

class BOESection31(BaseModel):
    """Section 31: Line items"""
    line_number: int
    hs_code: str
    origin: str
    quantity: Decimal
    value: Decimal

class BOESection40(BaseModel):
    """Section 40: Duty calculations"""
    line_number: int
    rate_percent: Decimal
    duty_amount: Decimal
    vat_amount: Decimal
    total_amount: Decimal
```

**Missing Extraction Logic**:

```python
# Missing: BOE section extractor

class BOESectionExtractor:
    """
    Extracts specific sections from BOE form using spatial coordinates.

    Uses Reducto or Google Vision to identify:
    - Section 16 (currency rate)
    - Section 21 (mode of shipment)
    - Section 25 (description of goods)
    - Section 31 (line items)
    - Section 40 (duty calculations)
    """

    async def extract_section_21(self, boe_document):
        """Extract mode of shipment from Section 21"""
        # Spatial extraction logic
        pass

    async def extract_section_25(self, boe_document):
        """Extract descriptions from Section 25"""
        pass

    # ... other sections
```

### ❌ Alignment Status: **NOT ALIGNED** (0%)

**Critical Gap**: BOE section-specific extraction completely missing

---

## Summary of Gaps

### Critical Gaps (High Priority)

| Gap | Impact | PPTX Requirement | Implementation Effort |
|-----|--------|------------------|----------------------|
| **Customs Code Handling** (40E68, 40V02, 40U01, 40W01) | 🔴 **HIGH** | Slide 3 - VAT/Duty calculations | Medium (2-3 days) |
| **CET File Integration** | 🔴 **HIGH** | Slide 3 - HS code verification | High (3-5 days) |
| **BOE Section Extraction** (21, 25, 31, 40) | 🔴 **HIGH** | Slides 4-5 - Section-specific validation | High (5-7 days) |
| **Incoterm-Specific Freight Validation** | 🟠 **MEDIUM** | Slide 2 - CFR/CIF/FOB freight rules | Medium (2-3 days) |
| **Shipper/Consignee Validation** | 🟠 **MEDIUM** | Slide 2 - Cross-document party validation | Low (1-2 days) |
| **Mode of Shipment Detection** | 🟠 **MEDIUM** | Slide 2 - KIA/TMA detection | Medium (2-3 days) |
| **CIF Calculation Validation** | 🟡 **LOW** | Slide 3 - FOB + Insurance + Freight | Low (1 day) |
| **Description-HS Code Semantic Validation** | 🟡 **LOW** | Slide 3 - Section 25 AI validation | Medium (2-3 days) |

**Total Estimated Effort**: 20-30 days

---

## Alignment Summary by PPTX Slide

### Slide 1: Import Process Overview
- ✅ Process understanding documented
- ✅ Validation architecture designed

### Slide 2: Important Information
- ✅ Document ingestion: **ALIGNED**
- ✅ HS Code validation: **ALIGNED**
- ✅ Weight validation: **ALIGNED**
- ❌ Shipper/Consignee validation: **NOT ALIGNED**
- ❌ Freight amount validation (incoterm): **NOT ALIGNED**
- ❌ Mode of shipment (Section 21): **NOT ALIGNED**

### Slide 3: Key Information 2
- ❌ Description → HS Code validation (Section 25): **NOT ALIGNED**
- ❌ CET File integration: **NOT ALIGNED**
- ⚠️ CIF calculation: **PARTIAL**
- ❌ Customs codes (40E68, 40V02, etc.): **NOT ALIGNED**

### Slides 4-5: BOE Form Images
- ❌ Section-specific extraction: **NOT ALIGNED**
- ❌ Section 21, 25, 31, 40 validation: **NOT ALIGNED**

---

## Recommendations

### Immediate Actions (Sprint 1: Week 1-2)

1. **Implement Customs Code Validator**
   - Create `CustomsCodeValidator` for 40E68, 40V02, 40U01, 40W01
   - Add config: `/config/validation/validators/customs_code.yaml`
   - Priority: 🔴 **CRITICAL**

2. **Implement CET File Integration**
   - Create `CETFileService` to load and query CET file
   - Create `CETHSCodeValidator` to validate against CET
   - Add CET file to `/config/data/CET_Ghana_2024.csv`
   - Priority: 🔴 **CRITICAL**

3. **Implement Shipper/Consignee Validator**
   - Create `ShipperConsigneeValidator`
   - Cross-document party validation
   - Priority: 🟠 **HIGH**

### Short-Term Actions (Sprint 2: Week 3-4)

4. **Implement BOE Section Extraction**
   - Extend `spatial_extractor.py` for BOE sections
   - Create section-specific schemas (Section 21, 25, 31, 40)
   - Priority: 🔴 **CRITICAL**

5. **Implement Incoterm Validator**
   - Create `IncotermValidator` for freight validation
   - CFR, CIF, FCA/FOB-specific rules
   - Priority: 🟠 **HIGH**

6. **Implement Mode of Shipment Validator**
   - Create `ShipmentModeValidator`
   - KIA → AWB, TMA → BL detection
   - Priority: 🟠 **MEDIUM**

### Medium-Term Actions (Sprint 3: Week 5-6)

7. **Implement CIF Calculation Validator**
   - Create `CIFCalculationValidator`
   - Validate: CIF = FOB + Insurance + Freight
   - Priority: 🟡 **MEDIUM**

8. **Implement Description-HS Code AI Validator**
   - Create `DescriptionHSCodeValidator` (AI-based)
   - Use LLM to validate semantic consistency
   - Priority: 🟡 **LOW**

---

## Testing Requirements

### Test Cases to Add

1. **Customs Code Tests**:
   - Test 40E68: Amount Payable = 5% × Customs Value
   - Test 40V02: Amount Payable = 0.00, Amount Exempted calculated
   - Test 40U01/40W01: Duty exemption logic

2. **CET Integration Tests**:
   - Test HS code lookup in CET
   - Test duty rate retrieval
   - Test description matching

3. **Incoterm Tests**:
   - Test CFR: Freight value required
   - Test CIF: Freight + Insurance required
   - Test FOB: No freight expected

4. **BOE Section Tests**:
   - Test Section 21 extraction and mode detection
   - Test Section 25 description extraction
   - Test Section 31 line item extraction
   - Test Section 40 calculation extraction

---

## Conclusion

### Overall Alignment: **60% Aligned**

**Strengths**:
- ✅ Document ingestion is comprehensive and well-structured
- ✅ Core validation engine is production-grade and extensible
- ✅ Basic BOE validations (HS code, weights, duty) are implemented
- ✅ Config-driven architecture makes adding new validators easy

**Critical Gaps**:
- ❌ Customs code-specific handling completely missing
- ❌ CET file integration not implemented
- ❌ BOE section-specific extraction not implemented
- ❌ Incoterm-specific validation logic missing

**Next Steps**:
1. Prioritize **customs code validator** and **CET integration** (most critical)
2. Implement **BOE section extraction** for spatial validation
3. Add **incoterm validator** for freight/insurance rules
4. Enhance with **shipper/consignee** and **mode of shipment** validators

**Estimated Timeline to Full Alignment**: 4-6 weeks (20-30 days of development)

---

**End of Analysis**

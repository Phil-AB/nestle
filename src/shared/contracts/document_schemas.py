"""
Pydantic schemas for document data validation.

These schemas validate extracted data before saving to database.
"""

from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from decimal import Decimal


# ==============================================================================
# INVOICE SCHEMAS
# ==============================================================================

class InvoiceItemSchema(BaseModel):
    """Invoice line item schema."""

    line_number: Optional[int] = None
    product_description: Optional[str] = None
    hs_code: Optional[str] = None
    country_of_origin: Optional[str] = Field(None, max_length=3)
    quantity: Optional[Decimal] = None
    unit_of_measure: Optional[str] = Field(None, max_length=20)
    unit_price: Optional[Decimal] = None
    total_value: Optional[Decimal] = None


class InvoiceSchema(BaseModel):
    """Invoice document schema."""

    invoice_number: str
    invoice_date: Optional[date] = None
    consignee_name: Optional[str] = None
    consignee_address: Optional[str] = None
    shipper_name: Optional[str] = None
    shipper_address: Optional[str] = None
    incoterm: Optional[str] = Field(None, max_length=10)
    currency: str = Field(default="USD", max_length=3)
    total_fob_value: Optional[Decimal] = None
    freight_value: Optional[Decimal] = None
    insurance_value: Optional[Decimal] = None
    total_invoice_value: Optional[Decimal] = None
    language: Optional[str] = Field(None, max_length=10)
    items: List[InvoiceItemSchema] = Field(default_factory=list)


# ==============================================================================
# BOE SCHEMAS
# ==============================================================================

class BOEItemSchema(BaseModel):
    """BOE line item schema."""

    line_number: Optional[int] = None
    product_description: Optional[str] = None
    hs_code: Optional[str] = None
    country_of_origin: Optional[str] = Field(None, max_length=3)
    quantity: Optional[Decimal] = None
    unit_of_measure: Optional[str] = Field(None, max_length=20)
    unit_value: Optional[Decimal] = None
    total_value: Optional[Decimal] = None


class BOESchema(BaseModel):
    """Bill of Entry document schema."""

    declaration_number: str
    declaration_date: Optional[date] = None
    consignee_name: Optional[str] = None
    consignee_address: Optional[str] = None
    shipper_name: Optional[str] = None
    shipper_address: Optional[str] = None
    fob_value: Optional[Decimal] = None
    freight_value: Optional[Decimal] = None
    insurance_value: Optional[Decimal] = None
    cif_value: Optional[Decimal] = None
    duty_value: Optional[Decimal] = None
    currency: str = Field(default="USD", max_length=3)
    items: List[BOEItemSchema] = Field(default_factory=list)


# ==============================================================================
# PACKING LIST SCHEMAS
# ==============================================================================

class PackingListItemSchema(BaseModel):
    """Packing list line item schema."""

    line_number: Optional[int] = None
    product_description: Optional[str] = None
    quantity: Optional[Decimal] = None
    unit_of_measure: Optional[str] = Field(None, max_length=20)
    package_number: Optional[str] = Field(None, max_length=50)
    gross_weight: Optional[Decimal] = None
    net_weight: Optional[Decimal] = None


class PackingListSchema(BaseModel):
    """Packing list document schema."""

    packing_list_number: Optional[str] = None
    packing_date: Optional[date] = None
    consignee_name: Optional[str] = None
    shipper_name: Optional[str] = None
    total_packages: Optional[int] = None
    total_gross_weight: Optional[Decimal] = None
    total_net_weight: Optional[Decimal] = None
    weight_unit: str = Field(default="KG", max_length=10)
    items: List[PackingListItemSchema] = Field(default_factory=list)


# ==============================================================================
# CERTIFICATE OF ORIGIN SCHEMAS
# ==============================================================================

class COOItemSchema(BaseModel):
    """Certificate of Origin line item schema."""

    line_number: Optional[int] = None
    product_description: Optional[str] = None
    hs_code: Optional[str] = None
    country_of_origin: Optional[str] = Field(None, max_length=3)
    quantity: Optional[Decimal] = None


class COOSchema(BaseModel):
    """Certificate of Origin document schema."""

    certificate_number: Optional[str] = None
    issue_date: Optional[date] = None
    issuing_authority: Optional[str] = None
    exporter_name: Optional[str] = None
    exporter_address: Optional[str] = None
    consignee_name: Optional[str] = None
    consignee_address: Optional[str] = None
    country_of_origin: Optional[str] = Field(None, max_length=3)
    items: List[COOItemSchema] = Field(default_factory=list)


# ==============================================================================
# FREIGHT DOCUMENT SCHEMA
# ==============================================================================

class FreightSchema(BaseModel):
    """Freight document schema."""

    contract_number: Optional[str] = None
    contract_period_start: Optional[date] = None
    contract_period_end: Optional[date] = None
    base_freight: Optional[Decimal] = None
    bunker_adjustment: Decimal = Field(default=Decimal("0"))
    total_freight: Optional[Decimal] = None
    currency: str = Field(default="USD", max_length=3)
    transport_mode: Optional[str] = Field(None, max_length=20)

    @field_validator("total_freight", mode="before")
    @classmethod
    def calculate_total_freight(cls, v, values):
        """Calculate total freight if not provided."""
        if v is None and "base_freight" in values.data:
            base = values.data.get("base_freight", Decimal("0"))
            bunker = values.data.get("bunker_adjustment", Decimal("0"))
            return base + bunker
        return v


# ==============================================================================
# SHIPMENT SCHEMA
# ==============================================================================

class ShipmentSchema(BaseModel):
    """Shipment schema."""

    shipment_number: str
    supplier_name: Optional[str] = None
    consignee_name: Optional[str] = None
    incoterm: Optional[str] = Field(None, max_length=10)
    transport_mode: Optional[str] = Field(None, max_length=20)
    status: str = Field(default="pending", max_length=50)

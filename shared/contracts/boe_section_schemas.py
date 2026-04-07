"""
BOE Section-Specific Schemas

Structured schemas for Ghana BOE form sections as shown in Process Flow PPTX.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from decimal import Decimal
from datetime import date


class BOESection16(BaseModel):
    """Section 16: Currency Exchange Rate"""
    currency_code: Optional[str] = Field(None, description="Currency code (e.g., USD, EUR)")
    exchange_rate: Optional[Decimal] = Field(None, description="Exchange rate to GHS")
    exchange_date: Optional[date] = Field(None, description="Exchange rate date")


class BOESection21(BaseModel):
    """Section 21: Mode of Shipment / Entry-Exit Point"""
    entry_exit_code: Optional[str] = Field(None, description="Entry/Exit code (e.g., KIA, TMA)")
    mode_of_transport: Optional[str] = Field(None, description="air, sea, road")
    port_of_entry: Optional[str] = Field(None, description="Port/Airport name")

    def get_transport_mode(self) -> Optional[str]:
        """Determine transport mode from entry/exit code"""
        if not self.entry_exit_code:
            return None

        code = self.entry_exit_code.upper()
        if "KIA" in code or "AIRPORT" in code:
            return "air"
        elif "TMA" in code or "PORT" in code or "HARBOR" in code:
            return "sea"
        elif "BORDER" in code or "LAND" in code:
            return "road"
        return None


class BOESection25Item(BaseModel):
    """Section 25: Description of Goods (per line item)"""
    line_number: Optional[int] = None
    description: Optional[str] = Field(None, description="Detailed description of goods")
    marks_and_numbers: Optional[str] = Field(None, description="Package marks/numbers")


class BOESection31Item(BaseModel):
    """Section 31: Tariff Information (per line item)"""
    line_number: Optional[int] = None
    hs_code: Optional[str] = Field(None, description="HS/Tariff code")
    country_of_origin: Optional[str] = Field(None, max_length=3)
    quantity: Optional[Decimal] = None
    unit_of_measure: Optional[str] = Field(None, max_length=20)
    net_weight: Optional[Decimal] = None
    unit_value: Optional[Decimal] = None
    total_value: Optional[Decimal] = None


class BOESection40Item(BaseModel):
    """Section 40: Duty and Tax Calculation (per line item)"""
    line_number: Optional[int] = None
    duty_rate_percent: Optional[Decimal] = Field(None, description="Duty rate %")
    duty_amount: Optional[Decimal] = Field(None, description="Calculated duty")
    vat_rate_percent: Optional[Decimal] = Field(None, description="VAT rate %")
    vat_amount: Optional[Decimal] = Field(None, description="Calculated VAT")
    nhil_amount: Optional[Decimal] = Field(None, description="NHIL amount")
    getfund_amount: Optional[Decimal] = Field(None, description="GETFUND amount")
    total_amount: Optional[Decimal] = Field(None, description="Total duties and taxes")


class BOEStructuredData(BaseModel):
    """Complete BOE with section-specific extraction"""

    # Basic BOE info
    declaration_number: Optional[str] = None
    declaration_date: Optional[date] = None

    # Section 16: Currency
    section_16: Optional[BOESection16] = None

    # Section 21: Mode of Shipment
    section_21: Optional[BOESection21] = None

    # Section 25: Descriptions
    section_25: List[BOESection25Item] = Field(default_factory=list)

    # Section 31: Tariff Info
    section_31: List[BOESection31Item] = Field(default_factory=list)

    # Section 40: Duty Calculations
    section_40: List[BOESection40Item] = Field(default_factory=list)

    # Aggregate values
    total_customs_value: Optional[Decimal] = None
    total_duty: Optional[Decimal] = None
    total_vat: Optional[Decimal] = None
    grand_total: Optional[Decimal] = None

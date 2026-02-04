"""
SQLAlchemy models for all database tables.
"""

from datetime import datetime
from uuid import uuid4
from typing import List

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Integer,
    Numeric,
    Text,
    ForeignKey,
    Date,
    Index,
    Enum,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
import enum

from .connection import Base


def generate_uuid() -> str:
    """Generate UUID as string"""
    return str(uuid4())


class ExtractionStatus(enum.Enum):
    """Extraction status enum."""
    complete = "complete"
    incomplete = "incomplete"
    failed = "failed"


class Shipment(Base):
    """Shipment - central entity linking all documents"""

    __tablename__ = "shipments"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=generate_uuid
    )
    shipment_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    supplier_name: Mapped[str | None] = mapped_column(String(255))
    consignee_name: Mapped[str | None] = mapped_column(String(255))
    incoterm: Mapped[str | None] = mapped_column(String(10))  # CFR, CIF, FCA
    transport_mode: Mapped[str | None] = mapped_column(String(20))  # sea, air
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)  # pending, validated, errors
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    invoices: Mapped[List["Invoice"]] = relationship("Invoice", back_populates="shipment", cascade="all, delete-orphan")
    bill_of_entries: Mapped[List["BillOfEntry"]] = relationship("BillOfEntry", back_populates="shipment", cascade="all, delete-orphan")
    packing_lists: Mapped[List["PackingList"]] = relationship("PackingList", back_populates="shipment", cascade="all, delete-orphan")
    certificates_of_origin: Mapped[List["CertificateOfOrigin"]] = relationship("CertificateOfOrigin", back_populates="shipment", cascade="all, delete-orphan")
    freight_documents: Mapped[List["FreightDocument"]] = relationship("FreightDocument", back_populates="shipment", cascade="all, delete-orphan")
    validation_results: Mapped[List["ValidationResult"]] = relationship("ValidationResult", back_populates="shipment", cascade="all, delete-orphan")
    audit_logs: Mapped[List["AuditLog"]] = relationship("AuditLog", back_populates="shipment", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Shipment(id={self.id}, number={self.shipment_number}, status={self.status})>"


class Invoice(Base):
    """Invoice document"""

    __tablename__ = "invoices"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    shipment_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("shipments.id", ondelete="CASCADE"), index=True)

    # Document metadata
    document_url: Mapped[str | None] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Extraction metadata
    extraction_status: Mapped[str] = mapped_column(Enum(ExtractionStatus, name='extraction_status_enum'), nullable=False, server_default='incomplete')
    extraction_confidence: Mapped[float | None] = mapped_column(Numeric(5, 2))
    raw_data: Mapped[dict | None] = mapped_column(JSONB)

    # Invoice details
    invoice_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    invoice_date: Mapped[datetime | None] = mapped_column(Date)

    # Parties
    consignee_name: Mapped[str | None] = mapped_column(String(255))
    consignee_address: Mapped[str | None] = mapped_column(Text)
    shipper_name: Mapped[str | None] = mapped_column(String(255))
    shipper_address: Mapped[str | None] = mapped_column(Text)

    # Terms
    incoterm: Mapped[str | None] = mapped_column(String(10))
    currency: Mapped[str] = mapped_column(String(3), default="USD")

    # Values
    total_fob_value: Mapped[float | None] = mapped_column(Numeric(15, 2))
    freight_value: Mapped[float | None] = mapped_column(Numeric(15, 2))
    insurance_value: Mapped[float | None] = mapped_column(Numeric(15, 2))
    total_invoice_value: Mapped[float | None] = mapped_column(Numeric(15, 2))

    # Metadata
    language: Mapped[str | None] = mapped_column(String(10))  # en, fr
    raw_parsed_data: Mapped[dict | None] = mapped_column(JSONB)
    document_id: Mapped[str | None] = mapped_column(String(255), index=True)  # Original document ID from API
    original_filename: Mapped[str | None] = mapped_column(String(500))  # Original uploaded filename

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    shipment: Mapped["Shipment"] = relationship("Shipment", back_populates="invoices")
    items: Mapped[List["InvoiceItem"]] = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Invoice(id={self.id}, number={self.invoice_number})>"


class InvoiceItem(Base):
    """Invoice line item"""

    __tablename__ = "invoice_items"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    invoice_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("invoices.id", ondelete="CASCADE"), index=True)

    line_number: Mapped[int | None] = mapped_column(Integer)
    product_description: Mapped[str | None] = mapped_column(Text)
    hs_code: Mapped[str | None] = mapped_column(String(10), index=True)
    country_of_origin: Mapped[str | None] = mapped_column(String(3))

    quantity: Mapped[float | None] = mapped_column(Numeric(15, 3))
    unit_of_measure: Mapped[str | None] = mapped_column(String(20))
    unit_price: Mapped[float | None] = mapped_column(Numeric(15, 2))
    total_value: Mapped[float | None] = mapped_column(Numeric(15, 2))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="items")

    def __repr__(self) -> str:
        return f"<InvoiceItem(id={self.id}, hs_code={self.hs_code})>"


class BillOfEntry(Base):
    """Bill of Entry (BOE) document"""

    __tablename__ = "bill_of_entries"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    shipment_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("shipments.id", ondelete="CASCADE"), index=True)

    # Document metadata
    document_url: Mapped[str | None] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Extraction metadata
    extraction_status: Mapped[str] = mapped_column(Enum(ExtractionStatus, name='extraction_status_enum'), nullable=False, server_default='incomplete')
    extraction_confidence: Mapped[float | None] = mapped_column(Numeric(5, 2))
    raw_data: Mapped[dict | None] = mapped_column(JSONB)

    # BOE details
    declaration_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    declaration_date: Mapped[datetime | None] = mapped_column(Date)

    # Parties
    consignee_name: Mapped[str | None] = mapped_column(String(255))
    consignee_address: Mapped[str | None] = mapped_column(Text)
    shipper_name: Mapped[str | None] = mapped_column(String(255))
    shipper_address: Mapped[str | None] = mapped_column(Text)

    # Values
    fob_value: Mapped[float | None] = mapped_column(Numeric(15, 2))
    freight_value: Mapped[float | None] = mapped_column(Numeric(15, 2))
    insurance_value: Mapped[float | None] = mapped_column(Numeric(15, 2))
    cif_value: Mapped[float | None] = mapped_column(Numeric(15, 2))
    duty_value: Mapped[float | None] = mapped_column(Numeric(15, 2))

    currency: Mapped[str] = mapped_column(String(3), default="USD")

    # Metadata
    raw_parsed_data: Mapped[dict | None] = mapped_column(JSONB)
    document_id: Mapped[str | None] = mapped_column(String(255), index=True)  # Original document ID from API
    original_filename: Mapped[str | None] = mapped_column(String(500))  # Original uploaded filename

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    shipment: Mapped["Shipment"] = relationship("Shipment", back_populates="bill_of_entries")
    items: Mapped[List["BOEItem"]] = relationship("BOEItem", back_populates="boe", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<BillOfEntry(id={self.id}, declaration={self.declaration_number})>"


class BOEItem(Base):
    """BOE line item"""

    __tablename__ = "boe_items"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    boe_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("bill_of_entries.id", ondelete="CASCADE"), index=True)

    line_number: Mapped[int | None] = mapped_column(Integer)
    product_description: Mapped[str | None] = mapped_column(Text)
    hs_code: Mapped[str | None] = mapped_column(String(10), index=True)
    country_of_origin: Mapped[str | None] = mapped_column(String(3))

    quantity: Mapped[float | None] = mapped_column(Numeric(15, 3))
    unit_of_measure: Mapped[str | None] = mapped_column(String(20))
    unit_value: Mapped[float | None] = mapped_column(Numeric(15, 2))
    total_value: Mapped[float | None] = mapped_column(Numeric(15, 2))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    boe: Mapped["BillOfEntry"] = relationship("BillOfEntry", back_populates="items")

    def __repr__(self) -> str:
        return f"<BOEItem(id={self.id}, hs_code={self.hs_code})>"


class PackingList(Base):
    """Packing List document"""

    __tablename__ = "packing_lists"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    shipment_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("shipments.id", ondelete="CASCADE"), index=True)

    # Document metadata
    document_url: Mapped[str | None] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Packing list details
    packing_list_number: Mapped[str | None] = mapped_column(String(100))
    packing_date: Mapped[datetime | None] = mapped_column(Date)

    # Parties
    consignee_name: Mapped[str | None] = mapped_column(String(255))
    shipper_name: Mapped[str | None] = mapped_column(String(255))

    # Shipping details
    total_packages: Mapped[int | None] = mapped_column(Integer)
    total_gross_weight: Mapped[float | None] = mapped_column(Numeric(15, 3))
    total_net_weight: Mapped[float | None] = mapped_column(Numeric(15, 3))
    weight_unit: Mapped[str] = mapped_column(String(10), default="KG")

    # Metadata
    raw_parsed_data: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    shipment: Mapped["Shipment"] = relationship("Shipment", back_populates="packing_lists")
    items: Mapped[List["PackingListItem"]] = relationship("PackingListItem", back_populates="packing_list", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<PackingList(id={self.id}, number={self.packing_list_number})>"


class PackingListItem(Base):
    """Packing List line item"""

    __tablename__ = "packing_list_items"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    packing_list_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("packing_lists.id", ondelete="CASCADE"), index=True)

    line_number: Mapped[int | None] = mapped_column(Integer)
    product_description: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[float | None] = mapped_column(Numeric(15, 3))
    unit_of_measure: Mapped[str | None] = mapped_column(String(20))

    package_number: Mapped[str | None] = mapped_column(String(50))
    gross_weight: Mapped[float | None] = mapped_column(Numeric(15, 3))
    net_weight: Mapped[float | None] = mapped_column(Numeric(15, 3))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    packing_list: Mapped["PackingList"] = relationship("PackingList", back_populates="items")

    def __repr__(self) -> str:
        return f"<PackingListItem(id={self.id})>"


class CertificateOfOrigin(Base):
    """Certificate of Origin document"""

    __tablename__ = "certificates_of_origin"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    shipment_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("shipments.id", ondelete="CASCADE"), index=True)

    # Document metadata
    document_url: Mapped[str | None] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Certificate details
    certificate_number: Mapped[str | None] = mapped_column(String(100))
    issue_date: Mapped[datetime | None] = mapped_column(Date)
    issuing_authority: Mapped[str | None] = mapped_column(String(255))

    # Parties
    exporter_name: Mapped[str | None] = mapped_column(String(255))
    exporter_address: Mapped[str | None] = mapped_column(Text)
    consignee_name: Mapped[str | None] = mapped_column(String(255))
    consignee_address: Mapped[str | None] = mapped_column(Text)

    # Origin
    country_of_origin: Mapped[str | None] = mapped_column(String(3))

    # Metadata
    raw_parsed_data: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    shipment: Mapped["Shipment"] = relationship("Shipment", back_populates="certificates_of_origin")
    items: Mapped[List["COOItem"]] = relationship("COOItem", back_populates="coo", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<CertificateOfOrigin(id={self.id}, number={self.certificate_number})>"


class COOItem(Base):
    """Certificate of Origin line item"""

    __tablename__ = "coo_items"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    coo_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("certificates_of_origin.id", ondelete="CASCADE"), index=True)

    line_number: Mapped[int | None] = mapped_column(Integer)
    product_description: Mapped[str | None] = mapped_column(Text)
    hs_code: Mapped[str | None] = mapped_column(String(10))
    country_of_origin: Mapped[str | None] = mapped_column(String(3))
    quantity: Mapped[float | None] = mapped_column(Numeric(15, 3))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    coo: Mapped["CertificateOfOrigin"] = relationship("CertificateOfOrigin", back_populates="items")

    def __repr__(self) -> str:
        return f"<COOItem(id={self.id}, hs_code={self.hs_code})>"


class FreightDocument(Base):
    """Freight document (Excel or PDF)"""

    __tablename__ = "freight_documents"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    shipment_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("shipments.id", ondelete="CASCADE"), index=True)

    # Document metadata
    document_url: Mapped[str | None] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Freight details
    contract_number: Mapped[str | None] = mapped_column(String(100))
    contract_period_start: Mapped[datetime | None] = mapped_column(Date)
    contract_period_end: Mapped[datetime | None] = mapped_column(Date)

    base_freight: Mapped[float | None] = mapped_column(Numeric(15, 2))
    bunker_adjustment: Mapped[float] = mapped_column(Numeric(15, 2), default=0)
    total_freight: Mapped[float | None] = mapped_column(Numeric(15, 2))

    currency: Mapped[str] = mapped_column(String(3), default="USD")
    transport_mode: Mapped[str | None] = mapped_column(String(20))  # sea, air

    # Metadata
    raw_parsed_data: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    shipment: Mapped["Shipment"] = relationship("Shipment", back_populates="freight_documents")

    def __repr__(self) -> str:
        return f"<FreightDocument(id={self.id}, contract={self.contract_number})>"


class ValidationResult(Base):
    """Validation results for a shipment"""

    __tablename__ = "validation_results"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    shipment_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("shipments.id", ondelete="CASCADE"), index=True)

    validation_type: Mapped[str | None] = mapped_column(String(50))  # invoice_vs_boe, etc.
    status: Mapped[str | None] = mapped_column(String(20), index=True)  # passed, failed, warning

    total_checks: Mapped[int | None] = mapped_column(Integer)
    passed_checks: Mapped[int | None] = mapped_column(Integer)
    failed_checks: Mapped[int | None] = mapped_column(Integer)
    accuracy_percentage: Mapped[float | None] = mapped_column(Numeric(5, 2))

    validation_details: Mapped[dict | None] = mapped_column(JSONB)

    validated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    shipment: Mapped["Shipment"] = relationship("Shipment", back_populates="validation_results")
    errors: Mapped[List["ValidationError"]] = relationship("ValidationError", back_populates="validation_result", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ValidationResult(id={self.id}, status={self.status}, accuracy={self.accuracy_percentage})>"


class ValidationError(Base):
    """Individual validation error"""

    __tablename__ = "validation_errors"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    validation_result_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("validation_results.id", ondelete="CASCADE"), index=True)

    field_name: Mapped[str | None] = mapped_column(String(255))
    error_type: Mapped[str | None] = mapped_column(String(50))  # mismatch, missing, calculation_error
    severity: Mapped[str | None] = mapped_column(String(20), index=True)  # high, medium, low

    expected_value: Mapped[str | None] = mapped_column(Text)
    actual_value: Mapped[str | None] = mapped_column(Text)

    source_document: Mapped[str | None] = mapped_column(String(50))  # invoice, boe, etc.
    target_document: Mapped[str | None] = mapped_column(String(50))

    correction_suggestion: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    validation_result: Mapped["ValidationResult"] = relationship("ValidationResult", back_populates="errors")

    def __repr__(self) -> str:
        return f"<ValidationError(id={self.id}, field={self.field_name}, severity={self.severity})>"


class AuditLog(Base):
    """Audit log for all system actions"""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=generate_uuid)
    shipment_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("shipments.id", ondelete="CASCADE"), index=True)

    action: Mapped[str | None] = mapped_column(String(100), index=True)  # document_uploaded, etc.
    entity_type: Mapped[str | None] = mapped_column(String(50))  # invoice, boe, shipment
    entity_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))

    user_id: Mapped[str | None] = mapped_column(String(100))  # For future user tracking
    details: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    shipment: Mapped["Shipment"] = relationship("Shipment", back_populates="audit_logs")

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action={self.action})>"

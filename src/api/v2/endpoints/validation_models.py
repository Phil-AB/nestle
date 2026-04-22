"""Shared request/response models for validation endpoints."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------

class CreateValidationSessionRequest(BaseModel):
    use_case: str
    documents: Dict[str, Dict[str, Any]]
    tolerance_overrides: Optional[Dict[str, float]] = None
    user_provided_data: Optional[Dict[str, Any]] = None


class CreateValidationSessionResponse(BaseModel):
    session_id: str
    use_case: str
    version: int
    status: str
    message: str


class ValidationStatusResponse(BaseModel):
    session_id: str
    use_case: str
    version: int
    current_step: str
    workflow_status: str
    final_status: Optional[str]
    summary: Dict[str, Any]
    created_at: str
    updated_at: str


class RunValidationRequest(BaseModel):
    skip_steps: Optional[List[str]] = None


class UserConfirmationRequest(BaseModel):
    discrepancy_id: str
    confirmed: bool
    comment: Optional[str] = None


class UserDataRequest(BaseModel):
    field_name: str
    value: Any


class ValidationReportResponse(BaseModel):
    session_id: str
    use_case: str
    final_status: str
    summary: Dict[str, Any]
    results: Dict[str, Any]
    discrepancies: Dict[str, Any]
    accuracy: Dict[str, Any]
    top_discrepancies: List[Dict[str, Any]]


# ---------------------------------------------------------------------------
# Pipeline (Shipments)
# ---------------------------------------------------------------------------

class CreateShipmentRequest(BaseModel):
    shipment_number: Optional[str] = None
    supplier_name: Optional[str] = None
    consignee_name: Optional[str] = None
    incoterm: Optional[str] = None
    transport_mode: Optional[str] = None


class DiscrepancyConfirmation(BaseModel):
    discrepancy_id: str
    confirmed: bool
    comment: Optional[str] = None


class ResumeSessionRequest(BaseModel):
    confirmations: List[DiscrepancyConfirmation] = []
    user_input: Optional[Dict[str, Any]] = None

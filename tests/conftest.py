"""Shared test fixtures and configuration"""

import sys
from pathlib import Path
import pytest
from decimal import Decimal

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def sample_boe_data():
    """Sample Bill of Entry data"""
    return {
        "document_id": "BOE-2024-001",
        "hs_code": "1806.32",
        "net_weight": 1000.0,
        "gross_weight": 1100.0,
        "quantity": 500,
        "duty_rate": 0.20,
        "duty_amount": 5000.0,
        "customs_value": 100000.0,
        "customs_code": "40E68",
        "amount_payable": 5000.0,
        "vat_amount": 5000.0,
        "shipper_name": "Global Exports Ltd",
        "consignee_name": "Nestle Ghana Ltd",
        "section_21": {
            "entry_exit_code": "KIA"
        },
        "cif_value": 110000.0,
        "description": "Chocolate bars"
    }


@pytest.fixture
def sample_invoice_data():
    """Sample Invoice data"""
    return {
        "invoice_number": "INV-2024-001",
        "hs_code": "1806.32",
        "net_weight": 1000.0,
        "unit_price": 200.0,
        "quantity": 500,
        "total_fob_value": 100000.0,
        "freight_value": 5000.0,
        "insurance_value": 5000.0,
        "incoterm": "CIF",
        "shipper_name": "Global Exports Limited",
        "consignee_name": "Nestle Ghana Limited",
        "description": "Chocolate bars"
    }


@pytest.fixture
def sample_packing_list_data():
    """Sample Packing List data"""
    return {
        "packing_list_number": "PL-2024-001",
        "hs_code": "1806.32",
        "net_weight": 1000.0,
        "gross_weight": 1100.0,
        "quantity": 500
    }


@pytest.fixture
def sample_bill_of_lading_data():
    """Sample Bill of Lading data"""
    return {
        "bl_number": "BL-2024-001",
        "shipper_name": "Global Exports Ltd.",
        "consignee_name": "Nestle Ghana Ltd.",
        "gross_weight": 1100.0
    }


@pytest.fixture
def sample_airway_bill_data():
    """Sample Air Waybill data"""
    return {
        "awb_number": "AWB-2024-001",
        "shipper_name": "Global Exports Ltd",
        "consignee_name": "Nestle Ghana Ltd",
        "gross_weight": 1100.0
    }


@pytest.fixture
def validation_context(sample_boe_data, sample_invoice_data, sample_packing_list_data):
    """Sample ValidationContext"""
    from modules.validation_engine.core.base import ValidationContext
    from uuid import uuid4
    from datetime import datetime

    return ValidationContext(
        session_id=uuid4(),
        use_case="boe_validation",
        version=1,
        documents={
            "bill_of_entry": sample_boe_data,
            "invoice": sample_invoice_data,
            "packing_list": sample_packing_list_data
        },
        normalized_data={
            "bill_of_entry": sample_boe_data,
            "invoice": sample_invoice_data,
            "packing_list": sample_packing_list_data
        },
        primary_document="bill_of_entry",
        supporting_documents=["invoice", "packing_list"],
        config={},
        discrepancies=[],
        validation_results=[],
        user_confirmations={},
        user_provided_data={},
        tolerance_overrides={},
        step_results={},
        workflow_state="initialized",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

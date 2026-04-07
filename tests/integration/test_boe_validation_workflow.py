"""Integration tests for complete BOE validation workflow"""

import pytest
from uuid import uuid4
from modules.validation_engine import get_validation_engine


@pytest.mark.asyncio
class TestBOEValidationWorkflow:
    """Test the complete 12-step BOE validation workflow"""

    @pytest.fixture
    async def engine(self):
        """Get validation engine instance"""
        return get_validation_engine()

    @pytest.fixture
    def complete_valid_boe_documents(self):
        """Complete set of valid BOE documents"""
        return {
            "bill_of_entry": {
                "document_id": "BOE-TEST-001",
                "hs_code": "1806.32",
                "net_weight": 1000.0,
                "gross_weight": 1100.0,
                "quantity": 500,
                "duty_rate": 0.20,
                "duty_amount": 20000.0,
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
                "description": "Chocolate products"
            },
            "invoice": {
                "invoice_number": "INV-TEST-001",
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
                "description": "Chocolate products"
            },
            "packing_list": {
                "packing_list_number": "PL-TEST-001",
                "hs_code": "1806.32",
                "net_weight": 1000.0,
                "gross_weight": 1100.0,
                "quantity": 500
            },
            "airway_bill": {
                "awb_number": "AWB-TEST-001",
                "shipper_name": "Global Exports Ltd.",
                "consignee_name": "Nestle Ghana Ltd.",
                "gross_weight": 1100.0
            }
        }

    async def test_complete_workflow_valid_documents(self, engine, complete_valid_boe_documents):
        """Test complete workflow with valid documents"""
        # Create session
        context = await engine.create_validation_session(
            use_case="boe_validation",
            documents=complete_valid_boe_documents
        )

        assert context is not None
        assert context.session_id is not None
        assert context.use_case == "boe_validation"
        assert len(context.documents) == 4

        # Run validation workflow
        from modules.validation_engine.orchestration import get_validation_workflow
        workflow = get_validation_workflow()

        final_state = await workflow.run(
            session_id=context.session_id,
            documents=complete_valid_boe_documents,
            config=context.config,
            primary_document="bill_of_entry",
            supporting_documents=["invoice", "packing_list", "airway_bill"]
        )

        assert final_state is not None
        assert "workflow_status" in final_state
        assert len(final_state.get("completed_steps", [])) == 12  # All 12 steps

    async def test_workflow_hs_code_mismatch(self, engine, complete_valid_boe_documents):
        """Test workflow catches HS code mismatch (Step 3)"""
        # Make HS code mismatch
        complete_valid_boe_documents["invoice"]["hs_code"] = "9999.99"

        context = await engine.create_validation_session(
            use_case="boe_validation",
            documents=complete_valid_boe_documents
        )

        from modules.validation_engine.orchestration import get_validation_workflow
        workflow = get_validation_workflow()

        final_state = await workflow.run(
            session_id=context.session_id,
            documents=complete_valid_boe_documents,
            config=context.config,
            primary_document="bill_of_entry",
            supporting_documents=["invoice", "packing_list", "airway_bill"]
        )

        # Should have critical discrepancy
        from modules.validation_engine.core.session_manager import get_session_manager
        session_manager = get_session_manager()
        updated_context = session_manager.get_session(context.session_id)

        critical_discs = [d for d in updated_context.discrepancies if d.severity == "CRITICAL"]
        assert len(critical_discs) > 0
        assert any("hs_code" in d.field_name.lower() for d in critical_discs)

    async def test_workflow_customs_code_40V02(self, engine, complete_valid_boe_documents):
        """Test workflow validates customs code 40V02 (VAT exempt)"""
        # Set up 40V02 scenario
        complete_valid_boe_documents["bill_of_entry"]["customs_code"] = "40V02"
        complete_valid_boe_documents["bill_of_entry"]["amount_payable"] = 0.0
        complete_valid_boe_documents["bill_of_entry"]["amount_exempted"] = 5000.0

        context = await engine.create_validation_session(
            use_case="boe_validation",
            documents=complete_valid_boe_documents
        )

        from modules.validation_engine.orchestration import get_validation_workflow
        workflow = get_validation_workflow()

        final_state = await workflow.run(
            session_id=context.session_id,
            documents=complete_valid_boe_documents,
            config=context.config,
            primary_document="bill_of_entry",
            supporting_documents=["invoice", "packing_list", "airway_bill"]
        )

        # Should pass customs code validation (Step 9)
        assert "completed_steps" in final_state
        assert any("customs_code" in step for step in final_state.get("completed_steps", []))

    async def test_workflow_incoterm_cfr_missing_freight(self, engine, complete_valid_boe_documents):
        """Test workflow catches missing freight for CFR incoterm"""
        # Set CFR but no freight
        complete_valid_boe_documents["invoice"]["incoterm"] = "CFR"
        complete_valid_boe_documents["invoice"]["freight_value"] = None

        context = await engine.create_validation_session(
            use_case="boe_validation",
            documents=complete_valid_boe_documents
        )

        from modules.validation_engine.orchestration import get_validation_workflow
        workflow = get_validation_workflow()

        final_state = await workflow.run(
            session_id=context.session_id,
            documents=complete_valid_boe_documents,
            config=context.config,
            primary_document="bill_of_entry",
            supporting_documents=["invoice", "packing_list", "airway_bill"]
        )

        # Should have discrepancy for missing freight
        from modules.validation_engine.core.session_manager import get_session_manager
        session_manager = get_session_manager()
        updated_context = session_manager.get_session(context.session_id)

        freight_discs = [d for d in updated_context.discrepancies
                        if "freight" in d.message.lower() and "CFR" in d.message]
        assert len(freight_discs) > 0

    async def test_workflow_mode_mismatch_kia_with_bl(self, engine, complete_valid_boe_documents):
        """Test workflow catches mode mismatch: KIA with BL instead of AWB"""
        # Replace AWB with BL (wrong!)
        del complete_valid_boe_documents["airway_bill"]
        complete_valid_boe_documents["bill_of_lading"] = {
            "bl_number": "BL-WRONG-001",
            "shipper_name": "Global Exports Ltd",
            "consignee_name": "Nestle Ghana Ltd"
        }

        context = await engine.create_validation_session(
            use_case="boe_validation",
            documents=complete_valid_boe_documents
        )

        from modules.validation_engine.orchestration import get_validation_workflow
        workflow = get_validation_workflow()

        final_state = await workflow.run(
            session_id=context.session_id,
            documents=complete_valid_boe_documents,
            config=context.config,
            primary_document="bill_of_entry",
            supporting_documents=["invoice", "packing_list", "bill_of_lading"]
        )

        # Should have mode mismatch discrepancy
        from modules.validation_engine.core.session_manager import get_session_manager
        session_manager = get_session_manager()
        updated_context = session_manager.get_session(context.session_id)

        mode_discs = [d for d in updated_context.discrepancies
                     if "transport" in d.message.lower() or "awb" in d.message.lower()]
        assert len(mode_discs) > 0

    async def test_workflow_performance_under_30_seconds(self, engine, complete_valid_boe_documents):
        """Test workflow completes within 30 seconds (performance target)"""
        import time

        context = await engine.create_validation_session(
            use_case="boe_validation",
            documents=complete_valid_boe_documents
        )

        from modules.validation_engine.orchestration import get_validation_workflow
        workflow = get_validation_workflow()

        start_time = time.time()

        await workflow.run(
            session_id=context.session_id,
            documents=complete_valid_boe_documents,
            config=context.config,
            primary_document="bill_of_entry",
            supporting_documents=["invoice", "packing_list", "airway_bill"]
        )

        elapsed_time = time.time() - start_time

        # Should complete in under 30 seconds
        assert elapsed_time < 30.0, f"Workflow took {elapsed_time:.2f}s, expected < 30s"

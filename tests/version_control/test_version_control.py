"""Tests for version control module"""

import pytest
from uuid import uuid4
from datetime import datetime

from modules.validation_engine.version_control import (
    get_version_manager,
    get_delta_analyzer,
    get_revalidation_engine,
    VersionStatus,
    ChangeType,
    RevalidationRequest
)
from modules.validation_engine.core.base import (
    ValidationContext,
    Discrepancy,
    ValidationResult
)


@pytest.fixture
def sample_context_v1():
    """Sample validation context V1 with discrepancies"""
    return ValidationContext(
        session_id=uuid4(),
        use_case="boe_validation",
        version=1,
        documents={
            "bill_of_entry": {"net_weight": "1000 KG"},
            "invoice": {"net_weight": "999 KG"}
        },
        config={},
        discrepancies=[
            Discrepancy(
                field_name="net_weight",
                source_document="bill_of_entry",
                target_document="invoice",
                source_value="1000 KG",
                target_value="999 KG",
                discrepancy_type="value_mismatch",
                severity="critical",
                confidence=0.95,
                category="weight",
                likely_cause="measurement_difference",
                impact="high"
            ),
            Discrepancy(
                field_name="hs_code",
                source_document="bill_of_entry",
                target_document="invoice",
                source_value="1234.56",
                target_value="1234.57",
                discrepancy_type="value_mismatch",
                severity="major",
                confidence=0.90,
                category="hs_code",
                likely_cause="ocr_error",
                impact="medium"
            )
        ],
        validation_results=[
            ValidationResult(
                validator_name="tolerance_validator",
                field_name="net_weight",
                passed=False,
                confidence=0.95,
                message="Weight exceeds tolerance"
            ),
            ValidationResult(
                validator_name="exact_match_validator",
                field_name="hs_code",
                passed=False,
                confidence=0.90,
                message="HS Code mismatch"
            )
        ]
    )


@pytest.fixture
def sample_context_v2():
    """Sample validation context V2 with fixed weight issue"""
    context = ValidationContext(
        session_id=uuid4(),
        use_case="boe_validation",
        version=2,
        documents={
            "bill_of_entry": {"net_weight": "999.5 KG"},
            "invoice": {"net_weight": "999 KG"}
        },
        config={},
        is_revalidation=True,
        discrepancies=[
            # Weight issue fixed, but HS code still wrong
            Discrepancy(
                field_name="hs_code",
                source_document="bill_of_entry",
                target_document="invoice",
                source_value="1234.56",
                target_value="1234.57",
                discrepancy_type="value_mismatch",
                severity="minor",  # Improved from major to minor
                confidence=0.90,
                category="hs_code",
                likely_cause="ocr_error",
                impact="low"
            ),
            # New discrepancy appeared
            Discrepancy(
                field_name="invoice_date",
                source_document="bill_of_entry",
                target_document="invoice",
                source_value="2025-01-01",
                target_value="2025-01-02",
                discrepancy_type="value_mismatch",
                severity="minor",
                confidence=0.85,
                category="date",
                likely_cause="data_entry_error",
                impact="low"
            )
        ],
        validation_results=[
            ValidationResult(
                validator_name="tolerance_validator",
                field_name="net_weight",
                passed=True,
                confidence=0.98,
                message="Weight within tolerance"
            ),
            ValidationResult(
                validator_name="exact_match_validator",
                field_name="hs_code",
                passed=False,
                confidence=0.90,
                message="HS Code mismatch"
            ),
            ValidationResult(
                validator_name="exact_match_validator",
                field_name="invoice_date",
                passed=False,
                confidence=0.85,
                message="Date mismatch"
            )
        ]
    )
    return context


class TestVersionManager:
    """Test version manager functionality"""

    @pytest.mark.asyncio
    async def test_create_version_metadata(self, sample_context_v1):
        """Test version metadata creation"""
        manager = get_version_manager()

        metadata = await manager.create_version_metadata(
            sample_context_v1,
            created_by="test_user",
            notes="Initial validation",
            tags=["test", "v1"]
        )

        assert metadata.session_id == sample_context_v1.session_id
        assert metadata.version == 1
        assert metadata.status == VersionStatus.ACTIVE
        assert metadata.total_validations == 2
        assert metadata.passed_validations == 0
        assert metadata.total_discrepancies == 2
        assert metadata.critical_count == 1
        assert metadata.major_count == 1
        assert metadata.final_status == "failed"
        assert metadata.created_by == "test_user"
        assert "test" in metadata.tags

    @pytest.mark.asyncio
    async def test_get_version_metadata(self, sample_context_v1):
        """Test retrieving version metadata"""
        manager = get_version_manager()

        # Create metadata
        await manager.create_version_metadata(sample_context_v1)

        # Retrieve metadata
        retrieved = await manager.get_version_metadata(
            sample_context_v1.session_id, 1
        )

        assert retrieved is not None
        assert retrieved.version == 1
        assert retrieved.total_discrepancies == 2

    @pytest.mark.asyncio
    async def test_version_history(self, sample_context_v1):
        """Test version history retrieval"""
        manager = get_version_manager()
        session_id = sample_context_v1.session_id

        # Create multiple versions
        await manager.create_version_metadata(sample_context_v1)

        context_v2 = sample_context_v1.copy()
        context_v2.version = 2
        await manager.create_version_metadata(context_v2)

        # Get history
        history = await manager.get_version_history(session_id)

        assert len(history) == 2
        assert history[0].version == 1
        assert history[1].version == 2

    @pytest.mark.asyncio
    async def test_update_version_status(self, sample_context_v1):
        """Test version status update"""
        manager = get_version_manager()

        await manager.create_version_metadata(sample_context_v1)

        # Update status
        success = await manager.update_version_status(
            sample_context_v1.session_id, 1, VersionStatus.SUPERSEDED
        )

        assert success is True

        # Verify update
        metadata = await manager.get_version_metadata(
            sample_context_v1.session_id, 1
        )
        assert metadata.status == VersionStatus.SUPERSEDED

    @pytest.mark.asyncio
    async def test_version_lineage(self, sample_context_v1):
        """Test version lineage tracking"""
        manager = get_version_manager()

        # V1
        await manager.create_version_metadata(sample_context_v1)

        # V2 (child of V1)
        context_v2 = sample_context_v1.copy()
        context_v2.session_id = uuid4()
        context_v2.version = 2
        context_v2.is_revalidation = True
        context_v2.previous_version_id = sample_context_v1.session_id
        await manager.create_version_metadata(context_v2)

        # Get lineage
        lineage = await manager.get_lineage(context_v2.session_id, 2)

        assert len(lineage) == 2
        assert lineage[0]["version"] == 1
        assert lineage[1]["version"] == 2


class TestDeltaAnalyzer:
    """Test delta analyzer functionality"""

    @pytest.mark.asyncio
    async def test_compare_versions(self, sample_context_v1, sample_context_v2):
        """Test version comparison"""
        analyzer = get_delta_analyzer()

        comparison = await analyzer.compare(
            sample_context_v1, sample_context_v2
        )

        # V1 had: net_weight (critical), hs_code (major)
        # V2 has: hs_code (minor), invoice_date (minor)

        # net_weight: FIXED (in V1, not in V2)
        # hs_code: IMPROVED (major → minor)
        # invoice_date: NEW (not in V1, in V2)

        assert comparison.fixed_count == 1  # net_weight
        assert comparison.new_count == 1    # invoice_date
        assert comparison.persistent_count == 1  # hs_code
        assert comparison.improved_count == 1    # hs_code severity improved

        # Check specific changes
        changes_by_field = {c.field_name: c for c in comparison.changes}

        # net_weight should be FIXED
        assert changes_by_field["net_weight"].change_type == ChangeType.FIXED
        assert changes_by_field["net_weight"].v1_present is True
        assert changes_by_field["net_weight"].v2_present is False

        # hs_code should be IMPROVED
        assert changes_by_field["hs_code"].change_type == ChangeType.IMPROVED
        assert changes_by_field["hs_code"].v1_severity == "major"
        assert changes_by_field["hs_code"].v2_severity == "minor"

        # invoice_date should be NEW
        assert changes_by_field["invoice_date"].change_type == ChangeType.NEW
        assert changes_by_field["invoice_date"].v1_present is False
        assert changes_by_field["invoice_date"].v2_present is True

    @pytest.mark.asyncio
    async def test_improvement_rate_calculation(
        self, sample_context_v1, sample_context_v2
    ):
        """Test improvement rate calculation"""
        analyzer = get_delta_analyzer()

        comparison = await analyzer.compare(
            sample_context_v1, sample_context_v2
        )

        # V1 had 2 discrepancies, 1 fixed
        # Improvement rate = 1/2 * 100 = 50%
        assert comparison.improvement_rate == 50.0

        # V1 had 2 discrepancies, 1 new appeared
        # Regression rate = 1/2 * 100 = 50%
        assert comparison.regression_rate == 50.0

    @pytest.mark.asyncio
    async def test_change_summary(self, sample_context_v1, sample_context_v2):
        """Test change summary generation"""
        analyzer = get_delta_analyzer()

        comparison = await analyzer.compare(
            sample_context_v1, sample_context_v2
        )

        summary = await analyzer.get_change_summary(comparison)

        assert "overall_assessment" in summary
        assert "key_metrics" in summary
        assert "recommendations" in summary

        # Should have positive assessment (50% improvement)
        assert "Fair" in summary["overall_assessment"] or "Good" in summary["overall_assessment"]


class TestRevalidationEngine:
    """Test revalidation engine functionality"""

    @pytest.mark.asyncio
    async def test_suggest_revalidation(self, sample_context_v1):
        """Test revalidation suggestion"""
        engine = get_revalidation_engine()
        manager = get_version_manager()

        # Create version metadata
        await manager.create_version_metadata(sample_context_v1)

        # Get suggestion
        suggestion = await engine.suggest_revalidation(
            sample_context_v1.session_id
        )

        # Should recommend revalidation (has critical discrepancy)
        assert suggestion["recommended"] is True
        assert suggestion["confidence"] == "high"
        assert len(suggestion["reasons"]) > 0

    @pytest.mark.asyncio
    async def test_suggest_no_revalidation(self):
        """Test suggestion when revalidation not needed"""
        engine = get_revalidation_engine()
        manager = get_version_manager()

        # Perfect validation (no discrepancies)
        perfect_context = ValidationContext(
            session_id=uuid4(),
            use_case="boe_validation",
            version=1,
            documents={},
            config={},
            discrepancies=[],
            validation_results=[
                ValidationResult(
                    validator_name="test",
                    field_name="test",
                    passed=True,
                    confidence=1.0,
                    message="Passed"
                )
            ]
        )

        await manager.create_version_metadata(perfect_context)

        suggestion = await engine.suggest_revalidation(
            perfect_context.session_id
        )

        # Should NOT recommend revalidation (perfect validation)
        assert suggestion["recommended"] is False


@pytest.mark.asyncio
async def test_full_revalidation_workflow():
    """Test complete revalidation workflow"""
    # This would be an integration test
    # Requires full validation engine setup
    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

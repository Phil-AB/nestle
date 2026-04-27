# Version Control Module

## Overview

The Version Control module provides comprehensive versioning capabilities for the validation engine, enabling:

- **Version Tracking**: Track validation sessions across multiple versions
- **Delta Analysis**: Compare V1 vs V2 to identify fixed/new/persistent discrepancies
- **Revalidation**: Create new validation versions with updated documents
- **Version Lineage**: Track ancestry chain across revalidations
- **Metadata Management**: Store comprehensive version metadata and statistics

## Architecture

### Components

```
version_control/
├── version_models.py      # Data models (VersionMetadata, VersionComparison, etc.)
├── version_manager.py     # Version tracking and metadata management
├── delta_analyzer.py      # V1 vs V2 comparison and delta analysis
└── revalidation_engine.py # Revalidation workflow orchestration
```

### Key Classes

1. **VersionManager**
   - Tracks version lineage
   - Stores version metadata
   - Manages version status transitions
   - Queries version history

2. **DeltaAnalyzer** (implements `IVersionComparator`)
   - Compares two validation versions
   - Identifies fixed/new/persistent discrepancies
   - Analyzes severity changes
   - Calculates improvement/regression rates

3. **RevalidationEngine**
   - Creates new validation versions
   - Orchestrates revalidation workflow
   - Generates comparison reports
   - Provides revalidation suggestions

## Data Models

### VersionMetadata

Comprehensive metadata for each validation version:

```python
{
    "session_id": UUID,
    "version": int,
    "status": "active|superseded|archived",
    "total_validations": int,
    "passed_validations": int,
    "total_discrepancies": int,
    "critical_count": int,
    "major_count": int,
    "minor_count": int,
    "info_count": int,
    "auto_fixed_count": int,
    "user_confirmed_count": int,
    "final_status": "passed|warning|partial|failed",
    "accuracy_score": float,
    "is_revalidation": bool,
    "previous_version_id": UUID,
    "parent_version": int,
    "created_at": datetime,
    "tags": ["tag1", "tag2"],
    "notes": "Version notes"
}
```

### VersionComparison

Delta analysis between two versions:

```python
{
    "v1_session_id": UUID,
    "v1_version": int,
    "v2_session_id": UUID,
    "v2_version": int,
    "total_changes": int,
    "fixed_count": int,          # Discrepancies in V1, not in V2
    "new_count": int,            # Discrepancies not in V1, in V2
    "persistent_count": int,     # Discrepancies in both V1 and V2
    "improved_count": int,       # Severity decreased
    "worsened_count": int,       # Severity increased
    "changes": [DiscrepancyChange],
    "improvement_rate": float,   # % of fixed discrepancies
    "regression_rate": float,    # % of new discrepancies
    "v1_final_status": str,
    "v2_final_status": str,
    "status_improved": bool,
    "v1_accuracy": float,
    "v2_accuracy": float,
    "accuracy_delta": float
}
```

### DiscrepancyChange

Details of a single discrepancy change:

```python
{
    "field_name": str,
    "change_type": "fixed|new|persistent|improved|worsened|value_changed",
    "v1_present": bool,
    "v1_severity": str,
    "v1_source_value": Any,
    "v1_target_value": Any,
    "v2_present": bool,
    "v2_severity": str,
    "v2_source_value": Any,
    "v2_target_value": Any,
    "severity_changed": bool,
    "values_changed": bool,
    "auto_fixed": bool
}
```

## Usage Examples

### 1. Create Revalidation

```python
from modules.validation_engine.version_control import (
    get_revalidation_engine, RevalidationRequest
)

# Create revalidation request
request = RevalidationRequest(
    original_session_id=original_session_id,
    revalidation_reason="Updated BOE document with corrected weights",
    updated_documents={
        "bill_of_entry": updated_boe_data
    },
    notes="Corrected net weight from 1000 KG to 999.5 KG",
    tags=["weight_correction", "revalidation"]
)

# Execute revalidation
engine = get_revalidation_engine()
result = await engine.create_revalidation(request)

print(f"New version: V{result.new_version}")
print(f"Fixed: {result.fixed_count}")
print(f"New issues: {result.new_count}")
print(f"Persistent: {result.persistent_count}")
```

### 2. Compare Versions

```python
from modules.validation_engine.version_control import get_delta_analyzer

analyzer = get_delta_analyzer()

# Compare V1 vs V2
comparison = await analyzer.compare(v1_context, v2_context)

print(f"Improvement rate: {comparison.improvement_rate}%")
print(f"Regression rate: {comparison.regression_rate}%")

# Get human-readable summary
summary = await analyzer.get_change_summary(comparison)
print(summary["overall_assessment"])
print(summary["recommendations"])
```

### 3. Get Version History

```python
from modules.validation_engine.version_control import get_version_manager

manager = get_version_manager()

# Get all versions for a session
versions = await manager.get_version_history(session_id)

for version in versions:
    print(f"V{version.version}: {version.final_status}")
    print(f"  Accuracy: {version.accuracy_score}%")
    print(f"  Discrepancies: {version.total_discrepancies}")
```

### 4. Get Version Lineage

```python
# Get ancestry chain
lineage = await manager.get_lineage(session_id, version=3)

# Shows: V1 → V2 → V3
for v in lineage:
    print(f"V{v['version']}: {v['final_status']} ({v['created_at']})")
```

### 5. Revalidation Suggestion

```python
# Get AI-powered suggestion
suggestion = await engine.suggest_revalidation(session_id)

if suggestion["recommended"]:
    print("Revalidation recommended:")
    for reason in suggestion["reasons"]:
        print(f"  - {reason}")
else:
    print("No revalidation needed")
```

## API Endpoints

### POST `/validation/sessions/{session_id}/revalidate`

Create a new validation version (revalidation).

**Request Body:**
```json
{
    "reason": "Updated BOE document with corrected weights",
    "updated_documents": {
        "bill_of_entry": {...}
    },
    "tolerance_overrides": {
        "net_weight": 0.5
    },
    "notes": "Corrected weight discrepancy",
    "tags": ["weight_correction"]
}
```

**Response:**
```json
{
    "new_session_id": "uuid",
    "new_version": 2,
    "original_session_id": "uuid",
    "original_version": 1,
    "status": "completed",
    "workflow_status": "completed",
    "final_status": "passed",
    "comparison": {...},
    "summary": {
        "total_discrepancies": 2,
        "fixed": 3,
        "new": 1,
        "persistent": 1
    }
}
```

### GET `/validation/sessions/{session_id}/versions`

Get version history for a session.

**Response:**
```json
{
    "session_id": "uuid",
    "total_versions": 3,
    "versions": [
        {
            "version": 1,
            "status": "superseded",
            "final_status": "partial",
            "accuracy_score": 87.5,
            "total_discrepancies": 5
        },
        ...
    ]
}
```

### GET `/validation/sessions/{session_id}/versions/{version}`

Get detailed version summary.

**Response:**
```json
{
    "session_id": "uuid",
    "version": 2,
    "status": "active",
    "final_status": "passed",
    "accuracy_score": 95.2,
    "validation_summary": {...},
    "discrepancy_summary": {...},
    "lineage": [...],
    "lineage_depth": 2
}
```

### POST `/validation/versions/compare`

Compare two validation versions.

**Request Body:**
```json
{
    "v1_session_id": "uuid",
    "v2_session_id": "uuid"
}
```

**Response:**
```json
{
    "comparison": {
        "fixed_count": 3,
        "new_count": 1,
        "persistent_count": 1,
        "improvement_rate": 60.0,
        "changes": [...]
    },
    "summary": {
        "overall_assessment": "Good: Significant progress made",
        "critical_changes": [...],
        "recommendations": [...]
    }
}
```

### GET `/validation/sessions/{session_id}/revalidation-history`

Get revalidation history with comparisons.

**Response:**
```json
{
    "session_id": "uuid",
    "total_revalidations": 2,
    "history": [
        {
            "version": 1,
            "final_status": "partial",
            "accuracy_score": 87.5,
            "comparison": null
        },
        {
            "version": 2,
            "final_status": "passed",
            "accuracy_score": 95.2,
            "comparison": {
                "fixed": 3,
                "new": 1,
                "improvement_rate": 60.0
            }
        }
    ]
}
```

### GET `/validation/sessions/{session_id}/revalidation-suggestion`

Get revalidation recommendation.

**Response:**
```json
{
    "session_id": "uuid",
    "recommended": true,
    "confidence": "high",
    "reasons": [
        "3 critical discrepancies require resolution",
        "Low accuracy (75%) indicates significant issues"
    ],
    "metrics": {
        "accuracy": 75.0,
        "critical_discrepancies": 3,
        "major_discrepancies": 2
    }
}
```

### GET `/validation/sessions/{session_id}/lineage`

Get version lineage (ancestry chain).

**Response:**
```json
{
    "session_id": "uuid",
    "version": 3,
    "lineage_depth": 3,
    "lineage": [
        {
            "session_id": "uuid1",
            "version": 1,
            "status": "superseded",
            "final_status": "failed",
            "created_at": "2025-01-01T10:00:00"
        },
        ...
    ]
}
```

## Change Type Classifications

The system classifies discrepancy changes into 6 types:

1. **FIXED**: Discrepancy present in V1, resolved in V2
   - Example: Weight mismatch corrected after BOE update

2. **NEW**: Discrepancy not in V1, appears in V2
   - Example: New HS Code mismatch after document correction

3. **PERSISTENT**: Discrepancy present in both V1 and V2
   - Example: Ongoing date format issue

4. **IMPROVED**: Severity decreased (e.g., critical → major)
   - Example: Critical weight issue became minor after partial correction

5. **WORSENED**: Severity increased (e.g., minor → major)
   - Example: Minor discrepancy escalated to major

6. **VALUE_CHANGED**: Values changed but discrepancy persists
   - Example: Weight mismatch changed from 1000 vs 999 to 1000 vs 998

## Version Status Lifecycle

```
DRAFT → ACTIVE → SUPERSEDED → ARCHIVED
```

- **DRAFT**: Version being created (not used currently)
- **ACTIVE**: Current active version
- **SUPERSEDED**: Replaced by newer version
- **ARCHIVED**: No longer actively used

## Best Practices

### 1. When to Revalidate

Revalidate when:
- Critical discrepancies detected (always)
- Multiple major discrepancies (≥3)
- Accuracy below threshold (<70%)
- Documents updated with corrections
- User requests verification

### 2. Tagging Strategy

Use meaningful tags:
```python
tags = [
    "weight_correction",
    "user_requested",
    "quarterly_review",
    "compliance_check"
]
```

### 3. Version Notes

Add clear notes:
```python
notes = "Updated BOE with corrected weights from customs. Net weight changed from 1000 KG to 999.5 KG."
```

### 4. Comparison Analysis

Always review:
- Fixed discrepancies (verify resolution)
- New discrepancies (investigate cause)
- Worsened severity (immediate attention)
- Persistent critical issues (requires action)

## Integration with Validation Engine

Version control is automatically integrated:

1. **After Validation**: Version metadata automatically created
2. **During Revalidation**: Previous version automatically marked as superseded
3. **In Reports**: Version information included in validation reports
4. **Via API**: All version operations accessible through REST API

## Performance Considerations

- **In-Memory Storage**: Current implementation uses in-memory storage (singleton pattern)
- **Production**: Replace with database (PostgreSQL recommended)
- **Indexing**: Index `session_id`, `version`, `status`, `created_at`
- **Caching**: Version metadata cached in memory for fast access
- **Batch Operations**: Use `batch_revalidate()` for multiple sessions

## Future Enhancements

Potential improvements:
- [ ] Database persistence layer
- [ ] Version branching (parallel versions)
- [ ] Automated revalidation triggers
- [ ] Version diff visualization
- [ ] Machine learning for revalidation prediction
- [ ] Version rollback capability
- [ ] Approval workflow for revalidations
- [ ] Version comments and annotations
- [ ] Export version history (PDF, Excel)

## Testing

Run tests:
```bash
pytest tests/version_control/
```

Example test:
```python
async def test_revalidation_workflow():
    # Create original validation (V1)
    context_v1 = await create_validation_session(...)
    await run_validation(context_v1.session_id)

    # Create revalidation (V2)
    request = RevalidationRequest(
        original_session_id=context_v1.session_id,
        revalidation_reason="Document correction"
    )
    result = await engine.create_revalidation(request)

    # Verify comparison
    assert result.new_version == 2
    assert result.comparison.fixed_count > 0
```

## Troubleshooting

### Issue: "Session not found"
- Ensure original session exists
- Check session UUID format

### Issue: "Comparison shows no changes"
- Verify documents actually changed
- Check if validation config changed

### Issue: "Version metadata not created"
- Ensure validation workflow completed successfully
- Check logs for creation errors

## Support

For issues or questions:
- Check logs: `logs/validation_engine.log`
- Review API documentation: `/docs`
- GitHub Issues: [nestle/validation-engine/issues]

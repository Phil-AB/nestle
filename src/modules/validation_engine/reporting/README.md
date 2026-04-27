# Reporting and Analytics Module

## Overview

The Reporting and Analytics module provides comprehensive reporting and analytics capabilities for the validation engine, enabling:

- **Multi-Format Reports**: Generate reports in JSON, CSV, PDF, HTML, and Excel
- **Multiple Report Types**: 6 different report types for various stakeholders
- **Analytics Dashboard**: Aggregated metrics and trends across sessions
- **Custom Report Generation**: Flexible reporting with filters and options
- **Performance Metrics**: Track validation performance over time

## Architecture

### Components

```
reporting/
├── report_models.py          # Data models for reports
├── report_manager.py         # Unified report management
├── generators/
│   ├── base_generator.py     # Base report generator
│   ├── json_generator.py     # JSON report generation
│   ├── csv_generator.py      # CSV report generation
│   └── pdf_generator.py      # PDF report generation
└── analytics/
    └── analytics_engine.py   # Analytics and metrics calculation
```

### Key Classes

1. **ReportManager**
   - Unified interface for report generation
   - Routes requests to appropriate generators
   - Manages report metadata
   - Caches generated reports

2. **Report Generators**
   - JSONReportGenerator: Structured JSON output
   - CSVReportGenerator: Tabular CSV export
   - PDFReportGenerator: Professional PDF documents
   - All inherit from BaseReportGenerator

3. **AnalyticsEngine**
   - Aggregated statistics across sessions
   - Trend analysis (daily, weekly, monthly)
   - Discrepancy pattern detection
   - Use case analytics

## Report Types

### 1. Validation Summary Report

Comprehensive validation overview with all metrics.

**Includes:**
- Validation overview (passed, failed, accuracy)
- Discrepancy breakdown by severity
- Top discrepancies (sorted by severity)
- Validation results by category
- Processing metrics

**Use Case:** Complete validation report for documentation

**Example:**
```python
request = ReportRequest(
    report_type=ReportType.VALIDATION_SUMMARY,
    format=ReportFormat.JSON,
    session_id=session_id
)
report = await manager.generate_report(request)
```

### 2. Discrepancy Detail Report

Detailed discrepancy breakdown with multiple groupings.

**Includes:**
- Discrepancies grouped by severity (critical, major, minor, info)
- Discrepancies grouped by category (hs_code, weight, duty, etc.)
- Discrepancies grouped by document
- Auto-fix status
- Resolution rate and confidence metrics

**Use Case:** Deep dive into validation issues

**Example:**
```python
request = ReportRequest(
    report_type=ReportType.DISCREPANCY_DETAIL,
    format=ReportFormat.JSON,
    session_id=session_id
)
report = await manager.generate_report(request)
```

### 3. Version Comparison Report

Compare V1 vs V2 validation results.

**Includes:**
- Fixed discrepancies (in V1, not in V2)
- New discrepancies (not in V1, in V2)
- Persistent discrepancies (in both)
- Severity changes (improved/worsened)
- Overall assessment and recommendations
- Side-by-side comparison

**Use Case:** Track progress after revalidation

**Example:**
```python
request = ReportRequest(
    report_type=ReportType.VERSION_COMPARISON,
    format=ReportFormat.JSON,
    v1_session_id=v1_id,
    v2_session_id=v2_id
)
report = await manager.generate_report(request)
```

### 4. Audit Trail Report

Complete audit trail with all events and interactions.

**Includes:**
- Session lifecycle (created, updated)
- Workflow events (all steps executed)
- Validation steps (all validators run)
- User interactions (inputs, confirmations)
- Version history
- Configuration used

**Use Case:** Compliance and auditing

**Example:**
```python
request = ReportRequest(
    report_type=ReportType.AUDIT_TRAIL,
    format=ReportFormat.JSON,
    session_id=session_id
)
report = await manager.generate_report(request)
```

### 5. Executive Summary Report

High-level overview for stakeholders.

**Includes:**
- Final status with color indicator (green/yellow/red)
- Accuracy score
- Key findings (top 3-5)
- Recommendations (top 3-5)
- Processing time
- Comparison with previous version (if available)

**Use Case:** Executive briefing

**Example:**
```python
request = ReportRequest(
    report_type=ReportType.EXECUTIVE_SUMMARY,
    format=ReportFormat.JSON,
    session_id=session_id
)
report = await manager.generate_report(request)
```

### 6. Analytics Dashboard

Aggregated analytics across multiple sessions.

**Includes:**
- Overall metrics (total sessions, avg accuracy)
- Status distribution
- Discrepancy trends over time
- Most common discrepancies
- Recurring issues
- Use case breakdown
- Daily/weekly trends

**Use Case:** Performance monitoring and insights

**Example:**
```python
from datetime import datetime, timedelta

end_date = datetime.utcnow()
start_date = end_date - timedelta(days=30)

dashboard = await analytics_engine.get_dashboard_data(
    start_date=start_date,
    end_date=end_date,
    use_case="boe_validation"
)
```

## Report Formats

### JSON Format

**Features:**
- Structured data
- Complete information preservation
- Nested objects support
- Easy parsing

**Best For:** API integration, data processing, storage

**Example Output:**
```json
{
    "report_metadata": {
        "report_type": "validation_summary",
        "format": "json",
        "generated_at": "2025-02-09T10:00:00Z",
        "session_id": "uuid"
    },
    "validation_summary": {
        "total_validations": 10,
        "passed_validations": 8,
        "accuracy_score": 80.0
    },
    "discrepancy_summary": {...}
}
```

### CSV Format

**Features:**
- Tabular data
- Multiple sections (summary, discrepancies, results)
- Excel-compatible
- Easy import to databases

**Best For:** Data analysis, Excel import, database loading

**Example Output:**
```csv
VALIDATION SUMMARY REPORT
Session ID,uuid
Use Case,boe_validation
Accuracy Score,80.0%

DISCREPANCIES DETAIL
Field Name,Severity,Category,Source Value,Target Value
net_weight,critical,weight,1000 KG,999 KG
```

### PDF Format

**Features:**
- Professional layout
- Tables and charts
- Headers and footers
- Color-coded severity

**Best For:** Documentation, reports, presentations

**Note:** Requires `weasyprint` or `reportlab` for production use.

### HTML Format

**Features:**
- Web-ready format
- Interactive elements
- Responsive design
- Printable

**Best For:** Web dashboards, email reports

### Excel Format

**Features:**
- Multiple sheets
- Formulas and formatting
- Charts and graphs
- Professional appearance

**Best For:** Advanced analysis, business reporting

## API Endpoints

### Generate Report (Generic)

```http
POST /validation/reports/generate
```

**Request Body:**
```json
{
    "report_type": "validation_summary",
    "format": "json",
    "session_id": "uuid",
    "include_raw_data": false,
    "max_discrepancies": 100
}
```

**Response:**
```json
{
    "metadata": {
        "report_id": "uuid",
        "report_type": "validation_summary",
        "format": "json",
        "generated_at": "2025-02-09T10:00:00Z"
    },
    "data": {...}
}
```

### Validation Summary

```http
GET /validation/reports/sessions/{session_id}/summary?format=json
```

### Discrepancy Detail

```http
GET /validation/reports/sessions/{session_id}/discrepancies
```

### Audit Trail

```http
GET /validation/reports/sessions/{session_id}/audit-trail
```

### Executive Summary

```http
GET /validation/reports/sessions/{session_id}/executive-summary
```

### Version Comparison

```http
POST /validation/reports/comparison
{
    "v1_session_id": "uuid1",
    "v2_session_id": "uuid2"
}
```

### Analytics Dashboard

```http
GET /validation/analytics/dashboard?days=30&use_case=boe_validation
```

### Use Case Analytics

```http
GET /validation/analytics/use-cases/{use_case}
```

### Discrepancy Trends

```http
GET /validation/analytics/discrepancy-trends?days=30
```

### List Report Formats

```http
GET /validation/reports/formats
```

### List Report Types

```http
GET /validation/reports/types
```

## Usage Examples

### 1. Generate Validation Summary (JSON)

```python
from modules.validation_engine.reporting import get_report_manager, ReportRequest, ReportFormat, ReportType

manager = get_report_manager()

request = ReportRequest(
    report_type=ReportType.VALIDATION_SUMMARY,
    format=ReportFormat.JSON,
    session_id=session_id
)

report = await manager.generate_report(request)

print(f"Accuracy: {report['data']['validation_summary']['accuracy_score']}%")
print(f"Total Discrepancies: {report['data']['discrepancy_summary']['total_discrepancies']}")
```

### 2. Export to CSV

```python
request = ReportRequest(
    report_type=ReportType.VALIDATION_SUMMARY,
    format=ReportFormat.CSV,
    session_id=session_id
)

report = await manager.generate_report(request)

# Save to file
with open("validation_report.csv", "w") as f:
    f.write(report['data'])
```

### 3. Generate PDF Report

```python
request = ReportRequest(
    report_type=ReportType.VALIDATION_SUMMARY,
    format=ReportFormat.PDF,
    session_id=session_id
)

report = await manager.generate_report(request)

# Save PDF
with open("validation_report.pdf", "wb") as f:
    f.write(report['data'])
```

### 4. Get Analytics Dashboard

```python
from modules.validation_engine.reporting import get_analytics_engine
from datetime import datetime, timedelta

analytics = get_analytics_engine()

end_date = datetime.utcnow()
start_date = end_date - timedelta(days=30)

dashboard = await analytics.get_dashboard_data(
    start_date=start_date,
    end_date=end_date
)

print(f"Total Sessions: {dashboard.total_sessions}")
print(f"Average Accuracy: {dashboard.avg_accuracy}%")
print(f"Most Common Issues: {dashboard.most_common_discrepancies}")
```

### 5. Compare Versions

```python
request = ReportRequest(
    report_type=ReportType.VERSION_COMPARISON,
    format=ReportFormat.JSON,
    v1_session_id=v1_id,
    v2_session_id=v2_id
)

report = await manager.generate_report(request)

print(f"Fixed: {len(report['data']['fixed_discrepancies'])}")
print(f"New: {len(report['data']['new_discrepancies'])}")
print(f"Assessment: {report['data']['assessment']}")
```

### 6. Get Executive Summary

```python
request = ReportRequest(
    report_type=ReportType.EXECUTIVE_SUMMARY,
    format=ReportFormat.JSON,
    session_id=session_id
)

report = await manager.generate_report(request)

summary = report['data']
print(f"Status: {summary['final_status']} ({summary['status_color']})")
print(f"Message: {summary['status_message']}")
print("\nKey Findings:")
for finding in summary['key_findings']:
    print(f"  - {finding}")
```

## Analytics Metrics

### Overall Metrics

- **Total Sessions**: Count of validation sessions
- **Total Validations**: Count of individual validations
- **Average Accuracy**: Mean accuracy across all sessions
- **Average Processing Time**: Mean processing time in milliseconds

### Status Distribution

Breakdown of final statuses:
- Passed
- Warning
- Partial
- Failed

### Discrepancy Metrics

- **Trends**: Daily counts by severity
- **By Category**: Count by category (hs_code, weight, etc.)
- **Most Common**: Top recurring discrepancies
- **Recurring Issues**: Issues appearing 3+ times

### Use Case Analytics

Per-use-case metrics:
- Session count
- Average accuracy
- Common discrepancies
- Trends over time

### Version Analytics

- **Revalidation Rate**: % of sessions revalidated
- **Average Improvement Rate**: Mean improvement from V1 to V2

## Best Practices

### 1. Choose Appropriate Report Type

- **Documentation**: Validation Summary (PDF)
- **Deep Analysis**: Discrepancy Detail (JSON/CSV)
- **Progress Tracking**: Version Comparison (JSON)
- **Compliance**: Audit Trail (PDF)
- **Stakeholders**: Executive Summary (PDF)
- **Monitoring**: Analytics Dashboard (JSON)

### 2. Select Right Format

- **API Integration**: JSON
- **Data Analysis**: CSV
- **Documentation**: PDF
- **Web Display**: HTML
- **Business Reporting**: Excel

### 3. Optimize Report Generation

- Use `max_discrepancies` to limit output size
- Set `include_raw_data=false` for summaries
- Cache frequently accessed reports
- Generate PDFs asynchronously for large reports

### 4. Analytics Period Selection

- **Real-time**: Last 7 days
- **Monitoring**: Last 30 days
- **Trends**: Last 90 days
- **Historical**: Custom range

## Performance Considerations

### Report Generation Speed

- **JSON**: Fastest (~10ms)
- **CSV**: Fast (~50ms)
- **HTML**: Medium (~100ms)
- **PDF**: Slow (~500ms, requires external library)
- **Excel**: Slow (~300ms)

### Caching Strategy

```python
# Reports are cached in memory by default
# For production, implement Redis/database caching

# Example: Manual caching
report_cache = {}

cache_key = f"{report_type}:{session_id}:{format}"
if cache_key in report_cache:
    return report_cache[cache_key]

report = await manager.generate_report(request)
report_cache[cache_key] = report
```

### Large Dataset Handling

For sessions with 1000+ discrepancies:
- Use pagination
- Filter by severity
- Limit results with `max_discrepancies`
- Generate summary first, then details on demand

## Production Deployment

### PDF Generation Setup

Install `weasyprint` for production PDF generation:

```bash
# Ubuntu/Debian
sudo apt-get install python3-pip python3-cffi python3-brotli libpango-1.0-0 libpangoft2-1.0-0
pip install weasyprint

# Or use reportlab
pip install reportlab
```

### Database Integration

Replace in-memory storage with database:

```python
# Example: PostgreSQL integration
async def _get_sessions_in_period(self, start_date, end_date, use_case):
    query = """
        SELECT * FROM validation_sessions
        WHERE created_at BETWEEN $1 AND $2
        AND ($3 IS NULL OR use_case = $3)
    """
    sessions = await db.fetch(query, start_date, end_date, use_case)
    return sessions
```

### Async Report Generation

For large reports, use background jobs:

```python
from celery import Celery

app = Celery('reports')

@app.task
async def generate_pdf_report(session_id):
    manager = get_report_manager()
    request = ReportRequest(
        report_type=ReportType.VALIDATION_SUMMARY,
        format=ReportFormat.PDF,
        session_id=session_id
    )
    report = await manager.generate_report(request)
    # Save to S3/file storage
    return report_url
```

## Troubleshooting

### Issue: PDF Generation Fails

**Solution:**
- Install weasyprint: `pip install weasyprint`
- Or use HTML format as fallback
- Check system dependencies (libpango, cairo)

### Issue: Slow Report Generation

**Solutions:**
- Use `max_discrepancies` to limit data
- Implement caching layer
- Generate asynchronously
- Use lighter formats (JSON/CSV)

### Issue: Large CSV Files

**Solutions:**
- Use pagination
- Split by severity
- Compress output (`compress=true`)
- Stream output instead of loading in memory

### Issue: Missing Data in Reports

**Solutions:**
- Ensure validation workflow completed
- Check session exists
- Verify version metadata created
- Check database connectivity

## Future Enhancements

Planned improvements:
- [ ] Excel export with charts
- [ ] Interactive HTML dashboards
- [ ] Email delivery integration
- [ ] Scheduled report generation
- [ ] Custom report templates
- [ ] Real-time streaming reports
- [ ] Report versioning
- [ ] Report sharing and permissions
- [ ] Webhook notifications
- [ ] Export to cloud storage (S3, GCS)

## Support

For issues or questions:
- Check logs: `logs/validation_engine.log`
- Review API documentation: `/docs`
- Test with sample data: `examples/reporting_demo.py`

---

**Module Version**: 1.0.0
**Last Updated**: 2025-02-09

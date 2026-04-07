"""Constants for validation engine"""

# Validation statuses
class ValidationStatus:
    CREATED = "created"
    EXTRACTING = "extracting"
    NORMALIZING = "normalizing"
    VALIDATING = "validating"
    ANALYZING = "analyzing"
    AWAITING_USER = "awaiting_user"
    COMPLETED = "completed"
    FAILED = "failed"


# Session types
class SessionType:
    VALIDATION = "validation"
    REVALIDATION = "revalidation"


# Final outcomes
class FinalStatus:
    PASSED = "passed"
    FAILED = "failed"
    REQUIRES_ATTENTION = "requires_attention"
    FALSE_POSITIVE = "false_positive"


# Validator types
class ValidatorType:
    RULE_BASED = "rule_based"
    AI_BASED = "ai_based"
    STATISTICAL = "statistical"
    CROSS_DOCUMENT = "cross_document"


# Severity levels
class Severity:
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    INFO = "info"


# Discrepancy types
class DiscrepancyType:
    VALUE_MISMATCH = "value_mismatch"
    MISSING_FIELD = "missing_field"
    CALCULATION_ERROR = "calculation_error"
    FORMAT_DIFFERENCE = "format_difference"
    TYPE_MISMATCH = "type_mismatch"


# Discrepancy categories
class DiscrepancyCategory:
    HS_CODE = "hs_code"
    WEIGHT = "weight"
    DUTY = "duty"
    CURRENCY = "currency"
    QUANTITY = "quantity"
    DATE = "date"
    CALCULATION = "calculation"
    OTHER = "other"


# Resolution statuses
class ResolutionStatus:
    OPEN = "open"
    FIXED = "fixed"
    FALSE_POSITIVE = "false_positive"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


# Comparison statuses
class ComparisonStatus:
    IMPROVED = "improved"
    DEGRADED = "degraded"
    UNCHANGED = "unchanged"


# Workflow steps
class WorkflowStep:
    INITIALIZE = "initialize"
    NORMALIZE = "normalize"
    VALIDATE = "validate"
    ANALYZE = "analyze"
    CLASSIFY = "classify"
    AUTO_FIX = "auto_fix"
    USER_CONFIRMATION = "user_confirmation"
    AUTOMATION = "automation"
    REPORT = "report"


# Validation modes
class ValidationMode:
    STRICT = "strict"
    LENIENT = "lenient"
    MODERATE = "moderate"


# Normalization strategies
class NormalizationStrategy:
    CONFIG_ONLY = "config_only"
    LLM_ONLY = "llm_only"
    HYBRID = "hybrid"  # Config first, LLM fallback


# Match types
class MatchType:
    EXACT = "exact"
    FUZZY = "fuzzy"
    SEMANTIC = "semantic"
    TOLERANCE = "tolerance"


# Document roles
class DocumentRole:
    PRIMARY = "primary"
    SUPPORTING = "supporting"
    SOURCE = "source"
    TARGET = "target"


# Confidence thresholds
class ConfidenceThreshold:
    HIGH = 0.9
    MEDIUM = 0.7
    LOW = 0.5


# Tolerance types
class ToleranceType:
    PERCENTAGE = "percentage"
    ABSOLUTE = "absolute"
    RELATIVE = "relative"


# Operators
class Operator:
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    LESS_THAN = "less_than"
    GREATER_THAN = "greater_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    WITHIN_RANGE = "within_range"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    MATCHES_PATTERN = "matches_pattern"


# Export formats
class ExportFormat:
    JSON = "json"
    PDF = "pdf"
    CSV = "csv"
    HTML = "html"


# Likely causes for discrepancies
class LikelyCause:
    OCR_ERROR = "OCR error"
    CALCULATION_ERROR = "calculation error"
    FORMAT_DIFFERENCE = "format difference"
    UNIT_DIFFERENCE = "unit difference"
    ROUNDING_DIFFERENCE = "rounding difference"
    MISSING_DATA = "missing data"
    TYPO = "typo"
    UNKNOWN = "unknown"


# Auto-fix types
class AutoFixType:
    FORMAT_NORMALIZATION = "format_normalization"
    UNIT_CONVERSION = "unit_conversion"
    SYNONYM_RESOLUTION = "synonym_resolution"
    DATE_STANDARDIZATION = "date_standardization"
    CURRENCY_CONVERSION = "currency_conversion"
    ROUNDING = "rounding"

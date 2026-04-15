"""Format normalizer for dates, decimals, currencies, and booleans"""

from typing import Dict, Any, Optional, Union
from decimal import Decimal
from datetime import datetime
import re
from ...core.config_loader import get_config_loader
from ...utils.exceptions import NormalizationException
from shared.utils.logger import get_logger

logger = get_logger(__name__)


class FormatNormalizer:
    """
    Normalize data formats to standard formats

    Handles:
    - Dates: DD/MM/YYYY, MM/DD/YYYY → YYYY-MM-DD
    - Decimals: 1,234.56 or 1.234,56 → 1234.56
    - Currencies: $1,000 or 1000$ → 1000.00
    - Booleans: yes/oui/1 → true
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize format normalizer

        Args:
            config: Normalization configuration
        """
        self.config = config or {}

        # Load normalization config
        config_loader = get_config_loader()
        norm_config = config_loader.load_normalization_config()

        # Format normalization settings
        self.format_config = norm_config.get("format_normalization", {})
        self.enabled = self.format_config.get("enabled", True)

        # Date settings
        self.date_config = self.format_config.get("date", {})
        self.date_target_format = self.date_config.get("target_format", "YYYY-MM-DD")
        self.date_supported_formats = self.date_config.get("supported_formats", [])

        # Decimal settings
        self.decimal_config = self.format_config.get("decimal", {})
        self.decimal_separator = self.decimal_config.get("decimal_separator", ".")
        self.thousands_separator = self.decimal_config.get("thousands_separator", ",")
        self.decimal_precision = self.decimal_config.get("precision", 2)

        # Currency settings
        self.currency_config = self.format_config.get("currency", {})
        self.currency_position = self.currency_config.get("position", "prefix")
        self.currency_symbol = self.currency_config.get("symbol", "$")

        # Boolean settings
        self.boolean_config = norm_config.get("format_normalization", {}).get("boolean", {})
        self.true_values = set(self.boolean_config.get("true_values", ["true", "yes", "1"]))
        self.false_values = set(self.boolean_config.get("false_values", ["false", "no", "0"]))

        logger.info("FormatNormalizer initialized")

    def normalize_date(
        self,
        value: Union[str, datetime],
        source_format: Optional[str] = None
    ) -> str:
        """
        Normalize date to YYYY-MM-DD format

        Args:
            value: Date value
            source_format: Optional source format hint

        Returns:
            Normalized date string (YYYY-MM-DD)

        Raises:
            NormalizationException: If date cannot be parsed
        """
        if not self.enabled:
            return str(value)

        # Already a datetime object
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")

        # Try to parse string
        value_str = str(value).strip()

        # Try source format first
        if source_format:
            try:
                dt = self._parse_date(value_str, source_format)
                return dt.strftime("%Y-%m-%d")
            except:
                pass

        # Try all supported formats
        for fmt in self.date_supported_formats:
            try:
                dt = self._parse_date(value_str, fmt)
                return dt.strftime("%Y-%m-%d")
            except:
                continue

        # Try common patterns with regex
        dt = self._parse_date_with_regex(value_str)
        if dt:
            return dt.strftime("%Y-%m-%d")

        raise NormalizationException(f"Cannot parse date: {value_str}")

    def normalize_decimal(
        self,
        value: Union[str, int, float, Decimal],
        precision: Optional[int] = None
    ) -> Decimal:
        """
        Normalize decimal number

        Args:
            value: Decimal value
            precision: Optional precision override

        Returns:
            Normalized Decimal

        Raises:
            NormalizationException: If value cannot be normalized
        """
        if not self.enabled:
            return Decimal(str(value))

        precision = precision or self.decimal_precision

        # Already a number
        if isinstance(value, (int, float, Decimal)):
            result = Decimal(str(value))
            return result.quantize(Decimal(f"0.{'0' * precision}"))

        # Parse string
        value_str = str(value).strip()

        try:
            # Remove thousands separators using the same heuristic as tolerance_validator:
            # whichever separator appears *last* is the decimal separator.
            cleaned = value_str.replace(" ", "")

            # Strip trailing non-numeric characters (units like kg, MT)
            import re as _re
            cleaned = _re.sub(r'[^0-9.,\-]+$', '', cleaned).strip()

            dot_count = cleaned.count('.')
            comma_count = cleaned.count(',')

            if dot_count > 0 and comma_count > 0:
                last_dot = cleaned.rindex('.')
                last_comma = cleaned.rindex(',')
                if last_comma > last_dot:
                    # European: dot=thousands, comma=decimal → "189.000,00"
                    cleaned = cleaned.replace('.', '').replace(',', '.')
                else:
                    # US: comma=thousands, dot=decimal → "189,000.000"
                    cleaned = cleaned.replace(',', '')
            elif comma_count > 0 and dot_count == 0:
                digits_after = len(cleaned) - cleaned.rindex(',') - 1
                if comma_count == 1 and digits_after in (1, 2):
                    cleaned = cleaned.replace(',', '.')
                else:
                    cleaned = cleaned.replace(',', '')
            elif dot_count > 0 and comma_count == 0:
                if dot_count == 1 and len(cleaned) - cleaned.rindex('.') - 1 == 3:
                    # European thousands: "7.560" → 7560
                    cleaned = cleaned.replace('.', '')
                elif dot_count > 1:
                    cleaned = cleaned.replace('.', '')

            result = Decimal(cleaned)
            return result.quantize(Decimal(f"0.{'0' * precision}"))

        except Exception as e:
            raise NormalizationException(
                f"Cannot parse decimal: {value_str} - {str(e)}"
            )

    def normalize_currency(
        self,
        value: Union[str, int, float, Decimal]
    ) -> Decimal:
        """
        Normalize currency value (remove symbols, standardize format)

        Args:
            value: Currency value ($1,000 or 1000$)

        Returns:
            Normalized decimal value

        Raises:
            NormalizationException: If value cannot be normalized
        """
        if not self.enabled:
            return Decimal(str(value))

        # Already a number
        if isinstance(value, (int, float, Decimal)):
            return self.normalize_decimal(value)

        # Parse string
        value_str = str(value).strip()

        # Currency dedup: "EUR 467,775.00 EUR" -> "EUR 467,775.00"
        _dedup = re.match(r'^([A-Z]{3})\s*([\d,.]+(?:\.\d+)?)\s+\1$', value_str, re.IGNORECASE)
        if _dedup:
            value_str = f"{_dedup.group(1)} {_dedup.group(2)}"

        # Remove currency symbols
        cleaned = value_str
        for symbol in ["$", "€", "£", "¥", "USD", "EUR", "GBP", "JPY"]:
            cleaned = cleaned.replace(symbol, "")

        cleaned = cleaned.strip()

        # Normalize as decimal
        return self.normalize_decimal(cleaned)

    def normalize_boolean(self, value: Any) -> bool:
        """
        Normalize boolean value

        Args:
            value: Value to normalize

        Returns:
            Boolean value

        Raises:
            NormalizationException: If value cannot be normalized
        """
        if not self.enabled:
            return bool(value)

        # Already a boolean
        if isinstance(value, bool):
            return value

        # Convert to string and check
        value_str = str(value).strip().lower()

        if value_str in self.true_values:
            return True

        if value_str in self.false_values:
            return False

        raise NormalizationException(f"Cannot parse boolean: {value}")

    def normalize_whitespace(self, value: str) -> str:
        """
        Normalize whitespace (trim, collapse multiple spaces)

        Args:
            value: String value

        Returns:
            Normalized string
        """
        if not self.enabled:
            return value

        # Trim and collapse spaces
        normalized = " ".join(value.split())

        return normalized

    def _parse_date(self, date_str: str, format_str: str) -> datetime:
        """
        Parse date with given format

        Args:
            date_str: Date string
            format_str: Format string (YYYY-MM-DD, DD/MM/YYYY, etc.)

        Returns:
            datetime object
        """
        # Convert format string to strptime format
        strptime_format = format_str
        strptime_format = strptime_format.replace("YYYY", "%Y")
        strptime_format = strptime_format.replace("MM", "%m")
        strptime_format = strptime_format.replace("DD", "%d")
        strptime_format = strptime_format.replace("MMM", "%b")
        strptime_format = strptime_format.replace("MMMM", "%B")

        return datetime.strptime(date_str, strptime_format)

    def _parse_date_with_regex(self, date_str: str) -> Optional[datetime]:
        """
        Try to parse date using regex patterns

        Args:
            date_str: Date string

        Returns:
            datetime object or None
        """
        patterns = [
            # YYYY-MM-DD or YYYY/MM/DD
            (r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", "%Y-%m-%d"),

            # DD-MM-YYYY or DD/MM/YYYY
            (r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", "%d-%m-%Y"),

            # MM-DD-YYYY or MM/DD/YYYY
            (r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", "%m-%d-%Y"),
        ]

        for pattern, fmt in patterns:
            match = re.match(pattern, date_str)
            if match:
                try:
                    # Normalize separators
                    normalized = date_str.replace("/", "-")
                    return datetime.strptime(normalized, fmt)
                except:
                    continue

        return None

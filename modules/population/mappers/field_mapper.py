"""
Field Mapper for Population Module.

Maps database fields to PDF form fields with transformations.
Independent implementation (not shared with generation module).
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from dateutil import parser as date_parser
import yaml
import re
import logging

logger = logging.getLogger(__name__)


class FieldMapper:
    """
    Map database fields to PDF form fields.

    Applies transformations (date formatting, string manipulation, etc.)
    and handles fallback field sources.

    Example:
        >>> mapper = FieldMapper(transformations=config["transformations"])
        >>> mapped = await mapper.map(
        ...     data={"fields": {"date": "2024-06-15", "vessel": "ship a"}},
        ...     mapping_config="config/population/mappings/boe_gra.yaml"
        ... )
        >>> print(mapped)
        {"date_field": "15/06/2024", "vessel_name_field": "SHIP A"}
    """

    def __init__(self, transformations: List[Dict[str, Any]]):
        """
        Initialize field mapper.

        Args:
            transformations: List of transformation definitions from config
        """
        self.transformations = {
            t["name"]: t for t in transformations
        }

        logger.info(
            f"FieldMapper initialized with {len(self.transformations)} transformations"
        )

    async def map(
        self,
        data: Dict[str, Any],
        mapping_config: str
    ) -> Dict[str, Any]:
        """
        Map database field names to PDF form field names.

        Args:
            data: Database data with structure:
                {
                    "fields": {field_name: value, ...},
                    "items": [{item_data}, ...],
                    "metadata": {...}
                }
            mapping_config: Path to mapping YAML configuration file

        Returns:
            Dictionary of {pdf_field_name: formatted_value}

        Example:
            Input data:
                {"fields": {"exporter_shipper": "Acme Corp, 123 Main St"}}

            Mapping config:
                exporter_name_field:
                  source: "fields.exporter_shipper"
                  transformation: "extract_company_name"

            Output:
                {"exporter_name_field": "Acme Corp"}
        """
        try:
            logger.info(f"Mapping fields using config: {mapping_config}")

            # Load mapping configuration
            mapping = self._load_mapping(mapping_config)

            mapped_fields = {}

            # Map each field
            for pdf_field_name, field_config in mapping.items():
                value = self._extract_value(data, field_config)

                if value is not None:
                    # Apply transformations
                    value = self._transform_value(value, field_config)
                    mapped_fields[pdf_field_name] = value
                elif "default" in field_config:
                    # Use default value if source not found
                    mapped_fields[pdf_field_name] = field_config["default"]

            logger.info(f"Mapped {len(mapped_fields)} fields successfully")
            return mapped_fields

        except Exception as e:
            logger.error(f"Field mapping failed: {e}", exc_info=True)
            raise

    def _load_mapping(self, mapping_config: str) -> Dict[str, Any]:
        """
        Load field mapping configuration from YAML.

        Args:
            mapping_config: Path to YAML config file

        Returns:
            Mapping dictionary

        Raises:
            FileNotFoundError: If config file not found
        """
        try:
            with open(mapping_config, 'r') as f:
                config = yaml.safe_load(f)

            # Extract field_mappings section
            if "field_mappings" not in config:
                raise ValueError(
                    f"Config file missing 'field_mappings' section: {mapping_config}"
                )

            return config["field_mappings"]

        except Exception as e:
            logger.error(f"Failed to load mapping config: {e}")
            raise

    def _extract_value(self, data: Dict, field_config: Dict) -> Any:
        """
        Extract value from nested data using dot notation.

        Supports fallback field sources.

        Args:
            data: Nested data dictionary
            field_config: Field configuration with 'source' and optional 'fallback'

        Returns:
            Extracted value or None if not found

        Example:
            data = {"fields": {"vessel": "SHIP A"}}
            field_config = {"source": "fields.vessel"}
            Returns: "SHIP A"

            With fallback:
            field_config = {
                "source": "fields.bl_number",
                "fallback": ["fields.awb_number", "fields.ref_no"]
            }
            Tries bl_number first, then awb_number, then ref_no
        """
        # Try primary source
        value = self._get_nested_value(data, field_config.get("source", ""))

        # If not found, try fallback sources
        if value is None and "fallback" in field_config:
            for fallback_source in field_config["fallback"]:
                value = self._get_nested_value(data, fallback_source)
                if value is not None:
                    logger.debug(
                        f"Used fallback source: {fallback_source}"
                    )
                    break

        return value

    def _get_nested_value(self, data: Dict, path: str) -> Any:
        """
        Get value from nested dictionary using dot notation.

        Args:
            data: Nested dictionary
            path: Dot-separated path (e.g., "fields.exporter.name")

        Returns:
            Value at path or None if not found

        Example:
            data = {"fields": {"exporter": {"name": "Acme"}}}
            path = "fields.exporter.name"
            Returns: "Acme"
        """
        if not path:
            return None

        keys = path.split(".")
        value = data

        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None

        # Auto-extract 'value' property from extracted field objects
        # Database stores fields as: {"value": "actual_value", "bbox": {...}, ...}
        if isinstance(value, dict) and "value" in value:
            value = value["value"]

        return value

    def _transform_value(self, value: Any, field_config: Dict) -> Any:
        """
        Apply transformations to field value.

        Args:
            value: Value to transform
            field_config: Field configuration with transformation specs

        Returns:
            Transformed value

        Supports:
            - Named transformations (from config)
            - Inline transformations (date_format, number_format, etc.)
            - String transformations (uppercase, max_length)
        """
        # Apply named transformation
        if "transformation" in field_config:
            trans_name = field_config["transformation"]
            if trans_name in self.transformations:
                value = self._apply_transformation(
                    value,
                    self.transformations[trans_name]
                )

        # Apply inline date formatting
        if "date_format" in field_config:
            value = self._format_date(value, field_config["date_format"])

        # Apply inline number formatting
        if "number_format" in field_config:
            value = self._format_number(value, field_config["number_format"])

        # Apply string transformations
        if field_config.get("uppercase"):
            value = str(value).upper()

        if field_config.get("lowercase"):
            value = str(value).lower()

        if "max_length" in field_config:
            value = str(value)[:field_config["max_length"]]

        return value

    def _apply_transformation(self, value: Any, trans_config: Dict) -> Any:
        """
        Apply named transformation from configuration.

        Args:
            value: Value to transform
            trans_config: Transformation configuration

        Returns:
            Transformed value
        """
        trans_type = trans_config.get("type")

        if trans_type == "regex":
            # Extract using regex pattern
            pattern = trans_config.get("pattern")
            group = trans_config.get("group", 0)

            match = re.search(pattern, str(value))
            if match:
                return match.group(group)
            return value

        elif trans_type == "split_lines":
            # Split by separator and extract line
            separator = trans_config.get("separator", ",")
            lines = str(value).split(separator)
            line_number = trans_config.get("line_number", 1)

            if 0 < line_number <= len(lines):
                return lines[line_number - 1].strip()
            return value

        elif trans_type == "date_format":
            # Format date
            input_formats = trans_config.get("input_formats", [])
            output_format = trans_config.get("output_format", "%Y-%m-%d")

            return self._format_date(
                value,
                output_format,
                input_formats=input_formats
            )

        elif trans_type == "number_format":
            # Format number
            decimals = trans_config.get("decimals", 2)
            thousand_sep = trans_config.get("thousand_separator", ",")
            decimal_sep = trans_config.get("decimal_separator", ".")

            return self._format_number(
                value,
                f",.{decimals}f",
                thousand_sep=thousand_sep,
                decimal_sep=decimal_sep
            )

        elif trans_type == "string_transform":
            # String manipulation
            operation = trans_config.get("operation")

            if operation == "upper":
                return str(value).upper()
            elif operation == "lower":
                return str(value).lower()
            elif operation == "title":
                return str(value).title()
            elif operation == "strip":
                return str(value).strip()

        return value

    def _format_date(
        self,
        value: Any,
        output_format: str,
        input_formats: Optional[List[str]] = None
    ) -> str:
        """
        Format date value.

        Args:
            value: Date value (string or datetime)
            output_format: Desired output format (strftime format)
            input_formats: List of possible input formats to try

        Returns:
            Formatted date string

        Example:
            >>> _format_date("2024-06-15", "%d/%m/%Y")
            "15/06/2024"
        """
        if not value or value == "":
            return ""

        try:
            # If already a datetime object
            if isinstance(value, datetime):
                return value.strftime(output_format)

            # Try to parse string date
            value_str = str(value)

            # Try specific input formats first
            if input_formats:
                for fmt in input_formats:
                    try:
                        dt = datetime.strptime(value_str, fmt)
                        return dt.strftime(output_format)
                    except ValueError:
                        continue

            # Fall back to dateutil parser (handles many formats)
            dt = date_parser.parse(value_str)
            return dt.strftime(output_format)

        except Exception as e:
            logger.warning(f"Date formatting failed: {e}, returning original value")
            return str(value)

    def _format_number(
        self,
        value: Any,
        format_spec: str,
        thousand_sep: str = ",",
        decimal_sep: str = "."
    ) -> str:
        """
        Format number value.

        Args:
            value: Number value
            format_spec: Format specification (e.g., ",.2f")
            thousand_sep: Thousand separator
            decimal_sep: Decimal separator

        Returns:
            Formatted number string

        Example:
            >>> _format_number(1234.56, ",.2f")
            "1,234.56"
        """
        if not value or value == "":
            return ""

        try:
            # Convert to float
            num = float(value)

            # Apply format
            formatted = f"{num:{format_spec}}"

            # Replace separators if different from default
            if thousand_sep != ",":
                formatted = formatted.replace(",", "TEMP")
                formatted = formatted.replace(thousand_sep, ",")
                formatted = formatted.replace("TEMP", thousand_sep)

            if decimal_sep != ".":
                formatted = formatted.replace(".", decimal_sep)

            return formatted

        except Exception as e:
            logger.warning(f"Number formatting failed: {e}, returning original value")
            return str(value)

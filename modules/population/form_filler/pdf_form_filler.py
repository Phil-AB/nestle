"""
PDF Form Filler - AcroForm field population.

Fills interactive form fields in fillable PDF forms using pypdf.
These are the same fields you can click and type into when opening
a PDF in a browser like Firefox or Chrome.
"""

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, BooleanObject
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class PDFFormFiller:
    """
    Fill AcroForm fields in fillable PDF forms.

    Uses pypdf to programmatically populate interactive form fields.
    Supports text fields, checkboxes, and other standard PDF form elements.

    Example:
        >>> filler = PDFFormFiller()
        >>> output_path = await filler.fill_form(
        ...     template_path="forms/boe_blank.pdf",
        ...     field_data={"regime": "40", "exporter_name": "Acme Corp"},
        ...     options={"flatten_form": True}
        ... )
    """

    def __init__(self, output_dir: str = "output/population"):
        """
        Initialize PDF form filler.

        Args:
            output_dir: Directory for saving filled PDFs
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"PDFFormFiller initialized: output_dir={self.output_dir}")

    async def fill_form(
        self,
        template_path: str,
        field_data: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None
    ) -> Path:
        """
        Fill PDF form fields with data.

        Args:
            template_path: Path to blank fillable PDF template
            field_data: Dictionary of {field_name: value}
            options: Optional settings:
                - flatten_form (bool): Make PDF read-only (default: False)
                - validate_required (bool): Check required fields (default: True)

        Returns:
            Path to filled PDF file

        Raises:
            ValueError: If PDF is not a fillable form
            FileNotFoundError: If template not found
        """
        options = options or {}

        try:
            logger.info(f"Filling form: template={template_path}")

            # Validate template exists
            template = Path(template_path)
            if not template.exists():
                raise FileNotFoundError(f"PDF template not found: {template_path}")

            # Load fillable PDF template
            reader = PdfReader(template_path)
            writer = PdfWriter()

            # Check if PDF has form fields
            if "/AcroForm" not in reader.trailer["/Root"]:
                raise ValueError(
                    f"PDF is not a fillable form (no AcroForm): {template_path}"
                )

            # Get form field definitions
            form_fields = self._get_form_fields(reader)
            logger.info(f"Found {len(form_fields)} form fields in PDF")

            # DEBUG: Log what we're trying to fill
            logger.info(f"DEBUG: Attempting to fill {len(field_data)} fields")
            logger.info(f"DEBUG: Field names from mapper: {list(field_data.keys())}")
            logger.info(f"DEBUG: Available PDF fields: {list(form_fields.keys())[:20]}")

            # Use pypdf's append method - properly copies pages AND form structure
            writer.append(reader)

            # Update form field values
            filled_count = 0
            for field_name, value in field_data.items():
                if field_name in form_fields:
                    try:
                        # Update the field value on all pages
                        for page in writer.pages:
                            writer.update_page_form_field_values(
                                page,
                                {field_name: str(value)},
                                auto_regenerate=False
                            )
                        filled_count += 1
                        logger.info(f"✓ Filled: {field_name} = {str(value)[:50]}")
                    except Exception as e:
                        logger.warning(f"✗ Failed to fill '{field_name}': {e}")
                else:
                    logger.warning(f"✗ Field '{field_name}' not in PDF")

            logger.info(f"Filled {filled_count}/{len(field_data)} fields")

            # Set NeedAppearances flag
            if "/AcroForm" in writer._root_object:
                acro_form = writer._root_object["/AcroForm"]
                acro_form.update({
                    NameObject("/NeedAppearances"): BooleanObject(True)
                })

            # Flatten form if requested (make read-only)
            if options.get("flatten_form", False):
                logger.info("Flattening form (making read-only)...")
                self._flatten_form(writer)

            # Save output
            output_path = self._generate_output_path(template_path, options)
            with open(output_path, 'wb') as f:
                writer.write(f)

            logger.info(f"Saved filled PDF: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Form filling failed: {e}", exc_info=True)
            raise

    def _get_form_fields(self, reader: PdfReader) -> Dict[str, Dict]:
        """
        Extract form field definitions from PDF.

        Args:
            reader: PdfReader instance

        Returns:
            Dictionary of {field_name: field_properties}
                field_properties:
                    - type: Field type (/Tx=text, /Btn=button/checkbox)
                    - value: Current value
                    - default: Default value
        """
        fields = {}

        try:
            if "/AcroForm" in reader.trailer["/Root"]:
                form = reader.trailer["/Root"]["/AcroForm"]

                if "/Fields" in form:
                    for field in form["/Fields"]:
                        try:
                            field_obj = field.get_object()
                            field_name = str(field_obj.get("/T", ""))
                            field_type = str(field_obj.get("/FT", ""))

                            if field_name:  # Only add if has a name
                                fields[field_name] = {
                                    "type": field_type,
                                    "value": field_obj.get("/V", ""),
                                    "default": field_obj.get("/DV", "")
                                }
                        except Exception as e:
                            logger.warning(f"Error reading field: {e}")
                            continue

        except Exception as e:
            logger.error(f"Error extracting form fields: {e}")

        return fields

    def _fill_fields(
        self,
        writer: PdfWriter,
        field_data: Dict[str, Any],
        form_fields: Dict[str, Dict]
    ) -> int:
        """
        Fill all form fields with provided data.

        Args:
            writer: PdfWriter instance
            field_data: Data to fill into fields
            form_fields: Form field definitions

        Returns:
            Number of fields successfully filled
        """
        filled_count = 0

        for field_name, value in field_data.items():
            if field_name in form_fields:
                try:
                    # DEBUG: Log raw value before formatting
                    logger.info(f"DEBUG: Processing field '{field_name}' with raw value: {repr(value)[:100]}")

                    # Format value according to field type
                    formatted_value = self._format_field_value(
                        value,
                        form_fields[field_name]
                    )

                    # DEBUG: Log formatted value
                    logger.info(f"DEBUG: Formatted value for '{field_name}': {repr(formatted_value)[:100]}")

                    # Update field value directly in AcroForm (more compatible with reportlab)
                    if self._update_field_value_direct(writer, field_name, formatted_value):
                        filled_count += 1
                        logger.debug(f"Filled field '{field_name}' = '{formatted_value}'")

                except Exception as e:
                    logger.warning(
                        f"Error filling field '{field_name}': {e}"
                    )
            else:
                logger.debug(
                    f"Field '{field_name}' not found in PDF form fields"
                )

        return filled_count

    def _fill_fields_direct(
        self,
        writer: PdfWriter,
        field_data: Dict[str, Any],
        form_fields: Dict[str, Dict]
    ) -> int:
        """
        Fill form fields by directly updating the AcroForm structure.

        This is a fallback when pypdf's update_page_form_field_values fails.
        """
        filled_count = 0

        # DEBUG: Log what we're trying to fill
        logger.info(f"DEBUG: Attempting to fill {len(field_data)} fields")
        logger.info(f"DEBUG: Field names from mapper: {list(field_data.keys())}")
        logger.info(f"DEBUG: Available PDF fields: {list(form_fields.keys())[:20]}")

        for field_name, value in field_data.items():
            if field_name in form_fields:
                try:
                    if self._update_field_value_direct(writer, field_name, str(value)):
                        filled_count += 1
                except Exception as e:
                    logger.warning(f"Error filling field '{field_name}': {e}")
            else:
                logger.warning(f"DEBUG: Field '{field_name}' from mapper NOT in PDF fields!")

        return filled_count

    def _update_field_value_direct(self, writer: PdfWriter, field_name: str, value: str) -> bool:
        """
        Directly update field value in AcroForm structure.
        More compatible with reportlab-generated forms than update_page_form_field_values.

        Args:
            writer: PdfWriter instance
            field_name: Name of the field to update
            value: Value to set

        Returns:
            True if field was updated successfully
        """
        try:
            if "/AcroForm" not in writer._root_object:
                logger.debug(f"No AcroForm in writer._root_object")
                return False

            acro_form = writer._root_object["/AcroForm"]
            if "/Fields" not in acro_form:
                logger.debug(f"No /Fields in AcroForm")
                return False

            # Find and update the field
            logger.info(f"DEBUG: Looking for field '{field_name}' among {len(acro_form['/Fields'])} fields")
            for i, field_ref in enumerate(acro_form["/Fields"]):
                field = field_ref.get_object()
                field_t = field.get("/T")
                logger.info(f"DEBUG: Field {i}: /T = {repr(field_t)}, looking for {repr(field_name)}")
                if field_t == field_name:
                    # Update the field value
                    logger.info(f"DEBUG: FOUND field '{field_name}', updating with value: {repr(value)}")
                    field.update({
                        NameObject("/V"): value
                    })
                    # Verify the update
                    new_value = field.get("/V")
                    logger.info(f"DEBUG: After update, /V = {repr(new_value)}")
                    return True

            logger.info(f"DEBUG: Field '{field_name}' NOT FOUND")
            return False

        except Exception as e:
            logger.debug(f"Direct field update failed for '{field_name}': {e}")
            return False

    def _format_field_value(self, value: Any, field_info: Dict) -> str:
        """
        Format value according to PDF field type.

        Args:
            value: Value to format
            field_info: Field metadata from PDF

        Returns:
            Formatted string value

        Handles:
            - Text fields (/Tx): String conversion
            - Checkbox fields (/Btn): "Yes"/"Off"
            - Date fields: String representation
            - Number fields: String representation
        """
        if value is None or value == "":
            return ""

        field_type = field_info.get("type", "")

        # Checkbox/Button field
        if field_type == "/Btn":
            # Standard checkbox values
            return "Yes" if value else "Off"

        # Text field (default)
        # Convert any value to string
        return str(value)

    def _flatten_form(self, writer: PdfWriter):
        """
        Flatten form fields (make read-only).

        Converts interactive form fields to static text,
        preventing further editing.

        Args:
            writer: PdfWriter instance
        """
        try:
            for page in writer.pages:
                # Flatten annotations (which include form fields)
                if "/Annots" in page:
                    page.flatten()

            logger.info("Form flattened successfully")

        except Exception as e:
            logger.warning(f"Error flattening form: {e}")

    def _generate_output_path(
        self,
        template_path: str,
        options: Dict[str, Any]
    ) -> Path:
        """
        Generate unique output file path.

        Args:
            template_path: Original template path
            options: Population options

        Returns:
            Path for output PDF
        """
        # Extract template name
        template_name = Path(template_path).stem

        # Generate timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Create unique filename
        output_filename = f"{template_name}_{timestamp}.pdf"

        return self.output_dir / output_filename

    def inspect_form(self, template_path: str) -> Dict[str, Any]:
        """
        Inspect form field structure of a PDF.

        Useful for discovering field names in a fillable PDF.

        Args:
            template_path: Path to PDF to inspect

        Returns:
            Dictionary with:
                - field_count: Number of fields
                - fields: List of field details

        Example:
            >>> filler = PDFFormFiller()
            >>> info = filler.inspect_form("forms/boe_blank.pdf")
            >>> print(f"Found {info['field_count']} fields:")
            >>> for field in info['fields']:
            ...     print(f"  - {field['name']}: {field['type']}")
        """
        try:
            reader = PdfReader(template_path)

            if "/AcroForm" not in reader.trailer["/Root"]:
                return {
                    "field_count": 0,
                    "fields": [],
                    "error": "PDF is not a fillable form"
                }

            form_fields = self._get_form_fields(reader)

            return {
                "field_count": len(form_fields),
                "fields": [
                    {
                        "name": name,
                        "type": info["type"],
                        "current_value": info["value"],
                        "default_value": info["default"]
                    }
                    for name, info in form_fields.items()
                ]
            }

        except Exception as e:
            logger.error(f"Error inspecting form: {e}")
            return {
                "field_count": 0,
                "fields": [],
                "error": str(e)
            }

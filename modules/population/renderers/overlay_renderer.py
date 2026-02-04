"""
Overlay Renderer for PDF Form Population.

Renders filled field values as a transparent overlay on template PDFs.
Uses reportlab to create the overlay, then merges with template using pypdf.

This approach is more reliable than direct field manipulation because it:
- Doesn't depend on PDF AcroForm structure
- Works with any PDF (fillable or not)
- Preserves exact visual layout
"""

from pathlib import Path
from typing import Dict, Any, Optional
from io import BytesIO
from datetime import datetime
import logging

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import black

from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


class OverlayRenderer:
    """
    Render filled PDF forms using overlay composition.

    Strategy:
    1. Create transparent overlay with filled text values using reportlab
    2. Merge overlay with template PDF using pypdf
    3. Result: Template PDF appearance + filled values

    Example:
        >>> renderer = OverlayRenderer()
        >>> output = await renderer.render(
        ...     template_path="blank_form.pdf",
        ...     field_mappings={
        ...         "company_name": {
        ...             "value": "Acme Corp",
        ...             "position": {"x": 100, "y": 200, "width": 200, "height": 20}
        ...         }
        ...     },
        ...     output_path="filled_form.pdf"
        ... )
    """

    def __init__(self, output_dir: str = "output/population"):
        """
        Initialize overlay renderer.

        Args:
            output_dir: Directory for saving filled PDFs
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"OverlayRenderer initialized: output_dir={self.output_dir}")

    async def render(
        self,
        template_path: str,
        field_mappings: Dict[str, Any],
        output_path: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Render filled PDF using overlay approach.

        Args:
            template_path: Path to blank PDF template
            field_mappings: Dict of {field_name: {value, position, ...}}
            output_path: Output path (auto-generated if None)
            options: Rendering options

        Returns:
            Path to rendered PDF

        Raises:
            FileNotFoundError: If template not found
            ValueError: If field mappings invalid
        """
        options = options or {}

        try:
            logger.info(
                f"Rendering PDF: template={template_path}, "
                f"fields={len(field_mappings)}"
            )

            # Validate template exists
            template = Path(template_path)
            if not template.exists():
                raise FileNotFoundError(f"Template not found: {template_path}")

            # Generate output path if not provided
            if output_path is None:
                output_path = str(self._generate_output_path(template_path))

            # Read template PDF to get dimensions
            template_reader = PdfReader(template_path)
            first_page = template_reader.pages[0]
            page_width = float(first_page.mediabox.width)
            page_height = float(first_page.mediabox.height)

            logger.info(f"Template dimensions: {page_width} x {page_height}")

            # Create overlay PDF with filled values
            overlay_buffer = self._create_overlay(
                field_mappings,
                page_width,
                page_height,
                options
            )

            # Merge overlay with template
            final_path = self._merge_pdfs(
                template_reader,
                overlay_buffer,
                output_path
            )

            logger.info(f"Rendered PDF saved to: {final_path}")

            return final_path

        except Exception as e:
            logger.error(f"Rendering failed: {e}", exc_info=True)
            raise

    def _create_overlay(
        self,
        field_mappings: Dict[str, Any],
        page_width: float,
        page_height: float,
        options: Dict[str, Any]
    ) -> BytesIO:
        """
        Create transparent overlay PDF with filled values.

        Args:
            field_mappings: Field mappings with values and positions
            page_width: PDF page width
            page_height: PDF page height
            options: Rendering options

        Returns:
            BytesIO buffer with overlay PDF
        """
        logger.debug(f"Creating overlay for {len(field_mappings)} fields")

        # Create canvas for overlay
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=(page_width, page_height))

        # Set default font
        default_font = options.get("font_family", "Helvetica")
        default_size = options.get("font_size", 10)

        # Render each field
        rendered_count = 0
        for field_name, field_data in field_mappings.items():
            try:
                self._render_field_on_canvas(
                    c,
                    field_name,
                    field_data,
                    page_height,
                    default_font,
                    default_size
                )
                rendered_count += 1
            except Exception as e:
                logger.warning(f"Failed to render field '{field_name}': {e}")

        logger.info(f"Rendered {rendered_count}/{len(field_mappings)} fields")

        # Save canvas to buffer
        c.save()
        buffer.seek(0)

        return buffer

    def _render_field_on_canvas(
        self,
        c: canvas.Canvas,
        field_name: str,
        field_data: Dict[str, Any],
        page_height: float,
        default_font: str,
        default_size: int
    ) -> None:
        """
        Render a single field onto the canvas.

        Args:
            c: Reportlab canvas
            field_name: Name of the field
            field_data: Field data with value and position
            page_height: PDF page height (for coordinate conversion)
            default_font: Default font family
            default_size: Default font size
        """
        # Step 1: Get the text value to render
        value = field_data.get("value", "")
        if not value:
            return  # Skip empty fields

        # Step 2: Get the position where to render (from Gemini vision)
        position = field_data.get("position", {})
        x = position.get("x", 0)
        y = position.get("y", 0)
        width = position.get("width", 100)
        height = position.get("height", 20)

        # Step 3: Convert coordinates
        # Gemini gives us top-left origin (y=0 at top)
        # PDF uses bottom-left origin (y=0 at bottom)
        # So we need to flip the Y coordinate
        pdf_y = page_height - y - height

        # Step 4: Calculate font size based on field height
        # Use 70% of field height, but don't exceed default size
        font_size = min(height * 0.7, default_size)
        font_size = max(font_size, 6)  # Minimum 6pt font

        # Step 5: Set the font and color
        c.setFont(default_font, font_size)
        c.setFillColor(black)

        # Step 6: Truncate text if too long to fit in field width
        text = str(value)
        text_width = c.stringWidth(text, default_font, font_size)

        # If text is too wide, truncate it
        while text_width > width and len(text) > 1:
            text = text[:-1]
            text_width = c.stringWidth(text, default_font, font_size)

        # Step 7: Render the text on the canvas
        # Add small vertical offset to center text in field
        vertical_offset = height * 0.25
        c.drawString(x, pdf_y + vertical_offset, text)

        # Step 8: Log for debugging
        logger.debug(
            f"Rendered '{field_name}' = '{value}' at "
            f"({x:.1f}, {pdf_y:.1f}) size={font_size:.1f}"
        )

    def _merge_pdfs(
        self,
        template_reader: PdfReader,
        overlay_buffer: BytesIO,
        output_path: str
    ) -> str:
        """
        Merge overlay PDF with template PDF.

        Args:
            template_reader: PdfReader for template
            overlay_buffer: BytesIO with overlay PDF
            output_path: Output file path

        Returns:
            Path to merged PDF
        """
        logger.debug("Merging overlay with template")

        # Create PDF writer
        writer = PdfWriter()

        # Read overlay
        overlay_reader = PdfReader(overlay_buffer)

        # Merge pages
        for i, template_page in enumerate(template_reader.pages):
            # Get overlay page (use first page if overlay has fewer pages)
            overlay_page_idx = min(i, len(overlay_reader.pages) - 1)
            overlay_page = overlay_reader.pages[overlay_page_idx]

            # Merge: template content + overlay on top
            template_page.merge_page(overlay_page)

            # Add to writer
            writer.add_page(template_page)

        # Write output
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "wb") as f:
            writer.write(f)

        logger.debug(f"Merged PDF saved: {output_path}")

        return output_path

    def _generate_output_path(self, template_path: str) -> Path:
        """
        Generate unique output file path.

        Args:
            template_path: Template path

        Returns:
            Path for output PDF
        """
        template_name = Path(template_path).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{template_name}_filled_{timestamp}.pdf"

        return self.output_dir / filename

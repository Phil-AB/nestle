"""
HTML to PDF Renderer.

Renders documents from HTML templates with CSS styling and converts to PDF.
Self-registers with RendererRegistry - NO factory changes needed.
"""

from typing import Dict, Any, Optional, List
import os
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, Template
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

from modules.generation.core.interfaces import IRenderer, GenerationResult
from modules.generation.core.exceptions import RendererException
from modules.generation.core.registry import register_renderer
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


@register_renderer("html")  # Registers as 'html' format
class HtmlPdfRenderer(IRenderer):
    """
    HTML to PDF renderer using WeasyPrint.

    Renders beautiful, styled PDF documents from HTML templates.
    Supports full CSS3 styling, custom fonts, and responsive layouts.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        project_root: Optional[Path] = None
    ):
        """
        Initialize HTML PDF renderer.

        Args:
            config: Renderer configuration
            project_root: Project root path for resolving template paths
        """
        super().__init__(config)
        self.project_root = project_root or Path.cwd()

        # Setup Jinja2 environment for templating
        template_dir = self.project_root / "config" / "generation" / "templates" / "files"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True
        )

        # Font configuration for WeasyPrint
        self.font_config = FontConfiguration()

        logger.info(f"Initialized HtmlPdfRenderer with template dir: {template_dir}")

    async def render(
        self,
        template_path: str,
        data: Dict[str, Any],
        options: Optional[Dict[str, Any]] = None
    ) -> GenerationResult:
        """
        Render HTML template to PDF.

        Args:
            template_path: Path to HTML template file (relative to templates dir)
            data: Template data (fields, items, metadata)
            options: Rendering options
                - output_path: Custom output path
                - css_file: Additional CSS file path
                - base_url: Base URL for resolving relative paths

        Returns:
            GenerationResult with PDF file path
        """
        options = options or {}

        try:
            logger.info(f"Rendering HTML template: {template_path}")
            logger.info(f"Data keys: {list(data.keys())}")

            # Resolve template path
            if not os.path.isabs(template_path):
                template_path = str(self.project_root / template_path)

            # Load HTML template
            template_name = Path(template_path).name
            template = self.jinja_env.get_template(template_name)

            # Render HTML with data
            html_content = template.render(**data)

            # Determine output path
            output_path = options.get('output_path')
            if not output_path:
                job_id = options.get('job_id', 'output')
                output_dir = self.project_root / "output" / "generated"
                output_dir.mkdir(parents=True, exist_ok=True)
                output_path = output_dir / f"{job_id}.pdf"

            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Load additional CSS if specified
            css_files = []
            if 'css_file' in options:
                css_path = self.project_root / options['css_file']
                if css_path.exists():
                    css_files.append(CSS(filename=str(css_path), font_config=self.font_config))

            # Convert HTML to PDF using WeasyPrint
            base_url = options.get('base_url', str(self.project_root / "config" / "generation" / "templates" / "files"))

            html_doc = HTML(
                string=html_content,
                base_url=base_url
            )

            html_doc.write_pdf(
                str(output_path),
                stylesheets=css_files,
                font_config=self.font_config
            )

            logger.info(f"Successfully rendered PDF: {output_path}")

            return GenerationResult(
                success=True,
                job_id=options.get('job_id', 'unknown'),
                output_path=str(output_path),
                output_format="pdf",
                renderer_name="html"
            )

        except Exception as e:
            logger.error(f"HTML to PDF rendering failed: {str(e)}", exc_info=True)
            return GenerationResult(
                success=False,
                job_id=options.get('job_id', 'unknown'),
                error_message=f"Rendering failed: {str(e)}"
            )

    def validate_template(self, template_path: str) -> bool:
        """Validate HTML template."""
        try:
            if not Path(template_path).exists():
                return False

            # Try to load the template
            template_name = Path(template_path).name
            self.jinja_env.get_template(template_name)
            return True
        except Exception as e:
            logger.error(f"Template validation failed: {str(e)}")
            return False

    def get_template_fields(self, template_path: str) -> List[str]:
        """Extract field placeholders from HTML template."""
        import re

        if not Path(template_path).exists():
            return []

        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Find {{ field_name }} and {% if field_name %} patterns
            field_pattern = r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_\.]*)\s*(?:\|[^}]*)?\}\}'
            if_pattern = r'\{%\s*if\s+([a-zA-Z_][a-zA-Z0-9_\.]*)'

            fields = set()
            fields.update(re.findall(field_pattern, content))
            fields.update(re.findall(if_pattern, content))

            return list(fields)
        except Exception as e:
            logger.error(f"Failed to extract template fields: {str(e)}")
            return []

    async def health_check(self) -> bool:
        """Check if renderer is functional."""
        try:
            # Test basic HTML to PDF conversion
            test_html = "<html><body><h1>Test</h1></body></html>"
            HTML(string=test_html).write_pdf()
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

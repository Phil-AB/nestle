"""
Template renderers for generation module.

Renderers generate documents from templates.
"""

# Import all renderers to trigger self-registration
from modules.generation.renderers.docx_renderer import DocxRenderer
from modules.generation.renderers.html_pdf_renderer import HtmlPdfRenderer

__all__ = [
    "DocxRenderer",
    "HtmlPdfRenderer",
]

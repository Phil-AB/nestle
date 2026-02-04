"""
PDF Renderers for Population Module.

Renderers for creating populated PDF forms using different strategies:
- OverlayRenderer: Renders filled values as overlay on template PDF
- (Future: Direct field filling, HTML rendering, etc.)
"""

from modules.population.renderers.overlay_renderer import OverlayRenderer

__all__ = ["OverlayRenderer"]

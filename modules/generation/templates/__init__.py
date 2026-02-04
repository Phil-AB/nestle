"""
Template management for generation module.
"""

from modules.generation.templates.registry import TemplateRegistry
from modules.generation.templates.loader import TemplateLoader

__all__ = [
    "TemplateRegistry",
    "TemplateLoader",
]

"""SVG figures for lectures, rendered from a structured hint.

Provides SVG-based diagram templates for common math visualizations.
"""

from .registry import render_diagram, DIAGRAM_REGISTRY

__all__ = ["render_diagram", "DIAGRAM_REGISTRY"]

# Import templates to register them
from . import templates  # noqa: F401

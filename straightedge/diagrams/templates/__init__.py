"""Diagram templates, each registering itself on import.

Import all templates here to ensure they're registered.
"""

from . import lattice_grid  # noqa: F401
from . import coordinate_plane  # noqa: F401
from . import function_graph  # noqa: F401
from . import unit_circle  # noqa: F401
from . import riemann_sum  # noqa: F401
from . import polar_graph  # noqa: F401
from . import dirichlet_function  # noqa: F401
from . import step_function  # noqa: F401
from . import array_state  # noqa: F401
from . import matrix_state  # noqa: F401
from . import linked_list  # noqa: F401
from . import binary_tree  # noqa: F401
from . import stack  # noqa: F401
from . import queue  # noqa: F401
from . import graph  # noqa: F401
from . import hash_table  # noqa: F401
from . import call_stack  # noqa: F401
from . import dp_table  # noqa: F401
from . import environment_diagram  # noqa: F401
from . import architecture_diagram  # noqa: F401
from . import matrix_transform  # noqa: F401
from . import heatmap  # noqa: F401
from . import project_network  # noqa: F401
from . import gantt  # noqa: F401
from . import wbs  # noqa: F401
from . import aoa_work  # noqa: F401
from . import aon_node  # noqa: F401
from . import structure_chart  # noqa: F401
from . import flow_diagram  # noqa: F401
from . import cycle_diagram  # noqa: F401
from . import t_account  # noqa: F401
from . import comparison  # noqa: F401
from . import timeline  # noqa: F401
from . import roadmap  # noqa: F401
from . import org_chart  # noqa: F401
from . import descent_triangles  # noqa: F401
from . import circle_chord_rational  # noqa: F401

__all__ = [
    "lattice_grid",
    "coordinate_plane",
    "function_graph",
    "unit_circle",
    "riemann_sum",
    "polar_graph",
    "dirichlet_function",
    "step_function",
    "array_state",
    "matrix_state",
    "linked_list",
    "binary_tree",
    "stack",
    "queue",
    "graph",
    "hash_table",
    "call_stack",
    "dp_table",
    "environment_diagram",
    "architecture_diagram",
    "matrix_transform",
    "heatmap",
    "project_network",
    "gantt",
    "wbs",
    "aoa_work",
    "aon_node",
    "structure_chart",
    "flow_diagram",
    "cycle_diagram",
    "t_account",
    "comparison",
    "timeline",
    "descent_triangles",
    "circle_chord_rational",
    "roadmap",
    "org_chart",
]

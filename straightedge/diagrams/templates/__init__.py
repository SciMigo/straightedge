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
from . import algorithm_trace  # noqa: F401
from . import animated_trace  # noqa: F401
from . import graph_traversal  # noqa: F401
from . import graph_algorithm  # noqa: F401
from . import disjoint_set  # noqa: F401
from . import priority_queue  # noqa: F401
from . import block_cut_tree  # noqa: F401
from . import graph_representation  # noqa: F401
from . import matrix_state  # noqa: F401
from . import linked_list  # noqa: F401
from . import binary_tree  # noqa: F401
from . import search_tree  # noqa: F401
from . import stack  # noqa: F401
from . import queue  # noqa: F401
from . import graph  # noqa: F401
from . import planar_graph  # noqa: F401
from . import network_flow  # noqa: F401
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
from . import construction  # noqa: F401
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
    "algorithm_trace",
    "animated_trace",
    "graph_traversal",
    "graph_algorithm",
    "disjoint_set",
    "priority_queue",
    "block_cut_tree",
    "graph_representation",
    "matrix_state",
    "linked_list",
    "binary_tree",
    "search_tree",
    "stack",
    "queue",
    "graph",
    "planar_graph",
    "network_flow",
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
    "construction",
]

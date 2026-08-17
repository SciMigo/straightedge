"""Tests for architecture_diagram template."""

import pytest

from straightedge.diagrams import render_diagram, DIAGRAM_REGISTRY


class TestRegistration:
    def test_architecture_diagram_registered(self):
        assert "architecture_diagram" in DIAGRAM_REGISTRY


class TestWrappedFormat:
    """Test the standard wrapped format (L02/L13 style): {type, params: {components, connections}}."""

    HINT = {
        "type": "architecture_diagram",
        "params": {
            "title": "API-first service architecture",
            "components": [
                {"id": "client", "type": "client", "label": "Client (Web/Mobile)"},
                {"id": "lb", "type": "service", "label": "Load Balancer"},
                {"id": "svc", "type": "service", "label": "App Service"},
                {"id": "db", "type": "database", "label": "PostgreSQL"},
                {"id": "cache", "type": "cache", "label": "Redis Cache"},
            ],
            "connections": [
                {"from": "client", "to": "lb", "label": "HTTPS"},
                {"from": "lb", "to": "svc"},
                {"from": "svc", "to": "db", "label": "SQL"},
                {"from": "svc", "to": "cache", "label": "get/set"},
            ],
            "annotations": [
                {"text": "Stateless tier scales horizontally", "near": "svc"},
            ],
            "caption": "A reusable API template",
        },
    }

    def test_renders_svg(self):
        svg = render_diagram(self.HINT)
        assert svg.startswith("<svg")
        assert "</svg>" in svg

    def test_contains_all_labels(self):
        svg = render_diagram(self.HINT)
        assert "Client (Web/Mobile)" in svg
        assert "Load Balancer" in svg
        assert "App Service" in svg
        assert "PostgreSQL" in svg
        assert "Redis Cache" in svg

    def test_contains_connection_labels(self):
        svg = render_diagram(self.HINT)
        assert "HTTPS" in svg
        assert "SQL" in svg

    def test_contains_caption(self):
        svg = render_diagram(self.HINT)
        assert "A reusable API template" in svg

    def test_contains_annotation(self):
        svg = render_diagram(self.HINT)
        assert "Stateless tier scales horizontally" in svg

    def test_arrow_marker_defined(self):
        svg = render_diagram(self.HINT)
        assert "arch-arrow" in svg
        assert "<marker" in svg


class TestFlatFormat:
    """Test the flat format (L06 style): {type, elements, connections, layout}."""

    HINT = {
        "type": "architecture_diagram",
        "layout": "left-to-right",
        "elements": [
            {"id": "mobile", "kind": "external", "label": "Mobile Client"},
            {"id": "gw", "kind": "service_cluster", "label": "Gateway (WebSocket)"},
            {"id": "chat_svc", "kind": "service", "label": "Chat Service"},
            {"id": "msg_queue", "kind": "queue", "label": "Message Queue"},
            {"id": "msg_db", "kind": "database", "label": "Message DB"},
        ],
        "connections": [
            {"from": "mobile", "to": "gw", "label": "send message"},
            {"from": "gw", "to": "chat_svc"},
            {"from": "chat_svc", "to": "msg_queue"},
            {"from": "msg_queue", "to": "msg_db"},
        ],
        "notes": [
            "Idempotency via client message id",
            "Fanout handled by queue consumers",
        ],
    }

    def test_renders_svg(self):
        svg = render_diagram(self.HINT)
        assert svg.startswith("<svg")
        assert "</svg>" in svg

    def test_kind_normalised(self):
        """Elements with 'kind' should render just like 'type'."""
        svg = render_diagram(self.HINT)
        assert "Mobile Client" in svg
        assert "Gateway (WebSocket)" in svg
        assert "Message DB" in svg

    def test_notes_rendered_as_annotations(self):
        svg = render_diagram(self.HINT)
        assert "Idempotency via client message id" in svg

    def test_connection_labels(self):
        svg = render_diagram(self.HINT)
        assert "send message" in svg


class TestComponentKinds:
    """Each component kind should produce a valid SVG fragment."""

    KINDS = [
        "service", "service_cluster", "worker",
        "database", "datastore",
        "cache",
        "queue", "bus",
        "client", "external",
    ]

    @pytest.mark.parametrize("kind", KINDS)
    def test_kind_renders(self, kind):
        hint = {
            "type": "architecture_diagram",
            "params": {
                "components": [
                    {"id": "a", "type": kind, "label": f"Test {kind}"},
                ],
                "connections": [],
            },
        }
        svg = render_diagram(hint)
        assert svg.startswith("<svg")
        assert f"Test {kind}" in svg

    def test_database_uses_path(self):
        """Database components should render a cylinder (SVG path), not a rect."""
        hint = {
            "type": "architecture_diagram",
            "params": {
                "components": [{"id": "db", "type": "database", "label": "DB"}],
                "connections": [],
            },
        }
        svg = render_diagram(hint)
        assert "<path" in svg

    def test_cache_uses_dashed_border(self):
        hint = {
            "type": "architecture_diagram",
            "params": {
                "components": [{"id": "c", "type": "cache", "label": "Cache"}],
                "connections": [],
            },
        }
        svg = render_diagram(hint)
        assert "stroke-dasharray" in svg

    def test_service_uses_rounded_rect(self):
        hint = {
            "type": "architecture_diagram",
            "params": {
                "components": [{"id": "s", "type": "service", "label": "Svc"}],
                "connections": [],
            },
        }
        svg = render_diagram(hint)
        assert "<rect" in svg
        assert 'rx="8"' in svg


class TestLayout:
    COMPONENTS = [
        {"id": "a", "type": "client", "label": "A"},
        {"id": "b", "type": "service", "label": "B"},
        {"id": "c", "type": "database", "label": "C"},
    ]
    CONNECTIONS = [
        {"from": "a", "to": "b"},
        {"from": "b", "to": "c"},
    ]

    def test_left_to_right_default(self):
        hint = {
            "type": "architecture_diagram",
            "params": {
                "components": self.COMPONENTS,
                "connections": self.CONNECTIONS,
            },
        }
        svg = render_diagram(hint)
        assert svg.startswith("<svg")

    def test_top_to_bottom(self):
        hint = {
            "type": "architecture_diagram",
            "params": {
                "components": self.COMPONENTS,
                "connections": self.CONNECTIONS,
                "layout": "top-to-bottom",
            },
        }
        svg = render_diagram(hint)
        assert svg.startswith("<svg")

    def test_invalid_layout_falls_back(self):
        hint = {
            "type": "architecture_diagram",
            "params": {
                "components": self.COMPONENTS,
                "connections": self.CONNECTIONS,
                "layout": "diagonal",
            },
        }
        svg = render_diagram(hint)
        assert svg.startswith("<svg")


class TestGracefulDegradation:
    def test_empty_components(self):
        hint = {
            "type": "architecture_diagram",
            "params": {"components": [], "connections": []},
        }
        svg = render_diagram(hint)
        assert svg == ""

    def test_missing_components_key(self):
        hint = {"type": "architecture_diagram", "params": {}}
        svg = render_diagram(hint)
        assert svg == ""

    def test_no_connections(self):
        hint = {
            "type": "architecture_diagram",
            "params": {
                "components": [
                    {"id": "a", "type": "service", "label": "A"},
                    {"id": "b", "type": "service", "label": "B"},
                ],
            },
        }
        svg = render_diagram(hint)
        assert svg.startswith("<svg")
        assert "A" in svg
        assert "B" in svg

    def test_connection_to_unknown_node(self):
        hint = {
            "type": "architecture_diagram",
            "params": {
                "components": [{"id": "a", "type": "service", "label": "A"}],
                "connections": [{"from": "a", "to": "missing"}],
            },
        }
        svg = render_diagram(hint)
        assert svg.startswith("<svg")

    def test_component_without_id_skipped(self):
        hint = {
            "type": "architecture_diagram",
            "params": {
                "components": [
                    {"type": "service", "label": "No ID"},
                    {"id": "ok", "type": "service", "label": "OK"},
                ],
                "connections": [],
            },
        }
        svg = render_diagram(hint)
        assert "OK" in svg


class TestFlatFormatRegistryIntegration:
    """Test that the registry correctly passes flat-format hints."""

    def test_flat_format_without_params_key(self):
        hint = {
            "type": "architecture_diagram",
            "elements": [
                {"id": "x", "kind": "service", "label": "X"},
            ],
            "connections": [],
        }
        svg = render_diagram(hint)
        assert svg.startswith("<svg")
        assert "X" in svg

    def test_wrapped_format_with_params_key(self):
        hint = {
            "type": "architecture_diagram",
            "params": {
                "components": [
                    {"id": "y", "type": "service", "label": "Y"},
                ],
                "connections": [],
            },
        }
        svg = render_diagram(hint)
        assert svg.startswith("<svg")
        assert "Y" in svg


class TestRealL06Data:
    """Integration test with actual L06 hint structure."""

    HINT = {
        "type": "architecture_diagram",
        "style": "PowerPoint",
        "layout": "left-to-right",
        "color_coding": {
            "services": "light blue",
            "datastores": "light green",
            "queues": "light purple",
            "external_clients": "light gray",
        },
        "elements": [
            {"id": "mobile_client", "kind": "external", "label": "Mobile Client"},
            {"id": "gateway_cluster", "kind": "service_cluster", "label": "Gateway (WebSocket/MQTT)"},
            {"id": "chat_service", "kind": "service", "label": "Chat Service"},
            {"id": "fanout_queue", "kind": "queue", "label": "Fanout Queue"},
            {"id": "presence_service", "kind": "service", "label": "Presence Service"},
            {"id": "message_db", "kind": "database", "label": "Message DB (Cassandra)"},
            {"id": "session_cache", "kind": "cache", "label": "Session Cache (Redis)"},
        ],
        "connections": [
            {"from": "mobile_client", "to": "gateway_cluster", "label": "send message"},
            {"from": "gateway_cluster", "to": "chat_service", "label": "route"},
            {"from": "chat_service", "to": "message_db", "label": "persist"},
            {"from": "chat_service", "to": "fanout_queue", "label": "enqueue"},
            {"from": "fanout_queue", "to": "gateway_cluster", "label": "push to recipients"},
            {"from": "gateway_cluster", "to": "session_cache", "label": "lookup session"},
            {"from": "presence_service", "to": "session_cache", "label": "heartbeat"},
        ],
        "notes": [
            "Idempotency via client message id to deduplicate retries",
            "Fanout queue decouples write latency from recipient count",
        ],
    }

    def test_renders_complete_svg(self):
        svg = render_diagram(self.HINT)
        assert svg.startswith("<svg")
        assert "</svg>" in svg

    def test_all_components_present(self):
        svg = render_diagram(self.HINT)
        for elem in self.HINT["elements"]:
            assert elem["label"] in svg, f"Missing label: {elem['label']}"

    def test_all_labeled_connections(self):
        svg = render_diagram(self.HINT)
        for conn in self.HINT["connections"]:
            if "label" in conn:
                assert conn["label"] in svg, f"Missing connection label: {conn['label']}"

    def test_notes_present(self):
        svg = render_diagram(self.HINT)
        assert "Idempotency via client message id" in svg

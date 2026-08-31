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


class TestLabelsFitAndNotesStack:
    """The four legibility errors this template shipped with in 0.5.0.

    Every unanchored note was placed at one hard-coded spot, so two notes were
    drawn one on top of the other and the reader saw neither -- and each was
    centred on the left margin, which put most of a 300px note off the canvas.
    Separately, a component label was drawn at whatever width it happened to
    be: "Gateway (WebSocket/MQTT)" measured 186px in a 140px box and reached
    far enough out to collide with the label on the connection leaving it.
    """

    HINT = {
        "type": "architecture_diagram",
        "params": {
            "elements": [
                {"id": "gw", "kind": "service", "label": "Gateway (WebSocket/MQTT)"},
                {"id": "svc", "kind": "service", "label": "Chat Service"},
                {"id": "cache", "kind": "cache", "label": "Session Cache (Redis)"},
            ],
            "connections": [{"from": "gw", "to": "svc", "label": "route"},
                            {"from": "svc", "to": "cache", "label": "lookup"}],
            "notes": ["Idempotency via client message id to deduplicate retries",
                      "Fanout queue decouples write latency from recipient count",
                      "Presence heartbeats are cheaper than a full session read"],
        },
    }

    def _boxes(self):
        from straightedge.diagrams.legibility import boxes_from_svg

        return boxes_from_svg(render_diagram(self.HINT))

    def test_the_figure_carries_no_legibility_error(self):
        from straightedge.diagrams.legibility import check_figure

        errors = [f for f in check_figure(render_diagram(self.HINT))
                  if f.severity == "error"]
        assert not errors, [f.message for f in errors]

    def test_no_two_notes_share_a_line(self):
        notes = sorted(b.y0 for b in self._boxes()
                       if b.kind == "text" and b.label.startswith(
                           ("Idempotency", "Fanout", "Presence")))
        assert len(notes) == 3
        assert len(set(notes)) == 3, f"notes drawn on top of each other at {notes}"

    def test_a_note_starts_inside_the_canvas(self):
        """Centring a long note on the left margin put its first half off the
        left edge, which is not a collision but is just as unreadable."""
        for b in self._boxes():
            if b.kind == "text" and b.label.startswith(("Idempotency", "Fanout")):
                assert b.x0 >= 0, f"{b.label!r} starts at x={b.x0}"

    def test_a_component_label_fits_its_box(self):
        from straightedge.diagrams.templates.architecture_diagram import _BOX_W

        for b in self._boxes():
            if b.kind == "text" and b.y0 < 250 and not b.label.startswith(
                    ("Idempotency", "Fanout", "Presence")):
                assert b.x1 - b.x0 <= _BOX_W, f"{b.label!r} is {b.x1 - b.x0:.0f}px"

    def test_the_whole_label_survives_even_when_the_box_cannot_show_it(self):
        """Wrapping and trimming both lose text on screen. The full string is
        the accessible name, so it is still in the document and still findable
        by anything reading it rather than looking at it."""
        svg = render_diagram(self.HINT)
        for elem in self.HINT["params"]["elements"]:
            assert f"<title>{elem['label']}</title>" in svg

    def test_each_title_names_its_own_component(self):
        """A `<title>` names its *parent*. Emitted beside the shapes they were
        seven children of the root `<svg>`, every one naming the whole document
        and all but the first ignored — the string was in the file and the
        tooltip and accessible name this claims to provide were not.
        """
        import xml.etree.ElementTree as ET

        ns = "{http://www.w3.org/2000/svg}"
        root = ET.fromstring(render_diagram(self.HINT))
        assert not [c for c in root if c.tag == f"{ns}title"], (
            "a title at root level names the document, not a component")
        titled = {}
        for g in root.iter(f"{ns}g"):
            first = list(g)[0] if len(g) else None
            if first is not None and first.tag == f"{ns}title":
                titled[first.text] = g
        for elem in self.HINT["params"]["elements"]:
            assert elem["label"] in titled, f"{elem['label']!r} names no group"
            shapes = [c.tag.split("}")[-1] for c in titled[elem["label"]]]
            assert any(t in ("rect", "path") for t in shapes), (
                f"{elem['label']!r} titles a group with no shape in it")


class TestALooseNoteKeepsItsText:
    """A note with nowhere to point goes in the bottom stack, and used to be
    trimmed to one line with an ellipsis and nothing holding the rest.

    Component labels got a `<title>` for exactly this and notes did not, so on a
    narrow diagram the note the caller supplied was not in the document at all —
    the ellipsis makes the loss visible on screen and recoverable nowhere.
    """

    LONG = "Idempotency via client message id to deduplicate retries across reconnects"

    def _svg(self, *notes, elements=None):
        return render_diagram({"type": "architecture_diagram", "params": {
            "elements": elements or [{"id": "a", "kind": "service", "label": "Only"}],
            "notes": list(notes)}})

    def _titles(self, svg):
        import xml.etree.ElementTree as ET

        ns = "{http://www.w3.org/2000/svg}"
        return [t.text for t in ET.fromstring(svg).iter(f"{ns}title")]

    def test_a_trimmed_note_is_still_in_the_document(self):
        assert self.LONG in self._titles(self._svg(self.LONG))

    def test_it_is_not_trimmed_when_the_canvas_has_room(self):
        """The old behaviour trimmed to one line whatever the width. A chained
        diagram lays out left-to-right and is 800px wide, which this note fits
        on a single line — so nothing should be cut from it at all."""
        import re

        els = [{"id": c, "kind": "service", "label": c} for c in "abcd"]
        conns = [{"from": a, "to": b} for a, b in zip("abc", "bcd")]
        svg = render_diagram({"type": "architecture_diagram", "params": {
            "elements": els, "connections": conns, "notes": [self.LONG]}})
        drawn = "".join(re.findall(r'font-style="italic"[^>]*>([^<]*)<', svg))
        assert "…" not in drawn, f"trimmed with room to spare: {drawn!r}"
        assert self.LONG in drawn, "the note was not drawn in full"

    def test_a_note_too_long_for_two_lines_keeps_its_text(self):
        note = "A" * 400
        svg = self._svg(note)
        assert note in self._titles(svg), "nothing holds what the lines could not"

    def test_the_reserved_height_holds_every_line(self):
        from straightedge.diagrams.legibility import check_figure

        svg = self._svg(self.LONG, "A" * 400, "short")
        assert not [f for f in check_figure(svg) if f.severity == "error"]

    def test_notes_still_do_not_share_a_line(self):
        from straightedge.diagrams.legibility import boxes_from_svg

        svg = self._svg("first note here", "second note here", "third note here")
        ys = sorted(b.y0 for b in boxes_from_svg(svg)
                    if b.kind == "text" and b.label.endswith("note here"))
        assert len(ys) == 3 and len(set(ys)) == 3, f"notes overlap at {ys}"


class TestAnchoredAnnotationsGetTheSameCare:
    """The loose-note rewrite skipped the notes that *do* point at something.

    An anchored annotation was drawn raw eight lines above the rewritten
    branch: unwrapped, unmeasured, no ``<title>``, and every note on one
    component at the same per-node spot — so two of them overlapped by 100%
    and a long one overhung the frame with nothing holding the lost text.
    """

    def _svg(self, *annotations):
        return render_diagram({"type": "architecture_diagram", "params": {
            "components": [{"id": "api", "type": "service", "label": "API"}],
            "annotations": [{"text": t, "near": "api"} for t in annotations],
        }})

    def test_two_notes_on_one_component_do_not_overlap(self):
        from straightedge.diagrams.legibility import check_figure

        svg = self._svg("first note", "second note")
        assert not [f for f in check_figure(svg) if f.check == "text_overlap"]

    def test_a_long_note_is_wrapped_not_clipped(self):
        from straightedge.diagrams.legibility import check_figure

        svg = self._svg("a note long enough that drawn raw it overhung the frame")
        errors = [f for f in check_figure(svg)
                  if f.check in ("text_clipped", "out_of_frame")
                  and f.severity == "error"]
        assert not errors, [f.message for f in errors]

    def test_the_full_text_is_the_accessible_name(self):
        note = "a note long enough that drawn raw it overhung the frame"
        assert f"<title>{note}</title>" in self._svg(note)


class TestALabelWrapsBeforeItTruncates:
    """The wrapper counts Latin at a flat half-em and the fitter measures with
    the per-character table plus the substitution headroom, so a label could
    pass the wrap count and fail the measure: "Session Cache (Redis)" came
    back as the single line "Session Cache (R…" with its second line empty,
    on the figure the wrap-don't-truncate rewrite shipped with."""

    def test_a_label_that_fits_two_lines_uses_them(self):
        svg = render_diagram({"type": "architecture_diagram", "params": {
            "components": [{"id": "c", "type": "cache",
                            "label": "Session Cache (Redis)"}]}})
        assert ">Session Cache<" in svg
        assert ">(Redis)<" in svg
        assert "…" not in svg, "ellipsised with a whole line to spare"


class TestAnchoredAnnotationsParticipateInLayout:
    """A stack that grows below its component without the layout knowing
    lands on whatever the layout put there — the component below it — or,
    under a bottom-row component, runs off the canvas. The notes are wrapped
    before layout so the gaps widen for the tallest stack and the canvas
    reserves the room a bottom stack draws into."""

    def test_four_wrapped_notes_fit_the_canvas(self):
        from straightedge.diagrams.legibility import check_figure

        svg = render_diagram({"type": "architecture_diagram", "params": {
            "components": [{"id": "api", "label": "API"}],
            "annotations": [{"text": f"note number {i} long enough to wrap "
                                     "to two lines here", "near": "api"}
                            for i in range(4)]}})
        errors = [f for f in check_figure(svg)
                  if f.check in ("text_clipped", "out_of_frame")
                  and f.severity == "error"]
        assert not errors, [f.message for f in errors]

    @pytest.mark.parametrize("layout", ["left-to-right", "top-to-bottom"])
    def test_a_note_clears_the_component_below_its_anchor(self, layout):
        from straightedge.diagrams.legibility import check_figure

        svg = render_diagram({"type": "architecture_diagram", "params": {
            "components": [{"id": "a", "label": "Upper"},
                           {"id": "b", "label": "Lower"}],
            "connections": ([{"from": "a", "to": "b"}]
                            if layout == "top-to-bottom" else []),
            "layout": layout,
            "annotations": [{"text": "a two line annotation that wraps "
                                     "because it is long", "near": "a"}]}})
        # The gate is the note landing *on* the lower component (or another
        # label). A connection stroke crossing the note is the ungated warn
        # class every centred annotation under a connected component has
        # always carried.
        collisions = [f for f in check_figure(svg)
                      if (f.check == "text_overlap" or "covered" in f.message)
                      and ("annotation" in (f.label or "")
                           or "wraps" in (f.label or ""))]
        assert not collisions, [f.message for f in collisions]


class TestFitLinesWrapsByMeasure:
    """The wrap and the fit must speak the same measure. Unit counting calls
    fifteen W's seven and a half ems when they render at eleven, so the
    wrapper handed the fitter one over-full line and a whole empty one; the
    breaks are now chosen with the same safe per-character widths the fitter
    and the legibility check apply."""

    def test_wide_glyphs_use_the_second_line(self):
        from straightedge.diagrams.renderer import fit_lines, text_width

        lines = fit_lines("W" * 15, 128, 12)
        assert len(lines) == 2 and "…" not in "".join(lines)
        assert "".join(lines) == "W" * 15
        assert all(text_width(line, 12, safe=True) <= 128 for line in lines)

    def test_words_still_break_at_spaces(self):
        from straightedge.diagrams.renderer import fit_lines

        assert fit_lines("Session Cache (Redis)", 128, 12) == [
            "Session Cache", "(Redis)"]

    def test_a_genuine_overflow_is_still_marked(self):
        from straightedge.diagrams.renderer import fit_lines, text_width

        lines = fit_lines("W" * 40, 128, 12)
        assert len(lines) == 2 and lines[-1].endswith("…")
        assert all(text_width(line, 12, safe=True) <= 128 for line in lines)

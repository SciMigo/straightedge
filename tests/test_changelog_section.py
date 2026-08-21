"""Release notes come out of the changelog, and an empty one is refused.

`publish.yml` uploaded to PyPI on a version tag and stopped there, so the
Releases page skipped 0.3.0, 0.3.1 and 0.3.2 while all three were tagged and on
the index — it read as though the project went from 0.2.0 to 0.4.0.

The workflow now creates the release too, and these guard the part that could go
wrong quietly. A release body is the one artifact nobody proofreads before it is
public: a shell one-liner that emitted an empty string would publish an empty
release and report success.
"""
from __future__ import annotations

import pytest

from tools.changelog_section import (
    CHANGELOG,
    is_prerelease,
    section_for,
    sections,
)

SAMPLE = """# Changelog

Some preamble that belongs to no version.

## [Unreleased]

### Added
- something not shipped yet

## [1.2.0] - 2026-01-02

A headline paragraph.

### Fixed
- a thing

## [1.1.0] - 2026-01-01

### Added
- the first thing
"""


class TestParsing:
    def test_every_heading_is_found(self):
        assert set(sections(SAMPLE)) == {"Unreleased", "1.2.0", "1.1.0"}

    def test_a_section_stops_at_the_next_heading(self):
        body = sections(SAMPLE)["1.2.0"]
        assert "A headline paragraph." in body and "a thing" in body
        assert "the first thing" not in body

    def test_the_preamble_belongs_to_no_version(self):
        assert all("preamble" not in body for body in sections(SAMPLE).values())

    def test_the_leading_v_is_optional(self):
        assert section_for("v1.2.0", SAMPLE) == section_for("1.2.0", SAMPLE)


class TestRefusals:
    def test_a_missing_version_names_the_ones_that_exist(self):
        with pytest.raises(SystemExit) as excinfo:
            section_for("9.9.9", SAMPLE)
        assert "1.2.0" in str(excinfo.value) and "1.1.0" in str(excinfo.value)

    def test_an_empty_section_is_refused(self):
        """An empty release body is worse than a failed step: it is public."""
        with pytest.raises(SystemExit, match="empty"):
            section_for("1.0.0", "## [1.0.0] - 2026-01-01\n\n## [0.9.0]\n- x\n")

    def test_a_tag_dated_as_unreleased_is_refused(self):
        """Tagging v1.3.0 while the changelog still says Unreleased means the
        notes were never written — which the release must report, not paper
        over by publishing whatever was nearest."""
        with pytest.raises(SystemExit):
            section_for("1.3.0", SAMPLE)


class TestPrereleaseDetection:
    @pytest.mark.parametrize("version,expected", [
        ("0.4.0", False), ("v0.4.0", False), ("1.0", False), ("2", False),
        ("0.5.0rc1", True), ("1.0.0b2", True), ("0.4.0.dev1", True),
        ("1.0.0-alpha", True),
    ])
    def test_it(self, version, expected):
        assert is_prerelease(version) is expected


class TestAgainstTheRealChangelog:
    def test_the_current_version_has_notes(self):
        """The version the package reports must be writable as a release."""
        import straightedge

        body = section_for(straightedge.__version__)
        assert len(body.splitlines()) > 3

    def test_every_shipped_version_has_a_section(self):
        """A tag with no changelog entry is a release nobody wrote up, and the
        workflow would refuse it at exactly the wrong moment — after PyPI."""
        found = sections(CHANGELOG.read_text(encoding="utf-8"))
        for version in ("0.1.0", "0.2.0", "0.3.0", "0.3.1", "0.3.2", "0.4.0"):
            assert version in found, f"{version} is tagged and has no notes"
            assert found[version].strip()

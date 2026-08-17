"""On-screen label language.

The distinction this module exists to keep: narration language is the caller's
(it arrives in the job payload), label language is the *scene's*. Getting only
the first right ships English audio over Chinese titles, which is what a
US-market render used to do.
"""

from __future__ import annotations

import pytest

from straightedge.calculus import ConceptCalculus
from straightedge.conics import ConceptConic
from straightedge.labels import (
    AUTHORED_LANGUAGE, DEFAULT_LANGUAGE, LANGUAGES, TRANSLATIONS,
    needs_cjk_font, normalize, translate, untranslated,
)
from straightedge.models import AnimationPlan, Topic
from straightedge.solids3d import Concept3D
from straightedge.templates import scene_code_for
from straightedge.trig import Concept as ConceptTrig


def _plan(topic=Topic.CONIC, concept=ConceptConic.ELLIPSE_FOCI):
    return AnimationPlan(
        topic=topic, title_zh="A Title", objective_zh="目标", english_prompt="p",
        concept=concept, parameters={"expression": "x**2"},
    )


def _every_concept():
    cases = [(t, None) for t in Topic.ALL]
    for cls, topic in [(ConceptConic, Topic.CONIC), (ConceptCalculus, Topic.CALCULUS),
                       (Concept3D, Topic.THREE_D), (ConceptTrig, Topic.TRIG)]:
        cases += [(topic, getattr(cls, n)) for n in dir(cls) if n.isupper()]
    return cases


class TestNormalize:

    @pytest.mark.parametrize("value,expected", [
        ("en", "en"), ("zh", "zh"),
        ("zh-CN", "zh"), ("en-US", "en"), ("EN", "en"),
    ])
    def test_the_forms_the_job_api_speaks(self, value, expected):
        """`AnimationJobRequest.language` is `en` | `zh-CN`, so the regional tag
        has to resolve rather than fall through to the default.
        """
        assert normalize(value) == expected

    @pytest.mark.parametrize("value", [None, "", "  ", "fr", "klingon"])
    def test_anything_else_is_the_default(self, value):
        assert normalize(value) == DEFAULT_LANGUAGE

    def test_the_default_is_a_supported_language(self):
        assert DEFAULT_LANGUAGE in LANGUAGES


class TestDefaultIsNotAuthored:
    """Two different questions that used to share one constant.

    `AUTHORED_LANGUAGE` is a fact about the source — the builders are written in
    Chinese, so translation is a no-op in that direction. `DEFAULT_LANGUAGE` is
    a product choice — the launch market is US YouTube and TikTok. Collapsing
    them is what made "no language specified" mean "Chinese labels".
    """

    def test_asking_for_nothing_gets_the_launch_market(self):
        assert DEFAULT_LANGUAGE == "en"

    def test_the_builders_are_still_authored_in_chinese(self):
        """The catalog is keyed by the Chinese literal, so this is also what
        makes a later Chinese track free rather than a re-authoring job.
        """
        assert AUTHORED_LANGUAGE == "zh"
        assert all(any("一" <= ch <= "鿿" for ch in key)
                   for key in TRANSLATIONS), "every catalog key is a Chinese literal"

    def test_a_scene_with_no_stated_language_renders_english(self):
        assert "Sum of Distances to the Foci" in scene_code_for(_plan())

    def test_the_authored_language_is_still_reachable(self):
        """A Chinese render must stay one argument away, not one refactor away."""
        assert "椭圆的焦点距离和" in scene_code_for(_plan(), language=AUTHORED_LANGUAGE)


class TestTranslate:

    def test_the_authored_language_is_untouched(self):
        code = scene_code_for(_plan())
        assert translate(code, "zh") == code

    def test_labels_become_english(self):
        assert "Sum of Distances to the Foci" in scene_code_for(_plan(), language="en")

    def test_a_phrase_is_matched_whole_not_by_fragment(self):
        """`"PF = d(P, 准线)"` contains `"准线"`, which is itself a label.

        Fragment substitution would rewrite the inner one first and leave the
        outer phrase half-English and unmatchable.
        """
        code = translate('label = MathTex("PF = d(P, 准线)")', "en")
        assert 'MathTex("PF = d(P, directrix)")' in code

    def test_an_unknown_label_is_left_alone_not_blanked(self):
        """A Chinese caption is a visible, reportable defect. An empty one looks
        like a render bug and loses the text entirely.
        """
        assert translate('_t("没有翻译")', "en") == '_t("没有翻译")'

    def test_a_comment_is_not_rewritten(self):
        """Only quoted literals are labels; prose about them is not."""
        source = "# the 准线 label sits below the curve\n"
        assert translate(source, "en") == source

    def test_an_empty_translation_is_honoured(self):
        """Chinese circumfixes (`函数` + formula + `的图像`) need a prefix only in
        English, so the suffix legitimately translates to nothing.
        """
        assert TRANSLATIONS["的图像"] == ""
        assert '_t("")' in translate('_t("的图像")', "en")


class TestCoverage:
    """A missing translation is a Chinese caption on an English channel."""

    @pytest.mark.parametrize("topic,concept", _every_concept())
    def test_every_concept_renders_fully_in_english(self, topic, concept):
        code = scene_code_for(_plan(topic, concept), language="en")
        assert untranslated(code, "en") == []

    def test_untranslated_reports_what_is_missing(self):
        assert untranslated('_t("没有翻译")', "en") == ["没有翻译"]

    def test_nothing_is_missing_in_the_authored_language(self):
        assert untranslated('_t("没有翻译")', "zh") == []

    def test_a_docstring_is_not_a_label(self):
        """The solid helpers carry Chinese in their docstrings. Those are never
        drawn, so reporting them would be noise that hides a real caption.
        """
        assert untranslated('    """Outline mobjects for textbook 三视图.\n', "en") == []


class TestFontRequirement:

    def test_english_does_not_need_a_cjk_font(self):
        """An English scene has no CJK glyphs left, so failing its render for a
        missing font would block a host that can serve it perfectly well.
        """
        assert needs_cjk_font("en") is False

    def test_chinese_still_does(self):
        assert needs_cjk_font("zh") is True

    def test_the_default_render_needs_no_cjk_font(self):
        """Follows from the default being English: a US-market host should not
        need a Chinese font installed to serve the only language it ships.
        """
        assert needs_cjk_font(None) is False


class TestLabelsFitTheFrame:
    """Translation alone is not enough.

    Chinese is dense: one 20-character caption becomes 66 in English. Layouts
    tuned against Chinese ran off both edges once translated — the first English
    vertical render clipped its conclusion to "oints whose distances to the two
    foci have a cons".
    """

    def test_the_text_helper_shrinks_what_would_overflow(self):
        assert "config.frame_width * 0.92" in scene_code_for(_plan())

    @pytest.mark.parametrize("topic,concept", _every_concept())
    def test_english_captions_stay_short(self, topic, concept):
        """Shrink-to-fit is the fallback, not the plan — a caption that only
        fits because it was scaled to 60% is unreadable on a phone.
        """
        code = scene_code_for(_plan(topic, concept), language="en")
        for english in TRANSLATIONS.values():
            if english and english in code:
                assert len(english) <= 70, f"caption too long to read: {english!r}"

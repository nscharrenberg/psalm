from catalog import build_catalog

import psalm.dimensions as psalm_dimensions
from psalm.dimensions.base import Dimension

# `psalm.dimensions.__all__` currently exports 10 built-in Dimension instances
# (verified live below, not hardcoded), not 9 as an earlier version of this
# plan assumed -- a same-day SDK refactor added SCENE_SEQUENCE, NARRATIVE_VOICE,
# WRITING_STYLE, CITATIONS, PASTICHE, and PARODY_SATIRE alongside the original
# CHARACTER, PLOT, WORLD_BUILDING, SCENES_A_FAIRE. Deriving the expected count
# from the live module (rather than hardcoding either 9 or 10) keeps this test
# honest if the SDK's dimension set changes again.
_LIVE_BUILTIN_DIMENSIONS = [
    getattr(psalm_dimensions, name)
    for name in psalm_dimensions.__all__
    if isinstance(getattr(psalm_dimensions, name), Dimension)
]


def test_build_catalog_includes_all_builtin_dimensions():
    catalog = build_catalog()
    assert len(catalog.dimensions) == len(_LIVE_BUILTIN_DIMENSIONS)
    assert all(d.name for d in catalog.dimensions)


def test_build_catalog_dimensions_have_type_and_sub_dimensions():
    catalog = build_catalog()
    for dim in catalog.dimensions:
        assert dim.dimension_type in {"infringement", "exception"}
        assert len(dim.sub_dimensions) > 0
        for sub in dim.sub_dimensions:
            assert sub.name
            assert sub.description


def test_build_catalog_includes_two_presets():
    catalog = build_catalog()
    ids = {p.id for p in catalog.presets}
    assert ids == {"infringing", "not-infringing"}
    for preset in catalog.presets:
        assert preset.source_text
        assert preset.target_text


def test_build_catalog_includes_three_evaluation_strategies():
    catalog = build_catalog()
    values = {s.value for s in catalog.evaluation_strategies}
    assert values == {"fully_separate", "shared_arg_per_dim_deliberation", "shared_all"}


def test_build_catalog_includes_provider_presets():
    catalog = build_catalog()
    ids = {p.id for p in catalog.provider_presets}
    assert "openai" in ids
    assert "custom" in ids


def test_build_catalog_env_status_reflects_actual_environment(monkeypatch):
    monkeypatch.delenv("PSALM_API_KEY", raising=False)
    catalog_without = build_catalog()
    assert catalog_without.env_status["PSALM_API_KEY"] is False

    monkeypatch.setenv("PSALM_API_KEY", "sk-test")
    catalog_with = build_catalog()
    assert catalog_with.env_status["PSALM_API_KEY"] is True

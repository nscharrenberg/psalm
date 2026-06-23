def test_public_imports():
    from psalm import PSALM, AgentConfig, PSALMConfigError, PSALMError, PSALMResult

    assert PSALM is not None
    assert AgentConfig is not None
    assert PSALMResult is not None
    assert PSALMError is not None
    assert PSALMConfigError is not None


def test_internal_modules_not_exported():
    import psalm
    assert not hasattr(psalm, "ArgumentationPhase")
    assert not hasattr(psalm, "DeliberationPhase")
    assert not hasattr(psalm, "SimpleMajorityVoting")
    assert not hasattr(psalm, "Prosecutor")

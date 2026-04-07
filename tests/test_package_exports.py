"""Regression tests for package export declarations."""


def test_all_declarations_present():
    """Verify __all__ exists on every data_api subpackage."""
    import data_api
    import data_api.collectors
    import data_api.processors
    import data_api.storage
    import data_api.jobs

    for module in [
        data_api,
        data_api.collectors,
        data_api.processors,
        data_api.storage,
        data_api.jobs,
    ]:
        assert hasattr(module, "__all__"), (
            f"{module.__name__} is missing __all__ declaration"
        )


def test_collector_exports_importable():
    """Verify named exports in collectors __all__ are actually importable."""
    import data_api.collectors as collectors

    for name in collectors.__all__:
        assert hasattr(collectors, name), (
            f"{name} is declared in __all__ but not importable from data_api.collectors"
        )


def test_processor_exports_importable():
    """Verify named exports in processors __all__ are actually importable."""
    import data_api.processors as processors

    for name in processors.__all__:
        assert hasattr(processors, name), (
            f"{name} is declared in __all__ but not importable from data_api.processors"
        )

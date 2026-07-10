"""Regression tests for package export declarations."""


def test_all_declarations_present():
    """Verify __all__ exists on every data-layer subpackage."""
    import data_layer
    import data_layer.collectors
    import data_layer.processors
    import infrastructure.database
    import orchestration.jobs

    for module in [
        data_layer,
        data_layer.collectors,
        data_layer.processors,
        infrastructure.database,
        orchestration.jobs,
    ]:
        assert hasattr(module, "__all__"), (
            f"{module.__name__} is missing __all__ declaration"
        )


def test_collector_exports_importable():
    """Verify named exports in collectors __all__ are actually importable."""
    import data_layer.collectors as collectors

    for name in collectors.__all__:
        assert hasattr(collectors, name), (
            f"{name} is declared in __all__ but not importable from data_layer.collectors"
        )


def test_processor_exports_importable():
    """Verify named exports in processors __all__ are actually importable."""
    import data_layer.processors as processors

    for name in processors.__all__:
        assert hasattr(processors, name), (
            f"{name} is declared in __all__ but not importable from data_layer.processors"
        )

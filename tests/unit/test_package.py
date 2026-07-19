"""Package import smoke tests."""

from importlib.metadata import version

import etlantic


def test_version() -> None:
    assert etlantic.__version__ == version("etlantic")


def test_root_exports() -> None:
    required = {
        "Pipeline",
        "Transformation",
        "Data",
        "Extract",
        "Load",
        "Source",
        "Sink",
        "PipelinePlan",
        "PipelineRuntime",
        "Profile",
        "SecretRef",
    }
    missing = sorted(name for name in required if not hasattr(etlantic, name))
    assert missing == []
    assert callable(etlantic.Pipeline.run)
    assert callable(etlantic.Pipeline.arun)

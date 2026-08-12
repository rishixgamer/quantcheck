from importlib.metadata import metadata

import quantcheck


def test_package_version_is_a_non_empty_string() -> None:
    assert isinstance(quantcheck.__version__, str)
    assert quantcheck.__version__ == "0.2.0.dev0"


def test_runtime_metadata_declares_pyarrow_for_supported_columnar_inputs() -> None:
    package = metadata("quantcheck")
    assert package["Version"] == quantcheck.__version__
    requirements = package.get_all("Requires-Dist")
    assert requirements is not None
    assert any(requirement.startswith("pyarrow") for requirement in requirements)

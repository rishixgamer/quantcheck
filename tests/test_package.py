import quantcheck


def test_package_version_is_a_non_empty_string() -> None:
    assert isinstance(quantcheck.__version__, str)
    assert quantcheck.__version__

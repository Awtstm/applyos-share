"""Phase 0 smoke tests: the scaffold itself works."""

import app


def test_package_importable():
    assert app.__version__ == "0.1.0"

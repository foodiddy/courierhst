import os

if os.environ.get("COURIERHST_REQUIRE_PYTE") == "1":
    try:
        import pyte  # noqa: F401
    except ImportError:
        raise ImportError(
            "COURIERHST_REQUIRE_PYTE=1 but pyte is not installed; "
            "pip install '.[test]'"
        )

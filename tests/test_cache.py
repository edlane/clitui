"""Tests for schema caching."""

import shutil
from pathlib import Path
from clitui.cache import clear_cache, get_cache_dir, load_cached_schema, save_cached_schema
from clitui.models import CliArgument, CliOption, CliSchema


def test_cache_roundtrip():
    schema = CliSchema(
        command="test-cmd",
        arguments=[CliArgument(name="ARG1", required=True)],
        options=[CliOption(switches=["-f", "--flag"], type="boolean")],
    )
    help_text = "Usage: test-cmd [options] ARG1\n  -f, --flag  Flag"

    # Save
    saved = save_cached_schema(schema, help_text)
    assert saved is True

    # Load with identical help text
    loaded = load_cached_schema("test-cmd", help_text)
    assert loaded is not None
    assert loaded.command == "test-cmd"
    assert loaded.options[0].primary_switch() == "--flag"

    # Invalidate on different help text (e.g. updated version)
    different_help = "Usage: test-cmd [options] ARG1\n  -f, --flag  Flag\n  -v  Verbose"
    invalidated = load_cached_schema("test-cmd", different_help)
    assert invalidated is None

    # Clear specific cache
    cleared = clear_cache("test-cmd")
    assert cleared == 1
    assert load_cached_schema("test-cmd", help_text) is None


if __name__ == "__main__":
    test_cache_roundtrip()
    print("CACHE TESTS PASSED!")

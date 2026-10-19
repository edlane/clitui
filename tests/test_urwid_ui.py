"""Tests for Urwid dual-pane TUI."""

from clitui.models import CliArgument, CliOption, CliSchema
from clitui.ui.urwid_app import UrwidCliApp
from clitui.parser.regex_parser import parse_regex

SAMPLE_HELP = """Usage: sample-tool [OPTIONS] <PATTERN> [PATH...]

A sample tool for testing CLI parsing.

Options:
  -v, --verbose              Enable verbose output
  -o, --output <FILE>        Output file destination
  -p, --port <PORT>          Network port number (e.g. 8080)
  --format [json|yaml|text]  Choose output format
  -h, --help                 Display this help text
"""


def test_urwid_app_build():
    schema = parse_regex("sample-tool", SAMPLE_HELP)
    app = UrwidCliApp(schema=schema)
    root = app.build_ui()
    assert root is not None
    assert len(app.option_widgets) == 5

    # Test toggling boolean option
    verbose_item = app.option_widgets[0]
    assert verbose_item.option.primary_switch() == "--verbose"
    verbose_item.keypress((80,), " ")
    assert app.option_values[verbose_item.index] is True
    assert "--verbose" in app.preview_text.text

    # Toggle off
    verbose_item.keypress((80,), " ")
    assert app.option_values[verbose_item.index] is False
    assert "--verbose" not in app.preview_text.text

    # Test setting positional argument
    app._on_arg_changed("PATTERN", "search_term")
    assert "search_term" in app.preview_text.text

    # Test filtering options
    app._on_filter_changed(None, "--output")
    assert len(app.filtered_widgets) == 1
    assert app.filtered_widgets[0].option.primary_switch() == "--output"

    # Reset filter
    app._on_filter_changed(None, "")
    assert len(app.filtered_widgets) == 5

    print("URWID APP TESTS PASSED!")


if __name__ == "__main__":
    test_urwid_app_build()

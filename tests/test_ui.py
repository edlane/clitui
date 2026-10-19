"""UI tests for Textual app in clitui."""

import asyncio
from clitui.models import CliArgument, CliOption, CliSchema
from clitui.ui.app import CliTuiApp
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


async def run_app_test():
    schema = parse_regex("sample-tool", SAMPLE_HELP)
    app = CliTuiApp(schema=schema)
    async with app.run_test() as pilot:
        # Check that widgets mounted
        assert app.query_one("#positional-card") is not None
        assert app.query_one("#filter-input") is not None
        assert app.query_one("#options-scroll") is not None
        assert app.query_one("#preview-bar") is not None
        assert app.query_one("#btn-run") is not None

        # Test filter input typing
        await pilot.press("ctrl+f")
        filter_input = app.query_one("#filter-input")
        filter_input.value = "verbose"
        await pilot.pause()

        # Test positional arg input
        arg_inp = app.query_one("#arg_PATTERN")
        arg_inp.value = "needle"
        await pilot.pause()

        # Check preview bar updated
        preview = app.query_one("#preview-bar")
        assert "needle" in preview.command_text

        # Test Reset Form button
        btn_reset = app.query_one("#btn-reset")
        await pilot.click(btn_reset)
        await pilot.pause()

        assert arg_inp.value == ""
        assert filter_input.value == ""
        assert preview.command_text == "sample-tool"

        print("TEXTUAL APP TEST PASSED!")


if __name__ == "__main__":
    asyncio.run(run_app_test())

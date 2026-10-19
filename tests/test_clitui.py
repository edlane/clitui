"""Tests for models and regex parser."""

from clitui.models import CliArgument, CliOption, CliSchema
from clitui.parser.regex_parser import parse_regex
from clitui.executor import build_command_line

SAMPLE_HELP = """Usage: sample-tool [OPTIONS] <PATTERN> [PATH...]

A sample tool for testing CLI parsing.

Options:
  -v, --verbose              Enable verbose output
  -o, --output <FILE>        Output file destination
  -p, --port <PORT>          Network port number (e.g. 8080)
  --format [json|yaml|text]  Choose output format
  -h, --help                 Display this help text
"""


def test_models():
    opt = CliOption(switches=["-v", "--verbose"], expects_value=False, type="boolean")
    assert opt.primary_switch() == "--verbose"
    assert opt.display_name() == "-v, --verbose"

    schema = CliSchema(
        command="sample-tool",
        arguments=[CliArgument(name="PATTERN", required=True)],
        options=[opt],
    )
    data = schema.to_dict()
    assert data["command"] == "sample-tool"
    assert len(data["options"]) == 1

    restored = CliSchema.from_dict(data)
    assert restored.command == "sample-tool"
    assert restored.options[0].primary_switch() == "--verbose"


def test_regex_parser():
    schema = parse_regex("sample-tool", SAMPLE_HELP)
    assert schema.command == "sample-tool"
    
    # Check positional args
    arg_names = [a.name for a in schema.arguments]
    assert "PATTERN" in arg_names

    # Check options
    opt_map = {opt.primary_switch(): opt for opt in schema.options}
    assert "--verbose" in opt_map
    assert opt_map["--verbose"].type == "boolean"

    assert "--output" in opt_map
    assert opt_map["--output"].type == "file_path"
    assert opt_map["--output"].expects_value is True

    assert "--port" in opt_map
    assert opt_map["--port"].type == "integer"

    assert "--format" in opt_map
    assert opt_map["--format"].type == "choice_enum"
    assert "json" in opt_map["--format"].choices


def test_executor_command_building():
    schema = parse_regex("sample-tool", SAMPLE_HELP)
    opt_map = {opt.primary_switch(): idx for idx, opt in enumerate(schema.options)}

    option_values = {
        opt_map["--verbose"]: True,
        opt_map["--output"]: "/tmp/result.txt",
    }
    argument_values = {
        "PATTERN": "hello_world",
        "PATH": "src/",
    }

    cmd = build_command_line(schema, option_values, argument_values)
    assert cmd[0] == "sample-tool"
    assert "--verbose" in cmd
    assert "--output" in cmd
    assert "/tmp/result.txt" in cmd
    assert "hello_world" in cmd
    assert "src/" in cmd


if __name__ == "__main__":
    test_models()
    test_regex_parser()
    test_executor_command_building()
    print("ALL UNIT TESTS PASSED!")


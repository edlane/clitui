"""Reusable widgets for the clitui Textual application."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Input,
    Label,
    RichLog,
    Select,
    Static,
    Switch,
)

from clitui.executor import run_command_interactive
from clitui.models import CliArgument, CliOption, CliSchema


class ValueChanged(Message):
    """Fired when any argument or option input changes value."""

    def __init__(self, key: str, value: Any, is_argument: bool = False):
        super().__init__()
        self.key = key
        self.value = value
        self.is_argument = is_argument


class PositionalArgsCard(Static):
    """Pinned top container for command positional arguments."""

    def __init__(self, arguments: List[CliArgument], **kwargs):
        super().__init__(**kwargs)
        self.arguments = arguments
        self.input_widgets: Dict[str, Input] = {}

    def compose(self) -> ComposeResult:
        if not self.arguments:
            yield Label("No positional arguments required.", classes="text-muted italic")
            return

        with Vertical(classes="args-container"):
            for arg in self.arguments:
                req_badge = "[red]* Required[/red]" if arg.required else "[dim](Optional)[/dim]"
                label_text = f"{arg.name} {req_badge}"
                if arg.description:
                    label_text += f" — [dim]{arg.description}[/dim]"

                yield Label(Text.from_markup(label_text), classes="arg-label")
                inp = Input(
                    placeholder=f"Enter {arg.name}...",
                    id=f"arg_{arg.name}",
                    classes="arg-input",
                )
                self.input_widgets[arg.name] = inp
                yield inp

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id and event.input.id.startswith("arg_"):
            arg_name = event.input.id[4:]
            self.post_message(ValueChanged(arg_name, event.value, is_argument=True))


class OptionCard(Static):
    """Renders a single CLI option with form controls according to inferred type."""

    def __init__(self, index: int, option: CliOption, **kwargs):
        super().__init__(**kwargs)
        self.index = index
        self.option = option

    def compose(self) -> ComposeResult:
        with Vertical(classes="option-box"):
            with Horizontal(classes="option-header"):
                switches_str = ", ".join(self.option.switches)
                type_tag = f"[{self.option.type.upper()}]"
                yield Label(f"[bold cyan]{switches_str}[/] [dim yellow]{type_tag}[/]", classes="option-title")

            if self.option.description:
                yield Label(self.option.description, classes="option-desc text-muted")

            with Horizontal(classes="option-control-row"):
                if self.option.type == "boolean":
                    yield Label("Enable:", classes="control-label")
                    yield Switch(value=bool(self.option.default), id=f"opt_switch_{self.index}")

                elif self.option.type == "choice_enum" and self.option.choices:
                    options = [(c, c) for c in self.option.choices]
                    options.insert(0, ("(None / Default)", ""))
                    yield Label("Select:", classes="control-label")
                    yield Select(options, value="", id=f"opt_select_{self.index}")

                elif self.option.type == "integer":
                    yield Label("Value:", classes="control-label")
                    yield Input(
                        placeholder="Integer value (e.g. 10)",
                        type="integer",
                        id=f"opt_input_{self.index}",
                    )

                elif self.option.type in ("file_path", "directory_path"):
                    ph = "Path to file..." if self.option.type == "file_path" else "Path to directory..."
                    yield Label("Path:", classes="control-label")
                    yield Input(placeholder=ph, id=f"opt_input_{self.index}")

                else:
                    # Default string input
                    yield Label("Value:", classes="control-label")
                    yield Input(placeholder="Argument value...", id=f"opt_input_{self.index}")

    def on_switch_changed(self, event: Switch.Changed) -> None:
        self.post_message(ValueChanged(str(self.index), event.value, is_argument=False))

    def on_select_changed(self, event: Select.Changed) -> None:
        val = event.value
        if val in (Select.BLANK, None, "") or str(val).startswith("Select."):
            val = ""
        self.post_message(ValueChanged(str(self.index), val, is_argument=False))

    def on_input_changed(self, event: Input.Changed) -> None:
        self.post_message(ValueChanged(str(self.index), event.value, is_argument=False))


class CommandPreviewBar(Static):
    """Shows live command line preview as user modifies options and arguments."""

    def __init__(self, initial_cmd: str = "", **kwargs):
        super().__init__(**kwargs)
        self.command_text = initial_cmd

    def update_command(self, tokens: List[str]) -> None:
        safe_str = " ".join(tokens)
        self.command_text = safe_str
        self.update(Text.from_markup(f"[bold green]$[/bold green] [bold white]{safe_str}[/bold white]"))

    def compose(self) -> ComposeResult:
        yield Label(Text.from_markup(f"[bold green]$[/bold green] [bold white]{self.command_text}[/bold white]"))


class ExecutionScreen(ModalScreen):
    """Full-screen modal displaying streaming subprocess execution output."""

    DEFAULT_CSS = """
    ExecutionScreen {
        align: center middle;
    }
    #dialog {
        width: 90%;
        height: 85%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #exec-log {
        height: 1fr;
        border: solid $primary;
        background: $background;
        margin: 1 0;
    }
    #status-row {
        height: 3;
        align: right middle;
    }
    """

    def __init__(self, cmd_tokens: List[str], **kwargs):
        super().__init__(**kwargs)
        self.cmd_tokens = cmd_tokens
        self.proc = None

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(
                f"[bold cyan]Running:[/] {' '.join(self.cmd_tokens)}",
                id="exec-header",
            )
            yield RichLog(id="exec-log", highlight=True, markup=True)
            with Horizontal(id="status-row"):
                yield Label("[yellow]Executing...[/yellow]", id="status-label")
                yield Button("Cancel", variant="error", id="btn-cancel")
                yield Button("Close", variant="primary", id="btn-close", disabled=True)

    def on_mount(self) -> None:
        log_widget = self.query_one("#exec-log", RichLog)
        status_label = self.query_one("#status-label", Label)
        btn_close = self.query_one("#btn-close", Button)
        btn_cancel = self.query_one("#btn-cancel", Button)

        def _on_output(line: str):
            self.app.call_from_thread(log_widget.write, line.rstrip("\n"))

        def _on_complete(code: int):
            color = "green" if code == 0 else "red"
            status_text = f"[{color}]Finished with exit code: {code}[/{color}]"

            def _update_ui():
                status_label.update(status_text)
                btn_close.disabled = False
                btn_cancel.disabled = True

            self.app.call_from_thread(_update_ui)

        self.proc = run_command_interactive(
            self.cmd_tokens,
            on_output=_on_output,
            on_complete=_on_complete,
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            if self.proc and self.proc.poll() is None:
                self.proc.terminate()
            self.dismiss()
        elif event.button.id == "btn-close":
            self.dismiss()

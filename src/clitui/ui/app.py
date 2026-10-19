"""Main Textual application for clitui."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
    Switch,
)

from clitui.executor import build_command_line
from clitui.models import CliSchema
from clitui.ui.widgets import (
    CommandPreviewBar,
    ExecutionScreen,
    OptionCard,
    PositionalArgsCard,
    ValueChanged,
)


class CliTuiApp(App):
    """Interactive TUI for arbitrary CLI commands."""

    CSS = """
    Screen {
        background: $background;
        color: $text;
    }

    #main-container {
        height: 1fr;
        padding: 0 1;
    }

    /* Pinned Top Card for Positional Arguments */
    #positional-card {
        border: solid $secondary;
        background: $surface;
        padding: 1;
        margin-bottom: 1;
        height: auto;
        max-height: 12;
    }

    .card-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    .arg-label {
        margin-top: 1;
        text-style: bold;
    }

    .arg-input {
        margin-bottom: 1;
    }

    /* Filter Search Box */
    #filter-input {
        margin-bottom: 1;
        border: tall $primary-darken-2;
    }

    /* Options Scroll Container */
    #options-scroll {
        height: 1fr;
        border: solid $surface-lighten-1;
        background: $surface-darken-1;
        padding: 0 1;
    }

    .option-box {
        background: $surface;
        border: solid $primary-muted;
        padding: 1;
        margin-bottom: 1;
    }

    .option-title {
        text-style: bold;
    }

    .option-desc {
        color: $text-muted;
        margin-top: 0;
        margin-bottom: 1;
    }

    .option-control-row {
        height: 3;
        align: left middle;
    }

    .control-label {
        margin-right: 1;
        text-style: bold;
    }

    /* Bottom Command Preview & Action Bar */
    #bottom-dock {
        height: auto;
        background: $surface-darken-2;
        border-top: heavy $primary;
        padding: 1;
    }

    #preview-bar {
        background: $background;
        border: tall $secondary;
        padding: 0 1;
        margin-bottom: 1;
    }

    #actions-row {
        height: 3;
        align: right middle;
    }

    #actions-row Button {
        margin-left: 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+r", "run_command", "Run", priority=True),
        Binding("ctrl+f", "focus_filter", "Filter"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, schema: CliSchema, initial_tokens: Optional[List[str]] = None, **kwargs):
        super().__init__(**kwargs)
        self.schema = schema
        self.option_values: Dict[int, Any] = {}
        self.argument_values: Dict[str, str] = {}
        self.option_cards: List[OptionCard] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Vertical(id="main-container"):
            # Option A: Pinned Top Card for Positional Arguments
            with Vertical(id="positional-card"):
                yield Label("Positional / Required Arguments", classes="card-title")
                yield PositionalArgsCard(self.schema.arguments, id="positional-args-widget")

            # Filter input for rapid search
            yield Input(
                placeholder="🔍 Type to filter options by switch or description (Ctrl+F)...",
                id="filter-input",
            )

            # Scrollable options list
            with VerticalScroll(id="options-scroll"):
                for idx, opt in enumerate(self.schema.options):
                    card = OptionCard(idx, opt, id=f"opt_card_{idx}")
                    self.option_cards.append(card)
                    yield card

        # Bottom Dock: Live Preview & Actions
        with Vertical(id="bottom-dock"):
            initial_tokens = build_command_line(self.schema, self.option_values, self.argument_values)
            yield CommandPreviewBar(" ".join(initial_tokens), id="preview-bar")

            with Horizontal(id="actions-row"):
                yield Button("Quit", variant="default", id="btn-quit")
                yield Button("Reset Form", variant="warning", id="btn-reset")
                yield Button("Run Command (Ctrl+R)", variant="success", id="btn-run")

        yield Footer()

    def on_mount(self) -> None:
        self.title = f"clitui — {self.schema.command}"
        if self.schema.description:
            self.sub_title = self.schema.description[:60]

    def on_value_changed(self, message: ValueChanged) -> None:
        if message.is_argument:
            self.argument_values[message.key] = str(message.value)
        else:
            opt_idx = int(message.key)
            self.option_values[opt_idx] = message.value

        self._refresh_preview()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "filter-input":
            query = event.value.strip().lower()
            for card in self.option_cards:
                if not query:
                    card.display = True
                    continue

                switches = " ".join(card.option.switches).lower()
                desc = card.option.description.lower()
                card.display = query in switches or query in desc

    def _refresh_preview(self) -> None:
        tokens = build_command_line(self.schema, self.option_values, self.argument_values)
        preview_bar = self.query_one("#preview-bar", CommandPreviewBar)
        preview_bar.update_command(tokens)

    def action_run_command(self) -> None:
        tokens = build_command_line(self.schema, self.option_values, self.argument_values)
        self.push_screen(ExecutionScreen(tokens))

    def action_focus_filter(self) -> None:
        filter_box = self.query_one("#filter-input", Input)
        filter_box.focus()

    def reset_form(self) -> None:
        """Cleans all inputs, switches, dropdowns, and filters back to starting state."""
        self.option_values.clear()
        self.argument_values.clear()

        # Reset all switches
        for sw in self.query(Switch):
            sw.value = False

        # Reset all positional and option text inputs
        for inp in self.query(Input):
            inp.value = ""

        # Reset all select dropdowns
        for sel in self.query(Select):
            sel.clear()

        # Unhide any filtered option cards
        for card in self.option_cards:
            card.display = True

        self._refresh_preview()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-run":
            self.action_run_command()
        elif event.button.id == "btn-reset":
            self.reset_form()
        elif event.button.id == "btn-quit":
            self.exit()

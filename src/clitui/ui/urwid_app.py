"""Urwid-based high-density keyboard-driven TUI for clitui."""

from __future__ import annotations

import fcntl
import os
import re
import subprocess
from typing import Any, Dict, List, Optional, Tuple

import urwid

from clitui.executor import build_command_line
from clitui.models import CliArgument, CliOption, CliSchema


PALETTE = [
    ("header", "white,bold", "dark blue"),
    ("header_sub", "light gray", "dark blue"),
    ("filter_label", "yellow,bold", "dark blue"),
    ("filter_text", "white", "black"),
    ("pos_box", "light gray", "default"),
    ("pos_title", "light cyan,bold", "default"),
    ("pos_label", "white,bold", "default"),
    ("pos_req", "light red,bold", "default"),
    ("pos_input", "white", "dark gray"),
    ("pos_input_focus", "black", "light cyan"),
    ("list_normal", "light gray", "default"),
    ("list_focus", "black,bold", "light cyan"),
    ("list_active", "light green,bold", "default"),
    ("list_active_focus", "black,bold", "light green"),
    ("tag_bool", "light magenta", "default"),
    ("tag_path", "yellow", "default"),
    ("tag_enum", "light blue", "default"),
    ("tag_int", "light green", "default"),
    ("tag_str", "light gray", "default"),
    ("inspector_title", "light cyan,bold", "default"),
    ("inspector_key", "yellow,bold", "default"),
    ("inspector_val", "white", "default"),
    ("inspector_desc", "light gray", "default"),
    ("preview_title", "yellow,bold", "dark blue"),
    ("preview_cmd", "light green,bold", "black"),
    ("footer", "white", "dark gray"),
    ("footer_key", "yellow,bold", "dark gray"),
    ("dialog", "white", "dark blue"),
    ("dialog_focus", "black", "light cyan"),
    ("dialog_border", "light cyan", "dark blue"),
    ("exec_header", "yellow,bold", "dark blue"),
    ("exec_log", "white", "black"),
    ("exec_status_running", "yellow,bold", "dark blue"),
    ("exec_status_success", "light green,bold", "dark blue"),
    ("exec_status_fail", "light red,bold", "dark blue"),
]


class OptionItemWidget(urwid.WidgetWrap):
    """Selectable row widget representing a CLI option in the explorer list."""

    def __init__(self, index: int, option: CliOption, app: UrwidCliApp):
        self.index = index
        self.option = option
        self.app = app
        self._w = urwid.AttrMap(self._build_content(), "list_normal", "list_focus")

    def selectable(self) -> bool:
        return True

    def _build_content(self) -> urwid.Widget:
        current_val = self.app.option_values.get(self.index)
        is_active = current_val not in (None, False, "")

        if self.option.type == "boolean":
            marker = "[X] " if is_active else "[ ] "
        else:
            marker = "[►] " if is_active else "[ ] "

        switches_str = ", ".join(self.option.switches)

        # Truncate switches if needed
        val_display = ""
        if is_active and self.option.type != "boolean":
            val_display = f" = {str(current_val)[:18]}"

        type_tag = f"[{self.option.type[:4].upper()}]"
        type_style = {
            "boolean": "tag_bool",
            "file_path": "tag_path",
            "directory_path": "tag_path",
            "choice_enum": "tag_enum",
            "integer": "tag_int",
        }.get(self.option.type, "tag_str")

        left_text = f"{marker}{switches_str}{val_display}"
        cols = urwid.Columns(
            [
                ("weight", 80, urwid.Text(left_text, wrap="clip")),
                ("fixed", 8, urwid.Text((type_style, type_tag), align="right")),
            ]
        )
        return cols

    def refresh(self):
        current_val = self.app.option_values.get(self.index)
        is_active = current_val not in (None, False, "")
        normal_attr = "list_active" if is_active else "list_normal"
        focus_attr = "list_active_focus" if is_active else "list_focus"
        self._w = urwid.AttrMap(self._build_content(), normal_attr, focus_attr)

    def keypress(self, size: Tuple[int], key: str) -> Optional[str]:
        if key == " ":
            # Toggle boolean or open edit
            if self.option.type == "boolean":
                curr = self.app.option_values.get(self.index, False)
                self.app.option_values[self.index] = not curr
                self.refresh()
                self.app.on_data_changed()
                return None
            else:
                self.app.prompt_edit_option(self.index, self.option)
                return None

        elif key == "enter":
            if self.option.type == "boolean":
                curr = self.app.option_values.get(self.index, False)
                self.app.option_values[self.index] = not curr
                self.refresh()
                self.app.on_data_changed()
                return None
            else:
                self.app.prompt_edit_option(self.index, self.option)
                return None

        elif key in ("backspace", "delete", "d"):
            # Clear value
            if self.index in self.app.option_values:
                del self.app.option_values[self.index]
                self.refresh()
                self.app.on_data_changed()
                return None

        elif key == "ctrl r":
            self.app.run_command()
            return None

        return key


class SingleLineEdit(urwid.Edit):
    """Single-line edit widget that fires callbacks on Enter and Esc."""

    def __init__(self, caption="", edit_text="", on_enter=None, on_cancel=None, **kwargs):
        super().__init__(caption=caption, edit_text=edit_text, multiline=False, **kwargs)
        self.on_enter = on_enter
        self.on_cancel = on_cancel

    def keypress(self, size, key):
        if key == "enter":
            if self.on_enter:
                self.on_enter(self.get_edit_text())
                return None
        elif key == "esc":
            if self.on_cancel:
                self.on_cancel()
                return None
        return super().keypress(size, key)


class UrwidCliApp:
    """Complete Urwid Application controller for clitui."""

    def __init__(self, schema: CliSchema):
        self.schema = schema
        self.option_values: Dict[int, Any] = {}
        self.argument_values: Dict[str, str] = {}
        self.option_widgets: List[OptionItemWidget] = []
        self.filtered_widgets: List[OptionItemWidget] = []

        # Widgets
        self.main_frame: Optional[urwid.Frame] = None
        self.loop: Optional[urwid.MainLoop] = None
        self.list_walker: Optional[urwid.SimpleFocusListWalker] = None
        self.options_listbox: Optional[urwid.ListBox] = None
        self.inspector_pile: Optional[urwid.Pile] = None
        self.filter_edit: Optional[urwid.Edit] = None
        self.in_exec_modal: bool = False
        self.pos_edits: Dict[str, urwid.Edit] = {}

    def build_ui(self) -> urwid.Widget:
        # 1. Header with title & filter
        title_text = urwid.Text(f" clitui — {self.schema.command} ")
        self.filter_edit = SingleLineEdit(
            caption="Search (/): ",
            on_enter=lambda _: self.main_frame.set_focus("body"),
            on_cancel=self._clear_filter,
        )
        urwid.connect_signal(self.filter_edit, "change", self._on_filter_changed)

        header_cols = urwid.Columns(
            [
                ("weight", 40, urwid.AttrMap(title_text, "header")),
                ("weight", 60, urwid.AttrMap(self.filter_edit, "filter_text")),
            ]
        )
        header_widget = urwid.Pile([urwid.AttrMap(header_cols, "header")])

        # 2. Positional Arguments Section (Top pinned card per Option A)
        pos_widgets = []
        if self.schema.arguments:
            pos_cols = []
            for arg in self.schema.arguments:
                label_txt = f" {arg.name}*" if arg.required else f" {arg.name}"
                edit = urwid.Edit(f"{label_txt}: ", "")
                self.pos_edits[arg.name] = edit
                urwid.connect_signal(
                    edit,
                    "change",
                    lambda _, text, name=arg.name: self._on_arg_changed(name, text),
                )
                pos_cols.append(
                    (
                        "weight",
                        1,
                        urwid.AttrMap(edit, "pos_input", "pos_input_focus"),
                    )
                )

            pos_grid = urwid.Columns(pos_cols, dividechars=2)
            pos_box = urwid.LineBox(
                urwid.Padding(pos_grid, left=1, right=1),
                title="Positional Arguments",
            )
            header_widget.contents.append((urwid.AttrMap(pos_box, "pos_box"), ("pack", None)))

        # 3. Left Pane: Options Explorer List
        for idx, opt in enumerate(self.schema.options):
            item = OptionItemWidget(idx, opt, self)
            self.option_widgets.append(item)
        self.filtered_widgets = list(self.option_widgets)

        self.list_walker = urwid.SimpleFocusListWalker(self.filtered_widgets)
        urwid.connect_signal(self.list_walker, "modified", self._on_focus_changed)
        self.options_listbox = urwid.ListBox(self.list_walker)
        left_box = urwid.LineBox(self.options_listbox, title="Options Explorer")

        # 4. Right Pane: Live Inspector
        self.inspector_pile = urwid.Pile(self._render_inspector_content(None))
        right_box = urwid.LineBox(
            urwid.Filler(self.inspector_pile, valign="top"),
            title="Option Inspector",
        )

        # 5. Body Columns (55% / 45%)
        body_columns = urwid.Columns(
            [
                ("weight", 55, left_box),
                ("weight", 45, right_box),
            ],
            dividechars=1,
        )

        # 6. Footer (Preview + Hotkeys)
        initial_tokens = build_command_line(
            self.schema, self.option_values, self.argument_values
        )
        self.preview_text = urwid.Text(f" $ {' '.join(initial_tokens)}")
        preview_box = urwid.AttrMap(self.preview_text, "preview_cmd")

        hotkey_bar = urwid.AttrMap(
            urwid.Text(
                " [Space/Enter] Toggle/Edit  [d] Clear  [/] Search  [Tab] Switch Pane  [Ctrl+R] Run  [q] Quit"
            ),
            "footer",
        )
        footer_widget = urwid.Pile([preview_box, hotkey_bar])

        self.main_frame = urwid.Frame(
            body=body_columns,
            header=header_widget,
            footer=footer_widget,
        )

        # Initialize inspector with first item if present
        if self.filtered_widgets:
            self._update_inspector(self.filtered_widgets[0].option)

        return self.main_frame

    def _render_inspector_content(self, option: Optional[CliOption]) -> List[urwid.Widget]:
        if not option:
            return [urwid.Text(("inspector_desc", "No option selected."))]

        switches_str = ", ".join(option.switches)
        current_val = self.option_values.get(
            self.filtered_widgets[self.list_walker.focus].index
            if self.list_walker and self.list_walker.focus is not None
            else -1
        )
        val_str = str(current_val) if current_val not in (None, False, "") else "(None / Default)"

        lines = [
            urwid.Text([("inspector_key", "Option:  "), ("inspector_title", switches_str)]),
            urwid.Text([("inspector_key", "Type:    "), ("inspector_val", f"{option.type}")]),
            urwid.Text([("inspector_key", "Value:   "), ("inspector_val", val_str)]),
        ]

        if option.choices:
            lines.append(
                urwid.Text(
                    [("inspector_key", "Choices: "), ("inspector_val", ", ".join(option.choices))]
                )
            )

        if option.default:
            lines.append(
                urwid.Text([("inspector_key", "Default: "), ("inspector_val", str(option.default))])
            )

        lines.append(urwid.Divider("─"))
        lines.append(urwid.Text(("inspector_key", "Description:")))
        desc_text = option.description if option.description else "No description provided."
        lines.append(urwid.Text(("inspector_desc", desc_text)))

        return lines

    def _update_inspector(self, option: CliOption):
        if self.inspector_pile:
            self.inspector_pile.contents = [
                (w, ("pack", None)) for w in self._render_inspector_content(option)
            ]

    def _on_focus_changed(self):
        if self.list_walker and self.list_walker.focus is not None:
            if 0 <= self.list_walker.focus < len(self.filtered_widgets):
                item = self.filtered_widgets[self.list_walker.focus]
                self._update_inspector(item.option)

    def _on_filter_changed(self, _, query: str):
        raw_q = query.strip()
        q = raw_q.lower()
        if not q:
            self.filtered_widgets = list(self.option_widgets)
        else:
            exact_case_switches = []
            exact_switches = []
            partial_switches = []
            desc_matches = []
            for item in self.option_widgets:
                if any(s == raw_q for s in item.option.switches):
                    exact_case_switches.append(item)
                elif any(s.lower() == q for s in item.option.switches):
                    exact_switches.append(item)
                elif any(q in s.lower() for s in item.option.switches):
                    partial_switches.append(item)
                elif q in item.option.description.lower():
                    desc_matches.append(item)

            self.filtered_widgets = exact_case_switches + exact_switches + partial_switches + desc_matches

        if self.list_walker:
            self.list_walker[:] = self.filtered_widgets
            if self.filtered_widgets:
                self.list_walker.set_focus(0)
                self._update_inspector(self.filtered_widgets[0].option)

    def _clear_filter(self):
        if self.filter_edit:
            self.filter_edit.set_edit_text("")
        self.main_frame.set_focus("body")

    def _on_arg_changed(self, name: str, value: str):
        self.argument_values[name] = value.strip()
        self.on_data_changed()

    def on_data_changed(self):
        tokens = build_command_line(self.schema, self.option_values, self.argument_values)
        if self.preview_text:
            self.preview_text.set_text(f" $ {' '.join(tokens)}")
        if self.list_walker and self.list_walker.focus is not None:
            if 0 <= self.list_walker.focus < len(self.filtered_widgets):
                self._update_inspector(self.filtered_widgets[self.list_walker.focus].option)

    def prompt_edit_option(self, index: int, option: CliOption):
        """Displays modal dialog to edit an option's value."""
        current_val = self.option_values.get(index, "")

        def _save(value: str):
            if value.strip():
                self.option_values[index] = value.strip()
            else:
                self.option_values.pop(index, None)
            self._close_dialog()
            # Refresh widget in list
            for item in self.option_widgets:
                if item.index == index:
                    item.refresh()
            self.on_data_changed()

        if option.choices:
            # Dropdown-like list of choices
            body_widgets = [
                urwid.Text(("dialog", f"Select value for {', '.join(option.switches)}:\n")),
            ]
            for c in ["(None / Default)"] + option.choices:
                val = "" if c == "(None / Default)" else c
                btn = urwid.Button(c)
                urwid.connect_signal(btn, "click", lambda _, v=val: _save(v))
                body_widgets.append(urwid.AttrMap(btn, "dialog", "dialog_focus"))
            cancel_btn = urwid.Button("Cancel")
            urwid.connect_signal(cancel_btn, "click", lambda _: self._close_dialog())
            body_widgets.append(urwid.AttrMap(cancel_btn, "dialog", "dialog_focus"))

            dialog_content = urwid.ListBox(urwid.SimpleFocusListWalker(body_widgets))
            self._show_dialog(dialog_content, width=50, height=min(16, len(body_widgets) + 4))
        else:
            # Single-line text edit box with instant Enter/Esc handling
            edit = SingleLineEdit(
                caption="Value: ",
                edit_text=str(current_val),
                on_enter=_save,
                on_cancel=self._close_dialog,
            )
            save_btn = urwid.Button("Save (Enter)")
            cancel_btn = urwid.Button("Cancel (Esc)")

            urwid.connect_signal(save_btn, "click", lambda _: _save(edit.get_edit_text()))
            urwid.connect_signal(cancel_btn, "click", lambda _: self._close_dialog())

            btn_row = urwid.Columns(
                [
                    ("weight", 1, urwid.AttrMap(save_btn, "dialog", "dialog_focus")),
                    ("weight", 1, urwid.AttrMap(cancel_btn, "dialog", "dialog_focus")),
                ],
                dividechars=2,
            )

            prompt_pile = urwid.Pile(
                [
                    urwid.Text(("dialog", f"Configure: {', '.join(option.switches)}\n")),
                    urwid.AttrMap(edit, "pos_input", "pos_input_focus"),
                    urwid.Divider(" "),
                    btn_row,
                ]
            )
            dialog_box = urwid.Filler(prompt_pile, valign="middle")
            self._show_dialog(dialog_box, width=60, height=8)

    def _show_dialog(self, widget: urwid.Widget, width: int = 60, height: int = 12):
        boxed = urwid.LineBox(widget)
        styled = urwid.AttrMap(boxed, "dialog_border")
        overlay = urwid.Overlay(
            styled,
            self.main_frame,
            align="center",
            width=width,
            valign="middle",
            height=height,
        )
        if self.loop:
            self.loop.widget = overlay

    def _close_dialog(self):
        self.in_exec_modal = False
        if self.loop:
            self.loop.widget = self.main_frame

    def run_command(self):
        """Launches command execution screen streaming stdout/stderr."""
        self.in_exec_modal = True
        cmd_tokens = build_command_line(self.schema, self.option_values, self.argument_values)

        log_lines: List[urwid.Widget] = [
            urwid.Text(("exec_header", f"Command: {' '.join(cmd_tokens)}\n")),
            urwid.Text(("exec_status_running", "Status: Running...\n")),
            urwid.Divider("─"),
        ]
        log_walker = urwid.SimpleFocusListWalker(log_lines)
        log_box = urwid.ListBox(log_walker)

        back_btn = urwid.Button("Back to Form (Enter / Esc)")
        urwid.connect_signal(back_btn, "click", lambda _: self._close_dialog())

        exec_frame = urwid.Frame(
            body=urwid.AttrMap(log_box, "exec_log"),
            footer=urwid.AttrMap(back_btn, "dialog_focus"),
        )
        boxed = urwid.LineBox(exec_frame, title="Execution Output")

        overlay = urwid.Overlay(
            urwid.AttrMap(boxed, "dialog_border"),
            self.main_frame,
            align="center",
            width=("relative", 90),
            valign="middle",
            height=("relative", 85),
        )
        if self.loop:
            self.loop.widget = overlay

        # Run command via non-shell subprocess and stream using native Urwid watch_file
        proc = subprocess.Popen(
            cmd_tokens,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        fd = proc.stdout.fileno()
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        def _read_stream():
            try:
                data = os.read(fd, 8192).decode("utf-8", errors="replace")
                if data:
                    for line in data.splitlines():
                        log_walker.append(urwid.Text(line))
                    log_walker.set_focus(len(log_walker) - 1)
                elif proc.poll() is not None:
                    code = proc.returncode
                    status_style = "exec_status_success" if code == 0 else "exec_status_fail"
                    status_text = f"Status: Finished with exit code {code}\n"
                    log_walker[1] = urwid.Text((status_style, status_text))
                    if self.loop:
                        self.loop.remove_watch_file(fd)
            except (OSError, BlockingIOError):
                if proc.poll() is not None:
                    code = proc.returncode
                    status_style = "exec_status_success" if code == 0 else "exec_status_fail"
                    status_text = f"Status: Finished with exit code {code}\n"
                    log_walker[1] = urwid.Text((status_style, status_text))
                    if self.loop:
                        self.loop.remove_watch_file(fd)

        if self.loop:
            self.loop.watch_file(fd, _read_stream)

    def handle_unhandled_input(self, key: str) -> bool:
        if key in ("q", "Q", "ctrl c"):
            raise urwid.ExitMainLoop()

        elif key == "ctrl r":
            self.run_command()
            return True

        elif key == "/":
            if self.filter_edit:
                self.main_frame.set_focus("header")
                self.main_frame.header.set_focus(0)
            return True

        elif key == "esc":
            # If dialog is open, close it; else clear filter
            if self.loop and self.loop.widget != self.main_frame:
                self._close_dialog()
            elif self.filter_edit:
                self.filter_edit.set_edit_text("")
                self.main_frame.set_focus("body")
            return True

        elif key == "tab":
            # Cycle focus between header (positional/filter) and body (options)
            if self.main_frame.focus_position == "body":
                if self.schema.arguments:
                    self.main_frame.set_focus("header")
                    # Focus positional box if present
                    if len(self.main_frame.header.contents) > 1:
                        self.main_frame.header.set_focus(1)
            else:
                self.main_frame.set_focus("body")
            return True

        return False

    def _input_filter(self, keys, raw):
        filtered = []
        for k in keys:
            if k == "ctrl r":
                self.run_command()
            elif self.in_exec_modal and k in ("enter", "esc", "q", " "):
                self._close_dialog()
            else:
                filtered.append(k)
        return filtered

    def run(self):
        root = self.build_ui()
        self.loop = urwid.MainLoop(
            root,
            palette=PALETTE,
            unhandled_input=self.handle_unhandled_input,
            input_filter=self._input_filter,
        )
        self.loop.run()

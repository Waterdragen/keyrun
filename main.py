import csv
import json
import random
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import filedialog
from tkinter import messagebox
from tkinter import ttk
from typing import Optional, Final, Callable, Iterator

import pynput

import actions
from actions import HoldSession

MASTER = tk.Tk()
MASTER.title("Keyrun")
MASTER.iconbitmap("./icons/github.ico")
MASTER.geometry("960x540+100+100")
MASTER.minsize(860, 450)
FONT: Final = ("Consolas", 14)
FONT_S: Final = ("Consolas", 11)
ICONS: Final = dict((Name, tk.PhotoImage(file=f"./icons/{Name}.png").zoom(2)) for Name in
                    ("action", "add", "compile", "delay", "delete", "failsafe", "filter", "github", "load",
                     "movedown", "moveup", "pick", "pick_add", "repeat", "run", "save", "settings", "tip"))
with open("tips.txt", 'r') as File:
    TIPS: Final = tuple(Tip.strip() for Tip in File.readlines())

# Note to self:
# keyword argument order convention:
# window(MASTER), text, font, image, compound, width, command

class EditableTreeview(ttk.Treeview):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bind("<Double-1>", self.on_double_click)
        self.edit_entry = None

    def on_double_click(self, event: tk.Event):
        """Handle double-click event on a cell"""
        row_id = self.identify_row(event.y)
        column_id = self.identify_column(event.x)
        if row_id and column_id:
            item = self.item(row_id)
            column_index = int(column_id[1:]) - 1
            # Columns 0, 1 (Serial number, Action) cannot be edited
            if column_index <= 1:
                return
            value = item['values'][column_index]
            bbox = self.bbox(row_id, column_index)
            if value is not None and bbox:
                # Create an Entry widget above the cell to edit the value
                x, y, width, height = bbox
                self.edit_entry = ttk.Entry(self, width=width)
                self.edit_entry.place(x=x, y=y, width=width, height=height)
                self.edit_entry.insert(0, value)
                self.edit_entry.bind("<Return>", lambda _event, _ri=row_id, _c=column_index: (
                                                        self.on_edit(_event, _ri, _c)))
                self.edit_entry.bind("<Escape>", lambda _event: self.cancel_edit(_event))
                self.edit_entry.bind("<FocusOut>", lambda _event, _ri=row_id, _c=column_index: (
                                                          self.on_edit(_event, _ri, _c)))
                self.edit_entry.focus_set()

    def on_edit(self, event: tk.Event, row_id, column_index):
        """Handle cell editing"""
        for _ in range(1):
            new_value: str = self.edit_entry.get()
            # Column 7 (Comment) accepts any text
            if column_index == 7:
                self.set(row_id, column_index, new_value)
                break
            # Columns 2~6 (X, Y, Strength, Delay, Repeat) accepts all digit values
            # X and Y have to be within monitor screen dimensions
            # Delay and Repeat have to be greater than 0
            if new_value.isdigit():
                _new_value = int(new_value)
                if column_index == 2 and _new_value > 2160:
                    break
                if column_index == 3 and _new_value > 3840:
                    break
                if column_index in (5, 6) and not _new_value:
                    break
                self.set(row_id, column_index, int(new_value))
        self.edit_entry.destroy()

    def cancel_edit(self, event: tk.Event):
        """Cancel cell editing"""
        self.edit_entry.destroy()


class SettingsWindow:
    def __init__(self, main: "Main"):
        self.TOP = tk.Toplevel(MASTER)
        self.TOP.title("Settings")
        self.TOP.iconbitmap("./icons/settings.ico")
        self.TOP.geometry("480x360+150+150")
        self.TOP.resizable(False, False)

        # Create the `Insert` or `Append` button (add_button)
        self.add_mode: bool = main.add_mode == "Insert"
        self.add_label = tk.Label(self.TOP, text="Toggle add row mode: ", font=FONT)
        self.add_label.place(relx=0.05, rely=0.17)
        self.add_button = tk.Button(self.TOP, text=main.add_mode, font=FONT, image=ICONS["add"], compound=tk.RIGHT,
                                    command=self.toggle_mode)
        self.add_button.place(relx=0.55, rely=0.15)

        # Create the `Tips` button
        self.view_tips = main.view_tips
        self.tips_label = tk.Label(self.TOP, text="Toggle tips visibility: ", font=FONT)
        self.tips_label.place(relx=0.05, rely=0.29)
        self.tips_button = tk.Button(self.TOP, text=("Visible" if main.view_tips else ""), font=FONT, compound=tk.RIGHT,
                                     width=10, command=self.toggle_tips)
        self.tips_button.place(relx=0.55, rely=0.27)

        # Create the `Run` button
        self.run_mode = main.run_mode
        self.run_label = tk.Label(self.TOP, text="Toggle Run/Compile: ", font=FONT)
        self.run_label.place(relx=0.05, rely=0.41)
        self.run_button = tk.Button(self.TOP, text=("Run" if main.run_mode else "Compile"), font=FONT,
                                    compound=tk.RIGHT, width=10, command=self.toggle_run)
        self.run_button.place(relx=0.55, rely=0.39)

    def toggle_mode(self):
        self.add_mode = not self.add_mode
        if self.add_mode:
            self.add_button.config(text="Insert")
        else:
            self.add_button.config(text="Append")

    def toggle_tips(self):
        self.view_tips = not self.view_tips
        if self.view_tips:
            self.tips_button.config(text="Visible")
        else:
            self.tips_button.config(text="")

    def toggle_run(self):
        self.run_mode = not self.run_mode
        if self.run_mode:
            self.run_button.config(text="Run")
        else:
            self.run_button.config(text="Compile")


class Main:
    def __init__(self):
        # dropdown font settings
        MASTER.option_add("*TCombobox*Listbox*Font", FONT_S)

        # ============ TOP PANEL ============
        # -----------------------------------
        # Create `filter` dropdown
        filter_label = tk.Label(MASTER, text="Type: ", font=FONT, image=ICONS["filter"],
                                compound=tk.LEFT)
        filter_label.place(relx=0.03, rely=0.05)
        self.active_filter = tk.StringVar(value="All")
        filter_options = ("All", "mouse", "combokey", "presskey", "input", "sleep")
        filter_dropdown = ttk.Combobox(values=filter_options, state="readonly", textvariable=self.active_filter)
        filter_dropdown.place(relx=0.16, rely=0.06)
        filter_dropdown.bind("<<ComboboxSelected>>", self.filter_changed)
        filter_dropdown.configure(font=FONT)

        # Read action options
        with open("action_options.json", "r") as f:
            self.actions_config: dict[str, dict[str, bool | str]] = json.load(f)
        # Create the `actions` dropdown
        action_label = tk.Label(MASTER, text="Action: ", font=FONT, image=ICONS["action"], compound=tk.LEFT)
        action_label.place(relx=0.03, rely=0.11)
        self.actions_options: tuple[str, ...] = tuple(self.actions_config.keys())
        self.active_action = tk.StringVar(value=self.actions_options[0])
        self.action_dropdown = ttk.Combobox(values=self.actions_options, state="readonly",
                                            textvariable=self.active_action, height=15)
        self.action_dropdown.place(relx=0.16, rely=0.12)
        self.action_dropdown.bind("<<ComboboxSelected>>", self.action_changed)
        self.action_dropdown.configure(font=FONT)

        # Create the `Pick` button, and Initialize invisible fullscreen and picked coordinates
        self.pick_button = tk.Button(MASTER, text="Pick", font=FONT, image=ICONS["pick"], compound=tk.RIGHT,
                                     command=self.pick_coordinate)
        self.pick_button.place(relx=0.51, rely=0.08)
        self.fake_fullscreen: Optional[tk.Toplevel] = None
        self.pick_x: int = 0
        self.pick_y: int = 0
        # Create the coordinate labels
        self.x_label = tk.Label(text="X: ", font=FONT)
        self.x_label.place(relx=0.42, rely=0.08)
        self.y_label = tk.Label(text="Y: ", font=FONT)
        self.y_label.place(relx=0.42, rely=0.12)

        # Create the `Insert` button (`add_button`)
        self.add_button = tk.Button(MASTER, text="Insert", font=FONT, image=ICONS["add"], compound=tk.RIGHT,
                                    command=self.add_row)
        self.add_button.place(relx=0.60, rely=0.08)

        # Create the `Settings` button
        self.settings_button = tk.Button(MASTER, text="Settings", font=FONT, image=ICONS["settings"], compound=tk.RIGHT,
                                         command=self.open_and_reload_settings)
        self.settings_button.place(relx=0.72, rely=0.08)
        self.add_mode = "Insert"

        # Create the `Github` button
        self.movedown_button = tk.Button(MASTER, text="Github", font=FONT, image=ICONS["github"],
                                         compound=tk.RIGHT, command=self.open_github)
        self.movedown_button.place(relx=0.86, rely=0.08)

        # ============ LEFT PANEL ============
        # ------------------------------------
        # Create the workflow table
        self.column_names = ("Seq", "Action", "X", "Y", "Strength", "Delay (ms)", "Repeat", "Comment")
        self.table: Optional[ttk.Treeview] = None
        self.create_table()
        self.table_columns_indexed = dict(zip(self.column_names, range(8)))

        # ============ RIGHT PANEL ============
        # -------------------------------------
        # Create the `Delete` button
        self.delete_button = tk.Button(MASTER, text=" Delete  ", font=FONT, image=ICONS["delete"],
                                       compound=tk.RIGHT, command=self.delete_row)
        self.delete_button.place(relx=0.82, rely=0.20)

        # Create the `Move Up` button
        self.moveup_button = tk.Button(MASTER, text=" Move Up ", font=FONT, image=ICONS["moveup"],
                                       compound=tk.RIGHT,  command=self.move_up)
        self.moveup_button.place(relx=0.82, rely=0.29)

        # Create the `Move Down` button
        self.movedown_button = tk.Button(MASTER, text="Move Down", font=FONT, image=ICONS["movedown"],
                                         compound=tk.RIGHT, command=self.move_down)
        self.movedown_button.place(relx=0.82, rely=0.38)

        # Create the `Save` button
        save_button = tk.Button(MASTER, text="Save", font=FONT, image=ICONS["save"], compound=tk.RIGHT,
                                width=80, command=self.save_file)
        save_button.place(relx=0.82, rely=0.47)

        # Create the `Save` button
        load_button = tk.Button(MASTER, text="Load", font=FONT, image=ICONS["load"], compound=tk.RIGHT,
                                width=80, command=self.load_file)
        load_button.place(relx=0.82, rely=0.56)

        # ============ BOTTOM PANEL ============
        # --------------------------------------
        # Create `Tip` label
        self.tip_num = random.randint(0, len(TIPS)-1)
        tip_icon = ICONS["tip"].subsample(2)
        self.tip_label = ttk.Label(MASTER, text=f"Tip: {TIPS[self.tip_num]}",
                                   image=tip_icon, compound=tk.LEFT, width=100)
        self.tip_label.bind("<Button-1>", self.tip_changed)
        self.tip_label.place(relx=0.03, rely=0.95)
        self.view_tips = True

        # Create the `Pick & Add` dropdown
        pick_add_label = tk.Label(MASTER, text="Pick & Add: ", font=FONT, image=ICONS["pick_add"], compound=tk.LEFT)
        pick_add_label.place(relx=0.03, rely=0.85)
        pick_add_options = ("ctrl", "shift", "command", "alt", "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9",
                            "f10", "f11", "f12")
        self.prev_get_add = "ctrl"
        self.active_get_add = tk.StringVar(value=self.prev_get_add)  # Fall back to prev if rejected
        pick_add_dropdown = ttk.Combobox(values=pick_add_options, state="readonly", textvariable=self.active_get_add,
                                         width=7)
        pick_add_dropdown.place(relx=0.20, rely=0.86)
        pick_add_dropdown.configure(font=FONT)
        pick_add_dropdown.bind("<<ComboboxSelected>>", self.pick_add_changed)
        MASTER.bind("<Control_L>", self.pick_add)

        # Create the `Failsafe` dropdown
        failsafe_label = tk.Label(MASTER, text="Failsafe: ", font=FONT, image=ICONS["failsafe"],
                                  compound=tk.LEFT)
        failsafe_label.place(relx=0.62, rely=0.85)
        failsafe_options = ("esc", "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
                            "delete", "backspace", "enter")
        self.prev_failsafe = "esc"
        self.active_failsafe = tk.StringVar(value=self.prev_failsafe)  # Fall back to prev if rejected
        failsafe_dropdown = ttk.Combobox(values=failsafe_options, state="readonly", textvariable=self.active_failsafe,
                                         width=7)
        failsafe_dropdown.place(relx=0.76, rely=0.86)
        failsafe_dropdown.configure(font=FONT)
        failsafe_dropdown.bind("<<ComboboxSelected>>", self.failsafe_changed)

        # Create the `Delay (ms)` textbox
        delay_icon = ICONS["delay"].subsample(2)
        delay_ms_label = tk.Label(MASTER, text="Delay (ms):", font=FONT_S, image=delay_icon, compound=tk.LEFT)
        delay_ms_label.place(relx=0.78, rely=0.72)
        delay_ms_changed = MASTER.register(lambda _input: (_input.isdigit() or _input == "") and len(_input) < 8)
        self.delay_ms_entry = tk.Entry(MASTER, validate="key", validatecommand=(delay_ms_changed, "%P"),
                                       font=FONT_S, width=8)
        self.delay_ms_entry.insert(0, "100")
        self.delay_ms_entry.bind("<FocusOut>", self.delay_ms_reset)
        self.delay_ms_entry.place(relx=0.90, rely=0.73)

        # Create the `Script repeat` textbox
        repeat_icon = ICONS["repeat"].subsample(2)
        script_repeat_label = tk.Label(MASTER, text="Script repeat:", font=FONT_S, image=repeat_icon, compound=tk.LEFT)
        script_repeat_label.place(relx=0.78, rely=0.77)
        script_repeat_changed = MASTER.register(lambda _input: (_input.isdigit() or _input == "") and len(_input) < 5)
        self.script_repeat_entry = tk.Entry(MASTER, validate="key", validatecommand=(script_repeat_changed, "%P"),
                                            font=FONT_S, width=5)
        self.script_repeat_entry.insert(0, '1')
        self.script_repeat_entry.bind("<FocusOut>", self.script_repeat_reset)
        self.script_repeat_entry.place(relx=0.93, rely=0.78)

        # Create the `Run` button
        self.run_button = tk.Button(MASTER, text="Run", font=FONT, image=ICONS["run"],
                                    compound=tk.RIGHT, command=self.run_starter)
        self.run_button.place(relx=0.88, rely=0.85)
        self.run_mode = True
        self.run_flag = True
        self.hold_session = HoldSession()
        self.holds_next = False

        # ============ MAIN WINDOW START ============
        # -------------------------------------------
        MASTER.mainloop()

    # Helper function notes
    # event is a used parameter for tkinter event bindings

    # ============ TOP PANEL ============
    # -----------------------------------
    def filter_changed(self, event: tk.Event):
        active_filter = self.active_filter.get()
        if active_filter == "All":
            # Show all options
            self.actions_options = tuple(k for k in self.actions_config.keys())
        else:
            # Filter options by class
            self.actions_options = tuple(k for k in filter(lambda k: self.actions_config[k]["type"] == active_filter,
                                                           self.actions_config.keys()))
        self.action_dropdown["values"] = self.actions_options
        self.active_action.set(self.actions_options[0])
        self.action_changed(None)

    def action_changed(self, event: Optional[tk.Event]):
        if self.actions_config[self.active_action.get()]["args"] == "xy":
            self.pick_button["state"] = "normal"
        else:
            self.pick_button["state"] = "disabled"

    def pick_coordinate(self):
        # New invisible fullscreen window
        self.fake_fullscreen = tk.Toplevel(MASTER)
        self.fake_fullscreen.attributes("-alpha", 1 / 256)
        self.fake_fullscreen.attributes("-fullscreen", True)
        # Binding window as button
        self.fake_fullscreen.bind("<Button-1>", self.get_clicked_position)
        self.fake_fullscreen.config(cursor="crosshair")
        # Minimize MASTER window while wait for the user to click on the fullscreen
        MASTER.iconify()
        self.fake_fullscreen.wait_window()

    def get_clicked_position(self, event: tk.Event):
        self.pick_x, self.pick_y = event.x_root, event.y_root
        # Update the labels with the picked coordinates
        self.x_label.configure(text=f"X: {self.pick_x}")
        self.y_label.configure(text=f"Y: {self.pick_y}")
        # Unbind button, destroy fullscreen, and pop back MASTER window
        self.fake_fullscreen.unbind("<Button-1>")
        self.fake_fullscreen.destroy()
        MASTER.deiconify()

    def open_and_reload_settings(self):
        settings_window = SettingsWindow(self)
        MASTER.wait_window(settings_window.TOP)
        self.add_mode = "Insert" if settings_window.add_mode else "Append"
        self.add_button.config(text=self.add_mode)
        self.view_tips = settings_window.view_tips
        if self.view_tips:
            self.tip_label.place(relx=0.03, rely=0.95)
        else:
            self.tip_label.place_forget()
        self.run_mode = settings_window.run_mode
        if self.run_mode:
            self.run_button.config(text="Run", image=ICONS["run"])  # Add code and change icon
        else:
            self.run_button.config(text="Compile", image=ICONS["compile"])  # Add code and change icon

    @staticmethod
    def open_github():
        webbrowser.open_new("https://github.com/Waterdragen/keyrun")

    # ============ LEFT PANEL ============
    # ------------------------------------
    def create_table(self):
        # Create the table
        column_widths = (30, 100, 30, 30, 30, 60, 60, 200)
        self.table = EditableTreeview(MASTER, columns=self.column_names, show="headings")
        # Set the column headings
        for col_name in self.column_names:
            self.table.heading(col_name, text=col_name)
        # Set the column widths
        for col_name, col_width in zip(self.column_names, column_widths):
            self.table.column(col_name, width=col_width, minwidth=col_width, stretch=True)
        # Add the table to the windiow
        self.table.pack(side=tk.TOP, padx=5, pady=5, fill=tk.BOTH, expand=True)
        self.table.place(relwidth=0.75, relheight=0.6, relx=0.03, rely=0.2)

    # ============ RIGHT PANEL ============
    # -------------------------------------
    def add_row(self):
        # Get the data for the new row
        selected_item = self.table.focus()
        seq = len(self.table.get_children())+1
        if self.add_mode == "Insert" and selected_item:
            seq = self.table.index(selected_item)+1
        action = self.active_action.get()
        delay = int(self.delay_ms_entry.get())
        repeat = 1
        comment = ""
        match self.actions_config[action]["args"]:
            case "xy":
                values = (seq, action, self.pick_x, self.pick_y, "", delay, repeat, comment)
            case "strength":
                values = (seq, action, "", "", 120, delay, repeat, comment)
            case _:
                values = (seq, action, "", "", "", delay, repeat, comment)
        # Add the new row
        if self.add_mode == "Insert":
            if selected_item:
                self.table.insert("", self.table.index(selected_item)+1, values=values)
                # Update the sequence numbers
                for i, item in enumerate(self.table.get_children()):
                    if i < seq:
                        continue
                    self.table.item(item, values=(i + 1, *self.table.item(item, "values")[1:]))
            else:
                self.table.insert("", tk.END, values=values)
        if self.add_mode == "Append":
            self.table.insert("", tk.END, values=values)

    def delete_row(self):
        # Get the selected row
        selection = self.table.selection()
        # Delete the selected row
        for item in selection:
            self.table.delete(item)
        # Update the sequence numbers
        for i, item in enumerate(self.table.get_children()):
            self.table.item(item, values=(i+1, *self.table.item(item, "values")[1:]))

    def move_up(self):
        # Get the selected row
        selection: tuple[str, ] = self.table.selection()
        if not selection:
            return
        selection: str = selection[0]
        # Get the index of the selected row
        index = self.table.index(selection)
        if index > 0:
            # Get the previous row
            prev_item = self.table.prev(selection)
            # Swap the values of the selected row and the previous row
            self.swap_rows(selection, prev_item)
            self.table.selection_set(prev_item)

    def move_down(self):
        # Get the selected row
        selection: tuple[str, ] = self.table.selection()
        if not selection:
            return
        selection: str = selection[0]
        # Get the index of the selected row
        index = self.table.index(selection)
        if index < len(self.table.get_children()) - 1:
            # Get the next row
            next_item = self.table.next(selection)
            # Swap the values of the selected row and the next row
            self.swap_rows(selection, next_item)
            self.table.selection_set(next_item)

    def swap_rows(self, item1: str, item2: str):
        # Get the values of the selected row and the previous row
        values1 = self.table.item(item1, "values")
        values2 = self.table.item(item2, "values")
        # Swap the sequence numbers of the rows
        seq1, *values1 = values1
        seq2, *values2 = values2
        self.table.item(item1, values=(seq1, *values2))
        self.table.item(item2, values=(seq2, *values1))

    def save_file(self):
        # Open file save dialog
        file_path = filedialog.asksaveasfilename(filetypes=(("CSV files", "*.csv"), ))
        if not file_path:
            return

        # Open file for writing
        with open(file_path, 'w', newline='') as f:
            writer = csv.writer(f)
            # Write headers
            headers = self.column_names
            writer.writerow(headers)
            # Write data rows
            for item in self.table.get_children():
                values = self.table.item(item)["values"]
                writer.writerow(values)

    def load_file(self):
        if self.table.get_children():
            confirm = tk.messagebox.askyesno("Clear table", "Are you sure you want to replace the current data?")
            if not confirm:
                return
        path = tk.filedialog.askopenfilename(filetypes=(("CSV files", "*.csv"), ))
        if not path:
            return
        self.table.delete(*self.table.get_children())
        with open(path, 'r') as csv_file:
            rows: Iterator = csv.reader(csv_file)
            # Skip the header of the csv
            next(rows)
            for row in rows:
                self.table.insert("", tk.END, values=row)

    # ============ BOTTOM PANEL ============
    # --------------------------------------
    def tip_changed(self, event: tk.Event):
        prev_num = self.tip_num
        self.tip_num = random.randint(0, len(TIPS)-1)
        while self.tip_num == prev_num:
            self.tip_num = random.randint(0, len(TIPS)-1)
        self.tip_label.config(text=f"Tip: {TIPS[self.tip_num]}")

    def pick_add_changed(self, event: tk.Event):
        def to_key_tag(_key: str):
            if _key.startswith('f'):
                return f"<{_key.capitalize()}>"
            match _key:
                case "command":
                    return "<Meta_L>"
                case "ctrl":
                    return "<Control_L>"
                case _:
                    return f"<{_key.capitalize()}_L>"

        active_get_add: str = self.active_get_add.get()
        if active_get_add == self.active_failsafe.get():
            self.active_get_add.set(self.prev_get_add)
        else:
            MASTER.unbind(to_key_tag(self.prev_get_add))
            MASTER.bind(to_key_tag(active_get_add), self.pick_add)
            self.prev_get_add = active_get_add

    def pick_add(self, event: tk.Event):
        self.pick_x, self.pick_y = event.x_root, event.y_root
        # Update the labels with the picked coordinates
        self.x_label.configure(text=f"X: {self.pick_x}")
        self.y_label.configure(text=f"Y: {self.pick_y}")
        # Add picked coordinates to the table
        self.add_row()

    def failsafe_changed(self, event: tk.Event):
        if self.active_failsafe.get() == self.active_get_add.get():
            self.active_failsafe.set(self.prev_failsafe)
        else:
            self.prev_failsafe = self.active_failsafe.get()

    def delay_ms_reset(self, event: tk.Event):
        delay_ms = self.delay_ms_entry.get()
        if not delay_ms:
            self.delay_ms_entry.insert(0, '0')

    def script_repeat_reset(self, event: tk.Event):
        script_repeat = self.script_repeat_entry.get()
        if not script_repeat or not int(script_repeat):
            self.script_repeat_entry.delete(0, tk.END)
            self.script_repeat_entry.insert(0, '1')

    def col_index(self, header: str) -> int:
        return self.table_columns_indexed[header]

    def arg_values(self, action_name: Optional[str], values: list) -> tuple:
        match self.actions_config[action_name]["args"]:
            case None:
                return ()
            case "xy":
                return values[self.col_index("X")], values[self.col_index("Y")]
            case "strength":
                return values[self.col_index("Strength")],
            case "key":
                return self.actions_config[values[self.col_index("Action")]]["key name"],
            case "ms":
                return values[self.col_index("Delay (ms)")],
            case "comment":
                return values[self.col_index("Comment")],
            case "comment char":
                s = values[self.col_index("Comment")]
                return (s[0],) if s else ("",)
            case _:
                raise NotImplementedError

    def run_starter(self):
        if not self.run_mode:
            self.compile()
            return
        self.run_button["state"] = "disabled"
        self.run_flag = True
        self.holds_next = False
        listener = pynput.keyboard.Listener(on_press=self.failsafe)
        listener.start()
        run_event = threading.Thread(target=self.run_and_end_handler, daemon=True)
        MASTER.iconify()
        run_event.start()

    def run_and_end_handler(self):
        self.run()
        self.run_flag = False
        self.run_button["state"] = "normal"
        MASTER.deiconify()

    def failsafe(self, key):
        key_name = getattr(key, "name", key)
        if key_name == self.active_failsafe.get():
            # Interrupt run flag to signal `self.run()`
            print("program stopped")
            self.run_flag = False
            self.run_button["state"] = "normal"

    def run(self):
        # Script repeat
        for script_rep in range(int(self.script_repeat_entry.get())):

            # ---- User script ----
            for item in self.table.get_children():
                values: list = self.table.item(item)["values"]
                # Repeat action
                for rep in range(values[self.col_index("Repeat")]):
                    # Logger
                    print(values)
                    # Delay before action
                    self.sleep(values[self.col_index("Delay (ms)")])
                    if not self.run_flag:
                        return
                    action_name = values[self.col_index("Action")]
                    # Get args for method
                    args: tuple = self.arg_values(action_name, values)
                    method_name = self.actions_config[action_name]["method"]
                    # imported
                    if self.actions_config[action_name]["use import"]:
                        getattr(actions, method_name)(*args)
                        continue
                    if method_name == "press_key":
                        # Normal press
                        if not self.holds_next:
                            getattr(actions, method_name)(*args)
                            continue
                        # Hold key
                        self.hold_key(*args)
                        print(f"holding {args[0]} key")
                        self.holds_next = False
                        continue
                    # non-imported
                    getattr(Main, method_name)(self, *args)

    def sleep(self, ms: int):
        while ms > 1000:
            time.sleep(1)
            ms -= 1000
            if not self.run_flag:
                return
        time.sleep(ms / 1000)

    def hold_key(self, key: str):
        self.hold_session.hold_key(key)

    def hold_next_press(self):
        self.holds_next = True

    def release_all(self):
        self.hold_session.release_all()
        self.holds_next = False

    def compile(self):
        top = tk.Toplevel(MASTER)
        top.title("Compile")
        top.geometry("480x360+150+150")
        top.resizable(False, False)

        # Create a printout with scrolling
        printout = tk.Text(top, font=FONT_S)
        printout.pack(fill="both", expand=True)

        script_repeat = int(self.script_repeat_entry.get())
        indent: Callable[[int], str] = lambda _lv: " " * _lv
        wrap_line: Callable[[str, int], str] = lambda _t, _lv: f"{' ' * 4 * _lv}{_t}\n"
        indent_lv = 0
        hold_next = False
        hold_keys: set[str] = set()

        if script_repeat > 1:
            printout.insert(tk.END, f"Repeats the whole script {script_repeat} times:\n\n")
            indent_lv = 1
        for item in self.table.get_children():
            values: list = self.table.item(item)["values"]
            action_name = values[self.col_index("Action")]
            delay_ms = values[self.col_index("Delay (ms)")]
            repeat = values[self.col_index("Repeat")]
            method_name = self.actions_config[action_name]["method"]

            if t := self.actions_config[action_name]["printout"]:
                if hold_keys:
                    printout.insert(tk.END, '\n')

                if self.actions_config[action_name]["args"] == "comment" and hold_keys:
                    printout.insert(tk.END, wrap_line(f"WARNING: {hold_keys} "
                                                      f"{'key is' if len(hold_keys) == 1 else 'keys are'} "
                                                      f"still holding", indent_lv))

                printout.insert(tk.END, wrap_line(f"{delay_ms}ms then"
                                                  f"{':' if repeat == 1 else f' repeat {repeat} times:'}", indent_lv))
                fills: tuple = self.arg_values(action_name, values)
                printout.insert(tk.END, wrap_line(t.format(*fills), indent_lv + (repeat > 1)))

            elif method_name == "hold_key" or hold_next or hold_keys:
                key_name = self.arg_values(action_name, values)[0]
                # Holding named or input keys
                if method_name == "hold_key" or hold_next:
                    # Holding combokey
                    hold_keys.add(key_name)
                    if len(hold_keys) == 1:
                        printout.insert(tk.END, indent(indent_lv))
                    else:
                        printout.insert(tk.END, f" + ")
                    printout.insert(tk.END, wrap_line(f"({delay_ms * repeat}ms) {key_name}", indent_lv))
                    hold_next = False
                # Press key is part of a combo
                else:
                    if repeat > 1:
                        printout.insert(tk.END, f"Repeat {repeat} times:")
                    printout.insert(tk.END, wrap_line(f"({delay_ms}ms) "
                                                      f"{' + '.join(_key for _key in hold_keys)} + {key_name}",
                                                      indent_lv + (repeat > 1)))

            elif method_name == "hold_next_press":
                hold_next = True

            elif method_name == "release_all":
                hold_keys.clear()
                hold_next = False

            # Regular press keys
            else:
                printout.insert(tk.END, wrap_line(f"{delay_ms}ms then"
                                                  f"{':' if repeat == 1 else f' repeat {repeat} times:'}", indent_lv))
                key_name = self.arg_values(action_name, values)[0]
                printout.insert(tk.END, wrap_line(f"Press {key_name}", indent_lv + (repeat > 1)))
                if not key_name:
                    printout.insert(tk.END, wrap_line(f"WARNING: nothing is pressed", indent_lv))

        # Warn active hold keys
        if hold_keys:
            printout.insert(tk.END, wrap_line(f"WARNING: {hold_keys} "
                                              f"{'key is' if len(hold_keys) == 1 else 'keys are'} "
                                              f"still holding but never released", indent_lv))
        printout.config(state=tk.DISABLED)


if __name__ == '__main__':
    Main()

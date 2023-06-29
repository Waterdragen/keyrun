import csv
import json
import pynput
import random
import time
import threading
import tkinter as tk
import webbrowser

import actions
from actions import HoldSession

from tkinter import ttk
from tkinter import filedialog
from typing import Optional, Final


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
            # Column 6 (Comment) accepts any text
            if column_index == 6:
                self.set(row_id, column_index, new_value)
                break
            # Columns 2~5 (X, Y, Delay, Repeat) accepts all digit values
            # X and Y have to be within monitor screen dimensions
            if new_value.isdigit():
                _new_value = int(new_value)
                if column_index == 2 and _new_value > 2160:
                    break
                if column_index == 3 and _new_value > 3840:
                    break
                self.set(row_id, column_index, int(new_value))
        self.edit_entry.destroy()

    def cancel_edit(self, event: tk.Event):
        """Cancel cell editing"""
        self.edit_entry.destroy()


class Main:
    MASTER = tk.Tk()
    MASTER.title("Keyrun")
    MASTER.geometry("960x540+100+100")
    MASTER.minsize(860, 450)
    FONT: Final = ("Consolas", 14)
    FONT_S: Final = ("Consolas", 11)
    ICONS: Final = dict((Name, tk.PhotoImage(file=f"./icons/{Name}.png").zoom(2)) for Name in
                        ("action", "add", "delete", "failsafe", "filter", "github", "movedown", "moveup",
                         "pick", "run", "save", "tip"))
    with open("tips.txt", 'r') as f:
        TIPS: Final = tuple(Tip.strip() for Tip in f.readlines())

    # Note to self:
    # keyword argument order convention:
    # window(self.MASTER), text, font, image, compound, width, command

    def __init__(self):
        # dropdown font settings
        self.MASTER.option_add("*TCombobox*Listbox*Font", self.FONT_S)
        # Create `filter` dropdown
        filter_label = tk.Label(self.MASTER, text="Type: ", font=self.FONT, image=self.ICONS["filter"],
                                compound=tk.LEFT)
        filter_label.place(relx=0.03, rely=0.05)
        self.active_filter = tk.StringVar(value="All")
        filter_options = ("All", "mouse", "hotkey", "non char key", "input", "sleep")
        filter_dropdown = ttk.Combobox(values=filter_options, state="readonly", textvariable=self.active_filter)
        filter_dropdown.place(relx=0.16, rely=0.06)
        filter_dropdown.bind("<<ComboboxSelected>>", self.filter_changed)
        filter_dropdown.configure(font=self.FONT)

        # Read action options
        with open("action_options.json", "r") as f:
            self.actions_config: dict[str, dict[str, bool | str]] = json.load(f)
        # Create the `actions` dropdown
        action_label = tk.Label(self.MASTER, text="Action: ", font=self.FONT, image=self.ICONS["action"],
                                compound=tk.LEFT)
        action_label.place(relx=0.03, rely=0.11)
        self.actions_options: tuple[str, ...] = tuple(self.actions_config.keys())
        self.active_action = tk.StringVar(value=self.actions_options[0])
        self.action_dropdown = ttk.Combobox(values=self.actions_options, state="readonly",
                                            textvariable=self.active_action, height=15)
        self.action_dropdown.place(relx=0.16, rely=0.12)
        self.action_dropdown.bind("<<ComboboxSelected>>", self.action_changed)
        self.action_dropdown.configure(font=self.FONT)

        # Create the `Pick` button, and Initialize invisible fullscreen and picked coordinates
        self.pick_button = tk.Button(self.MASTER, text="Pick", font=self.FONT, image=self.ICONS["pick"],
                                     compound=tk.RIGHT, command=self.pick_coordinate)
        self.pick_button.place(relx=0.51, rely=0.08)
        self.fake_fullscreen: Optional[tk.Toplevel] = None
        self.pick_x: int = 0
        self.pick_y: int = 0
        # Create the coordinate labels
        self.x_label = tk.Label(text="X: ", font=self.FONT)
        self.x_label.place(relx=0.42, rely=0.08)
        self.y_label = tk.Label(text="Y: ", font=self.FONT)
        self.y_label.place(relx=0.42, rely=0.12)

        # Create the workflow table
        self.column_names = ("Seq", "Action", "X", "Y", "Delay (ms)", "Repeat", "Comment")
        self.table: Optional[ttk.Treeview] = None
        self.create_table()
        self.table_columns_indexed = dict(zip(self.column_names, range(7)))

        # Create the `Add` button
        self.add_button = tk.Button(self.MASTER, text="Add", font=self.FONT, image=self.ICONS["add"],
                                    compound=tk.RIGHT, command=self.add_row)
        self.add_button.place(relx=0.60, rely=0.08)

        # Create the `Github` button
        self.movedown_button = tk.Button(self.MASTER, text="Github", font=self.FONT, image=self.ICONS["github"],
                                         compound=tk.RIGHT, command=self.open_github)
        self.movedown_button.place(relx=0.69, rely=0.08)

        # Create the `Delete` button
        self.delete_button = tk.Button(self.MASTER, text="Delete", font=self.FONT, image=self.ICONS["delete"],
                                       compound=tk.RIGHT, command=self.delete_row)
        self.delete_button.place(relx=0.82, rely=0.20)

        # Create the `Move Up` button
        self.moveup_button = tk.Button(self.MASTER, text="Move Up", font=self.FONT, image=self.ICONS["moveup"],
                                       compound=tk.RIGHT, command=self.move_up)
        self.moveup_button.place(relx=0.82, rely=0.29)

        # Create the `Move Down` button
        self.movedown_button = tk.Button(self.MASTER, text="Move Down", font=self.FONT, image=self.ICONS["movedown"],
                                         compound=tk.RIGHT, command=self.move_down)
        self.movedown_button.place(relx=0.82, rely=0.38)

        # Create the `Save` button
        save_button = tk.Button(self.MASTER, text="Save", font=self.FONT, image=self.ICONS["save"], compound=tk.RIGHT,
                                command=self.save_file)
        save_button.place(relx=0.82, rely=0.47)

        # Create `Tip` label
        self.tip_num = random.randint(0, len(self.TIPS)-1)
        tip_icon = self.ICONS["tip"].subsample(2)
        self.tip_label = ttk.Label(self.MASTER, text=f"Tip: {self.TIPS[self.tip_num]}",
                                   image=tip_icon, compound=tk.LEFT, width=100)
        self.tip_label.bind("<Button-1>", self.tip_changed)
        self.tip_label.place(relx=0.03, rely=0.95)

        # Create the `Failsafe` dropdown
        failsafe_label = tk.Label(self.MASTER, text="Failsafe: ", font=self.FONT, image=self.ICONS["failsafe"],
                                  compound=tk.LEFT)
        failsafe_label.place(relx=0.65, rely=0.85)
        failsafe_options = ("esc", "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12")
        self.active_failsafe = tk.StringVar(value="esc")
        failsafe_dropdown = ttk.Combobox(values=failsafe_options, state="readonly", textvariable=self.active_failsafe,
                                         width=7)
        failsafe_dropdown.place(relx=0.79, rely=0.86)
        failsafe_dropdown.configure(font=self.FONT)

        # Create the `Run` button
        self.run_button = tk.Button(self.MASTER, text="Run", font=self.FONT, image=self.ICONS["run"],
                                    compound=tk.RIGHT, command=self.run_starter)
        self.run_button.place(relx=0.9, rely=0.85)
        self.run_flag = True
        self.hold_session = HoldSession()
        self.holds_next = False

        # MAIN WINDOW START
        self.MASTER.mainloop()

    """
    Helper function notes
    1.  event is a used parameter for tkinter event bindings
    """

    def filter_changed(self, event: tk.Event = None):
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

    def action_changed(self, event: tk.Event):
        if self.actions_config[self.active_action.get()]["args"] == "xy":
            self.pick_button["state"] = "normal"
        else:
            self.pick_button["state"] = "disabled"

    def tip_changed(self, event: tk.Event):
        prev_num = self.tip_num
        self.tip_num = random.randint(0, len(self.TIPS)-1)
        while self.tip_num == prev_num:
            self.tip_num = random.randint(0, len(self.TIPS)-1)
        self.tip_label.config(text=f"Tip: {self.TIPS[self.tip_num]}")

    def pick_coordinate(self):
        # New invisible fullscreen window
        self.fake_fullscreen = tk.Toplevel(self.MASTER)
        self.fake_fullscreen.attributes("-alpha", 1 / 256)
        self.fake_fullscreen.attributes("-fullscreen", True)
        # Binding window as button
        self.fake_fullscreen.bind("<Button-1>", self.get_clicked_position)
        self.fake_fullscreen.config(cursor="crosshair")
        # Minimize MASTER window while wait for the user to click on the fullscreen
        self.MASTER.iconify()
        self.fake_fullscreen.wait_window()

    def get_clicked_position(self, event: tk.Event):
        self.pick_x, self.pick_y = event.x_root, event.y_root
        # Update the labels with the picked coordinates
        self.x_label.configure(text=f"X: {self.pick_x}")
        self.y_label.configure(text=f"Y: {self.pick_y}")
        # Unbind button, destroy fullscreen, and pop back MASTER window
        self.fake_fullscreen.unbind("<Button-1>")
        self.fake_fullscreen.destroy()
        self.MASTER.deiconify()

    def create_table(self):
        # Create the table
        column_widths = (30, 100, 30, 30, 60, 60, 200)
        self.table = EditableTreeview(self.MASTER, columns=self.column_names, show="headings")
        # Set the column headings
        for col_name in self.column_names:
            self.table.heading(col_name, text=col_name)
        # Set the column widths
        for col_name, col_width in zip(self.column_names, column_widths):
            self.table.column(col_name, width=col_width, minwidth=col_width, stretch=True)
        # Add the table to the windiow
        self.table.pack(side=tk.TOP, padx=5, pady=5, fill=tk.BOTH, expand=True)
        self.table.place(relwidth=0.75, relheight=0.6, relx=0.03, rely=0.2)

    def add_row(self):
        # Get the data for the new row
        seq = len(self.table.get_children()) + 1
        action = self.active_action.get()
        delay = 100
        repeat = 1
        comment = ""
        # Add the new row
        self.table.insert("", tk.END, values=(seq, action, self.pick_x, self.pick_y, delay, repeat, comment))

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

    @staticmethod
    def open_github():
        webbrowser.open_new("https://github.com/Waterdragen/keyrun")

    def col_index(self, header: str) -> int:
        return self.table_columns_indexed[header]

    def run_starter(self):
        self.run_button["state"] = "disabled"
        self.run_flag = True
        self.holds_next = False
        listener = pynput.keyboard.Listener(on_press=self.failsafe)
        listener.start()
        run_event = threading.Thread(target=self.run_and_end_handler, daemon=True)
        run_event.start()

    def run_and_end_handler(self):
        self.run()
        self.run_flag = False
        self.run_button["state"] = "normal"

    def failsafe(self, key):
        key_name = getattr(key, "name", key)
        if key_name == self.active_failsafe.get():
            # Interrupt run flag to signal `self.run()`
            print("program stopped")
            self.run_flag = False
            self.run_button["state"] = "normal"

    def run(self):
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
                args: tuple = ()
                match self.actions_config[action_name]["args"]:
                    case None:
                        pass
                    case "xy":
                        args = (values[self.col_index("X")], values[self.col_index("Y")])
                    case "strength":
                        raise NotImplementedError
                    case "key":
                        args = (self.actions_config[action_name]["key name"], )
                    case "ms":
                        args = (values[self.col_index("Delay (ms)")], )
                    case "comment":
                        args = (values[self.col_index("Comment")], )
                    case "comment char":
                        args = (values[self.col_index("Comment")][0], )
                    case _:
                        raise NotImplementedError
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

    def save_file(self):
        # Open file save dialog
        file_path = filedialog.asksaveasfilename(defaultextension=".csv")
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


if __name__ == '__main__':
    Main()

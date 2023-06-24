import json
import pynput
import time
import threading
import tkinter as tk

import actions
from actions import HoldSession

from tkinter import ttk
from typing import Optional

"""
Helper function notes
1.  event is a used parameter for tkinter event bindings
"""

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
    master = tk.Tk()
    master.title("Keyrun")
    master.geometry("960x540+100+100")

    def __init__(self):
        # Create `filter` dropdown
        self.active_filter = tk.StringVar(value="All")
        filter_options = ("All", "mouse", "hotkey", "non char key", "input", "sleep")
        filter_dropdown = ttk.Combobox(values=filter_options, state="readonly", textvariable=self.active_filter)
        filter_dropdown.place(relx=0.05, rely=0.05)
        filter_dropdown.bind("<<ComboboxSelected>>", self.filter_changed)
        filter_dropdown.configure(font=("Consolas", 14))

        # Read action options
        with open("action_options.json", "r") as f:
            self.actions_config: dict[str, dict[str, bool | str]] = json.load(f)
        # Create the `actions` dropdown
        self.actions_options: tuple[str, ...] = tuple(self.actions_config.keys())
        self.active_action = tk.StringVar(value=self.actions_options[0])
        self.action_dropdown = ttk.Combobox(values=self.actions_options, state="readonly",
                                            textvariable=self.active_action)
        self.action_dropdown.place(relx=0.05, rely=0.1)
        self.action_dropdown.bind("<<ComboboxSelected>>", self.action_changed)
        self.action_dropdown.configure(font=("Consolas", 14))

        # Create the `Pick` button, and Initialize invisible fullscreen and picked coordinates
        self.pick_button = tk.Button(text="Pick", font=("Consolas", 14), command=self.pick_coordinate)
        self.pick_button.place(relx=0.5, rely=0.08)
        self.fake_fullscreen: Optional[tk.Toplevel] = None
        self.pick_x: int = 0
        self.pick_y: int = 0
        # Create the coordinate labels
        self.x_label = tk.Label(text="X: ", font=("Consolas", 14))
        self.x_label.place(relx=0.3, rely=0.1)
        self.y_label = tk.Label(text="Y: ", font=("Consolas", 14))
        self.y_label.place(relx=0.4, rely=0.1)

        # Create the workflow table
        self.table: Optional[ttk.Treeview] = None
        self.create_table()
        self.table_columns_indexed = dict(zip(("Seq", "Action", "X", "Y", "Delay (ms)", "Repeat", "Comment"), range(7)))

        # Create the `Add` button
        self.add_button = tk.Button(self.master, text="Add", font=("Consolas", 14), command=self.add_row)
        self.add_button.place(relx=0.57, rely=0.08)

        # Create the `Delete` button
        self.delete_button = tk.Button(self.master, text="Delete", font=("Consolas", 14), command=self.delete_row)
        self.delete_button.place(relx=0.63, rely=0.08)

        # Create the `Move Up` button
        self.moveup_button = tk.Button(self.master, text="Move Up", font=("Consolas", 14), command=self.move_up)
        self.moveup_button.place(relx=0.72, rely=0.08)

        # Create the `Move Down` button
        self.movedown_button = tk.Button(self.master, text="Move Down", font=("Consolas", 14), command=self.move_down)
        self.movedown_button.place(relx=0.81, rely=0.08)

        # Create the `Failsafe` dropdown
        failsafe_options = ("esc", "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12")
        self.active_failsafe = tk.StringVar(value="esc")
        failsafe_dropdown = ttk.Combobox(values=failsafe_options, state="readonly", textvariable=self.active_failsafe,
                                         width=7)
        failsafe_dropdown.place(relx=0.75, rely=0.8)
        failsafe_dropdown.configure(font=("Consolas", 14))

        # Create the `Run` button
        self.run_button = tk.Button(self.master, text="Run", font=("Consolas", 14), command=self.run_starter)
        self.run_button.place(relx=0.95, rely=0.8)
        self.run_flag = True
        self.hold_session = HoldSession()
        self.holds_next = False

        # MAIN WINDOW START
        self.master.mainloop()

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

    def pick_coordinate(self):
        # New invisible fullscreen window
        self.fake_fullscreen = tk.Toplevel(self.master)
        self.fake_fullscreen.attributes("-alpha", 1 / 256)
        self.fake_fullscreen.attributes("-fullscreen", True)
        # Binding window as button
        self.fake_fullscreen.bind("<Button-1>", self.get_clicked_position)
        self.fake_fullscreen.config(cursor="crosshair")
        # Minimize master window while wait for the user to click on the fullscreen
        self.master.iconify()
        self.fake_fullscreen.wait_window()

    def get_clicked_position(self, event: tk.Event):
        self.pick_x, self.pick_y = event.x_root, event.y_root
        # Update the labels with the picked coordinates
        self.x_label.configure(text=f"X: {self.pick_x}")
        self.y_label.configure(text=f"Y: {self.pick_y}")
        # Unbind button, destroy fullscreen, and pop back master window
        self.fake_fullscreen.unbind("<Button-1>")
        self.fake_fullscreen.destroy()
        self.master.deiconify()

    def create_table(self):
        # Create the table
        column_names = ("Seq", "Action", "X", "Y", "Delay (ms)", "Repeat", "Comment")
        column_widths = (30, 60, 50, 50, 50, 50, 100)
        self.table = EditableTreeview(self.master, columns=column_names, show="headings")
        # Set the column headings
        for col_name in column_names:
            self.table.heading(col_name, text=col_name)
        # Set the column widths
        for col_name, col_width in zip(column_names, column_widths):
            self.table.column(col_name, width=col_width)
        # Add the table to the windiow
        self.table.pack(side=tk.TOP, padx=5, pady=5, fill=tk.BOTH, expand=True)
        table_width = sum(column_widths) // 2
        self.table.place(relwidth=0.5, width=table_width, relheight=0.5, relx=0.05, rely=0.2)

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


if __name__ == '__main__':
    Main()

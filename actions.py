"""
Actions module:
using pyautogui to control the keyboard and mouse inputs
"""

import pyautogui as auto

def left_click(x, y):
    auto.click(x=x, y=y)

def left_double_click(x, y):
    auto.doubleClick(x=x, y=y)

def middle_click(x, y):
    auto.click(x, y, button="middle")

def right_click(x, y):
    auto.click(x, y, button="right")

def left_mouse_down(x, y):
    auto.mouseDown(x, y)

def left_mouse_up(x, y):
    auto.mouseUp(x, y)

def middle_mouse_down(x, y):
    auto.mouseDown(x, y, button="middle")

def middle_mouse_up(x, y):
    auto.mouseUp(x, y, button="middle")

def right_mouse_down(x, y):
    auto.mouseDown(x, y, button="right")

def right_mouse_up(x, y):
    auto.mouseUp(x, y, button="right")

def move_mouse_to(x, y):
    auto.moveTo(x, y)

def scroll_up(strength=120):
    auto.scroll(strength)

def scroll_down(strength=120):
    auto.scroll(-strength)

def scroll_left(strength=120):
    auto.hscroll(strength)

def scroll_right(strength=120):
    auto.hscroll(-strength)

def ctrl_z():
    auto.hotkey("ctrl", 'z')

def ctrl_x():
    auto.hotkey("ctrl", 'x')

def ctrl_c():
    auto.hotkey("ctrl", 'c')

def ctrl_v():
    auto.hotkey("ctrl", 'v')

def ctrl_a():
    auto.hotkey("ctrl", 'a')

class HoldSession:
    def __init__(self):
        self.holding_keys: list[str] = []

    def hold_key(self, key: str):
        auto.keyDown(key)
        self.holding_keys.append(key)

    def release_all(self):
        for key in reversed(self.holding_keys):
            auto.keyUp(key)
        self.holding_keys.clear()

def press_key(key: str = ""):
    if key:
        auto.press(key)

def type_comment(comment: str):
    auto.typewrite(comment)

def type_text_file(path: str):
    with open(path, "r") as f:
        auto.typewrite(f.read())



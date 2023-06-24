import pyautogui as auto
from time import sleep, perf_counter

def left_click(x, y):
    auto.click(x=x, y=y)

def left_double_click(x, y):
    auto.doubleClick(x=x, y=y)

def middle_click(x, y):
    auto.click(button="middle", x=x, y=y)

def right_click(x, y):
    auto.click(button="right", x=x, y=y)

def left_mouse_down(x, y):
    auto.mouseDown(x=x, y=y)

def left_mouse_up(x, y):
    auto.mouseDown(x=x, y=y)

def scroll_up(strength=120):
    auto.scroll(strength)

def scroll_down(strength=120):
    auto.scroll(-strength)

def scroll_left(strength=120):
    auto.hscroll(strength)

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

def press_key(key: str):
    auto.press(key)

def type_comment(comment: str):
    auto.typewrite(comment)

def type_text_file(path: str):
    with open(path, "r") as f:
        auto.typewrite(f.read())

if __name__ == '__main__':
    t1 = perf_counter()
    session = HoldSession()
    session.hold_key("ctrl")
    session.hold_key("alt")
    session.hold_key("shift")
    session.release_all()
    t2 = perf_counter()
    print(f"Time elapsed: {t2 - t1}s")

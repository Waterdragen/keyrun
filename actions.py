import pyautogui as auto
from time import sleep

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

def hold_ctrl():
    auto.keyDown("ctrl")

def hold_alt():
    auto.keyDown("alt")

def hold_shift():
    auto.keyDown("shift")

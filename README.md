# keyrun
Automate your mouse and keyboard to do cool things. Free and open source alternative to ~Auto Mouse Click by Murgee~

## Work in progress
This app is still in the early stage and there are many things to be added
<img src="https://raw.githubusercontent.com/Waterdragen/keyrun/main/snapshot.png">

## WIP list
- a fully working `Run` button
- more action options (currently 67)
  - short term target: 100 options
  - mouse (clicks, move, scroll, hold & release)
  - hotkeys (press, hold & release)
  - inputs
  - delay and sleep
- `failsafe` activation after at most 1 sec (delay and action integration)
- classify actions 
- `save/load` csv
- UI
  - font choice/size
  - button positions
  - images
 
## WIP future plans
- load csv file
- fix disabled/enabled pick button
- add mouse position by key press
- tadd default delay ms
- add script repeat
- add more failsafe options (not all keyboards have f keys and esc)
- add move mouse
- renaming: up/down -> hold/release
-renaming: hotkeys -> combokeys, non char keys -> presskeys
- add a column for strength(scroll) 
- logger window to print what's going on
  - show warnings 
  - e.g. `[WARN] ctrl key is held but never released!`
- Settings:
  - Add to the end / add after selected line (append mode/insert mode)
  - show tips (show/hidden)
  - compile/run mode

## WIP issues
- failsafe may fail occasionally
- `Pick` button is sometimes disabled when switching types (`action_changed` method)

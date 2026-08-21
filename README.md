# controller_fusion

Combines 4-6 Xbox controllers (connected via Parsec) into 1 or 2 virtual Xbox
controllers, so several friends can share a team in a fighting game (built
for Ultimate Marvel vs Capcom 3).

Windows only. Uses pygame (SDL) to read the physical controllers and
vgamepad (ViGEmBus) to create the virtual one(s). No vJoy involved.

## Requirements

- **Windows 10/11**, Python **3.9+** with pip (the standard installer from
  python.org includes both pip and Tk/tkinter - use that one, not a minimal
  install).
- **pygame** and **vgamepad** - installed automatically the first time you run
  the script if they're missing. Nothing to do by hand.
- **ViGEmBus driver** - installed automatically by the `vgamepad` package the
  first time it runs (watch for a Windows driver-install prompt). If you
  already use Parsec, you likely already have it.
- **tkinter** - only needed for `--gui`. It ships with the standard Windows
  installer from python.org; if it's missing, reinstall Python with the
  default options (don't deselect it).

If any of this is missing when you run the script, it tells you exactly
what's missing and how to fix it - it doesn't fail silently.

## Quick start (no Python yet?)

Double-click **`setup.bat`**. It checks for a working Python 3.9+ (the
Microsoft Store's fake `python` placeholder doesn't count), installs a real
one via `winget` if needed, and then launches the GUI automatically. If
`winget` isn't available or the install fails, it opens the python.org
download page for you instead and tells you what to do - it won't leave you
stuck either way. Once Python is in place, `controller_fusion.py` installs
its own remaining dependencies (see Requirements above) on its own.

## Quick start (GUI)

```
python controller_fusion.py --gui
```

Opens a window: drag each detected gamepad's card into P1 or P2, pick a
button-mapping profile per card (or leave it on `standard`), hit **Start**.
Team assignments and profiles can be changed live, on the fly, without
closing the window or interrupting anyone's input.

GUI features:
- **Live gamepad diagram per card** - press a button, see it light up in the
  right spot, translated through whatever profile that card is using. Doubles
  as "who's holding which controller."
- **Combined view** (right-hand strip) - shows what each virtual pad (P1/P2)
  actually receives once merged across everyone assigned to that side, so
  each player can confirm they're wired in correctly.
- **Configure controls** (⚙ on each card) - build/edit/delete a custom
  button-mapping profile for a non-standard controller (fightsticks, etc.),
  with a live tester built in.
- **Refresh** - re-scan for gamepads that were plugged in or unplugged after
  the window opened. Only usable while stopped (Stop first, then Refresh,
  then Start again) - it doesn't run automatically in the background so it
  can't add any overhead to live input.
- **Latency test** - live, per-press timing of this script's own read+write
  pipeline (not USB/Parsec/game latency - just the part this script
  controls). Typically sub-millisecond.

## Quick start (text-only)

```
python controller_fusion.py --setup
```

Same idea as the GUI, driven by console prompts instead of a window: press
buttons to identify gamepads, assign each to a side, pick profiles, then it
starts playing right away.

## Other commands

```
python controller_fusion.py --list                    # list detected gamepads
python controller_fusion.py --identify                 # press a button, see which index it is
python controller_fusion.py --diagnose N [sec]          # log a gamepad's raw axis/button events
python controller_fusion.py --profile-create N [name]   # build a custom button-mapping profile
python controller_fusion.py --profile-list               # list saved profiles
python latency_probe.py N [sec]                          # same latency test as the GUI, from the console
```

See `AI_CONTEXT.md` for design decisions, known issues, and pending work.

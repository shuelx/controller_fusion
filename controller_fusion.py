#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
controller_fusion.py
Combines several Xbox (XInput) controllers into one or two virtual Xbox controllers
using ViGEmBus. Does NOT use vJoy. Reads physical controllers via SDL (pygame) and
creates the virtual one(s) with vgamepad.

Usage:
    python controller_fusion.py --list                    -> list detected gamepads with their index
    python controller_fusion.py --diagnose N [sec]         -> logs axis/button changes for gamepad N to
                                                                logs/diagnose_N.log for [sec] seconds (default 30)
    python controller_fusion.py --identify                 -> press a button on any gamepad and see which
                                                                index it is, live (handy with several people)
    python controller_fusion.py --profile-create N [name]  -> interactive wizard: builds a button profile
                                                                for gamepad N (for fightsticks or other
                                                                non-standard layouts)
    python controller_fusion.py --profile-list              -> lists saved profiles
    python controller_fusion.py --setup                     -> interactive wizard: assigns each detected
                                                                gamepad to P1/P2 and to a profile, saves
                                                                session.json and starts playing right away
    python controller_fusion.py --gui                       -> same as --setup but with a window: drag
                                                                each gamepad's card into P1/P2, pick a
                                                                profile per card, then Start
    python controller_fusion.py                             -> runs. Uses session.json if present,
                                                                otherwise falls back to the CONFIG block below

Requirements:
    Python 3.9+ with pip, on Windows. Everything else (pygame, vgamepad) is
    installed automatically on first run if missing - see _ensure_package below.
    ViGEmBus itself gets installed by the vgamepad package the first time it runs
    (watch for a Windows driver-install prompt); if you already have Parsec, you
    likely already have it.
"""

import sys
import time
import os
import json
import subprocess
import msvcrt
import ctypes

_VK_LBUTTON = 0x01


def _left_mouse_down():
    # While the left button is held (e.g. dragging the GUI window by its
    # title bar), pygame's SDL event pump drains Windows' message queue and
    # ends up swallowing the drag's own mouse-move messages before the OS
    # can apply them, making the window seem stuck. Skipping the pump during
    # that window avoids the conflict - see GUI polling loop.
    return ctypes.windll.user32.GetAsyncKeyState(_VK_LBUTTON) & 0x8000 != 0


def _ensure_package(import_name, pip_name=None):
    """Imports import_name, auto-installing pip_name via pip if it's missing.
    Makes the script runnable on a fresh machine without a manual install step."""
    pip_name = pip_name or import_name
    try:
        return __import__(import_name)
    except ImportError:
        pass

    print(f"Missing '{pip_name}'. Installing it now with pip (this happens once)...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])
    except (subprocess.CalledProcessError, OSError) as e:
        print(f"\nFAILED to install '{pip_name}' automatically: {e}")
        print(f"Install it by hand and try again:  {sys.executable} -m pip install {pip_name}")
        sys.exit(1)

    try:
        return __import__(import_name)
    except ImportError:
        print(f"\n'{pip_name}' was installed but still can't be imported.")
        print("Something is off with this Python environment - check it manually.")
        sys.exit(1)


def _try_ensure_optional(import_name, pip_name=None):
    """Like _ensure_package, but for purely cosmetic dependencies: never exits
    the program. Any failure (no internet, install error, whatever) just
    returns None so the caller can fall back to something built-in instead."""
    pip_name = pip_name or import_name
    try:
        return __import__(import_name)
    except ImportError:
        pass
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return __import__(import_name)
    except Exception:
        return None


pygame = _ensure_package("pygame")


# ============================ CONFIG ============================
# Edit this. The 'sources' indices come from:  python controller_fusion.py --list
# HEADS UP: those indices are NOT stable across Parsec sessions. Every time your
# friends reconnect you need to run --list again and update the 'sources' lists
# below. To go from 2v2 to 3v2/3v3 just move an index from one list to the other
# (or add one if a 5th/6th gamepad connects).
#
# This config is the manual fallback. If you ran --setup and session.json exists,
# that one is used instead (same shape, but with a profile per source). No need
# to touch this if you always use --setup.
CONFIG = {
    "virtual_pads": [
        {
            "name": "P1",             # team side 1
            "mode": "merge",          # "merge" = everyone adds up  |  "switch" = one active at a time
            "sources": [0, 1],        # indices of the physical gamepads feeding this virtual pad
            "switch_button": "BACK",  # (switch mode only) button that cycles the active source
        },
        {
            "name": "P2",             # team side 2
            "mode": "merge",
            "sources": [2, 3],
            "switch_button": "BACK",
        },
    ],
    "poll_ms": 4,   # how often it refreshes (ms). 4-8 is fine.
}

# Physical gamepad axis indices. Adjust with --diagnose if they don't match.
# Typical SDL2 layout for Xbox controllers on Windows. The D-pad (hat) and the
# sticks are NEVER remapped by a profile: they always use this.
AXES = {
    "LX": 0,   # left stick horizontal
    "LY": 1,   # left stick vertical
    "RX": 2,   # right stick horizontal
    "RY": 3,   # right stick vertical
    "LT": 4,   # left trigger (standard profile)
    "RT": 5,   # right trigger (standard profile)
}

# Physical button -> logical name for the "standard" profile (no remapping).
# Adjust with --diagnose if needed. Fightsticks with a different layout don't
# touch this: they get their own profile via --profile-create / --setup.
BUTTONS = {
    0: "A", 1: "B", 2: "X", 3: "Y",
    4: "LB", 5: "RB", 6: "BACK", 7: "START",
    8: "LS", 9: "RS",
}
BUTTON_NAMES = ("A", "B", "X", "Y", "LB", "RB", "BACK", "START", "LS", "RS")
# ===============================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILES_PATH = os.path.join(SCRIPT_DIR, "profiles.json")
SESSION_PATH = os.path.join(SCRIPT_DIR, "session.json")
LOGS_DIR = os.path.join(SCRIPT_DIR, "logs")

# Buttons that Ultimate Marvel vs Capcom 3 absolutely needs. Xbox <-> PlayStation
# naming used by most fightsticks/the fighting game community:
#   A=Cross  B=Circle  X=Square  Y=Triangle  LB=L1  RB=R1  LT=L2  RT=R2
#   BACK=Select  START=Start  LS=L3  RS=R3
REQUIRED_BUTTONS = ["A", "X", "Y", "B", "LB", "RB", "BACK", "START"]
OPTIONAL_BUTTONS = ["LT", "RT", "LS", "RS"]
FRIENDLY_NAME = {
    "A": "CROSS / X (bottom)",
    "B": "CIRCLE (right)",
    "X": "SQUARE (left)",
    "Y": "TRIANGLE (top)",
    "LB": "L1",
    "RB": "R1",
    "BACK": "SELECT",
    "START": "START",
    "LT": "L2 (press it fully if it's an analog trigger)",
    "RT": "R2 (press it fully if it's an analog trigger)",
    "LS": "L3 (left stick click)",
    "RS": "R3 (right stick click)",
}


def _init_pygame():
    pygame.init()
    pygame.joystick.init()


def _gamepads():
    js = []
    for i in range(pygame.joystick.get_count()):
        j = pygame.joystick.Joystick(i)
        j.init()
        js.append(j)
    return js


def _gamepad_index_by_instance(js, instance_id):
    for i, j in enumerate(js):
        if j.get_instance_id() == instance_id:
            return i
    return None


def cmd_list():
    _init_pygame()
    js = _gamepads()
    if not js:
        print("No gamepad detected. Connect them and try again.")
        return
    print(f"Detected {len(js)} gamepad(s):\n")
    for i, j in enumerate(js):
        print(f"  [{i}] {j.get_name()}  | axes={j.get_numaxes()} "
              f"buttons={j.get_numbuttons()} hats={j.get_numhats()}")
    print("\nUse these indices in CONFIG['virtual_pads'][...]['sources'] or in --setup.")


def cmd_diagnose(idx, seconds=30):
    _init_pygame()
    js = _gamepads()
    if idx < 0 or idx >= len(js):
        print(f"Index {idx} out of range. There are {len(js)} gamepad(s).")
        return
    j = js[idx]
    inst = j.get_instance_id()
    os.makedirs(LOGS_DIR, exist_ok=True)
    log_path = os.path.join(LOGS_DIR, f"diagnose_{idx}.log")
    print(f"Diagnose for [{idx}] {j.get_name()} (instance_id={inst})")
    print(f"You have {seconds}s. Move both sticks fully in every direction, press LT/RT fully,")
    print("press every button (A B X Y LB RB BACK START LS RS) and try the D-pad in all 4 directions.")
    print(f"Log: {log_path}\n")

    t0 = time.time()
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"Diagnose [{idx}] {j.get_name()} instance_id={inst}\n")
        f.write(f"axes={j.get_numaxes()} buttons={j.get_numbuttons()} hats={j.get_numhats()}\n\n")

        def log(msg):
            line = f"[{time.time() - t0:6.2f}s] {msg}"
            print(line)
            f.write(line + "\n")
            f.flush()

        try:
            while time.time() - t0 < seconds:
                for ev in pygame.event.get():
                    eid = getattr(ev, "instance_id", getattr(ev, "joy", None))
                    if eid != inst:
                        continue
                    if ev.type == pygame.JOYAXISMOTION:
                        if abs(ev.value) > 0.5:
                            log(f"AXIS {ev.axis} -> {ev.value:.2f}")
                    elif ev.type == pygame.JOYBUTTONDOWN:
                        log(f"BUTTON {ev.button} DOWN")
                    elif ev.type == pygame.JOYBUTTONUP:
                        log(f"BUTTON {ev.button} UP")
                    elif ev.type == pygame.JOYHATMOTION:
                        log(f"HAT {ev.hat} -> {ev.value}")
                time.sleep(0.01)
        except KeyboardInterrupt:
            pass
    print(f"\nDone. Log saved to: {log_path}")


def cmd_identify(js=None):
    owns_init = js is None
    if owns_init:
        _init_pygame()
        js = _gamepads()
    if not js:
        print("No gamepad detected.")
        return
    print(f"Detected {len(js)} gamepad(s). Ask each person to press ONE button on their controller,")
    print("one at a time. You'll see one line per press. Press ENTER here when you're done.\n")
    pygame.event.clear()
    try:
        while True:
            if msvcrt.kbhit():
                msvcrt.getch()
                break
            for ev in pygame.event.get():
                if ev.type == pygame.JOYBUTTONDOWN:
                    inst = getattr(ev, "instance_id", getattr(ev, "joy", None))
                    idx = _gamepad_index_by_instance(js, inst)
                    if idx is not None:
                        print(f"  -> Gamepad [{idx}] ({js[idx].get_name()}) pressed button {ev.button}")
                elif ev.type == pygame.JOYHATMOTION and ev.value != (0, 0):
                    inst = getattr(ev, "instance_id", getattr(ev, "joy", None))
                    idx = _gamepad_index_by_instance(js, inst)
                    if idx is not None:
                        print(f"  -> Gamepad [{idx}] ({js[idx].get_name()}) moved the D-pad")
            time.sleep(0.01)
    except KeyboardInterrupt:
        pass
    print()


# ============================ PROFILES ============================

def _load_profiles():
    if os.path.exists(PROFILES_PATH):
        with open(PROFILES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_profiles(profiles):
    with open(PROFILES_PATH, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2, ensure_ascii=False)


def _standard_profile():
    """The implicit profile: identical to the BUTTONS/AXES mapping above, no remapping."""
    inv = {v: k for k, v in BUTTONS.items()}
    profile = {}
    for name in BUTTON_NAMES:
        if name in inv:
            profile[name] = {"type": "button", "index": inv[name]}
    profile["LT"] = {"type": "axis", "index": AXES["LT"]}
    profile["RT"] = {"type": "axis", "index": AXES["RT"]}
    return profile


def _wait_for_input(j, timeout=15):
    """Waits for a button press or axis/trigger movement on j. Returns (type, index) or None."""
    inst = j.get_instance_id()
    t0 = time.time()
    pygame.event.clear()
    while time.time() - t0 < timeout:
        for ev in pygame.event.get():
            eid = getattr(ev, "instance_id", getattr(ev, "joy", None))
            if eid != inst:
                continue
            if ev.type == pygame.JOYBUTTONDOWN:
                return ("button", ev.button)
            if ev.type == pygame.JOYAXISMOTION and abs(ev.value) > 0.6:
                return ("axis", ev.axis)
        time.sleep(0.01)
    return None


def _create_profile_interactive(j, name):
    print(f"\nCreating profile '{name}' for {j.get_name()}")
    print("You'll press, one at a time, the button that does each function on YOUR controller.")
    print("Leave everything else untouched while you press. You have 15s per button.\n")

    profile = {}
    for key in REQUIRED_BUTTONS:
        print(f"  Press: {FRIENDLY_NAME[key]}  [{key}]")
        r = _wait_for_input(j)
        if r is None:
            print("    -> timeout, left unassigned (you can edit profiles.json by hand later).")
            continue
        kind, index = r
        profile[key] = {"type": kind, "index": index}
        print(f"    -> OK ({kind} {index})")
        time.sleep(0.3)

    print("\nOptional buttons (L2, R2, L3, R3) - configure only the ones you actually need:")
    for key in OPTIONAL_BUTTONS:
        r_in = input(f"  Configure {FRIENDLY_NAME[key]} [{key}]? (y/N): ").strip().lower()
        if r_in != "y":
            continue
        print("    Press the button...")
        r = _wait_for_input(j)
        if r is None:
            print("    -> timeout, skipped.")
            continue
        kind, index = r
        profile[key] = {"type": kind, "index": index}
        print(f"    -> OK ({kind} {index})")
        time.sleep(0.3)

    missing = [n for n in REQUIRED_BUTTONS if n not in profile]
    if missing:
        print(f"\nHEADS UP: required buttons left unassigned: {missing}")
    return profile


def cmd_profile_create(idx, name=None):
    _init_pygame()
    js = _gamepads()
    if idx < 0 or idx >= len(js):
        print(f"Index {idx} out of range. There are {len(js)} gamepad(s).")
        return
    if not name:
        name = input("Name for this profile: ").strip()
    if not name:
        print("Empty name, cancelled.")
        return
    profile = _create_profile_interactive(js[idx], name)
    profiles = _load_profiles()
    profiles[name] = profile
    _save_profiles(profiles)
    print(f"\nProfile '{name}' saved to {PROFILES_PATH}")


def cmd_profile_list():
    profiles = _load_profiles()
    if not profiles:
        print(f"No profiles saved in {PROFILES_PATH}")
        return
    for name, profile in profiles.items():
        missing = [n for n in REQUIRED_BUTTONS if n not in profile]
        optional = [n for n in OPTIONAL_BUTTONS if n in profile]
        status = "COMPLETE" if not missing else f"INCOMPLETE (missing {missing})"
        print(f"- {name}: {status} | optional configured: {optional or 'none'}")


def cmd_setup():
    _init_pygame()
    js = _gamepads()
    if not js:
        print("No gamepad detected. Connect them and try again.")
        return

    print(f"Detected {len(js)} gamepad(s):\n")
    for i, j in enumerate(js):
        print(f"  [{i}] {j.get_name()}")
    print()

    resp = input("Identify gamepads first? Ask each person to press a button, one at a time. (Y/n): ").strip().lower()
    if resp != "n":
        cmd_identify(js)

    profiles = _load_profiles()
    standard_profile = _standard_profile()
    sides = {"P1": [], "P2": []}

    for i, j in enumerate(js):
        resp = input(f"[{i}] {j.get_name()} -> side (1=P1, 2=P2, Enter=skip): ").strip()
        if resp not in ("1", "2"):
            continue
        side = "P1" if resp == "1" else "P2"

        names_avail = ", ".join(profiles.keys()) if profiles else "(none saved yet)"
        print(f"  Available profiles: {names_avail}")
        pf = input("  Profile to use (Enter=standard / 'new'=map buttons / existing name): ").strip()

        profile_name = None
        if pf == "new":
            new_name = input("  Name for the new profile: ").strip()
            if new_name:
                profile = _create_profile_interactive(j, new_name)
                profiles[new_name] = profile
                _save_profiles(profiles)
                profile_name = new_name
        elif pf and pf in profiles:
            profile_name = pf
        elif pf:
            print(f"  '{pf}' does not exist, using standard.")
        else:
            # standard layout, no remapping needed - still let them tag it with a
            # name (e.g. the player's name) so it's easy to review who's where later
            label = input("  Save this as a named profile for next time? "
                           "(player's name, or Enter to skip): ").strip()
            if label:
                profiles[label] = dict(standard_profile)
                _save_profiles(profiles)
                profile_name = label

        sides[side].append({"index": i, "profile": profile_name})

    session = {"virtual_pads": []}
    for side_name in ("P1", "P2"):
        if sides[side_name]:
            session["virtual_pads"].append({
                "name": side_name,
                "mode": "merge",
                "switch_button": "BACK",
                "sources": sides[side_name],
            })

    if not session["virtual_pads"]:
        print("\nNo gamepad was assigned to P1 or P2. Nothing saved.")
        return

    with open(SESSION_PATH, "w", encoding="utf-8") as f:
        json.dump(session, f, indent=2, ensure_ascii=False)

    print(f"\nSaved to {SESSION_PATH}")
    for v in session["virtual_pads"]:
        summary = [(s["index"], s["profile"] or "standard") for s in v["sources"]]
        print(f"  {v['name']}: {summary}")
    print("\nStarting now...\n")
    run()


PAD_DIAGRAM_SCALE = 1.3
PAD_DIAGRAM_W, PAD_DIAGRAM_H = round(176 * PAD_DIAGRAM_SCALE), round(62 * PAD_DIAGRAM_SCALE)


def _draw_pad_diagram(canvas, scale=1.0):
    """Draws a small generic gamepad schematic on `canvas` (not brand-accurate, just
    enough to tell buttons apart, with everything spaced so labels never touch a
    neighboring shape) and returns ({logical_name: canvas_item_id}, {name: (cx, cy,
    move_radius, dot_radius)}) - the second dict is only for the stick dots (LS/RS),
    so the caller can reposition them live with canvas.coords() instead of just
    recoloring them. Coordinates below are the base (scale=1.0) layout; everything
    is multiplied by `scale` so the same drawing can be shown bigger without
    redoing the numbers. Both sticks get a moving dot; the left one sits in the
    gap between the D-pad and face buttons, the right one is smaller since it has
    less free space to work with, squeezed just past the face buttons."""
    def s(v):
        return v * scale

    def sf(pt):
        return max(6, round(pt * scale))

    OFF = "#e4e7ec"
    OUT = "#aab0bc"
    ids = {}
    meta = {}

    # Row 1: shoulders, with Back/Select + Start in the gap between them
    ids["LB"] = canvas.create_rectangle(s(2), s(2), s(24), s(14), fill=OFF, outline=OUT)
    canvas.create_text(s(13), s(8), text="LB", font=("Segoe UI", sf(6)))
    ids["LT"] = canvas.create_rectangle(s(26), s(2), s(48), s(14), fill=OFF, outline=OUT)
    canvas.create_text(s(37), s(8), text="LT", font=("Segoe UI", sf(6)))
    ids["BACK"] = canvas.create_oval(s(66), s(2), s(78), s(14), fill=OFF, outline=OUT)
    ids["START"] = canvas.create_oval(s(84), s(2), s(96), s(14), fill=OFF, outline=OUT)
    ids["RB"] = canvas.create_rectangle(s(126), s(2), s(148), s(14), fill=OFF, outline=OUT)
    canvas.create_text(s(137), s(8), text="RB", font=("Segoe UI", sf(6)))
    ids["RT"] = canvas.create_rectangle(s(150), s(2), s(172), s(14), fill=OFF, outline=OUT)
    canvas.create_text(s(161), s(8), text="RT", font=("Segoe UI", sf(6)))
    # ovals are too small to hold "back"/"start" themselves, label just below
    canvas.create_text(s(72), s(17), text="back", font=("Segoe UI", sf(5)))
    canvas.create_text(s(90), s(17), text="start", font=("Segoe UI", sf(5)))

    # Row 2: D-pad (left) and face buttons (right)
    ids["dpad_up"] = canvas.create_rectangle(s(26), s(22), s(38), s(34), fill=OFF, outline=OUT)
    ids["dpad_down"] = canvas.create_rectangle(s(26), s(46), s(38), s(58), fill=OFF, outline=OUT)
    ids["dpad_left"] = canvas.create_rectangle(s(14), s(34), s(26), s(46), fill=OFF, outline=OUT)
    ids["dpad_right"] = canvas.create_rectangle(s(38), s(34), s(50), s(46), fill=OFF, outline=OUT)
    canvas.create_rectangle(s(26), s(34), s(38), s(46), fill="#f0f2f5", outline=OUT)

    ids["Y"] = canvas.create_oval(s(124), s(22), s(136), s(34), fill=OFF, outline=OUT)
    canvas.create_text(s(130), s(28), text="Y", font=("Segoe UI", sf(6)))
    ids["X"] = canvas.create_oval(s(112), s(34), s(124), s(46), fill=OFF, outline=OUT)
    canvas.create_text(s(118), s(40), text="X", font=("Segoe UI", sf(6)))
    ids["B"] = canvas.create_oval(s(136), s(34), s(148), s(46), fill=OFF, outline=OUT)
    canvas.create_text(s(142), s(40), text="B", font=("Segoe UI", sf(6)))
    ids["A"] = canvas.create_oval(s(124), s(46), s(136), s(58), fill=OFF, outline=OUT)
    canvas.create_text(s(130), s(52), text="A", font=("Segoe UI", sf(6)))

    # Left stick: sits in the gap between the D-pad and the face buttons. The
    # dot both moves (direction) and recolors (L3 click), same item for both.
    lcx, lcy, lr, ldot = 78, 40, 12, 3.5
    canvas.create_rectangle(s(lcx - lr), s(lcy - lr), s(lcx + lr), s(lcy + lr),
                             fill="#f4f4f4", outline=OUT)
    ids["LS"] = canvas.create_oval(s(lcx - ldot), s(lcy - ldot), s(lcx + ldot), s(lcy + ldot),
                                    fill=OFF, outline=OUT)
    meta["LS"] = (s(lcx), s(lcy), s(lr - ldot), s(ldot))

    # Right stick: same idea as the left one, just smaller - there's less room
    # to the right of the face buttons than there was in the D-pad gap.
    rcx, rcy, rr, rdot = 162, 40, 10, 3
    canvas.create_rectangle(s(rcx - rr), s(rcy - rr), s(rcx + rr), s(rcy + rr),
                             fill="#f4f4f4", outline=OUT)
    ids["RS"] = canvas.create_oval(s(rcx - rdot), s(rcy - rdot), s(rcx + rdot), s(rcy + rdot),
                                    fill=OFF, outline=OUT)
    meta["RS"] = (s(rcx), s(rcy), s(rr - rdot), s(rdot))

    return ids, meta


def _update_pad_diagram(canvas, ids, meta, st):
    """Colors/moves a diagram drawn by _draw_pad_diagram according to a _read_state()
    result. `meta` positions the stick dot(s) - see _draw_pad_diagram."""
    ON = "#3fae5c"
    OFF = "#e4e7ec"
    for name in ("A", "B", "X", "Y", "LB", "RB", "BACK", "START", "LS", "RS"):
        canvas.itemconfig(ids[name], fill=ON if st["buttons"].get(name) else OFF)
    canvas.itemconfig(ids["LT"], fill=ON if st["LT"] > 0.5 else OFF)
    canvas.itemconfig(ids["RT"], fill=ON if st["RT"] > 0.5 else OFF)
    dx, dy = st["dpad"]
    canvas.itemconfig(ids["dpad_up"], fill=ON if dy > 0 else OFF)
    canvas.itemconfig(ids["dpad_down"], fill=ON if dy < 0 else OFF)
    canvas.itemconfig(ids["dpad_left"], fill=ON if dx < 0 else OFF)
    canvas.itemconfig(ids["dpad_right"], fill=ON if dx > 0 else OFF)

    for name, keys in (("LS", ("LX", "LY")), ("RS", ("RX", "RY"))):
        cx, cy, r, dot_r = meta[name]
        vx, vy = _clamp(st[keys[0]]), _clamp(st[keys[1]])
        px, py = cx + vx * r, cy + vy * r
        canvas.coords(ids[name], px - dot_r, py - dot_r, px + dot_r, py + dot_r)


def cmd_gui():
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox
    except ImportError:
        print("Missing tkinter. It ships with the standard python.org Windows installer -")
        print("if it's missing, reinstall Python from python.org with the default options.")
        sys.exit(1)

    # Check every dependency up front, before the window even opens, instead of
    # only finding out vgamepad/ViGEmBus has a problem the first time someone
    # hits Start mid-session. pygame is already checked at import time (top of
    # this file); this just adds the one that --gui specifically needs.
    vg_module = {"vg": _ensure_package("vgamepad")}

    _init_pygame()
    js = _gamepads()
    # unlike the other commands, the GUI still opens with zero gamepads connected -
    # you can plug one in and hit Refresh instead of having to relaunch the app

    profiles = _load_profiles()
    profile_names = ["standard"] + sorted(profiles.keys())
    standard_profile = _standard_profile()

    def resolve_profile(name):
        return profiles.get(name, standard_profile) if name != "standard" else standard_profile

    CARD_W, CARD_H = 250, 155

    root = tk.Tk()
    root.title("controller_fusion setup")

    # Fit the initial size to whatever screen this is, instead of a fixed 900x748
    # that overflows on a 720p laptop. Still resizable so it can also grow on a
    # bigger monitor - everything below reflows on resize (see on_resize).
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    win_w = max(700, min(1300, screen_w - 40))
    win_h = max(560, min(780, screen_h - 100))
    root.geometry(f"{win_w}x{win_h}")
    root.minsize(700, 560)
    root.resizable(True, True)

    # Reverted: sv-ttk's button sizing didn't respect the fixed-pixel header
    # layout (Latency test/Refresh/Start overlapped) and I can't iterate on
    # pixel fixes without seeing it render. Back to the native Windows theme,
    # which was confirmed working. _try_ensure_optional is still here if we
    # want to revisit this later with a less fragile (non-fixed-pixel) layout.
    style = ttk.Style()
    for theme in ("vista", "xpnative", "clam"):
        try:
            style.theme_use(theme)
            break
        except tk.TclError:
            continue

    BG = "#f3f5f8"
    CARD_BG = "#ffffff"
    HEADER_BG = "#33384a"
    BORDER = "#c7ccd6"
    P1_BG = "#eaf1ff"
    P2_BG = "#fff1ef"
    ACCENT_OK = "#dff5e6"
    ACCENT_STOP = "#fbe1e0"

    root.configure(bg=BG)

    # Toggle, not a one-shot Start: flips sending input to the virtual pad(s) on
    # and off without ever closing this window. Off by default so dragging cards
    # around while setting up teams can't accidentally send input mid-shuffle.
    live_btn = tk.Button(root, text="Start", bg=ACCENT_OK, relief="flat", bd=1)
    live_btn.place(relx=1.0, rely=0.0, x=-100, y=6, width=90, height=24)

    # ttk.Button gets native hover for free from the theme; this one stayed a
    # plain tk.Button so it can flip green/red, which costs it that hover -
    # add it back by hand so it doesn't feel dead next to its ttk neighbors.
    live_btn.bind("<Enter>", lambda _e: live_btn.configure(
        bg="#f6b8b5" if live["on"] else "#b8e6c8"))
    live_btn.bind("<Leave>", lambda _e: live_btn.configure(
        bg=ACCENT_STOP if live["on"] else ACCENT_OK))

    # Re-scans connected gamepads. Only meant to be used while stopped (disabled
    # while live) - re-detecting hardware mid-merge is what we're avoiding here.
    refresh_btn = ttk.Button(root, text="Refresh")
    refresh_btn.place(relx=1.0, rely=0.0, x=-176, y=6, width=70, height=24)

    # Opens the latency test in its own window - see open_latency_test below.
    latency_btn = ttk.Button(root, text="Latency test")
    latency_btn.place(relx=1.0, rely=0.0, x=-266, y=6, width=84, height=24)

    # Narrow strip on the right: what each virtual pad actually receives, merged
    # across everyone on that side - for validating "am I in the right spot"
    # without a popup (that could get opened twice - it did) and without eating
    # into the pool's height budget (width had more slack than height at 720p).
    RIGHT_COL_W = 150

    combined_col = tk.LabelFrame(root, text="Combined", bg=BG)
    combined_col.place(relx=1.0, rely=0.0, x=-(RIGHT_COL_W + 10), y=30,
                        width=RIGHT_COL_W, relheight=1.0, height=-52)

    COMBINED_SCALE = 0.7
    combined_panels = {}
    for n, side in enumerate(("P1", "P2")):
        tk.Label(combined_col, text=side, font=("Segoe UI", 9, "bold"), bg=BG).place(
            x=6, y=6 + n * 90)
        cc = tk.Canvas(combined_col, width=round(176 * COMBINED_SCALE), height=round(62 * COMBINED_SCALE),
                       bg=CARD_BG, highlightthickness=1, highlightbackground=BORDER)
        cc.place(x=6, y=22 + n * 90)
        cids, cmeta = _draw_pad_diagram(cc, scale=COMBINED_SCALE)
        combined_panels[side] = (cc, cids, cmeta)

    # Frames use relative (%) placement so they scale with the window; card
    # positions inside them get recomputed in relayout_all() on every resize.
    # Pool gets the most room since worst case (extra/spare controllers waiting
    # to rotate in) everyone could be sitting there unassigned at once. Width is
    # trimmed by the combined-view column above.
    pool = tk.LabelFrame(root, text="Detected gamepads - drag a card by its dark header", bg=BG)
    pool.place(relx=0.0, rely=0.0, relwidth=1.0, relheight=0.62, x=10, y=30,
               width=-(30 + RIGHT_COL_W), height=-36)

    # Scroll for the pool only - P1/P2 don't need it (a handful of players per
    # side always fits), but "everyone still waiting to be assigned" could be
    # 6-8 cards at once, more rows than fit on a 720p screen. Cards that scroll
    # out of view are place_forget()'d, not just visually clipped - they're
    # still full root-level children (same as everything else), so dragging
    # and drop-zone detection don't need to change at all.
    pool_scroll = {"row": 0}

    def scroll_pool(delta):
        pool_scroll["row"] = max(0, pool_scroll["row"] + delta)
        relayout_all()

    pool_up_btn = ttk.Button(pool, text="▲", width=2, command=lambda: scroll_pool(-1))
    pool_up_btn.place(relx=1.0, x=-46, y=2)
    pool_down_btn = ttk.Button(pool, text="▼", width=2, command=lambda: scroll_pool(1))
    pool_down_btn.place(relx=1.0, x=-24, y=2)

    def _on_global_wheel(ev):
        # cards are siblings of `pool` (children of root), not descendants of
        # it, so binding the wheel on `pool` alone only fires when the cursor
        # is over its bare background - which cards cover almost entirely.
        # Check screen position instead of widget ancestry so it works no
        # matter what's directly under the cursor.
        px0, py0 = pool.winfo_rootx(), pool.winfo_rooty()
        px1, py1 = px0 + pool.winfo_width(), py0 + pool.winfo_height()
        if px0 <= ev.x_root <= px1 and py0 <= ev.y_root <= py1:
            scroll_pool(-1 if ev.delta > 0 else 1)

    root.bind_all("<MouseWheel>", _on_global_wheel)

    zone_p1 = tk.LabelFrame(root, text="P1", bg=P1_BG)
    zone_p2 = tk.LabelFrame(root, text="P2", bg=P2_BG)

    def layout_zone_frames():
        # derive P1/P2 geometry from the pool's actual rendered width instead of
        # a plain relwidth of the whole window, since the pool itself is already
        # narrowed to make room for the combined-view column on the right
        root.update_idletasks()
        pool_x, pool_w = pool.winfo_x(), pool.winfo_width()
        half = (pool_w - 10) // 2
        zone_p1.place(x=pool_x, rely=0.62, width=half, relheight=0.34, y=6, height=-12)
        zone_p2.place(x=pool_x + half + 10, rely=0.62, width=half, relheight=0.34, y=6, height=-12)

    layout_zone_frames()

    status_text = ("Press a button on a controller to see which card lights up." if js
                   else "No gamepad detected yet - connect one and hit Refresh.")
    status = tk.Label(root, text=status_text, anchor="w", bg=BG)
    status.place(relx=0.0, rely=1.0, relwidth=1.0, x=10, y=-22, width=-20, height=18)

    CARD_GAP = 8
    cards = []  # dicts: index, j, frame, handle, name_var, profile_var, zone ("pool"/"P1"/"P2")

    def make_card(i, j):
        card = tk.Frame(root, bd=2, relief="raised", bg=CARD_BG,
                         highlightthickness=3, highlightbackground=BORDER)

        # the whole handle is the drag grip - keep it free of any widget that
        # wants mouse clicks for itself (an Entry here broke dragging entirely,
        # since it grabbed the click before the handle's own binding saw it)
        handle = tk.Frame(card, bg=HEADER_BG, height=16)
        handle.pack(fill="x", side="top")
        index_label = tk.Label(handle, text=f"gamepad [{i}]", bg=HEADER_BG, fg="white",
                                font=("Segoe UI", 7))
        index_label.pack(side="left", padx=4)

        name_var = tk.StringVar(value=f"Player {i}")
        tk.Entry(card, textvariable=name_var, font=("Segoe UI", 9, "bold")).pack(
            fill="x", padx=5, pady=(2, 2))

        diagram_canvas = tk.Canvas(card, width=PAD_DIAGRAM_W, height=PAD_DIAGRAM_H, bg=CARD_BG,
                                    highlightthickness=0)
        diagram_canvas.pack(pady=(0, 2))
        diagram_ids, diagram_meta = _draw_pad_diagram(diagram_canvas, scale=PAD_DIAGRAM_SCALE)

        # profile picker + a small color dot (standard=gray/custom=gold) + a tiny
        # gear button to open the editor, all sharing one row instead of three -
        # the dropdown already shows the exact profile name, no need to repeat it
        profile_row = tk.Frame(card, bg=CARD_BG)
        profile_row.pack(fill="x", padx=6, pady=(0, 3))
        tag_dot = tk.Label(profile_row, text=" ", bg="#888888", width=1)
        tag_dot.pack(side="left", padx=(0, 4))
        profile_var = tk.StringVar(value="standard")
        combo = ttk.Combobox(profile_row, values=profile_names, textvariable=profile_var,
                              state="readonly", font=("Segoe UI", 8))
        combo.pack(side="left", fill="x", expand=True)

        def update_tag(*_a):
            tag_dot.configure(bg="#888888" if profile_var.get() == "standard" else "#b8860b")

        profile_var.trace_add("write", update_tag)
        update_tag()

        info = {"index": i, "j": j, "frame": card, "handle": handle, "index_label": index_label,
                "name_var": name_var, "profile_var": profile_var, "combo": combo,
                "diagram_canvas": diagram_canvas, "diagram_ids": diagram_ids,
                "diagram_meta": diagram_meta, "zone": "pool"}
        cards.append(info)

        config_btn = ttk.Button(profile_row, text="⚙", width=2)
        config_btn.pack(side="left", padx=(3, 0))
        config_btn.configure(command=lambda: open_profile_editor(info))

        def start_drag(ev):
            mx = ev.x_root - root.winfo_rootx()
            my = ev.y_root - root.winfo_rooty()
            info["drag_off"] = (mx - card.winfo_x(), my - card.winfo_y())
            card.lift()

        def do_drag(ev):
            mx = ev.x_root - root.winfo_rootx()
            my = ev.y_root - root.winfo_rooty()
            ox, oy = info["drag_off"]
            card.place(x=mx - ox, y=my - oy)

        def end_drag(_ev):
            drop_card(info)

        handle.bind("<ButtonPress-1>", start_drag)
        handle.bind("<B1-Motion>", do_drag)
        handle.bind("<ButtonRelease-1>", end_drag)
        return card

    def zone_bbox(zone_frame):
        return (zone_frame.winfo_x(), zone_frame.winfo_y(),
                zone_frame.winfo_x() + zone_frame.winfo_width(),
                zone_frame.winfo_y() + zone_frame.winfo_height())

    def point_in(px, py, bbox):
        x0, y0, x1, y1 = bbox
        return x0 <= px <= x1 and y0 <= py <= y1

    def relayout_grid(zone_frame, members):
        # however many cards fit across the frame's CURRENT width - this is what
        # lets the same layout work at 720p (fewer per row, more rows) and on a
        # bigger screen (more per row) without hardcoding a column count.
        per_row = max(1, zone_frame.winfo_width() // (CARD_W + CARD_GAP))
        for n, c in enumerate(members):
            col, row = n % per_row, n // per_row
            x = zone_frame.winfo_x() + 8 + col * (CARD_W + CARD_GAP)
            y = zone_frame.winfo_y() + 22 + row * (CARD_H + CARD_GAP)
            c["frame"].place(x=x, y=y, width=CARD_W, height=CARD_H)

    def relayout_pool_scrollable():
        members = [c for c in cards if c["zone"] == "pool"]
        per_row = max(1, pool.winfo_width() // (CARD_W + CARD_GAP))
        visible_rows = max(1, (pool.winfo_height() - 22) // (CARD_H + CARD_GAP))
        total_rows = max(1, -(-len(members) // per_row))  # ceil division

        pool_scroll["row"] = max(0, min(pool_scroll["row"], max(0, total_rows - visible_rows)))
        top_row = pool_scroll["row"]

        needs_scroll = total_rows > visible_rows
        pool_up_btn.place(relx=1.0, x=-46, y=2) if needs_scroll else pool_up_btn.place_forget()
        pool_down_btn.place(relx=1.0, x=-24, y=2) if needs_scroll else pool_down_btn.place_forget()
        pool_up_btn.configure(state="normal" if top_row > 0 else "disabled")
        pool_down_btn.configure(state="normal" if top_row < total_rows - visible_rows else "disabled")

        for n, c in enumerate(members):
            col, row = n % per_row, n // per_row
            if row < top_row or row >= top_row + visible_rows:
                c["frame"].place_forget()
                continue
            x = pool.winfo_x() + 8 + col * (CARD_W + CARD_GAP)
            y = pool.winfo_y() + 22 + (row - top_row) * (CARD_H + CARD_GAP)
            c["frame"].place(x=x, y=y, width=CARD_W, height=CARD_H)

    def relayout_all():
        relayout_pool_scrollable()
        relayout_grid(zone_p1, [c for c in cards if c["zone"] == "P1"])
        relayout_grid(zone_p2, [c for c in cards if c["zone"] == "P2"])

    def drop_card(info):
        cx = info["frame"].winfo_x() + CARD_W // 2
        cy = info["frame"].winfo_y() + CARD_H // 2
        if point_in(cx, cy, zone_bbox(zone_p1)):
            info["zone"] = "P1"
        elif point_in(cx, cy, zone_bbox(zone_p2)):
            info["zone"] = "P2"
        else:
            info["zone"] = "pool"
        relayout_all()

    for i, j in enumerate(js):
        make_card(i, j)
    root.update_idletasks()
    relayout_all()

    # <Configure> fires on every MOVE too, not just resize - doing the full
    # relayout (dozens of widgets + update_idletasks()) on every single pixel
    # while the user drags the window title bar is what made the window feel
    # like it was fighting the drag (and, on a slower machine, reportedly
    # crashed outright). Fix: only relayout when the SIZE actually changed,
    # and debounce it (wait for movement/resizing to settle) instead of
    # doing it synchronously inside the event, which can run nested inside
    # Windows' own modal drag/resize loop.
    resize_state = {"last_size": (win_w, win_h), "job": None}

    def _do_relayout():
        resize_state["job"] = None
        # the pool/P1/P2 frames use relative placement, so their own new
        # geometry isn't final yet at this exact instant - flush it first,
        # otherwise cards get positioned against stale frame sizes (this is
        # what made a card overlap the P1 label when maximizing, before).
        root.update_idletasks()
        layout_zone_frames()
        relayout_all()

    def on_resize(ev):
        if ev.widget is not root:
            return
        new_size = (root.winfo_width(), root.winfo_height())
        if new_size == resize_state["last_size"]:
            return  # just moved, not resized - nothing to recompute
        resize_state["last_size"] = new_size
        if resize_state["job"] is not None:
            root.after_cancel(resize_state["job"])
        resize_state["job"] = root.after(120, _do_relayout)

    root.bind("<Configure>", on_resize)

    # --- live identify: flash a card's header when its physical control moves ---
    # paused while a profile editor is open, so both stop fighting over the same
    # pygame event queue (that dialog runs its own polling loop instead).
    main_poll_paused = {"v": False}

    # --- virtual pad state - the pads themselves are still created lazily,
    # only once Start is pressed; vg_module (the module) was already ensured
    # up front, right after the tkinter import above.

    virtual_pads = {"P1": None, "P2": None}
    live = {"on": False}

    def unflash(info):
        info["frame"].configure(highlightbackground=BORDER)

    def flash(info):
        # a colored ring around the card, not a bg change - changing bg made
        # the 3D raised border recompute its shading, which read as a little
        # jump/shift on screen
        info["frame"].configure(highlightbackground="#3fae5c")
        root.after(250, lambda: unflash(info))

    # Split in two so the game-input path never waits on Tkinter/Canvas drawing:
    #   fast_tick  - every poll_ms (4ms, matching the CLI's own loop): drain
    #                events, read every controller, apply the live merge. No
    #                widget/canvas work happens here.
    #   diagram_tick - every ~30ms: paints the cards using whatever fast_tick
    #                last computed. Purely cosmetic, never touches the pads.
    last_states = {}

    def fast_tick():
        if not main_poll_paused["v"] and not _left_mouse_down():
            try:
                for ev in pygame.event.get():
                    if ev.type in (pygame.JOYBUTTONDOWN, pygame.JOYHATMOTION):
                        inst = getattr(ev, "instance_id", getattr(ev, "joy", None))
                        for c in cards:
                            if c["j"].get_instance_id() == inst:
                                flash(c)
                                if not live["on"]:
                                    status.configure(text=f" ese fue el gamepad {c['index']} MAMAAAAAA")

                for c in cards:
                    last_states[c["index"]] = _read_state(c["j"], resolve_profile(c["profile_var"].get()))

                if live["on"]:
                    for side in ("P1", "P2"):
                        pad = virtual_pads[side]
                        if pad is None:
                            continue
                        members = [c for c in cards if c["zone"] == side]
                        if not members:
                            pad.reset()
                            pad.update()
                            continue
                        merged = _merge([last_states[c["index"]] for c in members])
                        _apply(pad, merged, vg_module["vg"])
            except Exception as e:
                # most likely a gamepad got unplugged mid-tick - stop cleanly and
                # say so, instead of silently dying and never ticking again
                if live["on"]:
                    toggle_live(reason=f"Stopped - a gamepad stopped responding ({e}). "
                                        "Hit Refresh, then Go live again.")
                else:
                    status.configure(text=f"Gamepad read error ({e}). Hit Refresh.")
        root.after(CONFIG["poll_ms"], fast_tick)

    def _neutral_state():
        return {"LX": 0.0, "LY": 0.0, "RX": 0.0, "RY": 0.0, "LT": 0.0, "RT": 0.0,
                "buttons": {n: False for n in BUTTON_NAMES}, "dpad": (0, 0)}

    def diagram_tick():
        if not main_poll_paused["v"]:
            try:
                for c in cards:
                    st = last_states.get(c["index"])
                    if st is not None:
                        _update_pad_diagram(c["diagram_canvas"], c["diagram_ids"], c["diagram_meta"], st)

                for side, (cc, cids, cmeta) in combined_panels.items():
                    members = [c for c in cards if c["zone"] == side]
                    if members:
                        merged = _merge([last_states[c["index"]] for c in members
                                          if c["index"] in last_states]) or _neutral_state()
                    else:
                        merged = _neutral_state()
                    _update_pad_diagram(cc, cids, cmeta, merged)
            except Exception:
                pass
        root.after(30, diagram_tick)

    root.after(CONFIG["poll_ms"], fast_tick)
    root.after(30, diagram_tick)

    # --- profile editor: per-gamepad window with a live tester + button mapping ---
    def refresh_profile_choices():
        names = ["standard"] + sorted(profiles.keys())
        for c in cards:
            c["combo"]["values"] = names

    def open_profile_editor(target):
        j = target["j"]
        idx = target["index"]

        win = tk.Toplevel(root)
        win.title(f"Configure controls - gamepad [{idx}]")
        win.geometry("580x640")
        win.transient(root)
        win.grab_set()
        win.lift()
        win.focus_force()

        main_poll_paused["v"] = True

        def on_close():
            main_poll_paused["v"] = False
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", on_close)

        # edit the card's current custom profile if it has one, else start blank
        current_pf = target["profile_var"].get()
        if current_pf != "standard" and current_pf in profiles:
            working = dict(profiles[current_pf])
            start_name = current_pf
        else:
            working = {}
            start_name = ""

        tk.Label(win, text=f"{j.get_name()}  (instance {j.get_instance_id()})",
                 font=("Segoe UI", 9, "italic")).pack(anchor="w", padx=10, pady=(10, 0))

        # --- live tester ---
        tester = tk.LabelFrame(win, text="Live test - press anything on this controller")
        tester.pack(fill="x", padx=10, pady=10)

        n_bt = j.get_numbuttons()
        n_ax = j.get_numaxes()

        btn_row = tk.Frame(tester)
        btn_row.pack(fill="x", padx=6, pady=4)
        tk.Label(btn_row, text="Buttons:", width=8, anchor="w").pack(side="left")
        btn_labels = []
        for b in range(n_bt):
            lbl = tk.Label(btn_row, text=str(b), width=3, relief="ridge", bg=CARD_BG)
            lbl.pack(side="left", padx=1)
            btn_labels.append(lbl)

        axis_row = tk.Frame(tester)
        axis_row.pack(fill="x", padx=6, pady=4)
        tk.Label(axis_row, text="Axes:", width=8, anchor="w").pack(side="left")
        axis_vars = [tk.StringVar(value="0.00") for _ in range(n_ax)]
        for a in range(n_ax):
            tk.Label(axis_row, textvariable=axis_vars[a], width=6, relief="sunken",
                     bg="#f4f4f4").pack(side="left", padx=2)

        dpad_row = tk.Frame(tester)
        dpad_row.pack(fill="x", padx=6, pady=4)
        tk.Label(dpad_row, text="D-pad:", width=8, anchor="w").pack(side="left")
        dpad_var = tk.StringVar(value="(0, 0)")
        tk.Label(dpad_row, textvariable=dpad_var, width=8, relief="sunken",
                 bg="#f4f4f4").pack(side="left", padx=2)

        # --- mapping table ---
        mapping_frame = tk.LabelFrame(win, text="Button mapping")
        mapping_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        row_widgets = {}   # key -> (value_var, set_button)
        waiting = {"key": None}

        def format_spec(spec):
            return "(not set)" if spec is None else f"{spec['type']} {spec['index']}"

        def do_set(key):
            val_var, set_btn = row_widgets[key]
            if waiting["key"] == key:
                waiting["key"] = None
                set_btn.configure(text="Set")
                val_var.set(format_spec(working.get(key)))
                return
            if waiting["key"] is not None:
                pv, pb = row_widgets[waiting["key"]]
                pb.configure(text="Set")
                pv.set(format_spec(working.get(waiting["key"])))
            waiting["key"] = key
            set_btn.configure(text="Cancel")
            val_var.set("press now...")

        def do_clear(key):
            working.pop(key, None)
            row_widgets[key][0].set(format_spec(None))

        def make_row(parent, key, required):
            row = tk.Frame(parent)
            row.pack(fill="x", padx=6, pady=2)
            text = f"{FRIENDLY_NAME[key]} [{key}]" + ("" if required else "  (optional)")
            tk.Label(row, text=text, width=34, anchor="w").pack(side="left")
            val_var = tk.StringVar(value=format_spec(working.get(key)))
            tk.Label(row, textvariable=val_var, width=12, relief="sunken",
                     bg="#f4f4f4", anchor="w").pack(side="left", padx=4)
            set_btn = tk.Button(row, text="Set", width=6, command=lambda: do_set(key))
            set_btn.pack(side="left", padx=2)
            tk.Button(row, text="Clear", width=6, command=lambda: do_clear(key)).pack(
                side="left", padx=2)
            row_widgets[key] = (val_var, set_btn)

        for key in REQUIRED_BUTTONS:
            make_row(mapping_frame, key, True)
        tk.Frame(mapping_frame, height=1, bg="#cccccc").pack(fill="x", pady=4)
        for key in OPTIONAL_BUTTONS:
            make_row(mapping_frame, key, False)

        # --- save area ---
        save_row = tk.Frame(win)
        save_row.pack(fill="x", padx=10, pady=(0, 4))
        tk.Label(save_row, text="Profile name:").pack(side="left")
        name_var = tk.StringVar(value=start_name)
        tk.Entry(save_row, textvariable=name_var).pack(side="left", fill="x", expand=True, padx=6)

        editor_status = tk.StringVar(value="")
        tk.Label(win, textvariable=editor_status, fg="#888888", anchor="w").pack(
            fill="x", padx=10)

        def do_save():
            name = name_var.get().strip()
            if not name:
                editor_status.set("Type a profile name first.")
                return
            missing = [k for k in REQUIRED_BUTTONS if k not in working]
            profiles[name] = dict(working)
            _save_profiles(profiles)
            refresh_profile_choices()
            target["profile_var"].set(name)
            if missing:
                editor_status.set(f"Saved '{name}' - heads up, still missing: {missing}")
            else:
                editor_status.set(f"Saved '{name}'.")

        def do_delete():
            name = name_var.get().strip()
            if not name or name not in profiles:
                editor_status.set(f"'{name}' isn't a saved profile - nothing to delete.")
                return
            if not messagebox.askyesno("Delete profile", f"Delete profile '{name}'? "
                                        "This can't be undone.", parent=win):
                return
            del profiles[name]
            _save_profiles(profiles)
            refresh_profile_choices()
            # any card that was using this profile falls back to standard
            for c in cards:
                if c["profile_var"].get() == name:
                    c["profile_var"].set("standard")
            on_close()

        btns_row = tk.Frame(win)
        btns_row.pack(fill="x", padx=10, pady=(0, 10))
        tk.Button(btns_row, text="Save profile", command=do_save).pack(side="left")
        tk.Button(btns_row, text="Delete profile", fg="#a00000", command=do_delete).pack(
            side="left", padx=6)
        tk.Button(btns_row, text="Close", command=on_close).pack(side="right")

        # --- live polling for this dialog only, while it's open ---
        def editor_poll():
            if not win.winfo_exists():
                return
            if _left_mouse_down():
                win.after(30, editor_poll)
                return
            for ev in pygame.event.get():
                eid = getattr(ev, "instance_id", getattr(ev, "joy", None))
                if eid != j.get_instance_id() or waiting["key"] is None:
                    continue
                key = waiting["key"]
                if ev.type == pygame.JOYBUTTONDOWN:
                    working[key] = {"type": "button", "index": ev.button}
                elif ev.type == pygame.JOYAXISMOTION and abs(ev.value) > 0.6:
                    working[key] = {"type": "axis", "index": ev.axis}
                else:
                    continue
                row_widgets[key][0].set(format_spec(working[key]))
                row_widgets[key][1].configure(text="Set")
                waiting["key"] = None

            pygame.event.pump()
            for b, lbl in enumerate(btn_labels):
                lbl.configure(bg="#3fae5c" if j.get_button(b) else CARD_BG)
            for a in range(n_ax):
                axis_vars[a].set(f"{j.get_axis(a):.2f}")
            if j.get_numhats() > 0:
                dpad_var.set(str(j.get_hat(0)))

            win.after(30, editor_poll)

        editor_poll()

    # --- go live: create the virtual pad(s) lazily and start/stop sending input,
    # without ever closing this window. Dragging cards between sides while live
    # remaps on the fly - the poll loop above just reads whoever is in each zone
    # on every tick, there's no separate "commit" step.
    def ensure_pad(side):
        if virtual_pads[side] is not None:
            return virtual_pads[side]
        if vg_module["vg"] is None:
            vg_module["vg"] = _ensure_package("vgamepad")
        try:
            virtual_pads[side] = vg_module["vg"].VX360Gamepad()
        except Exception as e:
            messagebox.showerror(
                "Couldn't create virtual gamepad",
                f"{e}\n\nThis usually means the ViGEmBus driver isn't installed yet, or a "
                "reboot is pending after installing it.", parent=root)
            return None
        return virtual_pads[side]

    def release_pad(side):
        pad = virtual_pads[side]
        if pad is not None:
            try:
                pad.reset()
                pad.update()
            except Exception:
                pass
            # drop our reference and clear the slot - vgamepad unplugs the
            # virtual device from its own __del__ once nothing references it
            # anymore, so joy.cpl actually goes back to showing nothing on
            # Stop instead of leaving an idle-but-still-connected pad behind
            # (which was still eating an XInput slot - the exact thing we've
            # been trying to avoid this whole project).
            virtual_pads[side] = None

    def save_session():
        session = {"virtual_pads": []}
        for side_name in ("P1", "P2"):
            members = [c for c in cards if c["zone"] == side_name]
            if not members:
                continue
            session["virtual_pads"].append({
                "name": side_name, "mode": "merge", "switch_button": "BACK",
                "sources": [{"index": c["index"],
                             "profile": None if c["profile_var"].get() == "standard"
                             else c["profile_var"].get(),
                             "label": c["name_var"].get().strip() or None}
                            for c in members],
            })
        with open(SESSION_PATH, "w", encoding="utf-8") as f:
            json.dump(session, f, indent=2, ensure_ascii=False)

    def toggle_live(reason=None):
        if live["on"]:
            live["on"] = False
            release_pad("P1")
            release_pad("P2")
            live_btn.configure(text="Start", bg=ACCENT_OK)
            refresh_btn.configure(state="normal")
            status.configure(text=reason or "Stopped. Drag cards freely, then go live again when ready.")
            return

        p1 = [c for c in cards if c["zone"] == "P1"]
        p2 = [c for c in cards if c["zone"] == "P2"]
        if not p1 and not p2:
            status.configure(text="Drag at least one gamepad into P1 or P2 first.")
            return
        if (p1 and ensure_pad("P1") is None) or (p2 and ensure_pad("P2") is None):
            return

        save_session()
        live["on"] = True
        live_btn.configure(text="Stop", bg=ACCENT_STOP)
        refresh_btn.configure(state="disabled")
        status.configure(text="Live - sending input to the virtual pad(s). Drag cards to remap on the fly.")

    live_btn.configure(command=toggle_live)

    def refresh_gamepads():
        if live["on"]:
            return  # button is disabled while live anyway, this is just a guard
        new_js = _gamepads()
        kept_instances = set()
        for i, j in enumerate(new_js):
            inst = j.get_instance_id()
            kept_instances.add(inst)
            existing = next((c for c in cards if c["j"].get_instance_id() == inst), None)
            if existing is not None:
                existing["index"] = i
                existing["j"] = j
                existing["index_label"].configure(text=f"gamepad [{i}]")
            else:
                make_card(i, j)
        for c in list(cards):
            if c["j"].get_instance_id() not in kept_instances:
                c["frame"].destroy()
                cards.remove(c)
        root.update_idletasks()
        relayout_all()
        status.configure(text=f"Refreshed - {len(cards)} gamepad(s) detected.")

    refresh_btn.configure(command=refresh_gamepads)

    def open_latency_test():
        if not cards:
            status.configure(text="No gamepad to test - connect one first.")
            return

        win = tk.Toplevel(root)
        win.title("Latency test")
        win.geometry("400x205")
        win.resizable(False, False)
        win.transient(root)
        win.grab_set()
        win.lift()
        win.focus_force()

        main_poll_paused["v"] = True

        tk.Label(win, text="Gamepad:").place(x=10, y=12)
        names = [f"[{c['index']}] {c['name_var'].get()}" for c in cards]
        sel_var = tk.StringVar(value=names[0])
        combo = ttk.Combobox(win, values=names, textvariable=sel_var, state="readonly",
                              font=("Segoe UI", 9))
        combo.current(0)
        combo.place(x=80, y=10, width=280)

        # Just the conversion step: how long it takes this script to write a
        # press to the virtual pad once it's seen it. No poll-wait mixed in.
        headline_var = tk.StringVar(value="Extra lag: -- ms")
        tk.Label(win, textvariable=headline_var, font=("Segoe UI", 16, "bold")).place(x=10, y=40)

        tk.Label(win, text="(time to write your press to the virtual pad, once this",
                 font=("Segoe UI", 8), fg="#888888").place(x=10, y=70)
        tk.Label(win, text="script has seen it - not USB, Parsec, or the game)",
                 font=("Segoe UI", 8), fg="#888888").place(x=10, y=84)
        tk.Label(win, text="Press buttons on the selected controller to measure.",
                 font=("Segoe UI", 8), fg="#888888").place(x=10, y=102)

        details_var = tk.StringVar(value="No presses yet.")
        tk.Label(win, textvariable=details_var, font=("Consolas", 8), fg="#888888",
                 justify="left").place(x=10, y=126)

        tk.Label(win, text="(for reference: one frame at 60fps = 16.6 ms)",
                 font=("Segoe UI", 8), fg="#888888").place(x=10, y=164)

        test_pad = None
        try:
            vg = vg_module["vg"]
            test_pad = vg.VX360Gamepad()
            A = vg.XUSB_BUTTON.XUSB_GAMEPAD_A
        except Exception as e:
            details_var.set(f"Couldn't create a test pad: {e}")

        samples = []
        closed = {"v": False}

        def on_close():
            nonlocal test_pad
            closed["v"] = True
            main_poll_paused["v"] = False
            if test_pad is not None:
                try:
                    test_pad.reset()
                    test_pad.update()
                except Exception:
                    pass
                test_pad = None  # same as release_pad: let it get unplugged
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", on_close)

        def tick():
            if closed["v"]:
                return
            idx = combo.current()
            j = cards[idx]["j"] if 0 <= idx < len(cards) else None

            if j is not None and not _left_mouse_down():
                for ev in pygame.event.get():
                    eid = getattr(ev, "instance_id", getattr(ev, "joy", None))
                    if eid != j.get_instance_id() or ev.type != pygame.JOYBUTTONDOWN:
                        continue
                    if test_pad is not None:
                        t0 = time.perf_counter()
                        test_pad.press_button(button=A)
                        test_pad.update()
                        test_pad.reset()
                        test_pad.update()
                        convert_ms = (time.perf_counter() - t0) * 1000.0
                        samples.append(convert_ms)
                        # recent-window average, not all-time, so an early one-off
                        # slow sample (window warmup) doesn't drag it down forever
                        recent = samples[-20:]
                        avg = sum(recent) / len(recent)
                        headline_var.set(f"Extra lag: ~{avg:.2f} ms")
                        details_var.set(f"last press: {convert_ms:.2f}ms  |  "
                                         f"{len(samples)} presses total, max {max(recent):.2f}ms recent")
            win.after(CONFIG["poll_ms"], tick)

        tick()

    latency_btn.configure(command=open_latency_test)

    def on_root_close():
        if live["on"]:
            release_pad("P1")
            release_pad("P2")
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_root_close)
    root.mainloop()


# ============================ RUNTIME ============================

def _clamp(v):
    return max(-1.0, min(1.0, v))


def _trigger_255(v):
    # pygame reports triggers in -1..1 (rest -1) or 0..1 depending on the backend. Normalize to 0..255.
    if v < 0:
        v = (v + 1) / 2.0
    return max(0, min(255, int(v * 255)))


def _read_state(j, profile):
    n_ax = j.get_numaxes()
    n_bt = j.get_numbuttons()

    def ax(i):
        return j.get_axis(i) if (i is not None and i < n_ax) else 0.0

    def bt(i):
        return bool(j.get_button(i)) if (i is not None and i < n_bt) else False

    def read_logical(name):
        spec = profile.get(name)
        if spec is None:
            return 0.0 if name in ("LT", "RT") else False
        if spec["type"] == "button":
            pressed = bt(spec["index"])
            if name in ("LT", "RT"):
                return 1.0 if pressed else -1.0  # same convention as an axis at rest/fully pressed
            return pressed
        else:  # axis
            val = ax(spec["index"])
            if name in ("LT", "RT"):
                return val
            # Same rest(-1)/pressed(+1) convention as a real trigger - some fightsticks
            # report ordinary buttons this way instead of as a digital button event.
            # NOT abs(val): at rest this axis already sits near -1 (magnitude ~1), so
            # abs()>threshold would read "pressed" all the time. Only the positive end
            # (near +1) means actually pressed.
            return val > 0.5

    st = {
        "LX": ax(AXES["LX"]), "LY": ax(AXES["LY"]),
        "RX": ax(AXES["RX"]), "RY": ax(AXES["RY"]),
        "LT": read_logical("LT"), "RT": read_logical("RT"),
        "buttons": {name: read_logical(name) for name in BUTTON_NAMES},
    }
    st["dpad"] = j.get_hat(0) if j.get_numhats() > 0 else (0, 0)
    return st


def _merge(states):
    if not states:
        return None
    out = {"buttons": {}, "dpad": (0, 0)}
    for axis in ("LX", "LY", "RX", "RY"):
        val = 0.0
        for s in states:
            if abs(s[axis]) > abs(val):
                val = s[axis]
        out[axis] = val
    for t in ("LT", "RT"):
        out[t] = max(s[t] for s in states)
    for name in BUTTON_NAMES:
        out["buttons"][name] = any(s["buttons"][name] for s in states)
    dx = dy = 0
    for s in states:
        ex, ey = s["dpad"]
        dx = ex if ex != 0 else dx
        dy = ey if ey != 0 else dy
    out["dpad"] = (dx, dy)
    return out


def _apply(pad, st, vg):
    B = vg.XUSB_BUTTON
    pad.reset()
    pad.left_joystick_float(x_value_float=_clamp(st["LX"]), y_value_float=_clamp(-st["LY"]))
    pad.right_joystick_float(x_value_float=_clamp(st["RX"]), y_value_float=_clamp(-st["RY"]))
    pad.left_trigger(value=_trigger_255(st["LT"]))
    pad.right_trigger(value=_trigger_255(st["RT"]))
    button_map = {
        "A": B.XUSB_GAMEPAD_A, "B": B.XUSB_GAMEPAD_B,
        "X": B.XUSB_GAMEPAD_X, "Y": B.XUSB_GAMEPAD_Y,
        "LB": B.XUSB_GAMEPAD_LEFT_SHOULDER, "RB": B.XUSB_GAMEPAD_RIGHT_SHOULDER,
        "BACK": B.XUSB_GAMEPAD_BACK, "START": B.XUSB_GAMEPAD_START,
        "LS": B.XUSB_GAMEPAD_LEFT_THUMB, "RS": B.XUSB_GAMEPAD_RIGHT_THUMB,
    }
    for name, on in st["buttons"].items():
        if on:
            pad.press_button(button=button_map[name])
    dx, dy = st["dpad"]
    if dy > 0: pad.press_button(button=B.XUSB_GAMEPAD_DPAD_UP)
    if dy < 0: pad.press_button(button=B.XUSB_GAMEPAD_DPAD_DOWN)
    if dx < 0: pad.press_button(button=B.XUSB_GAMEPAD_DPAD_LEFT)
    if dx > 0: pad.press_button(button=B.XUSB_GAMEPAD_DPAD_RIGHT)
    pad.update()


def _resolve_source(entry, profiles, standard_profile):
    """Normalizes a 'sources' entry (plain int, or dict {index, profile}) to (index, profile_dict)."""
    if isinstance(entry, dict):
        idx = entry["index"]
        profile_name = entry.get("profile")
    else:
        idx = entry
        profile_name = None
    profile = profiles.get(profile_name, standard_profile) if profile_name else standard_profile
    return idx, profile


def run():
    vg = _ensure_package("vgamepad")

    _init_pygame()
    js = _gamepads()
    print(f"Gamepads detected: {len(js)}")

    profiles = _load_profiles()
    standard_profile = _standard_profile()

    if os.path.exists(SESSION_PATH):
        with open(SESSION_PATH, "r", encoding="utf-8") as f:
            session = json.load(f)
        virtual_cfgs = session["virtual_pads"]
        print(f"Using saved session: {SESSION_PATH}  (run --setup again to change it)")
    else:
        virtual_cfgs = CONFIG["virtual_pads"]

    virtual_pads = []
    for vcfg in virtual_cfgs:
        try:
            pad = vg.VX360Gamepad()
        except Exception as e:
            print(f"\nCouldn't create the virtual gamepad: {e}")
            print("This usually means the ViGEmBus driver isn't installed yet, or a reboot is")
            print("pending after installing it. It normally installs the first time 'vgamepad'")
            print("runs (watch for a Windows driver-install prompt). If it keeps failing, install")
            print("it by hand from: https://github.com/ViGEm/ViGEmBus/releases")
            sys.exit(1)
        sources = [_resolve_source(e, profiles, standard_profile) for e in vcfg["sources"]]
        virtual_pads.append({"cfg": vcfg, "pad": pad, "active": 0, "sources": sources})
        idxs = [i for i, _ in sources]
        print(f"  Virtual '{vcfg['name']}' created [{vcfg.get('mode', 'merge')}] <- sources {idxs}")

    print("\nRunning. Ctrl+C to stop.")
    prev_switch = {}
    poll = CONFIG["poll_ms"] / 1000.0
    try:
        while True:
            for ev in pygame.event.get():
                if ev.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
                    js = _gamepads()
                    print(f"\n[hot-plug] now there are {len(js)} gamepad(s)")
            pygame.event.pump()

            for v in virtual_pads:
                cfg = v["cfg"]
                sources = [(js[i], profile) for i, profile in v["sources"] if i < len(js)]
                if not sources:
                    continue
                states = [_read_state(j, profile) for j, profile in sources]

                if cfg.get("mode", "merge") == "switch":
                    sb = cfg.get("switch_button", "BACK")
                    act = v["active"] % len(states)
                    pressed = states[act]["buttons"].get(sb, False)
                    key = cfg["name"]
                    if pressed and not prev_switch.get(key, False):
                        v["active"] = (v["active"] + 1) % len(states)
                        physical_idx = v["sources"][v["active"] % len(v["sources"])][0]
                        print(f"\r[{cfg['name']}] control -> source {physical_idx}        ",
                              end="", flush=True)
                    prev_switch[key] = pressed
                    st = states[v["active"] % len(states)]
                else:
                    st = _merge(states)

                _apply(v["pad"], st, vg)

            time.sleep(poll)
    except KeyboardInterrupt:
        print("\nStopped. Bye.")


def main():
    args = sys.argv[1:]
    if not args:
        run()
    elif args[0] == "--list":
        cmd_list()
    elif args[0] == "--diagnose" and len(args) > 1:
        seconds = int(args[2]) if len(args) > 2 else 30
        cmd_diagnose(int(args[1]), seconds)
    elif args[0] == "--identify":
        cmd_identify()
    elif args[0] == "--profile-create" and len(args) > 1:
        name = args[2] if len(args) > 2 else None
        cmd_profile_create(int(args[1]), name)
    elif args[0] == "--profile-list":
        cmd_profile_list()
    elif args[0] == "--setup":
        cmd_setup()
    elif args[0] == "--gui":
        cmd_gui()
    else:
        print(__doc__)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(1)

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


def _capture_for(j, key, max_tries=3):
    """Waits for the physical input for logical button `key`, rejecting an axis capture
    for anything that isn't a trigger (LT/RT). A real button on an Xbox-layout controller
    should never come through as an axis - if it does, we almost certainly caught a
    trigger's motion event instead of the intended button (this is exactly what once made
    RB read as permanently pressed: it got mapped to a trigger axis, which never rests at
    0, so "is it pressed" was always true). Better to make the person redo it than save it."""
    for _ in range(max_tries):
        r = _wait_for_input(j)
        if r is None:
            return None
        kind, index = r
        if kind == "axis" and key not in ("LT", "RT"):
            print(f"    -> that was a trigger/axis moving (axis {index}), not a button press.")
            print(f"       {key} needs a real button. Press the actual button for {key} now...")
            continue
        return (kind, index)
    print(f"    -> kept getting a trigger instead of a button, giving up on {key} for now.")
    return None


def _create_profile_interactive(j, name):
    print(f"\nCreating profile '{name}' for {j.get_name()}")
    print("You'll press, one at a time, the button that does each function on YOUR controller.")
    print("Leave everything else untouched while you press. You have 15s per button.\n")

    profile = {}
    for key in REQUIRED_BUTTONS:
        print(f"  Press: {FRIENDLY_NAME[key]}  [{key}]")
        r = _capture_for(j, key)
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
        r = _capture_for(j, key)
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
            return abs(val) > 0.5

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
    else:
        print(__doc__)


if __name__ == "__main__":
    main()

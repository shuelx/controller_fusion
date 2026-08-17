#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
latency_probe.py
Standalone tool to measure how long OUR software pipeline takes to turn a
physical button press into a write on the virtual pad (pygame read -> apply
-> vgamepad write). Does NOT touch controller_fusion.py.

What this does NOT measure: USB/controller scan rate, Parsec network+encode
latency for remote friends, or the game engine's own input polling. Those are
almost certainly bigger than anything measured here - this is only useful to
confirm our own code isn't the bottleneck.

Usage:
    python latency_probe.py <physical_index> [seconds]

Example:
    python latency_probe.py 0 20
"""

import sys
import time

from controller_fusion import _ensure_package, _init_pygame, _gamepads

pygame = _ensure_package("pygame")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    idx = int(sys.argv[1])
    seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 20

    vg = _ensure_package("vgamepad")
    _init_pygame()
    js = _gamepads()
    if idx < 0 or idx >= len(js):
        print(f"Index {idx} out of range. There are {len(js)} gamepad(s) detected.")
        sys.exit(1)
    j = js[idx]
    pad = vg.VX360Gamepad()
    A = vg.XUSB_BUTTON.XUSB_GAMEPAD_A

    print(f"Probing pipeline latency: [{idx}] {j.get_name()} -> virtual pad")
    print(f"Press any button and you'll see the result immediately. Ctrl+C to stop.\n")
    print(f"{'wait':>8}  {'convert':>8}  {'TOTAL':>8}")

    wait_samples = []    # how long since we last checked for input (the "did we notice yet" part)
    convert_samples = [] # how long the actual read+write takes (the "converting" part)

    t_end = time.time() + seconds
    last_check = time.perf_counter()
    try:
        while time.time() < t_end:
            check_time = time.perf_counter()
            wait_ms = (check_time - last_check) * 1000.0
            last_check = check_time

            for ev in pygame.event.get():
                if ev.type == pygame.JOYBUTTONDOWN:
                    t0 = time.perf_counter()
                    # exercise the exact same write path controller_fusion.py uses,
                    # regardless of which physical button this was
                    pad.press_button(button=A)
                    pad.update()
                    pad.reset()
                    pad.update()
                    convert_ms = (time.perf_counter() - t0) * 1000.0
                    total_ms = wait_ms + convert_ms

                    wait_samples.append(wait_ms)
                    convert_samples.append(convert_ms)
                    print(f"{wait_ms:7.2f}ms  {convert_ms:7.2f}ms  {total_ms:7.2f}ms   button {ev.button}")
            time.sleep(0.001)
    except KeyboardInterrupt:
        pass

    if not wait_samples:
        print("\nNo button was pressed, nothing to report.")
        return

    n = len(wait_samples)
    avg_total = (sum(wait_samples) + sum(convert_samples)) / n
    print(f"\n{n} presses. Average total: ~{avg_total:.2f} ms "
          f"(wait ~{sum(wait_samples)/n:.2f}ms + convert ~{sum(convert_samples)/n:.2f}ms)")
    print("(for reference, one frame at 60fps = 16.6 ms)")


if __name__ == "__main__":
    main()

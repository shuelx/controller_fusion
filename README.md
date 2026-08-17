# controller_fusion

Combines 4-6 Xbox controllers (connected via Parsec) into 1 or 2 virtual Xbox
controllers, so several friends can share a team in a fighting game (built
for Ultimate Marvel vs Capcom 3).

Windows only. Uses pygame (SDL) to read the physical controllers and
vgamepad (ViGEmBus) to create the virtual one(s). No vJoy involved.

## Quick start

```
python controller_fusion.py --setup
```

Installs missing dependencies on its own, walks you through identifying
gamepads and assigning them to a side, then starts playing right away.

## Other commands

```
python controller_fusion.py --list              # list detected gamepads
python controller_fusion.py --identify           # press a button, see which index it is
python controller_fusion.py --diagnose N         # log a gamepad's raw axis/button events
python controller_fusion.py --profile-create N   # build a custom button-mapping profile
python controller_fusion.py --profile-list       # list saved profiles
python latency_probe.py N                        # measure the physical->virtual lag, live
```

See `AI_CONTEXT.md` for design decisions, known issues, and pending work
(HidHide setup is next).

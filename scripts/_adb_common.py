"""ADB device discovery shared by all wuwa_* scripts.

Lazy-imports adbutils, picks the first MuMu-looking device, returns
both the adbutils Device object and useful metadata.  Centralised so
each tool isn't reinventing the wheel.
"""

from __future__ import annotations

import re
import sys
from typing import Optional, Tuple


# Recognise MuMu's standard ADB serials.  16384 = player 0, +2 per player.
_MUMU_SERIAL_RE = re.compile(r'^127\.0\.0\.1:163[89]\d$|^127\.0\.0\.1:1638[46]$')


def find_device(prefer_serial: Optional[str] = None):
    """Return an :class:`adbutils.AdbDevice` connected to MuMu.

    If ``prefer_serial`` is given, use it.  Otherwise pick the first
    device whose serial matches MuMu's local-port pattern.  Falls back
    to the first online device if no MuMu-pattern match.
    """
    import adbutils
    client = adbutils.AdbClient()
    devices = client.list()
    online = [d for d in devices if d.state == 'device']
    if not online:
        sys.stderr.write(
            'No online ADB devices.  '
            'Try `adb connect 127.0.0.1:16384` or open MuMu Player 12.\n'
        )
        sys.exit(2)

    if prefer_serial:
        for d in online:
            if d.serial == prefer_serial:
                return client.device(serial=prefer_serial)
        sys.stderr.write(f'Preferred serial {prefer_serial} not online.\n')
        sys.exit(2)

    # Prefer MuMu-pattern serials.
    for d in online:
        if _MUMU_SERIAL_RE.match(d.serial):
            return client.device(serial=d.serial)

    # Fall back to first online device (probably non-MuMu, but works).
    return client.device(serial=online[0].serial)


def screen_size(device) -> Tuple[int, int]:
    """Return (width, height) of the device's screen in landscape orientation.

    ``wm size`` reports portrait, so we sort the two numbers.  This is
    fine for WuWa which always renders landscape.
    """
    out = device.shell('wm size').strip()
    m = re.search(r'(\d+)x(\d+)', out)
    if not m:
        return (0, 0)
    a, b = int(m.group(1)), int(m.group(2))
    return (max(a, b), min(a, b))   # landscape: width >= height

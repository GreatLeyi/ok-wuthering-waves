"""Tap the Android screen at a relative (0..1, 0..1) coordinate.

Usage::

    python scripts/wuwa_tap.py 0.93 0.85
    python scripts/wuwa_tap.py 0.93 0.85 --capture-after tmp/after.png
    python scripts/wuwa_tap.py 0.93 0.85 --serial 127.0.0.1:16384

Prints absolute pixel coords and (optionally) saves a follow-up
screenshot so the caller can verify what changed.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys
import time

from _adb_common import find_device, screen_size


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('rel_x', type=float, help='0..1, 0=left, 1=right')
    parser.add_argument('rel_y', type=float, help='0..1, 0=top, 1=bottom')
    parser.add_argument('--capture-after', type=pathlib.Path, default=None,
                        help='Take a screenshot after the tap (PNG path)')
    parser.add_argument('--delay', type=float, default=0.5,
                        help='Seconds to wait after tap before screenshot')
    parser.add_argument('--serial', type=str, default=None)
    args = parser.parse_args()

    if not (0.0 <= args.rel_x <= 1.0 and 0.0 <= args.rel_y <= 1.0):
        sys.stderr.write(f'rel coords out of range: ({args.rel_x}, {args.rel_y})\n')
        return 2

    device = find_device(prefer_serial=args.serial)
    w, h = screen_size(device)
    px = round(args.rel_x * w)
    py = round(args.rel_y * h)

    device.shell(f'input tap {px} {py}')
    sys.stdout.write(
        f'tap rel=({args.rel_x:.4f}, {args.rel_y:.4f}) '
        f'abs=({px}, {py}) screen={w}x{h}\n'
    )

    if args.capture_after:
        time.sleep(args.delay)
        img = device.screenshot()
        args.capture_after.parent.mkdir(parents=True, exist_ok=True)
        img.save(args.capture_after)
        sys.stdout.write(f'after_png={args.capture_after}\n')

    return 0


if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.exit(main())

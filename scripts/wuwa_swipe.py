"""Swipe the Android screen between two relative coordinates.

Usage::

    python scripts/wuwa_swipe.py 0.18 0.78 0.18 0.68
    python scripts/wuwa_swipe.py 0.18 0.78 0.18 0.68 --duration 800
    python scripts/wuwa_swipe.py 0.18 0.78 0.18 0.68 --capture-after tmp/after.png

Used to calibrate the joystick: swipe from estimated centre toward a
direction and see whether the character moves.
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
    parser.add_argument('start_x', type=float)
    parser.add_argument('start_y', type=float)
    parser.add_argument('end_x', type=float)
    parser.add_argument('end_y', type=float)
    parser.add_argument('--duration', type=int, default=800,
                        help='Swipe duration in ms')
    parser.add_argument('--capture-after', type=pathlib.Path, default=None)
    parser.add_argument('--delay', type=float, default=0.5)
    parser.add_argument('--serial', type=str, default=None)
    args = parser.parse_args()

    for label, val in [('start_x', args.start_x), ('start_y', args.start_y),
                       ('end_x', args.end_x),     ('end_y', args.end_y)]:
        if not (0.0 <= val <= 1.0):
            sys.stderr.write(f'{label} out of range: {val}\n')
            return 2

    device = find_device(prefer_serial=args.serial)
    w, h = screen_size(device)
    sx = round(args.start_x * w)
    sy = round(args.start_y * h)
    ex = round(args.end_x * w)
    ey = round(args.end_y * h)

    device.shell(f'input swipe {sx} {sy} {ex} {ey} {args.duration}')
    sys.stdout.write(
        f'swipe rel=({args.start_x:.3f}, {args.start_y:.3f})->'
        f'({args.end_x:.3f}, {args.end_y:.3f}) '
        f'abs=({sx}, {sy})->({ex}, {ey}) '
        f'duration={args.duration}ms screen={w}x{h}\n'
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

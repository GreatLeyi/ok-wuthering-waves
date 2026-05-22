"""Capture the Android screen and save it as a PNG.

Used by AI / humans alike to inspect game state.  Companion of
``wuwa_tap.py`` / ``wuwa_swipe.py``.

Usage::

    python scripts/wuwa_capture.py                       # default: tmp/wuwa_screen.png
    python scripts/wuwa_capture.py --out tmp/foo.png
    python scripts/wuwa_capture.py --wait-stable 60      # poll until 3 frames look identical
    python scripts/wuwa_capture.py --launch              # launch WuWa first if not running
    python scripts/wuwa_capture.py --launch --wait-stable 90
    python scripts/wuwa_capture.py --info                # print extra device facts

Stdout: structured one-line summary suitable for piping / grepping.
PNG path is always the last token.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys
import time

from _adb_common import find_device, screen_size


# Best-known WuWa Android packages (the real one is com.kurogame.mingchao
# on the CN client; western/global builds may differ).
WUWA_PACKAGE_CANDIDATES = [
    'com.kurogame.mingchao',
    'com.kurogame.wutheringwaves',
    'com.kurogame.wutheringwaves.cn',
    'com.kurogamestudio.wutheringwaves',
    'com.kurogame.wutheringwaves.global',
    'com.kurogame.mc',
]


def installed_wuwa_package(device) -> str | None:
    """Return the first installed WuWa package found, or None."""
    try:
        out = device.shell('pm list packages')
    except Exception:
        return None
    listed = {line.replace('package:', '').strip()
              for line in out.splitlines() if line.startswith('package:')}
    for cand in WUWA_PACKAGE_CANDIDATES:
        if cand in listed:
            return cand
    # Last-ditch: any package containing wuther/kurogame/mingchao.
    for pkg in listed:
        low = pkg.lower()
        if any(k in low for k in ('wuther', 'mingchao', 'kurogame')):
            return pkg
    return None


def current_focus(device) -> str:
    out = device.shell("dumpsys window | grep -E 'mCurrentFocus'") or ''
    return out.strip()


def is_wuwa_focused(device, package: str) -> bool:
    return package in current_focus(device)


def launch_wuwa(device, package: str) -> None:
    """Launch WuWa via monkey + LAUNCHER intent (most reliable)."""
    device.shell(
        f'monkey -p {package} -c android.intent.category.LAUNCHER 1'
    )


def screenshot_to(device, path: pathlib.Path):
    img = device.screenshot()
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return img


def wait_for_stable(device, out_path: pathlib.Path, timeout_s: int,
                    settle_frames: int = 3, poll_s: float = 2.0):
    """Screencap repeatedly, return when N consecutive frames match.

    Used to wait for boot animations / loading screens to finish.
    Falls through after `timeout_s` whether or not stable.
    """
    last_hash = None
    streak = 0
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        img = screenshot_to(device, out_path)
        # Quick perceptual fingerprint: downscale + average pixels per channel.
        small = img.resize((32, 18))
        sig = bytes(small.tobytes()[::4])  # subsample
        if sig == last_hash:
            streak += 1
            if streak >= settle_frames:
                return img, True
        else:
            streak = 0
            last_hash = sig
        time.sleep(poll_s)
    return img, False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--out', type=pathlib.Path,
                        default=pathlib.Path('tmp/wuwa_screen.png'),
                        help='PNG output path')
    parser.add_argument('--launch', action='store_true',
                        help="If WuWa isn't focused, launch it first")
    parser.add_argument('--wait-stable', type=int, default=0,
                        help='Poll until 3 successive frames match, '
                             'or this many seconds elapsed (whichever first)')
    parser.add_argument('--info', action='store_true',
                        help='Print extra device facts on stdout')
    parser.add_argument('--serial', type=str, default=None,
                        help='Explicit ADB serial; otherwise auto-detect')
    args = parser.parse_args()

    device = find_device(prefer_serial=args.serial)
    w, h = screen_size(device)
    package = installed_wuwa_package(device)

    if args.launch and package and not is_wuwa_focused(device, package):
        sys.stdout.write(f'launching {package} ...\n')
        launch_wuwa(device, package)
        # Give the launcher a beat before we start polling.
        time.sleep(3)

    if args.wait_stable > 0:
        img, settled = wait_for_stable(device, args.out, args.wait_stable)
        sys.stdout.write(f'stable={settled} ')
    else:
        img = screenshot_to(device, args.out)

    iw, ih = img.size
    focus = current_focus(device).replace('mCurrentFocus=', '').strip()

    sys.stdout.write(
        f'serial={device.serial} '
        f'screen={iw}x{ih} '
        f'wm_size={w}x{h} '
        f'pkg={package or "?"} '
        f'focus={focus or "?"} '
        f'png={args.out}\n'
    )

    if args.info:
        for label, args_ in [
            ('android.version',     ('getprop', 'ro.build.version.release')),
            ('android.sdk',         ('getprop', 'ro.build.version.sdk')),
            ('device.model',        ('getprop', 'ro.product.model')),
            ('device.manufacturer', ('getprop', 'ro.product.manufacturer')),
        ]:
            try:
                value = device.shell(' '.join(args_)).strip()
                sys.stdout.write(f'  {label}={value!r}\n')
            except Exception as e:
                sys.stdout.write(f'  {label}=ERROR({e})\n')

    return 0


if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.exit(main())

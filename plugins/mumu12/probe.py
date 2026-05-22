"""Standalone ADB / MuMu probe -- does NOT require ok-script GUI.

Run from the project root, with the venv Python::

    .venv\\Scripts\\python.exe -m plugins.mumu12.probe

What it checks, in order:

1. **MuMu processes** -- is MuMu Player 12 actually running?
   We list every ``MuMu*`` process so you can confirm the emulator is up
   before worrying about ADB.  In ADB mode we don't need the host
   window's hwnd anymore -- this is purely a "is the emulator alive"
   smoke test.

2. **ADB binary discovery** -- where is ``adb.exe``?
   ok-script imports its own copy via ``adbutils._utils._get_bin_dir``,
   but if that's missing the whole stack fails to start.  We surface
   the same path here.

3. **ADB devices** -- which serials does ``adb devices`` see?
   MuMu 12 exposes itself as ``127.0.0.1:16384`` (or 16386, 16388...
   for additional players).  If your serial isn't listed, run
   ``adb connect 127.0.0.1:16384`` and re-try.

4. **Per-device facts** -- for each device, dump ``wm size``,
   ``getprop ro.product.model``, and search for Wuthering Waves
   packages via ``pm list packages``.  Use the discovered package name
   to populate ``Mobile Config -> Game Package Names`` if our defaults
   don't match.

This is the bootstrap diagnostic for stage-2 setup.  It works without
a running GUI, so you can use it to debug "why won't main_mobile.py
boot" before any visual feedback is available.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import List, Optional, Tuple


# Process-name prefixes considered part of the MuMu 12 stack.  Lowercased.
MUMU_PROC_PREFIXES = (
    'mumuplayer',
    'mumunxdevice',
    'mumuvmmheadless',
    'mumuvmm',
    'mumu',           # catch-all for anything else MuMu names
)


# ---------------------------------------------------------------------
# Step 1: list MuMu processes
# ---------------------------------------------------------------------

def list_mumu_processes() -> List[Tuple[int, str]]:
    """Return ``[(pid, exe_name)]`` for every running MuMu process."""
    try:
        import psutil  # type: ignore
    except ImportError:
        print("ERROR: psutil missing.  Run build.bat to reinstall deps.")
        return []

    rows: List[Tuple[int, str]] = []
    for p in psutil.process_iter(['pid', 'name']):
        try:
            name = (p.info.get('name') or '').lower()
        except Exception:
            continue
        if any(name.startswith(prefix) for prefix in MUMU_PROC_PREFIXES):
            rows.append((p.info['pid'], p.info['name']))
    return rows


# ---------------------------------------------------------------------
# Step 2: find adb.exe (matches ok-script's logic)
# ---------------------------------------------------------------------

def find_adb_exe() -> Optional[str]:
    """Same resolution order ok-script uses: adbutils' bundled copy."""
    try:
        from adbutils._utils import _get_bin_dir, _is_valid_exe
    except Exception:
        # adbutils not installed yet (build.bat hasn't run).
        return None
    try:
        bin_dir = _get_bin_dir()
        exe = os.path.join(bin_dir, 'adb.exe' if os.name == 'nt' else 'adb')
        if os.path.isfile(exe) and _is_valid_exe(exe):
            return exe
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------
# Step 3 + 4: list devices and probe each
# ---------------------------------------------------------------------

def adb_run(adb_exe: str, *args: str, serial: Optional[str] = None,
            timeout: int = 8) -> str:
    """Run ``adb [-s SERIAL] <args>`` and return stdout (stderr on error)."""
    cmd = [adb_exe]
    if serial:
        cmd.extend(['-s', serial])
    cmd.extend(args)
    try:
        out = subprocess.run(
            cmd,
            capture_output=True, text=True,
            timeout=timeout, check=False,
        )
        if out.returncode != 0 and not out.stdout:
            return f'<error: {out.stderr.strip()}>'
        return out.stdout
    except Exception as e:
        return f'<exception: {e}>'


def list_adb_devices(adb_exe: str) -> List[str]:
    """Return a list of online device serials known to adb."""
    raw = adb_run(adb_exe, 'devices')
    serials: List[str] = []
    for line in raw.splitlines()[1:]:   # skip "List of devices attached"
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] == 'device':
            serials.append(parts[0])
    return serials


def probe_one_device(adb_exe: str, serial: str) -> None:
    """Print per-device facts: wm size, model, candidate WuWa packages."""
    print(f'  serial    = {serial}')

    wm = adb_run(adb_exe, 'shell', 'wm', 'size', serial=serial).strip()
    print(f'  wm size   = {wm!r}')

    model = adb_run(adb_exe, 'shell', 'getprop', 'ro.product.model',
                    serial=serial).strip()
    manufacturer = adb_run(adb_exe, 'shell', 'getprop',
                           'ro.product.manufacturer', serial=serial).strip()
    sdk = adb_run(adb_exe, 'shell', 'getprop', 'ro.build.version.sdk',
                  serial=serial).strip()
    release = adb_run(adb_exe, 'shell', 'getprop', 'ro.build.version.release',
                      serial=serial).strip()
    print(f'  model     = {manufacturer!r} / {model!r}')
    print(f'  android   = {release!r} (sdk {sdk!r})')

    # Look for Wuthering Waves' package.
    pm = adb_run(adb_exe, 'shell', 'pm', 'list', 'packages', serial=serial)
    hits = []
    for line in pm.splitlines():
        low = line.lower()
        if any(k in low for k in ('wuther', 'kuro', 'mc', 'kurogame')):
            pkg = line.replace('package:', '').strip()
            if pkg:
                hits.append(pkg)
    if hits:
        print(f'  packages  = WuWa-candidates: {hits}')
    else:
        print('  packages  = (no obvious Wuthering Waves match)')


# ---------------------------------------------------------------------
# main
# ---------------------------------------------------------------------

def main() -> int:
    print()
    print('== Step 1: MuMu processes ==')
    procs = list_mumu_processes()
    if not procs:
        print('  No MuMu processes running.  Start MuMu Player 12 + boot the')
        print('  Android instance, then re-run this probe.')
    else:
        for pid, name in sorted(procs):
            print(f'  pid={pid}  {name}')
        print(f'  ({len(procs)} process(es) total)')

    print()
    print('== Step 2: ADB binary ==')
    adb_exe = find_adb_exe()
    if adb_exe is None:
        print('  ERROR: cannot locate adb.exe via adbutils._utils._get_bin_dir.')
        print('  Run build.bat (or pip install adbutils) and re-try.')
        return 2
    print(f'  adb       = {adb_exe}')
    version = adb_run(adb_exe, 'version').strip().splitlines()
    if version:
        print(f'  version   = {version[0]!r}')

    print()
    print('== Step 3: ADB devices ==')
    serials = list_adb_devices(adb_exe)
    if not serials:
        print('  No devices listed.  Try:')
        print('    adb connect 127.0.0.1:16384')
        print('  (16384 is MuMu 12 default; multi-instance shifts by +2.)')
        return 1
    for s in serials:
        print(f'  {s}')

    print()
    print('== Step 4: per-device probe ==')
    for s in serials:
        print()
        probe_one_device(adb_exe, s)

    print()
    print('Next steps:')
    print('  1. If a device above lists the WuWa package, copy it into')
    print("     'Mobile Config -> Game Package Names' (GUI).")
    print('  2. Boot main_mobile.py.  ok-script picks up the same ADB')
    print('     stack we just probed (NEMU IPC capture preferred, ADB')
    print('     capture as fallback).')
    print('  3. Use the in-GUI calibration tasks (Tap Test, Swipe Test)')
    print('     to fill in plugins/mumu12/key_map.py.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

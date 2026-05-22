"""Calibration tasks for stage-2 setup of the MuMu 12 mobile-mode plugin.

These tasks live in the GUI under the **Mobile** group and exist purely
as interactive helpers for the user (you) to:

- verify the ADB connection works and read Android-side facts
  (:class:`AdbProbeTask`)
- iteratively find on-screen virtual-button coordinates
  (:class:`TapTestTask`)
- calibrate the movement joystick centre and radius
  (:class:`SwipeTestTask`)

All three are :class:`~ok.BaseTask`-style one-time tasks: enable in the
GUI, click *Start*, watch the info panel + log pane.

They deliberately bypass :class:`MobileInputMixin` -- they're allowed
direct access to ok-script's ADB transport without the key_map
translation layer.  ``task_wrapper.wrap_task_entry`` recognises any
``plugins.mumu12.*`` module path and skips wrapping.

Why no ``WindowProbeTask`` anymore: ok-script's ADB mode talks to the
Android side directly via ``adb`` + NEMU IPC.  The Windows hwnd of the
MuMu render surface is irrelevant in this mode -- we no longer have to
discover it.  Use :mod:`plugins.mumu12.probe` from the command line if
you want to inspect MuMu windows for other reasons.
"""

from __future__ import annotations

import time

from qfluentwidgets import FluentIcon

from ok import Logger, og
from src.task.BaseWWTask import BaseWWTask

logger = Logger.get_logger(__name__)


# Common configuration shared across the calibration tasks.
_GROUP_NAME = 'Mobile'
_GROUP_ICON = FluentIcon.PHONE


# ---------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------

def _get_adb_device():
    """Return the connected adbutils Device object, or raise.

    Goes through ok-script's :class:`DeviceManager` which already owns
    the ADB connection, the chosen serial, and the auto-discovered
    MuMu serial via :class:`EmulatorManager`.  We never instantiate our
    own adb client.
    """
    dm = og.device_manager
    if dm is None:
        raise RuntimeError(
            'og.device_manager is not initialised yet -- the GUI must '
            'be fully started before running this calibration task.'
        )
    device = dm.device
    if device is None:
        raise RuntimeError(
            'No ADB device selected.  Open Settings -> Choose Device '
            'and pick your MuMu 12 instance first.'
        )
    return device


def _shell(*args) -> str:
    """Run an ADB shell command via the DeviceManager.

    Bundles ``args`` into a single ``cmdargs`` list because adbutils
    2.12 reads ``device.shell(cmdargs, stream=False, ...)`` -- passing
    multiple positional strings makes ``'size'`` slot in as
    ``stream=True`` and you get an ``AdbConnection`` back instead of
    stdout text.
    """
    cmd = list(args) if len(args) != 1 else args[0]
    return og.device_manager.shell(cmd)


# =====================================================================
# 1. AdbProbe -- verify ADB connection + dump Android-side facts
# =====================================================================

class AdbProbeTask(BaseWWTask):
    """Run a fixed battery of ADB commands and dump output to the GUI.

    No game interaction.  Use this to confirm:

    - ok-script's ADB chain reaches the emulator
    - The Android-side display size matches what you see
    - Wuthering Waves is installed (or what its real package name is)
    - NEMU IPC is reachable (the fast capture path)
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = 'Probe ADB Connection'
        self.description = (
            'Probe the ADB connection ok-script has set up: report serial, '
            'Android display, OS version, installed Wuthering Waves '
            'package, and the active capture method.  Use this to verify '
            'the device is wired up before fine-tuning key_map.py.'
        )
        self.group_name = _GROUP_NAME
        self.group_icon = _GROUP_ICON
        self.icon = FluentIcon.WIFI

    def run(self):
        try:
            device = _get_adb_device()
        except Exception as e:
            self.log_error(f'ADB device not available: {e}', notify=True)
            return

        self.log_info(f'ADB device: serial={device.serial}')
        self.info_set('adb.serial', device.serial)

        # Display size from the Android side (independent of host window).
        try:
            wm_out = _shell('wm', 'size').strip()
            self.log_info(f'wm size: {wm_out!r}')
            self.info_set('adb.wm_size', wm_out)
        except Exception as e:
            self.log_warning(f'wm size failed: {e}')

        # Capture-side resolution (the actual frame ok-script sees).
        try:
            cw = og.device_manager.width
            ch = og.device_manager.height
            if cw and ch:
                self.log_info(f'capture_method resolution: {cw}x{ch}')
                self.info_set('adb.capture_size', f'{cw}x{ch}')
        except Exception as e:
            self.log_warning(f'capture size failed: {e}')

        # Identify the active capture method (NEMU IPC vs fallback ADB).
        try:
            cm = og.device_manager.capture_method
            self.log_info(f'capture_method: {type(cm).__name__}')
            self.info_set('adb.capture_method', type(cm).__name__)
        except Exception:
            pass

        # Useful Android-side properties.
        for label, args in [
            ('android.version',     ('getprop', 'ro.build.version.release')),
            ('android.sdk',         ('getprop', 'ro.build.version.sdk')),
            ('device.model',        ('getprop', 'ro.product.model')),
            ('device.manufacturer', ('getprop', 'ro.product.manufacturer')),
        ]:
            try:
                value = _shell(*args).strip()
                self.log_info(f'{label}: {value!r}')
                self.info_set(label, value)
            except Exception as e:
                self.log_warning(f'{label} probe failed: {e}')

        # Look for Wuthering Waves' real package name on this device.
        try:
            pm = _shell('pm', 'list', 'packages')
            hits = []
            for line in pm.splitlines():
                low = line.lower()
                if any(k in low for k in ('wuther', 'kuro', 'mc', 'kurogame')):
                    hits.append(line.replace('package:', '').strip())
            if hits:
                self.log_info(f'WuWa-candidate packages: {hits}')
                self.info_set('adb.wuwa_packages', ', '.join(hits))
            else:
                self.log_warning(
                    'No Wuthering Waves-looking package found.  '
                    'You may need to install the game in MuMu 12 first.'
                )
        except Exception as e:
            self.log_warning(f'pm list packages failed: {e}')

        self.log_info('ADB probe complete.')


# =====================================================================
# 2. TapTest -- iteratively pin down a virtual button's coordinates
# =====================================================================

class TapTestTask(BaseWWTask):
    """Tap a user-specified relative coordinate three times, with feedback.

    Workflow for finding a button (e.g. the resonance skill):

    1. Open MuMu, get into combat in mobile WW.
    2. Estimate the button's relative position by eye (e.g. 0.93, 0.85).
    3. Set ``Relative X`` and ``Relative Y`` in this task's config.
    4. Click *Start*.  The task fires three taps spaced 1 s apart so you
       have time to watch which button (if any) lights up.
    5. Adjust by 0.01 increments and retry until you hit the centre.
    6. Copy the final values into ``plugins/mumu12/key_map.py``.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = 'Tap Test (find button coords)'
        self.description = (
            'Tap the Android screen at the given relative (0..1) coordinates '
            'three times, 1 s apart.  Iterate to home in on a virtual button '
            'before adding it to key_map.py.'
        )
        self.group_name = _GROUP_NAME
        self.group_icon = _GROUP_ICON
        self.icon = FluentIcon.PIN
        self.default_config = {
            'Relative X': 0.5,
            'Relative Y': 0.5,
            'Tap Count': 3,
            'Interval (s)': 1.0,
        }
        self.config_description = {
            'Relative X': 'Horizontal position 0..1, where 0=left edge, 1=right edge.',
            'Relative Y': 'Vertical position 0..1, where 0=top edge, 1=bottom edge.',
            'Tap Count': 'How many taps to issue (so you have time to see them).',
            'Interval (s)': 'Seconds between consecutive taps.',
        }

    def run(self):
        rx = float(self.config.get('Relative X', 0.5))
        ry = float(self.config.get('Relative Y', 0.5))
        n = int(self.config.get('Tap Count', 3))
        interval = float(self.config.get('Interval (s)', 1.0))

        if not (0.0 <= rx <= 1.0 and 0.0 <= ry <= 1.0):
            self.log_error(f'Relative coords out of range: ({rx}, {ry})')
            return

        # Use BaseTask.click_relative -- it auto-resolves the current
        # capture resolution and dispatches through ADBInteraction.
        self.log_info(
            f'Tap test: rel=({rx:.4f}, {ry:.4f})  count={n} interval={interval}s'
        )
        self.info_set('tap.rel', f'({rx:.4f}, {ry:.4f})')

        for i in range(n):
            try:
                self.click_relative(rx, ry)
                self.log_info(f'  tap {i + 1}/{n} sent')
            except Exception as e:
                self.log_error(f'  tap {i + 1} failed: {e}')
                return
            if i < n - 1:
                time.sleep(interval)

        self.log_info(
            'Done.  If a button lit up, copy these coords into key_map.py:  '
            f'ScreenPoint(rel_x={rx}, rel_y={ry}, name="..."),'
        )


# =====================================================================
# 3. SwipeTest -- calibrate joystick centre + radius
# =====================================================================

class SwipeTestTask(BaseWWTask):
    """Issue a swipe from one relative point to another.

    Used to calibrate the movement joystick:

    1. Eyeball the joystick centre, e.g. (0.18, 0.78).
    2. Set ``Start X = End X = 0.18``, ``Start Y = 0.78``,
       ``End Y = 0.68`` (push 0.10 upward).
    3. Click *Start*.  The character should walk forward briefly.
    4. If they don't move, the centre is wrong; adjust Start X/Y.
    5. If they move but stop too soon, increase the End offset.
    6. Final values give you ``JoystickConfig(center_x=Start X,
       center_y=Start Y, radius=hypot(End-Start))`` for key_map.py.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = 'Swipe Test (calibrate joystick)'
        self.description = (
            'Issue a swipe between two relative coordinates via ok-script\'s '
            'ADBInteraction.  Used to find the joystick centre and the push '
            'radius needed for full-speed movement.'
        )
        self.group_name = _GROUP_NAME
        self.group_icon = _GROUP_ICON
        self.icon = FluentIcon.MOVE
        self.default_config = {
            'Start X': 0.18,
            'Start Y': 0.78,
            'End X': 0.18,
            'End Y': 0.68,
            'Duration (ms)': 800,
        }
        self.config_description = {
            'Start X': 'Swipe start, horizontal 0..1 (your guess at joystick centre).',
            'Start Y': 'Swipe start, vertical 0..1.',
            'End X': 'Swipe end, horizontal 0..1.',
            'End Y': 'Swipe end, vertical 0..1.',
            'Duration (ms)': 'How long the swipe takes (longer = held longer).',
        }

    def run(self):
        sx = float(self.config.get('Start X', 0.18))
        sy = float(self.config.get('Start Y', 0.78))
        ex = float(self.config.get('End X', 0.18))
        ey = float(self.config.get('End Y', 0.68))
        dur = int(self.config.get('Duration (ms)', 800))

        for label, val in [('Start X', sx), ('Start Y', sy),
                           ('End X', ex), ('End Y', ey)]:
            if not (0.0 <= val <= 1.0):
                self.log_error(f'{label} out of range: {val}')
                return

        # BaseTask.swipe_relative -> swipe(from_x_px, from_y_px, ...).
        # ok-script's ADBInteraction.swipe routes to swipe_nemu /
        # swipe_u2 / `input swipe` depending on the active capture
        # method.  See ok/device/interaction_methods/adb.py.
        self.log_info(
            f'Swipe: rel=({sx:.3f},{sy:.3f}) -> ({ex:.3f},{ey:.3f})  '
            f'duration={dur}ms'
        )

        # swipe_relative wants duration in seconds (see ok/task/task.py L211).
        # The GUI exposes ms because ms is what 'input swipe' takes -- divide.
        dur_seconds = dur / 1000.0
        try:
            self.swipe_relative(sx, sy, ex, ey, dur_seconds)
        except AttributeError:
            # Older ok-script: fall back to manual computation.
            try:
                screen_w = int(self.width)
                screen_h = int(self.height)
            except Exception:
                self.log_error('Capture resolution unknown -- is the device connected?')
                return
            try:
                self.executor.interaction.swipe(
                    int(sx * screen_w), int(sy * screen_h),
                    int(ex * screen_w), int(ey * screen_h),
                    duration=dur,
                )
            except Exception as e:
                self.log_error(f'Swipe failed: {e}')
                return
        except Exception as e:
            self.log_error(f'Swipe failed: {e}')
            return

        # Compute the radius the user would write into JoystickConfig.
        from math import hypot
        radius = hypot(ex - sx, ey - sy)
        self.log_info(
            'If the character moved as expected, your JoystickConfig is:  '
            f'JoystickConfig(center_x={sx}, center_y={sy}, radius={radius:.4f})'
        )
        self.info_set('joystick.center', f'({sx}, {sy})')
        self.info_set('joystick.radius', f'{radius:.4f}')

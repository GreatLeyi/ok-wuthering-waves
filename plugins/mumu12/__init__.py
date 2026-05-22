"""MuMu 12 emulator support for ok-ww.

Architecture and implementation plan: see ``ai-doc/mobile-port-plan.md``.

This package provides a single public entry point -- :func:`apply_to` --
that takes the original ``config`` dict from ``config.py`` and returns
a patched copy suitable for running ok-ww against the *mobile* version
of Wuthering Waves inside MuMu Player 12.

Four things ``apply_to`` does:

0. **Monkey-patch** ok-script's broken NEMU IPC capture (1.0.130 has a
   dead-code early-return that breaks every frame).  See
   :func:`_patch_nemu_ipc_capture`.

1. **Replace** ``config['windows']`` with ``config['adb']``.  ok-script's
   own ADB mode handles emulator discovery, ADB connection, NEMU IPC
   capture (works on minimized windows!), and ADB ``input`` injection.
   See ``ok/device/DeviceManager.py`` and
   ``ok/device/capture_methods/nemu_ipc.py`` for the underlying impl.

2. **Wrap** every entry in ``config['onetime_tasks']`` /
   ``config['trigger_tasks']`` so that PC-style ``self.send_key('e')``
   calls are translated to ``self.click_relative(rel_x, rel_y)`` via the
   user-supplied ``key_map.py``.  Mobile WuWa has on-screen virtual
   buttons; the PC interpreter's keyboard semantics need that mapping.
   See :class:`plugins.mumu12.task_wrapper.MobileInputMixin`.

3. **Append** plugin-internal helper tasks (diagnosis overlay, tap/swipe
   probes) so the user can calibrate ``key_map.py`` interactively.

Removing the plugin folder + ``main_mobile.py`` reverts the project
fully -- ``src/``, ``main.py``, ``config.py`` are never touched.
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


# ok-script ADB-mode capture method names.  Order matters -- ok-script
# tries each in order, falling back on failure.
#   'ipc' -> NemuIpcCaptureMethod  (~30 fps, MuMu 12 only, works minimized)
#   'adb' -> ADBCaptureMethod      (~3 fps, universal, works minimized)
#
# See ok/device/DeviceManager.py around line 612 for the dispatch.
DEFAULT_CAPTURE_METHODS = ['ipc', 'adb']

# The interaction class used in ADB mode.  See
# ok/device/interaction_methods/adb.py -- supplies click(x,y), swipe,
# send_key (Android KEYCODE_*), input_text, etc.
DEFAULT_INTERACTION = 'ADB'


def _patch_nemu_ipc_capture() -> None:
    """Monkey-patch a known bug in ok-script 1.0.130's NEMU IPC capture.

    ``ok/device/capture_methods/nemu_ipc.py`` line 67-73 reads::

        def do_get_frame(self):
            self.init_nemu()
            return self.screencap()                       # <-- BUG
            if self.exit_event.is_set():                  # dead code
                return None
            if self.nemu_impl:                            # dead code
                return self.nemu_impl.screenshot(timeout=0.5)

    ``self.screencap()`` does not exist on the class (or anywhere in
    the ok package), so every frame attempt raises
    ``AttributeError`` -> ``CaptureException``.  ok-script's startup
    self-test catches that, marks the device "not connected", and the
    GUI never advances past "Starting" when you click a task.

    The post-return code is the *intended* implementation, so we
    reinstate it via monkey-patching.  Idempotent: tagged with
    ``__mumu12_patched__`` so re-running ``apply_to`` is a no-op.
    """
    try:
        from ok.device.capture_methods.nemu_ipc import NemuIpcCaptureMethod
    except Exception as e:  # pragma: no cover -- ok-script not importable
        logger.warning('cannot import NemuIpcCaptureMethod for patch: %s', e)
        return

    if getattr(NemuIpcCaptureMethod.do_get_frame, '__mumu12_patched__', False):
        return  # already patched in this Python process

    def _patched_do_get_frame(self):
        self.init_nemu()
        if self.exit_event.is_set():
            return None
        if self.nemu_impl:
            return self.nemu_impl.screenshot(timeout=0.5)
        return None

    _patched_do_get_frame.__mumu12_patched__ = True
    NemuIpcCaptureMethod.do_get_frame = _patched_do_get_frame
    logger.info(
        'patched NemuIpcCaptureMethod.do_get_frame '
        '(works around ok-script 1.0.130 dead-code bug)'
    )


def apply_to(original_config: Dict[str, Any]) -> Dict[str, Any]:
    """Return a deep-copied config patched for MuMu 12 mobile mode.

    The original ``config`` dict is **not** mutated.  Callers do::

        from config import config
        from plugins.mumu12 import apply_to
        from ok import OK

        OK(apply_to(config)).start()

    The PC-mode entry point ``main.py`` is unaffected.
    """
    # 0. Patch ok-script's NEMU IPC bug before any capture method is
    #    instantiated.  Safe to call repeatedly; idempotent.
    _patch_nemu_ipc_capture()

    config = copy.deepcopy(original_config)

    # 1. Drop PC window-attached config; switch to ok-script's ADB mode.
    config.pop('windows', None)
    config.pop('window_size', None)
    config.pop('supported_resolution', None)

    from .mobile_config import DEFAULT_WUWA_PACKAGES
    config['adb'] = {
        'capture_method': list(DEFAULT_CAPTURE_METHODS),
        'interaction': DEFAULT_INTERACTION,
        'packages': list(DEFAULT_WUWA_PACKAGES),
    }

    # 2. Wrap every task so PC keyboard calls are routed through
    #    MobileInputMixin -> key_map -> click_relative.
    from .task_wrapper import wrap_task_entry
    for key in ('onetime_tasks', 'trigger_tasks'):
        if key in config:
            config[key] = [wrap_task_entry(entry) for entry in config[key]]

    # 3. Append plugin-internal tasks (diagnosis + calibration tools).
    #    These are NOT wrapped (see wrap_task_entry's plugins.mumu12.*
    #    early-return) -- they want direct access to ok-script's ADB
    #    interaction so they can probe / calibrate without going through
    #    the key_map translation layer.
    config.setdefault('trigger_tasks', []).append(
        ['plugins.mumu12.diagnosis_task', 'MobileDiagnosisTask']
    )
    config.setdefault('onetime_tasks', []).extend([
        ['plugins.mumu12.calibration_tasks', 'AdbProbeTask'],
        ['plugins.mumu12.calibration_tasks', 'TapTestTask'],
        ['plugins.mumu12.calibration_tasks', 'SwipeTestTask'],
    ])

    # 4. Add the Mobile Config GUI option (Packages, Show Diagnosis).
    from .mobile_config import build_mobile_config_option
    config.setdefault('global_configs', []).append(build_mobile_config_option())

    return config


__all__ = ['apply_to']

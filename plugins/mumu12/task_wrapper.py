"""Task wrapping + PC-keyboard -> mobile-screen input translation.

How the wrapping works (also explained in ``ai-doc/mobile-port-plan.md``):

1. ``apply_to(config)`` walks the task lists, each of which is
   ``[module_path, class_name]`` string pairs.
2. For each pair :func:`wrap_task_entry` dynamically creates a subclass
   ``Mobile<ClassName>`` whose MRO is ``(MobileInputMixin, OriginalClass)``
   and registers it under :mod:`plugins.mumu12.tasks` so ok-script's
   string-based importer can find it.
3. ok-script later instantiates these wrapped classes; their
   ``self.send_key('e')`` resolves through MRO to
   :meth:`MobileInputMixin.send_key`, which translates the keystroke
   into a screen-relative tap via :mod:`plugins.mumu12.key_map`.

Why the layer is so thin now:

ok-script's ADB mode already provides the *transport*: ``self.click(x, y)``
in ADB mode goes through ``ADBInteraction.click`` which uses ``input tap``
or NEMU IPC's ``click_nemu_ipc``.  Multi-touch swipes route through
``swipe_nemu`` / ``swipe_u2`` automatically.  We don't need to touch
the wire layer at all.

What we DO still need:

- **Translation**: PC code calls ``self.send_key('e')``.  Mobile WuWa
  has no keyboard; that needs to become a tap on the on-screen
  resonance button.  ``key_map.py`` holds those coordinates and the
  mixin does the lookup.
- **Joystick state**: PC code calls ``self.send_key_down('w')`` and
  expects the character to keep walking until ``send_key_up('w')``.
  Mobile has an on-screen joystick; we hold a virtual finger on it via
  short, periodic swipes (best-effort -- true held multi-touch would
  need either NemuIpc.down/move/up directly or uiautomator2's
  ``touch.down/move/up``; the swipe approach works on every backend).
"""

from __future__ import annotations

import importlib
import logging
import math
import time
from typing import Iterable, List, Set

from . import tasks as _mobile_tasks_namespace

logger = logging.getLogger(__name__)


# Task modules that should NOT be wrapped, because they're either
# plugin-internal (calibration/diagnosis -- they need raw access) or
# meaningless on mobile (e.g. PC-only mouse-grab counter-measures).
DISABLED_ON_MOBILE = {
    ('src.task.MouseResetTask', 'MouseResetTask'),
}


# Direction key -> unit vector for joystick composition.
_DIR_VECTORS = {
    'w': (0.0, -1.0),
    'a': (-1.0, 0.0),
    's': (0.0, 1.0),
    'd': (1.0, 0.0),
}


class MobileInputMixin:
    """First parent in the MRO of every wrapped Mobile<XxxTask>.

    Overrides only the input methods that need keyboard->coordinate
    translation.  Everything else (``self.click(x, y)``, OCR, template
    matching, scene checks) inherits unchanged from the original task
    class and goes through ok-script's ADB transport via
    ``self.executor.interaction``.
    """

    # Per-task instance state for the joystick.  Lazily initialized to
    # avoid touching ``__init__`` (preserves the original task's init
    # signature exactly).
    _joystick_dirs: Set[str]

    # ----- helpers -------------------------------------------------------

    def _ensure_joystick_state(self) -> None:
        if not hasattr(self, '_joystick_dirs'):
            self._joystick_dirs = set()
            self._joystick_last_pump = 0.0

    @staticmethod
    def _norm_key(key) -> str:
        if isinstance(key, int):
            return str(key)
        return str(key).strip().lower()

    def _tap_mapped(self, key: str) -> bool:
        """Look up ``key`` in the user's key_map and tap the screen.

        Returns True on hit, False if the key is unmapped (logs a
        ``[mobile-key-map TODO]`` warning -- caller decides whether to
        treat that as a soft failure).
        """
        from .key_map import lookup
        point = lookup(key)
        if point is None:
            logger.warning("[mobile-key-map TODO] key=%r -- drop tap", key)
            return False
        # BaseTask.click auto-proxies to click_relative when 0<x<1, but
        # we call click_relative directly to be unambiguous and avoid
        # collisions with literal pixel coordinates the original code
        # might have passed elsewhere.
        try:
            self.click_relative(point.rel_x, point.rel_y)
        except Exception as e:
            logger.error("click_relative(%s, %s) failed: %s",
                         point.rel_x, point.rel_y, e)
            return False
        return True

    def _pump_joystick(self) -> None:
        """Recompute joystick target from currently-held dirs and swipe.

        Each call issues one short swipe from joystick centre toward the
        composite direction.  Held continuously, this produces sustained
        movement (the character keeps walking).  Direction changes
        retarget on the next pump.
        """
        from .key_map import JOYSTICK
        if JOYSTICK is None:
            logger.warning("[mobile-key-map TODO] JOYSTICK config not provided")
            return

        if not self._joystick_dirs:
            return

        dx = sum(_DIR_VECTORS[d][0] for d in self._joystick_dirs)
        dy = sum(_DIR_VECTORS[d][1] for d in self._joystick_dirs)
        norm = math.hypot(dx, dy) or 1.0
        ux, uy = dx / norm, dy / norm

        target_rel_x = JOYSTICK.center_x + ux * JOYSTICK.radius
        target_rel_y = JOYSTICK.center_y + uy * JOYSTICK.radius

        # BaseTask.swipe_relative handles px conversion + dispatch through
        # ok-script's ADBInteraction (swipe_nemu / swipe_u2 / input swipe).
        # Duration is in seconds here -- BaseTask multiplies by 1000 internally.
        try:
            self.swipe_relative(
                JOYSTICK.center_x, JOYSTICK.center_y,
                target_rel_x, target_rel_y,
                duration=0.3,
            )
            self._joystick_last_pump = time.time()
        except Exception as e:
            logger.debug("joystick swipe failed: %s", e)

    # ----- keyboard surface ---------------------------------------------

    def send_key(self, key, *args, **kwargs):
        """One-shot keypress -> tap on the mapped on-screen button."""
        key = self._norm_key(key)
        if key in _DIR_VECTORS:
            # Treat a stand-alone send_key('w') as "nudge forward briefly".
            self.send_key_down(key)
            time.sleep(0.10)
            self.send_key_up(key)
            return True
        return self._tap_mapped(key)

    def send_key_down(self, key, *args, **kwargs):
        """Begin holding a key.  Direction keys feed the joystick."""
        key = self._norm_key(key)
        self._ensure_joystick_state()
        if key in _DIR_VECTORS:
            self._joystick_dirs.add(key)
            self._pump_joystick()
        else:
            # Most virtual buttons can't actually be "held"; do a tap.
            self._tap_mapped(key)

    def send_key_up(self, key, *args, **kwargs):
        """Release a key.  For dirs, recompute / stop the joystick."""
        key = self._norm_key(key)
        self._ensure_joystick_state()
        if key in _DIR_VECTORS:
            self._joystick_dirs.discard(key)
            if self._joystick_dirs:
                # Other directions still held -- retarget.
                self._pump_joystick()
            # else: no swipe in flight to abort; the previous swipe will
            # naturally end on its duration timer (~300 ms).

    # ----- mouse surface ------------------------------------------------

    def middle_click(self, *args, **kwargs):
        """PC middle-click was used for enemy lock-on.  Mobile usually
        has a dedicated lock button (or auto-targeting); look it up in
        ``key_map.SPECIAL_MAP['middle_click']``.  No mapping = no-op,
        which is fine because mobile WuWa tends to auto-target."""
        from .key_map import lookup
        point = lookup('middle_click')
        if point is None:
            logger.debug("middle_click: no lock-on button mapped, skipping")
            return
        try:
            self.click_relative(point.rel_x, point.rel_y)
        except Exception as e:
            logger.error("middle_click failed: %s", e)

    def mouse_down(self, key='left', *args, **kwargs):
        """PC right-mouse was sprint.  No automatic mapping yet -- if
        your key_map has a ``mouse_right`` entry it's used as a tap;
        otherwise this is a no-op."""
        if key in ('right', 'middle'):
            from .key_map import lookup
            point = lookup(f'mouse_{key}')
            if point is not None:
                self.click_relative(point.rel_x, point.rel_y)
                return
        logger.debug("mouse_down(%s): no-op on mobile", key)

    def mouse_up(self, key='left', *args, **kwargs):
        logger.debug("mouse_up(%s): no-op on mobile", key)

    # ``move`` / ``scroll_relative`` from the PC API don't have natural
    # mobile equivalents; let them fall through to ok-script defaults
    # (which on ADB just no-op or log).


# =====================================================================
# Wrapping mechanism
# =====================================================================

def wrap_task_entry(entry: Iterable[str]) -> List[str]:
    """Turn ``[module, class]`` into ``[plugins.mumu12.tasks, Mobile<class>]``.

    Idempotent: wrapping the same entry twice returns the same target.
    Disabled tasks (e.g. ``MouseResetTask``) become no-op stubs.
    Plugin-internal tasks (``plugins.mumu12.*``) are returned unchanged
    so they keep direct ok-script ADB access.
    """
    module_path, class_name = list(entry)
    key = (module_path, class_name)

    if module_path.startswith('plugins.mumu12.'):
        return [module_path, class_name]

    if key in DISABLED_ON_MOBILE:
        return ['plugins.mumu12.tasks', _ensure_disabled_stub(class_name)]

    return ['plugins.mumu12.tasks', _ensure_wrapped(module_path, class_name)]


def _ensure_wrapped(module_path: str, class_name: str) -> str:
    wrapped_name = f'Mobile{class_name}'
    if hasattr(_mobile_tasks_namespace, wrapped_name):
        return wrapped_name

    try:
        module = importlib.import_module(module_path)
    except ImportError as e:
        raise RuntimeError(
            f"Cannot import original task module {module_path!r}: {e}"
        ) from e

    original_cls = getattr(module, class_name, None)
    if original_cls is None:
        raise RuntimeError(
            f"Module {module_path!r} has no class {class_name!r}"
        )

    wrapped = type(
        wrapped_name,
        (MobileInputMixin, original_cls),
        {
            '__module__': _mobile_tasks_namespace.__name__,
            '__qualname__': wrapped_name,
            '__doc__': (
                f'Mobile-mode wrapper around {module_path}.{class_name}.  '
                f'Generated by plugins.mumu12.task_wrapper.'
            ),
        },
    )
    setattr(_mobile_tasks_namespace, wrapped_name, wrapped)
    logger.debug('wrapped %s.%s as %s', module_path, class_name, wrapped_name)
    return wrapped_name


def _ensure_disabled_stub(class_name: str) -> str:
    stub_name = f'Disabled{class_name}'
    if hasattr(_mobile_tasks_namespace, stub_name):
        return stub_name

    if class_name == 'MouseResetTask':
        from src.task.MouseResetTask import MouseResetTask as Base
    else:
        raise RuntimeError(f'No disabled-stub recipe for {class_name!r}')

    def _noop_run(self, *_a, **_kw):
        return None

    stub = type(
        stub_name,
        (Base,),
        {
            '__module__': _mobile_tasks_namespace.__name__,
            '__qualname__': stub_name,
            '__doc__': (
                f'No-op mobile-mode replacement for {class_name}.  '
                f'PC mouse-anti-grab logic is meaningless inside MuMu 12.'
            ),
            'run': _noop_run,
        },
    )
    setattr(_mobile_tasks_namespace, stub_name, stub)
    return stub_name

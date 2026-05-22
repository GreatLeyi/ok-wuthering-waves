"""PC keyboard / mouse → mobile screen-coordinate mapping for MuMu 12.

Every value here is **TODO** until you (the user) provide the actual
on-screen coordinates of each virtual button in mobile Wuthering Waves.

Coordinates are stored as **screen-relative** ``(rel_x, rel_y)`` in
``[0, 1] × [0, 1]`` so the same map works regardless of the Android
display resolution.  ``MobileInputAdapter`` translates them to absolute
Android pixel coordinates at call time using ``AdbHelper.to_android_xy``.

To fill this in:

1. Take a 1080p screenshot of mobile WW in combat.
2. For each entry below, mouse over the corresponding virtual button and
   read its centre as ``(x / image_width, y / image_height)``.
3. Replace ``None`` with ``ScreenPoint(rel_x=..., rel_y=..., name=...)``.

Until that's done, every unmapped key call is logged as
``[mobile-key-map TODO] key='e'`` and silently dropped.  This lets you
boot the plugin and explore the GUI without crashing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


# ---------------------------------------------------------------------
# Coordinate primitives
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class ScreenPoint:
    """A single tappable button at relative coords (0..1, 0..1)."""
    rel_x: float
    rel_y: float
    name: str = ''


@dataclass(frozen=True)
class JoystickConfig:
    """Virtual movement joystick.

    ``center_x/y`` is where the joystick rests; the adapter holds a finger
    here and drags it ``radius`` away from the centre to walk in a
    direction.  All values are screen-relative.
    """
    center_x: float
    center_y: float
    radius: float        # max push distance from centre, in screen units
    name: str = 'joystick'


# ---------------------------------------------------------------------
# Key map.  TODO: fill these in once user provides coordinates.
# ---------------------------------------------------------------------

# Skill keys (mapped to single tappable buttons on the HUD).
KEY_MAP: Dict[str, Optional[ScreenPoint]] = {
    # Combat skills
    'e':       None,    # TODO: Resonance Skill button (共鸣技能)
    'r':       None,    # TODO: Resonance Liberation button (共鸣解放)
    'q':       None,    # TODO: Echo Skill button (声骸技能)
    't':       None,    # TODO: Tool / explore item button (探索工具)
    'tab':     None,    # TODO: Levitator / glider wheel (滑翔伞 / 浮空轮盘)
    'space':   None,    # TODO: Jump button (跳跃)
    'lshift':  None,    # TODO: Dodge button (闪避)
    'f':       None,    # TODO: Pickup / interact button (F 拾取 / 互动)
    'esc':     None,    # TODO: Back / close button (返回)

    # Character switching
    '1':       None,    # TODO: Char slot 1 portrait
    '2':       None,    # TODO: Char slot 2 portrait
    '3':       None,    # TODO: Char slot 3 portrait

    # Map / book / menu
    'm':       None,    # TODO: Open map button (M)
    'f2':      None,    # TODO: Open guide book (F2)
    'alt':     None,    # TODO: Cursor / mouse mode toggle (Alt)
}


# Aliases used by middle_click etc.
SPECIAL_MAP: Dict[str, Optional[ScreenPoint]] = {
    'middle_click':  None,   # TODO: Lock-on-enemy button if present, else None means noop
}


# Movement joystick.
JOYSTICK: Optional[JoystickConfig] = None
# TODO: e.g. JoystickConfig(center_x=0.18, center_y=0.78, radius=0.10, name='left_joystick')


# ---------------------------------------------------------------------
# Convenience accessors used by the adapter.
# ---------------------------------------------------------------------

def lookup(key: str) -> Optional[ScreenPoint]:
    """Look up a key, falling through KEY_MAP -> SPECIAL_MAP -> None."""
    return KEY_MAP.get(key) or SPECIAL_MAP.get(key)


def is_complete() -> bool:
    """True iff every entry above has been filled in.

    Useful for an at-startup sanity check: an incomplete map is fine for
    boot-up, but combat will fail until JOYSTICK and the skill keys are set.
    """
    return JOYSTICK is not None and all(
        v is not None for v in KEY_MAP.values()
    )

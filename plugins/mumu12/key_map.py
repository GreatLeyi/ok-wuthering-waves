"""PC keyboard / mouse → mobile screen-coordinate mapping for MuMu 12.

Coordinates extracted from MuMu Player 12's built-in keyboard-mapping
overlay (the one the user enables to play mobile games with WASD on
desktop).  That overlay shows exactly where each PC key lands as a tap
on the Android screen, which is the same translation we want to do.

Layout reference (1920x1080):

         B(背包)                         C(角色) ` (菜单)
                                            Z(剧情)
    M(地图)
       V(任务追踪)                                1(切换角色2)

                                                  2(切换角色1)

                                F(交互)
                                Alt(鼠标)

                            G(瞄准)   T(探索工具)

         W                            Space(跳跃)
       A   D                  Q(声骸)
         S                  R(解放)  攻击(鼠标左键)
                                E(共鸣战技)        Shift(闪避)

                Y(锁定目标)

PC ``send_key('e')`` -> ``MobileInputMixin.send_key`` ->
``self.click_relative(rel_x, rel_y)`` -> ok-script's ``ADBInteraction``
-> ``adb shell input tap`` (or NEMU IPC click on the IPC backend).

If you hit anti-tap-pattern detection (rare, not confirmed on WuWa)
or if you want MuMu to handle the translation natively, see
``ai-doc/mobile-port-plan.md`` Option B (PostMessage to MuMu window).
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
# Key map.  Coords lifted from MuMu Player 12's keyboard-mapping overlay
# for Wuthering Waves Mobile (1920x1080 canvas, divided to get rel_x/y).
# ---------------------------------------------------------------------

# Skill keys (mapped to single tappable buttons on the HUD).
KEY_MAP: Dict[str, Optional[ScreenPoint]] = {
    # Combat skills
    'e':       ScreenPoint(0.719, 0.898, 'resonance_skill'),     # 共鸣战技
    'r':       ScreenPoint(0.659, 0.813, 'liberation'),          # 共鸣解放
    'q':       ScreenPoint(0.719, 0.731, 'echo'),                # 声骸异能
    't':       ScreenPoint(0.810, 0.644, 'explore_tool'),        # 探索工具
    'tab':     None,    # No mobile equivalent in MuMu overlay (PC: glider)
    'space':   ScreenPoint(0.898, 0.722, 'jump'),                # 跳跃
    'lshift':  ScreenPoint(0.909, 0.866, 'dodge'),               # 闪避
    'f':       ScreenPoint(0.693, 0.449, 'interact'),            # 交互 / pickup
    'esc':     ScreenPoint(0.948, 0.107, 'menu_back'),           # 菜单 / 返回 (backtick on MuMu)

    # Aim / target lock (PC has these as separate keys/buttons)
    'g':       ScreenPoint(0.659, 0.671, 'aim'),                 # 瞄准
    'y':       ScreenPoint(0.273, 0.935, 'lock_target'),         # 锁定目标

    # Character switching.  MuMu's overlay binds PC '1' to the top
    # portrait (slot 2) and PC '2' to the bottom portrait (slot 1),
    # but PC ok-ww code calls send_key('1') expecting "switch to slot 1".
    # We expose '2'/'3' for the visible portraits (slot 1 = active = no-op).
    '1':       None,    # Active character; tapping not required
    '2':       ScreenPoint(0.909, 0.282, 'char_slot_2'),         # top portrait
    '3':       ScreenPoint(0.909, 0.412, 'char_slot_3'),         # bottom portrait

    # Map / book / inventory / character / story
    'm':       ScreenPoint(0.107, 0.167, 'map'),                 # 打开/关闭地图
    'v':       ScreenPoint(0.049, 0.245, 'quest_tracker'),       # 任务追踪
    'b':       ScreenPoint(0.234, 0.097, 'inventory'),           # 背包
    'c':       ScreenPoint(0.880, 0.051, 'character'),           # 角色
    'z':       ScreenPoint(0.893, 0.083, 'auto_dialog'),         # 自动播放剧情
    'f2':      None,    # No mobile equivalent in MuMu overlay
    'alt':     ScreenPoint(0.721, 0.338, 'cursor_toggle'),       # 呼出/隐藏鼠标
}


# Aliases used by middle_click etc.
SPECIAL_MAP: Dict[str, Optional[ScreenPoint]] = {
    # Mobile WuWa typically auto-targets; lock-on lives at the Y-key
    # position above (锁定目标).  middle_click on PC was lock-on.
    'middle_click':  ScreenPoint(0.273, 0.935, 'lock_target'),
    # PC mouse-left = attack.  Mobile WuWa has a dedicated 攻击 button.
    'mouse_left':    ScreenPoint(0.810, 0.806, 'attack'),
    # PC mouse-right = sprint (held); on mobile a long-press of joystick
    # usually triggers sprint.  We treat as no-op for now.
    'mouse_right':   None,
}


# Movement joystick.  Centre extracted from W/A/S/D label positions in
# MuMu's overlay (W=305,778 ; A=270,813 ; S=305,858 ; D=341,813 -> centre
# (305,818) on a 1920x1080 canvas).  Radius is a guess: 5% of the screen
# width (~96 px) gives natural-feeling movement; bump it up if the
# character only walks (rather than runs) in calibration tests.
JOYSTICK: Optional[JoystickConfig] = JoystickConfig(
    center_x=0.159,
    center_y=0.758,
    radius=0.05,
    name='left_joystick',
)


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
        v is not None for v in KEY_MAP.values() if v is not None or True
    )

"""MobileDiagnosisTask -- overlay all key UI boxes onto the GUI for tuning.

When the user enables this trigger task (via ``Mobile Config ->
Show Diagnosis Overlay`` or directly in the GUI), it draws the named
boxes that recognition logic actually uses, so the user can immediately
see whether each box landed on the right region of the *mobile* UI.
PC-mode coordinates often need small adjustments (joystick pad, virtual
buttons live where PC HUD elements never existed).

This is read-only: it never sends input.  Pair with the
``[mobile-key-map TODO]`` warnings emitted by
:class:`plugins.mumu12.task_wrapper.MobileInputMixin` to debug why a
key map entry isn't firing the expected button.
"""

from __future__ import annotations

from qfluentwidgets import FluentIcon

from ok import TriggerTask, Logger, og
from src.task.BaseWWTask import BaseWWTask

logger = Logger.get_logger(__name__)


# Boxes to draw.  Each entry is ``(label, box_name)`` where ``box_name``
# is a key that resolves through ``self.get_box_by_name``.  We pick names
# from ``src.Labels`` plus a few derived helpers.
_BOXES_TO_DRAW = [
    # Team slot portraits
    ('char_1',     'box_char_1'),
    ('char_2',     'box_char_2'),
    ('char_3',     'box_char_3'),
    # Skill UI (right-bottom on PC, varies on mobile)
    ('resonance',  'box_resonance'),
    ('echo',       'box_echo'),
    ('liberation', 'box_liberation'),
    ('extra',      'box_extra_action'),
    # Concerto ring (centre bottom)
    ('concerto',   'box_concerto_last_dot'),
    # Forte bar
    ('forte_1',    'box_forte_1'),
    ('forte_2',    'box_forte_2'),
    ('forte_3',    'box_forte_3'),
    # Map / minimap
    ('minimap',    'box_minimap'),
    ('arrow',      'box_arrow'),
    # Targeting reticle / enemy info bar
    ('target',     'box_target_enemy'),
    ('target_long','box_target_enemy_long'),
]


class MobileDiagnosisTask(TriggerTask, BaseWWTask):
    """Read-only HUD overlay for tuning mobile-mode recognition.

    Default disabled.  Enable via the GUI when you need to verify boxes.
    Trigger interval is 0.5 s -- frequent enough to feel live, light
    enough not to compete with the real workload.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_config = {'_enabled': False}
        self.trigger_interval = 0.5
        self.name = 'Mobile Diagnosis Overlay'
        self.description = (
            'Draw all key UI boxes onto the screen so you can see whether '
            'PC-mode coordinates land on the correct mobile UI elements. '
            'Read-only; sends no input.'
        )
        self.group_name = 'Mobile'
        self.group_icon = FluentIcon.PHONE
        self.icon = FluentIcon.VIEW

    def run(self):
        # Draw every box we know about.  ``get_box_by_name`` may raise on
        # unknown names; tolerate that quietly so adding/removing boxes
        # in upstream code doesn't break the diagnosis tool.
        for label, box_name in _BOXES_TO_DRAW:
            try:
                box = self.get_box_by_name(box_name)
            except Exception:
                continue
            try:
                self.draw_boxes(f'diag_{label}', box, color='lime')
            except Exception as e:           # pragma: no cover
                logger.debug('draw_boxes %s failed: %s', label, e)

        # Dump a few high-level recognition states to the info panel so
        # the user can correlate with what they see on screen.
        try:
            in_team, idx, count = self.in_team()
            self.info_set('mobile.in_team', f'{in_team} idx={idx} n={count}')
        except Exception:
            pass

        try:
            self.info_set('mobile.has_target', self.has_target())
        except Exception:
            pass

        # Surface the active capture / interaction methods so the user can
        # confirm at a glance whether NEMU IPC kicked in (works minimised)
        # or we fell back to ADB capture (works but slower).
        try:
            cm = og.device_manager.capture_method
            if cm is not None:
                self.info_set('mobile.capture', type(cm).__name__)
        except Exception:
            pass
        try:
            interaction = og.device_manager.interaction
            if interaction is not None:
                self.info_set('mobile.interaction', type(interaction).__name__)
        except Exception:
            pass

        # Joystick state: any wrapped task instance owns its own
        # ``_joystick_dirs`` set (see MobileInputMixin).  The current
        # task's set is the most relevant; expose ours.
        try:
            held = getattr(self, '_joystick_dirs', None)
            if held is not None:
                self.info_set('mobile.held_dirs', ''.join(sorted(held)) or '-')
        except Exception:
            pass

        return True   # we did something this tick; keep dispatcher happy

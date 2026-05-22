"""GUI configuration option exposed by the MuMu 12 plugin.

This shows up under ``Settings -> Mobile Config`` in the ok-ww GUI once
``apply_to(config)`` has been called.

Stable-string config keys live here in English (persisted to ``configs/``).
Translations belong in ``i18n/<locale>/LC_MESSAGES/ok.po``.

NOTE: the previous version of this file exposed an "ADB Port" and an
"Input Backend" selector.  Both are now obsolete because ok-script's
own ADB mode (``config['adb']``) handles port discovery via
EmulatorManager and the capture/interaction backend via
``capture_method`` / ``interaction`` strings inside that dict.
"""

from __future__ import annotations

from ok import ConfigOption


# ---- config keys (stable, persisted to JSON; do NOT translate) ----------
KEY_PACKAGES = 'Game Package Names'
KEY_SHOW_DIAGNOSIS = 'Show Diagnosis Overlay'


# Best-known Wuthering Waves Android package candidates.  The plugin
# passes all of these to ok-script's ``adb_check_in_front`` so any one
# matching brings the front-foreground check to success.  Edit if you
# discover a different package on your client; running
# ``python -m plugins.mumu12.probe`` will list installed packages
# containing 'wuther', 'kuro', or 'mc' so you can confirm.
DEFAULT_WUWA_PACKAGES = [
    'com.kurogame.mingchao',                 # CN client (verified 2026-05)
    'com.kurogame.wutheringwaves',           # historical / global guess
    'com.kurogame.wutheringwaves.cn',        # CN variant guess
    'com.kurogamestudio.wutheringwaves',     # alternate spelling
    'com.kurogame.wutheringwaves.global',    # global / overseas
    'com.kurogame.mc',                       # historical CN beta name
]


def build_mobile_config_option() -> ConfigOption:
    """Build the global ConfigOption that ``apply_to`` registers."""
    defaults = {
        # Stored as a comma-separated string in JSON for simplicity;
        # parse back to a list at use-time.
        KEY_PACKAGES: ','.join(DEFAULT_WUWA_PACKAGES),
        KEY_SHOW_DIAGNOSIS: False,
    }
    config_description = {
        KEY_PACKAGES: (
            'Comma-separated Android package names of mobile Wuthering '
            'Waves.  ok-script tests them in order.  Run '
            "'python -m plugins.mumu12.probe' to discover the real "
            'package on your installation.'
        ),
        KEY_SHOW_DIAGNOSIS: (
            'Show recognition box overlay (MobileDiagnosisTask) for tuning '
            'box coordinates against the mobile UI.'
        ),
    }
    return ConfigOption(
        'Mobile Config',
        defaults,
        description='Settings for the MuMu 12 mobile-mode plugin',
        config_description=config_description,
    )


def get_packages(global_configs) -> list[str]:
    """Helper: read the configured package list from ok-script's globals.

    ``global_configs`` is the iterable typically obtained via
    ``og.config.get('global_configs')``.  Returns the default list on
    any failure so callers don't have to handle missing config.
    """
    try:
        for opt in global_configs or []:
            if getattr(opt, 'key', None) == 'Mobile Config':
                raw = (opt.config or {}).get(KEY_PACKAGES, '')
                items = [p.strip() for p in str(raw).split(',') if p.strip()]
                return items or list(DEFAULT_WUWA_PACKAGES)
    except Exception:
        pass
    return list(DEFAULT_WUWA_PACKAGES)

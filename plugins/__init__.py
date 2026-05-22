"""ok-ww plugin namespace.

Plugins live under ``plugins/<name>/`` and expose a top-level ``apply_to(config)``
function that returns a patched ``config`` dict (the dict passed to
``ok.OK(config)``).  Plugins must NOT modify any file under ``src/``,
``main.py``, ``main_debug.py``, ``config.py``, ``assets/``, or ``ok_templates/``.

To enable a plugin, create a sibling entry-point script (e.g. ``main_mobile.py``)
that imports the plugin and calls ``apply_to(config)`` before ``OK(config).start()``.

Removing a plugin = ``rm -rf plugins/<name>/`` + delete its entry-point script.
The project returns to the original PC behavior with zero residue.
"""

"""Namespace for dynamically-generated Mobile<XxxTask> classes.

Empty by design.  The real classes are created at startup time by
:func:`plugins.mumu12.task_wrapper.wrap_task_entry` and bolted onto this
module via ``setattr(this_module, 'MobileDailyTask', ...)``.

ok-script imports them by string path::

    importlib.import_module('plugins.mumu12.tasks').MobileDailyTask

so all that matters is that ``plugins.mumu12.tasks`` is a real package
that supports ``setattr`` (it is — modules always do).

Do not put your own classes here; they will be silently shadowed if the
wrapper picks the same name.
"""

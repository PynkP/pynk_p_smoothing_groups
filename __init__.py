# SPDX-License-Identifier: GPL-3.0-or-later
"""pynk_p Smoothing Groups. Created by pynk_p."""


def register():
    import bpy
    from .properties import PYNKPSG_Settings
    from . import operators, panels
    for cls in (PYNKPSG_Settings,) + operators.CLASSES + panels.CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Object.pynkp_sg = bpy.props.PointerProperty(type=PYNKPSG_Settings)


def unregister():
    import bpy
    from .properties import PYNKPSG_Settings
    from . import operators, panels
    del bpy.types.Object.pynkp_sg
    for cls in reversed((PYNKPSG_Settings,) + operators.CLASSES + panels.CLASSES):
        bpy.utils.unregister_class(cls)
    # Keep saved Geometry Nodes and attributes: disabling the add-on must not
    # destroy the model or require Python to evaluate its saved modifiers.

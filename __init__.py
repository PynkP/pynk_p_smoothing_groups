# SPDX-License-Identifier: GPL-3.0-or-later
"""pynk_p Smoothing Groups. Created by pynk_p."""


def register():
    import bpy
    from .properties import PYNKPSG_Settings
    from . import operators, panels
    if not hasattr(bpy.types, 'GeometryNodeSetMeshNormal'):
        raise RuntimeError("pynk_p requires Set Mesh Normal (target: Blender 5.2.3 LTS)")
    classes = (PYNKPSG_Settings,) + operators.CLASSES + panels.CLASSES
    registered = []
    try:
        for cls in classes:
            bpy.utils.register_class(cls)
            registered.append(cls)
        bpy.types.Object.pynkp_sg = bpy.props.PointerProperty(type=PYNKPSG_Settings)
    except Exception:
        if hasattr(bpy.types.Object, 'pynkp_sg'):
            del bpy.types.Object.pynkp_sg
        for cls in reversed(registered):
            bpy.utils.unregister_class(cls)
        raise


def unregister():
    import bpy
    from .properties import PYNKPSG_Settings
    from . import operators, panels
    if hasattr(bpy.types.Object, 'pynkp_sg'):
        del bpy.types.Object.pynkp_sg
    for cls in reversed((PYNKPSG_Settings,) + operators.CLASSES + panels.CLASSES):
        bpy.utils.unregister_class(cls)
    # Keep saved Geometry Nodes and attributes: disabling the add-on must not
    # destroy the model or require Python to evaluate its saved modifiers.

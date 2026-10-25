# SPDX-License-Identifier: GPL-3.0-or-later
"""Saved object settings. No mesh writes from property callbacks."""
from math import radians
from bpy.props import BoolProperty, FloatProperty, IntProperty, StringProperty
from bpy.types import PropertyGroup


class PYNKPSG_Settings(PropertyGroup):
    angle: FloatProperty(
        name="Angle", description="Auto Smooth threshold between face normals",
        subtype='ANGLE', default=radians(30), min=0.0, max=radians(180))
    select_group: IntProperty(name="Group", default=1, min=1, max=30)
    use_groups: BoolProperty(name="Use Smoothing Groups", default=True)
    subdivision_name: StringProperty(name="Managed Subdivision", default="")

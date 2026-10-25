# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only panels. Selection is read afresh; drawing never changes the mesh."""
from bpy.types import Panel
from .core import group_bit
from .mesh_repository import selection_state, editable_object
from . import node_backend as backend
from . import constants as C


class PanelMixin:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'pynk_p'

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH'


def usable(layout, context):
    try:
        editable_object(context)
    except ValueError as exc:
        layout.label(text=str(exc), icon='INFO')
        return False
    return True


class PYNKPSG_PT_groups(PanelMixin, Panel):
    bl_idname = 'PYNKPSG_PT_groups'
    bl_label = 'Smoothing Groups'
    bl_order = 0

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        if not usable(layout, context):
            return
        count, active = selection_state(obj)
        layout.label(text=f"Selected Faces: {count}")
        if obj.mode != 'EDIT':
            layout.label(text="Enter Edit Mode to assign groups", icon='EDITMODE_HLT')
        body = layout.column()
        body.enabled = obj.mode == 'EDIT' and count > 0
        grid = body.grid_flow(row_major=True, columns=6, even_columns=True, even_rows=True, align=True)
        grid.scale_y = 1.2
        for number in range(1, 31):
            op = grid.operator('pynkp_sg.toggle_group', text=str(number),
                               depress=bool(active & group_bit(number)))
            op.number = number
        body.operator('pynkp_sg.clear_groups', icon='X')
        body.separator()
        body.prop(obj.pynkp_sg, 'angle')
        body.operator('pynkp_sg.auto_smooth', icon='MOD_SMOOTH')
        row = layout.row(align=True)
        row.enabled = obj.mode == 'EDIT'
        row.prop(obj.pynkp_sg, 'select_group', text="Group")
        row.operator('pynkp_sg.select_group', text="Select")
        layout.separator()
        layout.label(text="Created by pynk_p")


class PYNKPSG_PT_subdivision(PanelMixin, Panel):
    bl_idname = 'PYNKPSG_PT_subdivision'
    bl_label = 'Subdivision By Smoothing Groups'
    bl_order = 1

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        if not usable(layout, context):
            return
        try:
            mod = backend.subdivision(obj)
            boundary = backend.owned_modifier(obj, C.CREASE_ROLE)
            backend.validate_stack(obj)
        except ValueError as exc:
            layout.label(text="Check modifier order / names", icon='ERROR')
            layout.label(text=str(exc))
            layout.operator('pynkp_sg.remove_subdivision')
            return
        if not mod:
            layout.operator('pynkp_sg.add_subdivision', icon='MOD_SUBSURF')
        else:
            layout.operator('pynkp_sg.use_groups',
                            icon='CHECKBOX_HLT' if obj.pynkp_sg.use_groups else 'CHECKBOX_DEHLT',
                            depress=obj.pynkp_sg.use_groups)
            for target, label, flag in (
                ('VIEWPORT', 'Show in Viewport', mod.show_viewport),
                ('RENDER', 'Show in Render', mod.show_render),
            ):
                op = layout.operator('pynkp_sg.subdivision_visibility', text=label,
                                     icon='CHECKBOX_HLT' if flag else 'CHECKBOX_DEHLT', depress=flag)
                op.target = target
            layout.prop(mod, 'levels', text='Viewport Levels')
            layout.prop(mod, 'render_levels', text='Render Levels')
            layout.label(text="Boundary Method: Crease", icon='MOD_EDGESPLIT')
            layout.operator('pynkp_sg.remove_subdivision', icon='X')
        layout.separator()
        layout.operator('pynkp_sg.refresh', icon='FILE_REFRESH')
        layout.label(text="Refresh after mesh edits", icon='INFO')


CLASSES = (PYNKPSG_PT_groups, PYNKPSG_PT_subdivision)

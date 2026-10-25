# SPDX-License-Identifier: GPL-3.0-or-later
"""Thin, undoable UI commands. No domain logic in operators."""
import traceback
import bpy
from bpy.props import EnumProperty, IntProperty
from bpy.types import Operator

from . import application as services
from . import node_backend as backend
from . import mesh_repository as repository


def redraw(context):
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()


class CommandMixin:
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'MESH' and obj.mode in {'OBJECT', 'EDIT'}

    def execute(self, context):
        try:
            message = self.run(context)
        except (ValueError, RuntimeError) as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        except Exception as exc:
            traceback.print_exc()
            self.report({'ERROR'}, f"pynk_p: {type(exc).__name__}: {exc}")
            return {'CANCELLED'}
        redraw(context)
        if message:
            self.report({'INFO'}, message)
        return {'FINISHED'}


class PYNKPSG_OT_toggle(CommandMixin, Operator):
    bl_idname = 'pynkp_sg.toggle_group'
    bl_label = "Toggle Smoothing Group"
    bl_description = "On: remove from all selected faces. Off: add to all selected faces. Update shading immediately"
    number: IntProperty(default=1, min=1, max=30)

    def run(self, context):
        services.change_groups(context, 'TOGGLE', self.number)


class PYNKPSG_OT_clear(CommandMixin, Operator):
    bl_idname = 'pynkp_sg.clear_groups'
    bl_label = "Clear Groups"
    bl_description = "Clear every group on the selected faces and update shading"

    def run(self, context):
        services.change_groups(context, 'CLEAR')


class PYNKPSG_OT_auto(CommandMixin, Operator):
    bl_idname = 'pynkp_sg.auto_smooth'
    bl_label = "Auto Smooth"
    bl_description = "Replace selected-face groups by angle; preserve unselected group assignments"

    def run(self, context):
        return services.change_groups(context, 'AUTO')


class PYNKPSG_OT_select(CommandMixin, Operator):
    bl_idname = 'pynkp_sg.select_group'
    bl_label = "Select by Group"
    bl_description = "Replace the visible face selection with faces in the chosen group"

    def run(self, context):
        services.select_group(context, context.active_object.pynkp_sg.select_group)


class PYNKPSG_OT_refresh(CommandMixin, Operator):
    bl_idname = 'pynkp_sg.refresh'
    bl_label = "Update Boundaries"
    bl_description = "Rebuild group normals and boundaries after moving vertices, Extrude, Bevel, or other mesh edits"

    def run(self, context):
        services.refresh(context)
        return "Group normals and boundaries updated"


class PYNKPSG_OT_add_subdivision(CommandMixin, Operator):
    bl_idname = 'pynkp_sg.add_subdivision'
    bl_label = "Add Subdivision"
    bl_description = "Add a non-destructive, crease-based subdivision driven by smoothing-group boundaries"

    def run(self, context):
        services.add_subdivision(context)


class PYNKPSG_OT_use_groups(CommandMixin, Operator):
    bl_idname = 'pynkp_sg.use_groups'
    bl_label = "Use Smoothing Groups"
    bl_description = "Toggle group-derived subdivision creases; preserve source mesh creases"

    def run(self, context):
        obj = repository.editable_object(context)
        backend.validate_stack(obj)
        if not backend.subdivision(obj):
            raise ValueError("Add an SG subdivision first")
        # Turning on also refreshes any topology changes made since last use.
        if not obj.pynkp_sg.use_groups:
            services.refresh(context)
        obj.pynkp_sg.use_groups = not obj.pynkp_sg.use_groups
        backend.sync_visibility(obj)


class PYNKPSG_OT_visibility(CommandMixin, Operator):
    bl_idname = 'pynkp_sg.subdivision_visibility'
    bl_label = "Toggle Subdivision Visibility"
    target: EnumProperty(items=[('VIEWPORT', "Viewport", ""), ('RENDER', "Render", "")])

    def run(self, context):
        obj = repository.editable_object(context)
        backend.validate_stack(obj)
        mod = backend.subdivision(obj)
        if not mod:
            raise ValueError("Add an SG subdivision first")
        key = 'show_viewport' if self.target == 'VIEWPORT' else 'show_render'
        setattr(mod, key, not getattr(mod, key))
        backend.sync_visibility(obj)


class PYNKPSG_OT_remove_subdivision(CommandMixin, Operator):
    bl_idname = 'pynkp_sg.remove_subdivision'
    bl_label = "Remove SG Subdivision"
    bl_description = "Remove the managed subdivision and boundary modifier; keep groups and original creases"

    def run(self, context):
        backend.remove_subdivision(repository.editable_object(context))


CLASSES = (
    PYNKPSG_OT_toggle, PYNKPSG_OT_clear, PYNKPSG_OT_auto, PYNKPSG_OT_select,
    PYNKPSG_OT_refresh, PYNKPSG_OT_add_subdivision, PYNKPSG_OT_use_groups,
    PYNKPSG_OT_visibility, PYNKPSG_OT_remove_subdivision,
)

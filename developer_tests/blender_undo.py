"""Explicit pushes emulate Blender's UI undo boundaries in background scripts."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import bpy
import bmesh
import pynkp_smoothing_groups as addon
from pynkp_smoothing_groups import mesh_repository as repo
addon.register()
bpy.ops.mesh.primitive_cube_add()
bpy.ops.object.mode_set(mode='EDIT')
bpy.context.tool_settings.mesh_select_mode = (False, False, True)
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.ed.undo_push(message='Before groups')
bpy.ops.pynkp_sg.toggle_group(number=1)
bpy.ops.ed.undo_push(message='Group 1')
bpy.ops.pynkp_sg.toggle_group(number=2)
bpy.ops.ed.undo_push(message='Group 2')
assert repo.selection_state(bpy.context.object)[1] == 3
bpy.ops.ed.undo()
assert repo.selection_state(bpy.context.object)[1] == 1
bpy.ops.ed.redo()
assert repo.selection_state(bpy.context.object)[1] == 3
print('PASS: EDIT MODE UNDO / REDO restores group attributes')
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.ed.undo_push(message='Before sub')
bpy.ops.pynkp_sg.add_subdivision()
bpy.ops.ed.undo_push(message='Add sub')
assert len(bpy.context.object.modifiers) == 3
bpy.ops.ed.undo()
assert len(bpy.context.object.modifiers) == 1
bpy.ops.ed.redo()
assert len(bpy.context.object.modifiers) == 3
print('PASS: SUBDIVISION UNDO / REDO restores managed stack')

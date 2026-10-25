"""Run: blender --background --factory-startup --python tests/blender_integration.py"""
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import bpy
import bmesh
import pynkp_smoothing_groups as addon
from pynkp_smoothing_groups import constants as C, mesh_repository as repo, node_backend as backend

results = []


def check(label, condition):
    assert condition, label
    results.append(label)
    print('PASS:', label, flush=True)


def masks(obj):
    with repo.open_mesh(obj) as bm:
        return list(repo.masks_of(bm).values())


def select(obj, indices):
    if obj.mode != 'EDIT':
        bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    for face in bm.faces:
        face.select_set(False)
    for edge in bm.edges:
        edge.select_set(False)
    for vertex in bm.verts:
        vertex.select_set(False)
    for i in indices:
        bm.faces[i].select_set(True)
    bm.select_mode = {'FACE'}
    bpy.context.tool_settings.mesh_select_mode = (False, False, True)
    bm.select_flush_mode()
    bmesh.update_edit_mesh(obj.data)


def evaluated(obj):
    bpy.context.view_layer.update()
    return obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).data


def main():
    print('BLENDER:', bpy.app.version_string, flush=True)
    addon.register()
    check('Add-on registration', hasattr(bpy.types.Object, 'pynkp_sg'))
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.mesh.primitive_cube_add()
    obj = bpy.context.object
    obj.name = 'SG_Integration_Cube'
    # Preserve user-authored base attributes and settings.
    crease = obj.data.attributes.new('crease_edge', 'FLOAT', 'EDGE')
    crease.data[0].value = 0.35
    original_sharp = [e.use_edge_sharp for e in obj.data.edges]
    original_smooth = [p.use_smooth for p in obj.data.polygons]
    select(obj, [0])
    for n, expected in [(1, 1), (2, 3), (2, 1), (1, 0)]:
        check(f'Toggle operation {n} -> {expected}', bpy.ops.pynkp_sg.toggle_group(number=n) == {'FINISHED'})
        check(f'Saved mask {expected}', masks(obj)[0] == expected)
    select(obj, [0])
    bpy.ops.pynkp_sg.toggle_group(number=1)
    select(obj, [1])
    bpy.ops.pynkp_sg.toggle_group(number=2)
    select(obj, [0, 1])
    check('Union display is 1|2', repo.selection_state(obj) == (2, 3))
    bpy.ops.pynkp_sg.toggle_group(number=1)
    check('Mixed selection removes group from all', masks(obj)[:2] == [0, 2])
    check('No duplicate normal modifiers', len(obj.modifiers) == 1)

    select(obj, range(6))
    obj.pynkp_sg.angle = math.radians(30)
    check('Angle auto-assignment operator', bpy.ops.pynkp_sg.auto_smooth() == {'FINISHED'})
    assigned = masks(obj)
    with repo.open_mesh(obj) as bm:
        check('Cube sharp adjacency differs', all(not (assigned[e.link_faces[0].index] & assigned[e.link_faces[1].index]) for e in bm.edges))
    bpy.ops.object.mode_set(mode='OBJECT')
    mesh = evaluated(obj)
    check('Evaluated normals exist', len(mesh.corner_normals) == 24)
    check('Base creases preserved', abs(obj.data.attributes['crease_edge'].data[0].value - 0.35) < 1e-6)
    check('Base sharp flags preserved', [e.use_edge_sharp for e in obj.data.edges] == original_sharp)
    check('Base face shading preserved', [p.use_smooth for p in obj.data.polygons] == original_smooth)
    check('Source has no new custom normals', not obj.data.has_custom_normals)

    check('Add subdivision', bpy.ops.pynkp_sg.add_subdivision() == {'FINISHED'})
    sub = backend.subdivision(obj)
    sub.levels = 1
    mesh = evaluated(obj)
    check('Subdivision increases face count', len(mesh.polygons) == 24)
    crease_on = max(v.co.length for v in mesh.vertices)
    check('Crease-based cube corners retained', abs(crease_on - math.sqrt(3)) < 1e-4)
    check('Group boundary disabled', bpy.ops.pynkp_sg.use_groups() == {'FINISHED'})
    mesh = evaluated(obj)
    crease_off = max(v.co.length for v in mesh.vertices)
    check('Group toggle changes subdivision geometry', crease_off < crease_on - 0.1)
    check('Original crease still preserved after disable', abs(obj.data.attributes['crease_edge'].data[0].value - 0.35) < 1e-6)
    bpy.ops.pynkp_sg.use_groups()
    check('Group link enabled again', obj.pynkp_sg.use_groups)

    # Check edit-mode geometry and refresh, no object-mode switches inside command.
    select(obj, [0])
    bm = bmesh.from_edit_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.verts[0].co.z += 0.25
    bmesh.update_edit_mesh(obj.data)
    check('Refresh after vertex movement', bpy.ops.pynkp_sg.refresh() == {'FINISHED'})
    check('Edit mode retained', obj.mode == 'EDIT')
    bpy.ops.object.mode_set(mode='OBJECT')

    file = ROOT / 'validation_scene.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(file))
    before = masks(obj)
    bpy.ops.wm.open_mainfile(filepath=str(file))
    obj = bpy.context.object
    check('Save and reload masks', masks(obj) == before)
    check('Save and reload managed link', backend.subdivision(obj) is not None)
    check('Save and reload geometry', len(evaluated(obj).polygons) == 24)
    bpy.ops.pynkp_sg.remove_subdivision()
    check('Remove only managed subdivision pair', len(obj.modifiers) == 1)
    check('Original crease survives removal', abs(obj.data.attributes['crease_edge'].data[0].value - 0.35) < 1e-6)

    # Three faces sharing a vertex: A={1}, B={1,2}, C={2}.
    bpy.ops.object.select_all(action='DESELECT')
    data = bpy.data.meshes.new('FanMesh')
    data.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)], [],
                     [(0, 1, 2), (0, 2, 3), (0, 3, 1)])
    fan = bpy.data.objects.new('Overlapping_Group_Fan', data)
    bpy.context.collection.objects.link(fan)
    fan.select_set(True)
    bpy.context.view_layer.objects.active = fan
    select(fan, [0, 1])
    bpy.ops.pynkp_sg.toggle_group(number=1)
    select(fan, [1, 2])
    bpy.ops.pynkp_sg.toggle_group(number=2)
    bpy.ops.object.mode_set(mode='OBJECT')
    fan_mesh = evaluated(fan)
    normals = [fan_mesh.corner_normals[p.loop_start].vector.copy() for p in fan_mesh.polygons]
    check('Direct-overlap normal A excludes C', abs(normals[0].y) < 1e-5)
    check('Direct-overlap normal C excludes A', abs(normals[2].z) < 1e-5)
    check('Bridge B includes all three', min(normals[1]) > 0.5)

    addon.unregister()
    check('Unregister preserves evaluated geometry', len(evaluated(fan).polygons) == 3)
    addon.register()
    check('Re-register', hasattr(bpy.types.Object, 'pynkp_sg'))
    payload = {'blender': bpy.app.version_string, 'passed': len(results), 'checks': results}
    (ROOT / 'integration_results.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')
    print('ALL INTEGRATION CHECKS PASSED', len(results), flush=True)


try:
    main()
except Exception:
    import traceback
    traceback.print_exc()
    sys.exit(1)

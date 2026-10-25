# SPDX-License-Identifier: GPL-3.0-or-later
"""BMesh persistence adapter; no UI or modifier responsibilities."""
from contextlib import contextmanager
from itertools import combinations
import math

import bmesh
from mathutils import Vector

from . import constants as C
from .core import ALL_GROUPS, auto_assign, corner_normal, edge_is_boundary, union_mask


def editable_object(context):
    obj = context.active_object
    if not obj or obj.type != 'MESH' or obj.mode not in {'OBJECT', 'EDIT'}:
        raise ValueError("Select an editable mesh")
    if obj.library or obj.data.library or obj.override_library:
        raise ValueError("Use a local, editable mesh")
    if context.mode == 'EDIT_MESH' and len(context.objects_in_mode_unique_data) != 1:
        raise ValueError("Edit one mesh at a time")
    # Shared meshes otherwise change other objects without their modifier setup.
    if obj.data.users > 1:
        raise ValueError("Make the mesh single-user before editing smoothing groups")
    return obj


@contextmanager
def open_mesh(obj, write=False):
    live = obj.mode == 'EDIT'
    bm = bmesh.from_edit_mesh(obj.data) if live else bmesh.new()
    if not live:
        bm.from_mesh(obj.data)
    try:
        bm.faces.ensure_lookup_table()
        bm.faces.index_update()
        bm.edges.ensure_lookup_table()
        bm.edges.index_update()
        bm.verts.ensure_lookup_table()
        yield bm
        if write:
            if live:
                bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
            else:
                bm.to_mesh(obj.data)
                obj.data.update()
    finally:
        if not live:
            bm.free()


def selected_faces(bm):
    return [face for face in bm.faces if face.select and not face.hide]


def masks_of(bm):
    layer = bm.faces.layers.int.get(C.MASK)
    return {f.index: (f[layer] & ALL_GROUPS if layer else 0) for f in bm.faces}


def selection_state(obj):
    if not obj or obj.type != 'MESH' or obj.mode != 'EDIT':
        return 0, 0
    with open_mesh(obj) as bm:
        layer = bm.faces.layers.int.get(C.MASK)
        selected = selected_faces(bm)
        return len(selected), union_mask(f[layer] for f in selected) if layer else 0


def validate_attributes(mesh):
    for name, domain, data_type in (
        (C.MASK, 'FACE', 'INT'), (C.BOUNDARY, 'EDGE', 'INT'),
        (C.NORMAL, 'CORNER', 'FLOAT_VECTOR'), (C.FLAT, 'FACE', 'INT'),
    ):
        attr = mesh.attributes.get(name)
        if attr and (attr.domain != domain or attr.data_type != data_type):
            raise ValueError(f"Attribute name conflict: {name}")


def vertex_fans(vertex):
    """Do not average across bow-tie vertices or non-manifold edges."""
    faces = {f.index: f for f in vertex.link_faces}
    adjacent = {i: set() for i in faces}
    for edge in vertex.link_edges:
        if len(edge.link_faces) == 2:
            a, b = (f.index for f in edge.link_faces)
            adjacent[a].add(b)
            adjacent[b].add(a)
    remaining = set(faces)
    while remaining:
        seed = min(remaining)
        component = set()
        stack = [seed]
        while stack:
            f = stack.pop()
            if f in component:
                continue
            component.add(f)
            stack.extend(adjacent[f] - component)
        remaining -= component
        yield [faces[i] for i in sorted(component)]


def derive(bm, masks):
    """Calculate all results before any write, including custom corner normals."""
    bm.normal_update()
    boundaries = [(e.index, int(edge_is_boundary(masks[f.index] for f in e.link_faces)))
                  for e in bm.edges]
    normals = []
    for vertex in bm.verts:
        loops_by_face = {loop.face.index: loop for loop in vertex.link_loops}
        for fan in vertex_fans(vertex):
            contributors = []
            for face in fan:
                loop = loops_by_face[face.index]
                angle = loop.calc_angle()
                if not math.isfinite(angle):
                    angle = 0.0
                contributors.append((masks[face.index], tuple(face.normal), angle))
            # Cache repeated masks at a vertex; dense smooth regions use one sum.
            cache = {}
            for face in fan:
                mask = masks[face.index]
                if mask:
                    if mask not in cache:
                        cache[mask] = corner_normal(mask, face.normal, contributors)
                    normal = cache[mask]
                else:
                    normal = tuple(face.normal)
                loop_index = list(face.loops).index(loops_by_face[face.index])
                normals.append((face.index, loop_index, normal))
    return boundaries, normals


def commit(bm, masks, derived):
    layer = bm.faces.layers.int.get(C.MASK) or bm.faces.layers.int.new(C.MASK)
    flat = bm.faces.layers.int.get(C.FLAT) or bm.faces.layers.int.new(C.FLAT)
    boundary = bm.edges.layers.int.get(C.BOUNDARY) or bm.edges.layers.int.new(C.BOUNDARY)
    normal = bm.loops.layers.float_vector.get(C.NORMAL) or bm.loops.layers.float_vector.new(C.NORMAL)
    for face in bm.faces:
        face[layer] = masks[face.index]
        face[flat] = int(masks[face.index] == 0)
    # Creating CustomData layers can invalidate cached BMEdge/BMLoop wrappers.
    # Plans contain indices only; reacquire every element after adding layers.
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    for index, is_boundary in derived[0]:
        bm.edges[index][boundary] = is_boundary
    for face_index, loop_index, direction in derived[1]:
        bm.faces[face_index].loops[loop_index][normal] = Vector(direction)


def plan_auto(bm, masks, angle):
    bm.normal_update()
    selected = {f.index for f in selected_faces(bm)}
    smooth, hard = set(), set()
    forbidden = {i: 0 for i in selected}
    threshold = math.cos(angle)
    for edge in bm.edges:
        if len(edge.link_faces) != 2:
            continue
        a, b = edge.link_faces
        if a.index in selected and b.index in selected:
            pair = tuple(sorted((a.index, b.index)))
            if a.normal.dot(b.normal) >= threshold - 1e-7:
                smooth.add(pair)
            else:
                hard.add(pair)
    for vertex in bm.verts:
        for fan in vertex_fans(vertex):
            for a, b in combinations(fan, 2):
                sa, sb = a.index in selected, b.index in selected
                if sa and sb:
                    if a.normal.dot(b.normal) < threshold - 1e-7:
                        hard.add(tuple(sorted((a.index, b.index))))
                elif sa:
                    forbidden[a.index] |= masks[b.index]
                elif sb:
                    forbidden[b.index] |= masks[a.index]
    return auto_assign(selected, smooth, hard, forbidden)

# SPDX-License-Identifier: GPL-3.0-or-later
"""Replaceable, non-destructive Blender modifier backend.

Derived SG attributes are interpreted on evaluated geometry only. Original
sharpness, crease_edge, and custom normals are never overwritten.
"""
import bpy
from . import constants as C


def owned_modifier(obj, role):
    found = [m for m in obj.modifiers if m.type == 'NODES' and m.node_group
             and m.node_group.get(C.ROLE) == role]
    if len(found) > 1:
        raise ValueError("Duplicate pynk_p modifiers found; keep one of each")
    return found[0] if found else None


def subdivision(obj):
    name = obj.pynkp_sg.subdivision_name
    mod = obj.modifiers.get(name) if name else None
    return mod if mod and mod.type == 'SUBSURF' else None


def _tree(name, role):
    tree = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    tree[C.ROLE] = role
    tree["pynkp_schema"] = C.SCHEMA
    tree.interface.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    tree.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    tree.nodes.new('NodeGroupInput').location = (-600, 100)
    tree.nodes.new('NodeGroupOutput').location = (600, 100)
    return tree


def _attribute(tree, name, kind, location):
    node = tree.nodes.new('GeometryNodeInputNamedAttribute')
    node.data_type = kind
    node.inputs['Name'].default_value = name
    node.label = name
    node.location = location
    return node.outputs['Attribute']


def build_normals():
    tree = _tree("pynk_p • Group Normals", C.NORMAL_ROLE)
    try:
        source = tree.nodes.get('Group Input')
        target = tree.nodes.get('Group Output')
        sharp = tree.nodes.new('GeometryNodeSetMeshNormal')
        sharp.mode = 'SHARPNESS'
        sharp.location = (-100, 100)
        sharp.inputs['Remove Custom'].default_value = True
        tree.links.new(source.outputs['Geometry'], sharp.inputs['Mesh'])
        tree.links.new(_attribute(tree, C.BOUNDARY, 'INT', (-600, -100)), sharp.inputs['Edge Sharpness'])
        tree.links.new(_attribute(tree, C.FLAT, 'INT', (-600, -300)), sharp.inputs['Face Sharpness'])
        normal = tree.nodes.new('GeometryNodeSetMeshNormal')
        normal.mode = 'FREE'
        normal.domain = 'CORNER'
        normal.location = (250, 100)
        tree.links.new(sharp.outputs['Mesh'], normal.inputs['Mesh'])
        tree.links.new(_attribute(tree, C.NORMAL, 'FLOAT_VECTOR', (-100, -300)), normal.inputs['Custom Normal'])
        tree.links.new(normal.outputs['Mesh'], target.inputs['Geometry'])
        return tree
    except Exception:
        bpy.data.node_groups.remove(tree)
        raise


def build_boundaries():
    tree = _tree("pynk_p • SG Subdivision Boundaries", C.CREASE_ROLE)
    try:
        source = tree.nodes.get('Group Input')
        target = tree.nodes.get('Group Output')
        store = tree.nodes.new('GeometryNodeStoreNamedAttribute')
        store.data_type = 'FLOAT'
        store.domain = 'EDGE'
        store.inputs['Name'].default_value = 'crease_edge'
        store.location = (200, 100)
        maximum = tree.nodes.new('ShaderNodeMath')
        maximum.operation = 'MAXIMUM'
        maximum.location = (-100, -100)
        tree.links.new(_attribute(tree, 'crease_edge', 'FLOAT', (-600, -100)), maximum.inputs[0])
        tree.links.new(_attribute(tree, C.BOUNDARY, 'INT', (-600, -300)), maximum.inputs[1])
        tree.links.new(maximum.outputs[0], store.inputs['Value'])
        tree.links.new(source.outputs['Geometry'], store.inputs['Geometry'])
        tree.links.new(store.outputs['Geometry'], target.inputs['Geometry'])
        return tree
    except Exception:
        bpy.data.node_groups.remove(tree)
        raise


def _ensure(obj, role, name, builder):
    mod = owned_modifier(obj, role)
    if mod:
        return mod
    tree = builder()
    try:
        mod = obj.modifiers.new(name, 'NODES')
        mod.node_group = tree
        mod.show_in_editmode = True
        # Do not display a displaced subdivision cage as the editable mesh.
        mod.show_on_cage = False
        return mod
    except Exception:
        if tree.users == 0:
            bpy.data.node_groups.remove(tree)
        raise


def ensure_normals(obj):
    return _ensure(obj, C.NORMAL_ROLE, "pynk_p • Smoothing Groups", build_normals)


def ensure_boundaries(obj):
    return _ensure(obj, C.CREASE_ROLE, "pynk_p • SG Boundaries", build_boundaries)


def validate_subdivision_support():
    """Check required node sockets before a user operation mutates mesh data."""
    probe = build_boundaries()
    bpy.data.node_groups.remove(probe)


def validate_stack(obj):
    """Normal data is derived from the base mesh; no upstream topology edits."""
    normal = owned_modifier(obj, C.NORMAL_ROLE)
    boundary = owned_modifier(obj, C.CREASE_ROLE)
    sub = subdivision(obj)
    if normal and obj.modifiers.find(normal.name) != 0:
        raise ValueError("Move 'pynk_p • Smoothing Groups' to the top of the modifier stack")
    if sub:
        if not normal or not boundary:
            raise ValueError("Managed modifier stack is incomplete; remove the SG subdivision and add it again")
        if obj.modifiers.find(boundary.name) != 1 or obj.modifiers.find(sub.name) != 2:
            raise ValueError("Keep the SG stack first: Smoothing Groups, SG Boundaries, Subdivision")
    if boundary and not sub:
        raise ValueError("Managed Subdivision was renamed or deleted; use Remove SG Subdivision, then add it again")


def move_to(obj, mod, index):
    obj.modifiers.move(obj.modifiers.find(mod.name), index)


def add_subdivision(obj):
    if subdivision(obj):
        raise ValueError("This object already has an SG subdivision")
    normal = ensure_normals(obj)
    move_to(obj, normal, 0)
    boundary = ensure_boundaries(obj)
    mod = obj.modifiers.new("pynk_p • Subdivision By Smoothing Groups", 'SUBSURF')
    mod.subdivision_type = 'CATMULL_CLARK'
    mod.levels = 2
    mod.render_levels = 2
    mod.show_in_editmode = True
    mod.show_only_control_edges = True
    # Interpolating base custom normals would flatten the subdivision shading.
    if hasattr(mod, 'use_custom_normals'):
        mod.use_custom_normals = False
    if hasattr(mod, 'use_creases'):
        mod.use_creases = True
    obj.pynkp_sg.subdivision_name = mod.name
    move_to(obj, boundary, 1)
    move_to(obj, mod, 2)
    obj.pynkp_sg.use_groups = True
    sync_visibility(obj)
    return mod


def sync_visibility(obj):
    boundary = owned_modifier(obj, C.CREASE_ROLE)
    sub = subdivision(obj)
    if boundary:
        boundary.show_viewport = bool(sub and obj.pynkp_sg.use_groups and sub.show_viewport)
        boundary.show_render = bool(sub and obj.pynkp_sg.use_groups and sub.show_render)


def remove_subdivision(obj):
    sub = subdivision(obj)
    if sub:
        obj.modifiers.remove(sub)
    boundary = owned_modifier(obj, C.CREASE_ROLE)
    if boundary:
        tree = boundary.node_group
        obj.modifiers.remove(boundary)
        if tree.users == 0:
            bpy.data.node_groups.remove(tree)
    obj.pynkp_sg.subdivision_name = ""

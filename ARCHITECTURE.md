# Architecture — pynk_p Smoothing Groups

Created by pynk_p. Target runtime: Blender 5.2.3 LTS.

## Modules and responsibility

| Module | Responsibility |
|---|---|
| `core.py` | Bit-mask operations, direct-overlap normal rule, angle-relation graph assignment; no Blender import |
| `ports.py` | Small structural Protocol interfaces for storage and rendering backends |
| `services.py` | Application actions: validate, plan, commit |
| `application.py` | Composition root; inject concrete Blender adapters |
| `mesh_repository.py` | BMesh reads/writes, face selection, geometry-derived relations and data |
| `node_backend.py` | Geometry Nodes and Subdivision modifier construction and lifecycle |
| `operators.py` | Undoable Blender commands and error reporting |
| `panels.py` | Read-only UI; live selection union and two panels |
| `properties.py` | Persistent per-object user settings |
| `constants.py` | Namespaced data contracts |
| `__init__.py` | Registration and unregister lifecycle |

## SOLID intent

- **Single responsibility:** UI, persistence, algorithm, and Blender evaluation are separate.
- **Open/closed:** a different normal or subdivision backend can implement the ports
  and be injected in `application.py` without rewriting toggle rules or panels.
- **Liskov substitution:** adapters must honor the ports' semantics: preserve base
  mesh data, reject unsupported inputs, and provide the same group meaning.
- **Interface segregation:** storage, normal backend, and subdivision backend are
  distinct Protocols instead of one giant abstract Blender framework.
- **Dependency inversion:** services depend on ports and the pure core; only the
  composition root selects the BMesh/Geometry Nodes implementation. UI inspection
  uses the Blender adapter directly because it is already an outer layer.

This is deliberately a small implementation. Operator selection code still works
with repository-provided BMesh objects; supporting an entirely different host
would also require a selection adapter rather than pretending the whole add-on
is host-independent.

## Storage contract

| Attribute | Domain | Type | Meaning |
|---|---|---|---|
| `pynkp_sg_mask` | FACE | INT | Bits 0–29 = groups 1–30; zero = flat |
| `pynkp_sg_boundary` | EDGE | INT | 0/1 derived boundary |
| `pynkp_sg_flat` | FACE | INT | Derived zero-mask flag |
| `pynkp_sg_corner_normal` | CORNER | FLOAT_VECTOR | Derived angle-weighted normal |

The mask is authoritative. All other attributes are caches rebuilt on group
operations and Update Boundaries. Group masks fit in positive signed 32-bit integers.
Namespaced attributes with incompatible domains/types cause an error.

The base mesh's standard sharpness, crease, and custom-normal attributes are not
written. The normal Geometry Nodes modifier sets sharpness and FREE corner normals
on evaluated geometry. The boundary modifier stores
`max(source crease_edge, group boundary)` on evaluated geometry before Subdivision.
Disabling the boundary modifier therefore restores the source crease without a
fragile backup keyed by edge indices. A subdivision with custom-normal interpolation
disabled recomputes shading on its new geometry.

## Graph semantics and auto assignment

Group overlap is pairwise (`mask_a & mask_b != 0`), not transitive equivalence.
Normal contributions are restricted to the same manifold vertex fan, and then
filtered by direct mask overlap. At a fan, identical masks share cached sums.

Auto Smooth first creates angle-based smooth/hard constraints. It merges regions
only when no hard pair would be joined, covers remaining smooth pairs with
overlapping patches, and colors the patch-conflict graph with DSATUR and 30 bits.
Bits of untouched neighboring faces are forbidden for selected patches. A capacity
failure occurs in the pure planning stage, before changing masks. Greedy failure
does not prove no mathematical solution exists; the UI says the assignment could
not fit, rather than claiming the mesh intrinsically needs more than 30 groups.

## Update and undo policy

One group command plans all normals and boundaries before committing. BMesh plans
store element indices, not wrappers, because adding CustomData layers may invalidate
BMEdge/BMLoop wrappers. Standard Blender operators have `REGISTER` and `UNDO`.
No depsgraph mutation handler or timer is installed. Ordinary modeling edits require
Update Boundaries; this avoids background writes outside Blender's undo commands.

The managed normal modifier must be first, followed by the boundary modifier and
managed Subdivision if present. Existing user modifiers are retained after them.
The currently managed Subdivision is stored by name; renaming it is unsupported
and results in a visible recovery message, not guessing and deleting another modifier.

## Compatibility and limitations

Crease-driven subdivision is a concrete first backend, not a verified clone of
TurboSmooth Separate by Smoothing Groups. Corner/junction behavior and topology can
differ. Normals use the documented weighting in this project, not an undocumented
promise of numerical equivalence to Autodesk. A future backend can replace these
policies without changing the 30-button UI or stored masks.

Source deformation, newly generated faces, and topology-changing modifiers may
invalidate cached normals or interpolate mask values. The supported workflow is
editing the base mesh and explicitly refreshing after geometry edits. Animation,
FBX/Unreal round-trips, and arbitrary modifier stacks are not certified.

## Development tests

The `developer_tests` folder includes the unit suite and Blender integration/undo
scripts. Extract the extension into a folder named `pynkp_smoothing_groups`.
From that folder run:

```sh
python -m unittest discover -s developer_tests -p 'test_core.py'
blender --background --factory-startup --python-exit-code 1 --python developer_tests/blender_integration.py
blender --background --factory-startup --python-exit-code 1 --python developer_tests/blender_undo.py
```

The integration script creates a validation `.blend` and JSON report beside the
extracted package. It runs in factory startup and does not touch an existing project.
The background undo script explicitly pushes stack boundaries to emulate UI undo.
Visual desktop testing of the N-panel and a reference-Max comparison remain useful.

## References consulted

- Blender Mesh API: https://docs.blender.org/api/5.2/bpy.types.Mesh.html
- Blender Set Mesh Normal: https://docs.blender.org/api/current/bpy.types.GeometryNodeSetMeshNormal.html
- Blender source socket definitions: https://github.com/blender/blender/blob/main/source/blender/nodes/geometry/nodes/node_geo_set_mesh_normal.cc
- Autodesk TurboSmooth: https://help.autodesk.com/cloudhelp/2023/ENU/3DSMax-Modifiers/files/GUID-EA8FF838-B197-4565-9A85-71CE93DA4F68.htm

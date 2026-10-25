# SPDX-License-Identifier: GPL-3.0-or-later
"""Application commands: validate, plan, then commit one user action."""
from .ports import MeshRepositoryPort, NormalBackendPort, SubdivisionBackendPort
from .core import group_bit, toggle_masks


class SmoothingService:
    def __init__(self, repository: MeshRepositoryPort, backend: NormalBackendPort):
        self.repository = repository
        self.backend = backend

    def prepare(self, context, require_faces=False):
        obj = self.repository.editable_object(context)
        if require_faces and obj.mode != 'EDIT':
            raise ValueError("Enter Edit Mode and select faces")
        self.repository.validate_attributes(obj.data)
        self.backend.validate_stack(obj)
        return obj


    def change_groups(self, context, action, number=1):
        obj = self.prepare(context, require_faces=True)
        with self.repository.open_mesh(obj, write=True) as bm:
            selected = self.repository.selected_faces(bm)
            if not selected:
                raise ValueError("Select at least one visible face")
            masks = self.repository.masks_of(bm)
            message = "Smoothing groups updated"
            if action == 'TOGGLE':
                values = toggle_masks((masks[f.index] for f in selected), number)
                masks.update((f.index, value) for f, value in zip(selected, values))
            elif action == 'CLEAR':
                masks.update((f.index, 0) for f in selected)
            elif action == 'AUTO':
                assignment = self.repository.plan_auto(bm, masks, obj.pynkp_sg.angle)
                masks.update(assignment.masks)
                message = f"Auto Smooth assigned {assignment.used_groups} group(s)"
            else:
                raise ValueError("Unknown smoothing action")
            derived = self.repository.derive(bm, masks)
            normal = self.backend.ensure_normals(obj)
            self.backend.move_to(obj, normal, 0)
            self.repository.commit(bm, masks, derived)
        self.backend.sync_visibility(obj)
        obj.update_tag(refresh={'DATA'})
        return message


    def refresh(self, context):
        obj = self.prepare(context)
        with self.repository.open_mesh(obj, write=True) as bm:
            masks = self.repository.masks_of(bm)
            derived = self.repository.derive(bm, masks)
            normal = self.backend.ensure_normals(obj)
            self.backend.move_to(obj, normal, 0)
            self.repository.commit(bm, masks, derived)
        self.backend.sync_visibility(obj)
        obj.update_tag(refresh={'DATA'})


    def select_group(self, context, number):
        obj = self.prepare(context, require_faces=True)
        bit = group_bit(number)
        with self.repository.open_mesh(obj, write=True) as bm:
            masks = self.repository.masks_of(bm)
            # Replace the visible selection; never reveal hidden faces.
            for face in bm.faces:
                if not face.hide:
                    face.select_set(False)
            for edge in bm.edges:
                if not edge.hide:
                    edge.select_set(False)
            for vert in bm.verts:
                if not vert.hide:
                    vert.select_set(False)
            bm.select_mode = {'FACE'}
            for face in bm.faces:
                if not face.hide and masks[face.index] & bit:
                    face.select_set(True)
            bm.select_flush_mode()
        context.tool_settings.mesh_select_mode = (False, False, True)



class SubdivisionService:
    def __init__(self, smoothing: SmoothingService, backend: SubdivisionBackendPort):
        self.smoothing = smoothing
        self.backend = backend

    def add_subdivision(self, context):
        obj = self.smoothing.prepare(context)
        if self.backend.subdivision(obj):
            raise ValueError("An SG subdivision already exists")
        self.backend.validate_subdivision_support()
        self.smoothing.refresh(context)
        self.backend.add_subdivision(obj)

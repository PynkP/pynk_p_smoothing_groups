# SPDX-License-Identifier: GPL-3.0-or-later
"""Composition root: inject Blender adapters into independent services."""
from . import mesh_repository, node_backend
from .services import SmoothingService, SubdivisionService

smoothing = SmoothingService(mesh_repository, node_backend)
subdivision = SubdivisionService(smoothing, node_backend)

change_groups = smoothing.change_groups
select_group = smoothing.select_group
refresh = smoothing.refresh
add_subdivision = subdivision.add_subdivision

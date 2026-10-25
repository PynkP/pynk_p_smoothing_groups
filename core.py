# SPDX-License-Identifier: GPL-3.0-or-later
"""Blender-independent rules. Group IDs are bit positions, never labels to union.

Created by pynk_p.
"""
from __future__ import annotations

from dataclasses import dataclass
import heapq
from math import sqrt

GROUP_COUNT = 30
ALL_GROUPS = (1 << GROUP_COUNT) - 1


class GroupCapacityError(ValueError):
    """The deterministic assignment could not fit in the available palette."""


def group_bit(number: int) -> int:
    if not 1 <= number <= GROUP_COUNT:
        raise ValueError("Group must be between 1 and 30")
    return 1 << (number - 1)


def union_mask(masks) -> int:
    result = 0
    for mask in masks:
        result |= mask & ALL_GROUPS
    return result


def toggle_masks(masks, number: int) -> list[int]:
    """An illuminated union button removes the bit from ALL selected faces."""
    masks = list(masks)
    bit = group_bit(number)
    remove = bool(union_mask(masks) & bit)
    return [((m & ~bit) if remove else (m | bit)) & ALL_GROUPS for m in masks]


def share_group(a: int, b: int) -> bool:
    return bool(a & b & ALL_GROUPS)


def edge_is_boundary(masks) -> bool:
    masks = tuple(masks)
    # Open and non-manifold edges are not smoothed through.
    return len(masks) != 2 or not share_group(*masks)


def corner_normal(mask: int, own_normal, contributors):
    """Average one connected smoothing group of corners at this vertex."""
    mask &= ALL_GROUPS
    if not mask:
        return tuple(own_normal)

    contributors = tuple(contributors)
    connected_mask = mask

    # Expand only within the vertex fan supplied by mesh_repository.
    while True:
        previous_mask = connected_mask

        for other, normal, weight in contributors:
            if share_group(connected_mask, other):
                connected_mask |= other & ALL_GROUPS

        if connected_mask == previous_mask:
            break

    accum = [0.0, 0.0, 0.0]
    fallback = None

    for other, normal, weight in contributors:
        if not share_group(connected_mask, other):
            continue

        for axis in range(3):
            accum[axis] += normal[axis] * weight

        # Use the same fallback for all corners if normals cancel out.
        if fallback is None:
            normal_length = sqrt(sum(c * c for c in normal))

            if normal_length > 1e-12:
                fallback = tuple(c / normal_length for c in normal)

    length = sqrt(sum(c * c for c in accum))

    if length < 1e-12:
        return fallback if fallback is not None else tuple(own_normal)

    return tuple(c / length for c in accum)

@dataclass(frozen=True)
class AutoAssignment:
    masks: dict[int, int]
    used_groups: int
    patch_count: int


def auto_assign(faces, smooth_pairs, hard_pairs, forbidden=None) -> AutoAssignment:
    """Cover smooth relations without accidentally joining a hard relation.

    Greedily merge compatible regions, cover remaining smooth relations with
    overlapping patches, then color the patch conflict graph (DSATUR). A face
    may receive several bits. Disconnected compatible regions reuse bits.
    All computation is pure and completes before the caller changes a mesh.
    forbidden maps face IDs to bits used by untouched neighboring faces.
    Failure is explicit and atomic; it never silently wraps group IDs.
    """
    faces = set(faces)
    if not faces:
        return AutoAssignment({}, 0, 0)
    smooth = sorted({tuple(sorted(p)) for p in smooth_pairs if p[0] != p[1]})
    hard = sorted({tuple(sorted(p)) for p in hard_pairs if p[0] != p[1]})
    if any(a not in faces or b not in faces for a, b in smooth + hard):
        raise ValueError("Relations must reference selected faces")
    if set(smooth) & set(hard):
        raise ValueError("A face pair cannot be both smooth and hard")
    forbidden = forbidden or {}
    conflicts = {f: set() for f in faces}
    for a, b in hard:
        conflicts[a].add(b)
        conflicts[b].add(a)

    parent = {f: f for f in faces}
    members = {f: {f} for f in faces}

    def root(f):
        while parent[f] != f:
            parent[f] = parent[parent[f]]
            f = parent[f]
        return f

    for a, b in smooth:
        ra, rb = root(a), root(b)
        if ra == rb:
            continue
        if len(members[ra]) > len(members[rb]):
            ra, rb = rb, ra
        if any(conflicts[f] & members[rb] for f in members[ra]):
            continue
        parent[ra] = rb
        members[rb].update(members.pop(ra))

    patches = [members[k] for k in sorted(members)]
    membership = {f: set() for f in faces}
    for i, patch in enumerate(patches):
        for f in patch:
            membership[f].add(i)
    for a, b in smooth:
        if membership[a] & membership[b]:
            continue
        i = len(patches)
        patches.append({a, b})
        membership[a].add(i)
        membership[b].add(i)

    neighbors = [set() for _ in patches]
    for a, b in hard:
        for i in membership[a]:
            for j in membership[b]:
                if i == j:
                    raise AssertionError("Hard pair inside a patch")
                neighbors[i].add(j)
                neighbors[j].add(i)
    blocked = [union_mask(forbidden.get(f, 0) for f in patch) for patch in patches]
    colors = [-1] * len(patches)
    saturation = [set() for _ in patches]
    revision = [0] * len(patches)
    heap = [(-blocked[i].bit_count(), -len(neighbors[i]), i, 0)
            for i in range(len(patches))]
    heapq.heapify(heap)
    while heap:
        _, _, i, rev = heapq.heappop(heap)
        if colors[i] >= 0 or rev != revision[i]:
            continue
        unavailable = blocked[i]
        for color in saturation[i]:
            unavailable |= 1 << color
        available = ALL_GROUPS & ~unavailable
        if not available:
            raise GroupCapacityError(
                "Auto Smooth could not fit this selection into 30 groups. "
                "No groups were changed. Try a smaller selection or another angle.")
        bit = available & -available
        colors[i] = bit.bit_length() - 1
        for j in neighbors[i]:
            if colors[j] < 0 and colors[i] not in saturation[j]:
                saturation[j].add(colors[i])
                revision[j] += 1
                occupied = blocked[j]
                for c in saturation[j]:
                    occupied |= 1 << c
                heapq.heappush(heap, (-occupied.bit_count(), -len(neighbors[j]), j, revision[j]))

    result = {f: union_mask(1 << colors[i] for i in membership[f]) for f in faces}
    if any(not share_group(result[a], result[b]) for a, b in smooth):
        raise AssertionError("Lost smooth relation")
    if any(share_group(result[a], result[b]) for a, b in hard):
        raise AssertionError("Lost hard relation")
    return AutoAssignment(result, union_mask(result.values()).bit_count(), len(patches))

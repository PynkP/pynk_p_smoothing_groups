from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import itertools
import math
import random
import unittest

from pynkp_smoothing_groups.core import (
    ALL_GROUPS, GroupCapacityError, auto_assign, corner_normal,
    edge_is_boundary, group_bit, share_group, toggle_masks, union_mask,
)


class GroupRulesTests(unittest.TestCase):
    def test_exact_requested_click_sequence(self):
        masks = [0]
        for number, expected in [(1, 1), (2, 3), (2, 1), (1, 0)]:
            masks = toggle_masks(masks, number)
            self.assertEqual(masks, [expected])

    def test_union_button_removes_from_all_even_partial(self):
        self.assertEqual(union_mask([3, 6]), 7)
        self.assertEqual(toggle_masks([3, 6], 1), [2, 6])
        self.assertEqual(toggle_masks([2, 6], 1), [3, 7])

    def test_group_30_positive_int(self):
        self.assertEqual(group_bit(30), 536870912)
        self.assertLess(ALL_GROUPS, 2**31)
        for n in [0, 31, -1]:
            with self.assertRaises(ValueError):
                group_bit(n)

    def test_boundaries_and_zero(self):
        for masks in [[], [1], [1, 2], [0, 0], [1, 1, 1]]:
            self.assertTrue(edge_is_boundary(masks))
        self.assertFalse(edge_is_boundary([1, 3]))

    def test_normals_do_not_transitively_union(self):
        contributors = [(1, (1, 0, 0), 1), (3, (0, 1, 0), 1), (2, (0, 0, 1), 1)]
        a = corner_normal(1, (1, 0, 0), contributors)
        b = corner_normal(3, (0, 1, 0), contributors)
        c = corner_normal(2, (0, 0, 1), contributors)
        self.assertEqual(a[2], 0)
        self.assertEqual(c[0], 0)
        self.assertAlmostEqual(a[0], 1 / math.sqrt(2))
        self.assertAlmostEqual(b[2], 1 / math.sqrt(3))
        self.assertEqual(corner_normal(0, (0, 0, 1), contributors), (0, 0, 1))

    def test_chain_hard_closure_requires_overlapping_groups(self):
        result = auto_assign(range(3), [(0, 1), (1, 2)], [(0, 2)]).masks
        self.assertTrue(share_group(result[0], result[1]))
        self.assertTrue(share_group(result[1], result[2]))
        self.assertFalse(share_group(result[0], result[2]))
        self.assertGreater(result[1].bit_count(), 1)

    def test_disconnected_regions_reuse_palette(self):
        result = auto_assign(range(500), [], [])
        self.assertEqual(result.used_groups, 1)

    def test_30_conflicting_regions(self):
        result = auto_assign(range(30), [], itertools.combinations(range(30), 2))
        self.assertEqual(result.used_groups, 30)

    def test_overflow_is_explicit(self):
        with self.assertRaises(GroupCapacityError):
            auto_assign(range(31), [], itertools.combinations(range(31), 2))

    def test_untouched_neighbors_reserved(self):
        result = auto_assign([0, 1], [(0, 1)], [], {0: 3, 1: 4})
        self.assertEqual(result.masks, {0: 8, 1: 8})
        with self.assertRaises(GroupCapacityError):
            auto_assign([0], [], [], {0: ALL_GROUPS})

    def test_random_relations_preserved(self):
        rng = random.Random(20261025)
        # Each original mask assignment is a constructive feasible solution.
        for _ in range(200):
            source = [rng.randrange(1, 32) for _ in range(9)]
            smooth, hard = [], []
            for a, b in itertools.combinations(range(9), 2):
                (smooth if share_group(source[a], source[b]) else hard).append((a, b))
            result = auto_assign(range(9), smooth, hard).masks
            for a, b in smooth:
                self.assertTrue(share_group(result[a], result[b]))
            for a, b in hard:
                self.assertFalse(share_group(result[a], result[b]))


if __name__ == '__main__':
    unittest.main()

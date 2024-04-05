#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import unittest

import ops
import ops.testing

from charm import KarapaceCharm


class TestCharm(unittest.TestCase):
    def setUp(self):
        self.harness = ops.testing.Harness(KarapaceCharm)
        self.addCleanup(self.harness.cleanup)

    def test_start(self):
        # Simulate the charm starting
        self.harness.begin_with_initial_hooks()

        # Ensure we set an ActiveStatus with no message
        self.assertEqual(self.harness.model.unit.status, ops.ActiveStatus())

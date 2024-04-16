#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from ops.testing import Harness
from src.literals import CONTAINER, SUBSTRATE, Status

from charm import KarapaceCharm

CONFIG = str(yaml.safe_load(Path("./config.yaml").read_text()))
ACTIONS = str(yaml.safe_load(Path("./actions.yaml").read_text()))
METADATA = str(yaml.safe_load(Path("./metadata.yaml").read_text()))
CHARM_KEY = "karapace"


@pytest.fixture
def harness() -> Harness:
    harness = Harness(KarapaceCharm, meta=METADATA, actions=ACTIONS, config=CONFIG)

    if SUBSTRATE == "k8s":
        harness.set_can_connect(CONTAINER, True)

    harness.add_relation("restart", CHARM_KEY)
    harness.begin()
    return harness


def test_install_blocks_snap_install_failure(harness: Harness):
    """Checks unit goes to BlockedStatus after snap failure on install hook."""
    with patch("workload.KarapaceWorkload.install", return_value=False):
        harness.charm.on.install.emit()
        assert harness.charm.unit.status == Status.SNAP_NOT_INSTALLED.value.status

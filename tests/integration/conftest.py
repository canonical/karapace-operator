#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

from pathlib import Path

import pytest
from pytest_operator.plugin import OpsTest


@pytest.fixture(scope="module")
async def karapace_charm(ops_test: OpsTest) -> Path:
    """Kafka charm used for integration testing."""
    charm = await ops_test.build_charm(".")
    return charm

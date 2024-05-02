#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def patched_workload_write():
    with patch("workload.KarapaceWorkload.write") as workload_write:
        yield workload_write


@pytest.fixture(autouse=True)
def patched_exec():
    with patch("workload.KarapaceWorkload.exec") as patched_exec:
        yield patched_exec

#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import asyncio
import logging

import pytest
from pytest_operator.plugin import OpsTest

from .helpers import (
    APP_NAME,
    KAFKA,
    ZOOKEEPER,
    DATA_INTEGRATOR,
)

logger = logging.getLogger(__name__)


@pytest.mark.abort_on_fail
async def test_build_and_deploy(ops_test: OpsTest, karapace_charm):
    """Build the charm-under-test and deploy it together with related charms.

    Assert on the unit status before any relations/configurations take place.
    """
    await ops_test.model.deploy(
        karapace_charm, application_name=APP_NAME, num_units=1, series="jammy"
    )
    await ops_test.model.wait_for_idle(apps=[APP_NAME], idle_period=30, timeout=3600)
    assert ops_test.model.applications[APP_NAME].status == "waiting"


@pytest.mark.abort_on_fail
async def test_integrate_kafka(ops_test: OpsTest):
    """Integrate charm with Kafka."""
    data_integrator_config = {
        "topic": "_schemas",
        "extra-user-roles": "admin",
        "consumer-group-prefix": "schema-registry",
    }
    await asyncio.gather(
            ops_test.model.deploy(
            ZOOKEEPER, channel="edge", application_name=ZOOKEEPER, num_units=1, series="jammy"
        ),
        ops_test.model.deploy(
            KAFKA, channel="edge", application_name=KAFKA, num_units=1, series="jammy"
        ),
        ops_test.model.deploy(
            DATA_INTEGRATOR,
            channel="edge",
            application_name=DATA_INTEGRATOR,
            num_units=1,
            series="jammy",
            config=data_integrator_config,
        ),
    )
    await ops_test.model.wait_for_idle(
        apps=[ZOOKEEPER, KAFKA, DATA_INTEGRATOR], idle_period=30, timeout=3600
    )

    await ops_test.model.add_relation(KAFKA, ZOOKEEPER)
    async with ops_test.fast_forward():
        await ops_test.model.wait_for_idle(apps=[KAFKA, ZOOKEEPER])
    
    await ops_test.model.add_relation(KAFKA, DATA_INTEGRATOR)
    async with ops_test.fast_forward():
        await ops_test.model.wait_for_idle(apps=[KAFKA, DATA_INTEGRATOR])

    assert ops_test.model.applications[KAFKA].status == "active"
    assert ops_test.model.applications[ZOOKEEPER].status == "active"
    assert ops_test.model.applications[DATA_INTEGRATOR].status == "active"

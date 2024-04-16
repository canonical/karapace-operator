#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import asyncio
import logging
from subprocess import PIPE, check_output

import pytest
from pytest_operator.plugin import OpsTest

from literals import PORT

from helpers import (
    APP_NAME,
    DATA_INTEGRATOR,
    KAFKA,
    ZOOKEEPER,
    check_socket,
    get_address,
    get_admin_credentials,
    get_data_integrator_credentials,
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
        "topic-name": "_schemas",
        "extra-user-roles": "admin",
        "consumer-group-prefix": "schema-registry",
    }
    await asyncio.gather(
        ops_test.model.deploy(
            ZOOKEEPER, channel="3/edge", application_name=ZOOKEEPER, series="jammy"
        ),
        ops_test.model.deploy(KAFKA, channel="3/edge", application_name=KAFKA, series="jammy"),
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

    data_integrator_creds = await get_data_integrator_credentials(ops_test)

    # FIXME
    await ops_test.model.applications[APP_NAME].set_config(
        {
            "username": data_integrator_creds["username"],
            "karapace_password": data_integrator_creds["password"],
            "bootstrap_servers": data_integrator_creds["endpoints"],
        }
    )

    await ops_test.model.wait_for_idle(apps=[APP_NAME])
    assert ops_test.model.applications[APP_NAME].status == "active"


@pytest.mark.abort_on_fail
async def test_service(ops_test: OpsTest):
    """Check that port is open."""
    address = await get_address(ops_test=ops_test)
    assert check_socket(address, PORT)


@pytest.mark.abort_on_fail
async def test_schema_creation(ops_test: OpsTest):
    """Check that a schema can be registered using internal credentials."""
    operator_password = await get_admin_credentials(ops_test)
    address = await get_address(ops_test=ops_test)
    command = " ".join(
        [
            "curl",
            "-u",
            f"operator:{operator_password}",
            "-X",
            "POST",
            "-H",
            '"Content-Type: application/vnd.schemaregistry.v1+json"',
            "--data",
            '\'{"schema": "{\\"type\\": \\"record\\", \\"name\\": \\"Obj\\", \\"fields\\":[{\\"name\\": \\"age\\", \\"type\\": \\"int\\"}]}"}\'',
            f"http://{address}:{PORT}/subjects/test-key/versions",
        ]
    )

    result = check_output(command, stderr=PIPE, shell=True, universal_newlines=True)
    assert '{"id":1}' in result

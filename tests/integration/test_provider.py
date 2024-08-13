#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import asyncio
import logging
from subprocess import PIPE, check_output

import pytest
from helpers import (
    APP_NAME,
    DUMMY_NAME,
    KAFKA,
    ZOOKEEPER,
    assert_list_schemas,
    get_address,
    get_application_credentials,
)
from pytest_operator.plugin import OpsTest

from literals import PORT

logger = logging.getLogger(__name__)


@pytest.mark.abort_on_fail
@pytest.mark.skip_if_deployed
async def test_build_and_deploy(ops_test: OpsTest, karapace_charm, app_charm):
    await asyncio.gather(
        ops_test.model.deploy(
            karapace_charm, application_name=APP_NAME, num_units=1, series="jammy"
        ),
        ops_test.model.deploy(
            ZOOKEEPER, channel="3/edge", application_name=ZOOKEEPER, series="jammy"
        ),
        ops_test.model.deploy(KAFKA, channel="3/edge", application_name=KAFKA, series="jammy"),
        ops_test.model.deploy(app_charm, application_name=DUMMY_NAME, num_units=1, series="jammy"),
    )

    await ops_test.model.add_relation(KAFKA, ZOOKEEPER)
    await ops_test.model.wait_for_idle(apps=[KAFKA, ZOOKEEPER])

    assert ops_test.model.applications[KAFKA].status == "active"
    assert ops_test.model.applications[ZOOKEEPER].status == "active"

    await ops_test.model.add_relation(KAFKA, APP_NAME)
    await ops_test.model.wait_for_idle(apps=[KAFKA, APP_NAME, DUMMY_NAME])

    assert ops_test.model.applications[APP_NAME].status == "active"


@pytest.mark.abort_on_fail
async def test_relate_requirer(ops_test: OpsTest):
    await ops_test.model.add_relation(APP_NAME, f"{DUMMY_NAME}:karapace-client-admin")
    await ops_test.model.wait_for_idle(apps=[APP_NAME, DUMMY_NAME])

    assert ops_test.model.applications[APP_NAME].status == "active"
    assert ops_test.model.applications[DUMMY_NAME].status == "active"

    admin_username, admin_password = await get_application_credentials(ops_test, role="admin")
    address = await get_address(ops_test=ops_test)
    command = " ".join(
        [
            "curl",
            "-u",
            f"{admin_username}:{admin_password}",
            "-X",
            "POST",
            "-H",
            '"Content-Type: application/vnd.schemaregistry.v1+json"',
            "--data",
            '\'{"schema": "{\\"type\\": \\"record\\", \\"name\\": \\"Obj\\", \\"fields\\":[{\\"name\\": \\"age\\", \\"type\\": \\"int\\"}]}"}\'',
            f"http://{address}:{PORT}/subjects/other-key/versions",
        ]
    )

    result = check_output(command, stderr=PIPE, shell=True, universal_newlines=True)
    assert '{"id":1}' in result

    await assert_list_schemas(ops_test, expected_schemas='["other-key"]')


@pytest.mark.abort_on_fail
async def test_scaling_karapace_with_requirer(ops_test: OpsTest):
    await ops_test.model.applications[APP_NAME].add_units(count=2)
    await ops_test.model.wait_for_idle(apps=[KAFKA, APP_NAME])

    assert ops_test.model.applications[APP_NAME].status == "active"

    # Add a second schema using the API on a different unit from the scaled app
    admin_username, admin_password = await get_application_credentials(ops_test, role="admin")
    address = await get_address(ops_test=ops_test, unit_num=2)
    command = " ".join(
        [
            "curl",
            "-u",
            f"{admin_username}:{admin_password}",
            "-X",
            "POST",
            "-H",
            '"Content-Type: application/vnd.schemaregistry.v1+json"',
            "--data",
            '\'{"schema": "{\\"type\\": \\"record\\", \\"name\\": \\"Obj\\", \\"fields\\":[{\\"name\\": \\"age\\", \\"type\\": \\"int\\"}]}"}\'',
            f"http://{address}:{PORT}/subjects/second-key/versions",
        ]
    )

    result = check_output(command, stderr=PIPE, shell=True, universal_newlines=True)
    assert '{"id":1}' in result

    await assert_list_schemas(ops_test, expected_schemas='["other-key","second-key"]')

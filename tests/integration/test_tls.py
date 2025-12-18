#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import asyncio
import logging

import pytest
import requests
from helpers import (
    APP_NAME,
    CA_FILE,
    KAFKA,
    SERIES,
    ZOOKEEPER,
    get_address,
    get_admin_credentials,
    set_tls_private_key,
)
from pytest_operator.plugin import OpsTest

from literals import PORT

logger = logging.getLogger(__name__)

TLS_NAME = "self-signed-certificates"
TLS_CHANNEL = "1/stable"


@pytest.mark.abort_on_fail
@pytest.mark.skip_if_deployed
async def test_deploy_tls(ops_test: OpsTest, karapace_charm):
    tls_config = {"ca-common-name": "kafka"}

    await asyncio.gather(
        ops_test.model.deploy(karapace_charm, application_name=APP_NAME, series=SERIES),
        ops_test.model.deploy(TLS_NAME, channel=TLS_CHANNEL, config=tls_config),
        ops_test.model.deploy(ZOOKEEPER, channel="3/stable", application_name=ZOOKEEPER),
        ops_test.model.deploy(KAFKA, channel="3/stable", application_name=KAFKA),
    )
    await ops_test.model.wait_for_idle(
        apps=[APP_NAME, ZOOKEEPER, KAFKA, TLS_NAME], idle_period=20, timeout=1800
    )

    assert ops_test.model.applications[APP_NAME].status == "blocked"
    assert ops_test.model.applications[KAFKA].status == "blocked"
    assert ops_test.model.applications[ZOOKEEPER].status == "active"
    assert ops_test.model.applications[TLS_NAME].status == "active"

    # Relate Zookeeper & Kafka to TLS
    await ops_test.model.add_relation(KAFKA, ZOOKEEPER)
    await ops_test.model.add_relation(TLS_NAME, ZOOKEEPER)
    await ops_test.model.add_relation(TLS_NAME, f"{KAFKA}:certificates")

    async with ops_test.fast_forward(fast_interval="60s"):
        await ops_test.model.wait_for_idle(
            apps=[TLS_NAME, ZOOKEEPER, KAFKA], idle_period=25, timeout=1800, status="active"
        )

    assert ops_test.model.applications[TLS_NAME].status == "active"
    assert ops_test.model.applications[ZOOKEEPER].status == "active"
    assert ops_test.model.applications[KAFKA].status == "active"


@pytest.mark.abort_on_fail
async def test_karapace_tls(ops_test: OpsTest):
    """Tests TLS on Karapace."""
    # Relate Kafka[TLS] to Karapace[Non-TLS]
    await ops_test.model.add_relation(KAFKA, APP_NAME)
    await ops_test.model.wait_for_idle(apps=[KAFKA], idle_period=15, timeout=1000, status="active")
    await ops_test.model.wait_for_idle(
        apps=[APP_NAME], idle_period=15, timeout=1000, status="blocked"
    )

    # Unit is on 'blocked' but whole app is on 'waiting'
    assert ops_test.model.applications[APP_NAME].status == "blocked"

    # Set a custom private key, by running set-tls-private-key action with no parameters,
    # as this will generate a random one
    await set_tls_private_key(ops_test)

    logger.info("Relate Karapace to TLS")
    await ops_test.model.add_relation(APP_NAME, TLS_NAME)
    await ops_test.model.wait_for_idle(
        apps=[APP_NAME, KAFKA, TLS_NAME], idle_period=30, timeout=1200, status="active"
    )

    assert ops_test.model.applications[APP_NAME].status == "active"
    assert ops_test.model.applications[KAFKA].status == "active"


@pytest.mark.abort_on_fail
async def test_schema_creation(ops_test: OpsTest):
    """Check that a schema can be registered using internal credentials."""
    # Store the CA cert for requests
    action = await ops_test.model.units.get(f"{TLS_NAME}/0").run_action("get-ca-certificate")
    ca = await action.wait()
    ca = ca.results.get("ca-certificate")
    open(CA_FILE, "w").write(ca)

    schema_name = "test-key"
    operator_password = await get_admin_credentials(ops_test)
    address = await get_address(ops_test=ops_test)
    base_url = f"https://{address}:{PORT}"
    auth = ("operator", operator_password)

    # Create the schema
    schema_data = {
        "schema": '{"type": "record", "name": "Obj", "fields":[{"name": "age", "type": "int"}]}'
    }

    response = requests.post(
        f"{base_url}/subjects/{schema_name}/versions",
        json=schema_data,
        headers={"Content-Type": "application/vnd.schemaregistry.v1+json"},
        auth=auth,
        verify=CA_FILE,
    )
    response.raise_for_status()
    result = response.text
    assert '{"id":1}' in result

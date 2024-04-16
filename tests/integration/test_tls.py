#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import asyncio
import logging

import pytest
from pytest_operator.plugin import OpsTest

from helpers import APP_NAME, DATA_INTEGRATOR, KAFKA, ZOOKEEPER

logger = logging.getLogger(__name__)

TLS_NAME = "self-signed-certificates"
CERTS_NAME = "tls-certificates-operator"


@pytest.mark.abort_on_fail
@pytest.mark.skip_if_deployed
async def test_deploy_tls(ops_test: OpsTest, karapace_charm):
    tls_config = {"ca-common-name": "kafka"}
    data_integrator_config = {
        "topic-name": "_schemas",
        "extra-user-roles": "admin",
        "consumer-group-prefix": "schema-registry",
    }

    await asyncio.gather(
        ops_test.model.deploy(karapace_charm, application_name=APP_NAME, series="jammy"),
        ops_test.model.deploy(TLS_NAME, channel="edge", config=tls_config, series="jammy"),
        ops_test.model.deploy(
            ZOOKEEPER, channel="3/edge", series="jammy", application_name=ZOOKEEPER
        ),
        ops_test.model.deploy(KAFKA, channel="3/edge", series="jammy", application_name=KAFKA),
        ops_test.model.deploy(
            DATA_INTEGRATOR,
            channel="edge",
            application_name=DATA_INTEGRATOR,
            series="jammy",
            config=data_integrator_config,
        ),
    )
    await ops_test.model.wait_for_idle(
        apps=[APP_NAME, ZOOKEEPER, KAFKA, TLS_NAME], idle_period=15, timeout=1800
    )

    assert ops_test.model.applications[APP_NAME].status == "waiting"
    assert ops_test.model.applications[KAFKA].status == "blocked"
    assert ops_test.model.applications[ZOOKEEPER].status == "active"
    assert ops_test.model.applications[TLS_NAME].status == "active"

    # Relate Zookeeper & Kafka to TLS
    async with ops_test.fast_forward():
        await ops_test.model.add_relation(TLS_NAME, ZOOKEEPER)
        await ops_test.model.add_relation(TLS_NAME, KAFKA)
        await ops_test.model.wait_for_idle(apps=[TLS_NAME, ZOOKEEPER, KAFKA], idle_period=15)

        assert ops_test.model.applications[TLS_NAME].status == "active"
        assert ops_test.model.applications[ZOOKEEPER].status == "active"
        assert ops_test.model.applications[KAFKA].status == "active"


@pytest.mark.skip(reason="No relation yet between kafka-karapace")
@pytest.mark.abort_on_fail
async def test_karapace_tls(ops_test: OpsTest):
    """Tests TLS on Karapace."""
    # Relate Kafka[TLS] to Karapace[Non-TLS]
    async with ops_test.fast_forward():
        await ops_test.model.add_relation(KAFKA, APP_NAME)
        await ops_test.model.wait_for_idle(
            apps=[KAFKA], idle_period=15, timeout=1000, status="active"
        )

        # Unit is on 'blocked' but whole app is on 'waiting'
        assert ops_test.model.applications[APP_NAME].status == "blocked"

    # Set a custom private key, by running set-tls-private-key action with no parameters,
    # as this will generate a random one
    # num_unit = 0
    # await set_tls_private_key(ops_test)

    # Extract the key
    # private_key = extract_private_key(
    #     show_unit(f"{APP_NAME}/{num_unit}", model_full_name=ops_test.model_full_name), unit=0
    # )

    # async with ops_test.fast_forward():
    #     logger.info("Relate Karapace to TLS")
    #     await ops_test.model.add_relation(APP_NAME, TLS_NAME)
    #     await ops_test.model.wait_for_idle(
    #         apps=[APP_NAME, KAFKA, TLS_NAME], idle_period=30, timeout=1200, status="active"
    #     )

    # assert ops_test.model.applications[APP_NAME].status == "active"
    # assert ops_test.model.applications[KAFKA].status == "active"

#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import asyncio
import logging

import pytest
from helpers import APP_NAME, KAFKA, ZOOKEEPER, set_tls_private_key
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)

TLS_NAME = "self-signed-certificates"
CERTS_NAME = "tls-certificates-operator"


@pytest.mark.abort_on_fail
@pytest.mark.skip_if_deployed
async def test_deploy_tls(ops_test: OpsTest, karapace_charm):
    tls_config = {"ca-common-name": "kafka"}

    await asyncio.gather(
        ops_test.model.deploy(karapace_charm, application_name=APP_NAME, series="jammy"),
        ops_test.model.deploy(TLS_NAME, channel="edge", config=tls_config, series="jammy"),
        ops_test.model.deploy(
            ZOOKEEPER, channel="3/edge", series="jammy", application_name=ZOOKEEPER
        ),
        ops_test.model.deploy(KAFKA, channel="3/edge", series="jammy", application_name=KAFKA),
    )
    await ops_test.model.wait_for_idle(
        apps=[APP_NAME, ZOOKEEPER, KAFKA, TLS_NAME], idle_period=15, timeout=1800
    )

    assert ops_test.model.applications[APP_NAME].status == "blocked"
    assert ops_test.model.applications[KAFKA].status == "blocked"
    assert ops_test.model.applications[ZOOKEEPER].status == "active"
    assert ops_test.model.applications[TLS_NAME].status == "active"

    # Relate Zookeeper & Kafka to TLS
    await ops_test.model.add_relation(KAFKA, ZOOKEEPER)
    await ops_test.model.add_relation(TLS_NAME, ZOOKEEPER)
    await ops_test.model.add_relation(TLS_NAME, f"{KAFKA}:certificates")
    await ops_test.model.wait_for_idle(apps=[TLS_NAME, ZOOKEEPER, KAFKA], idle_period=15)

    assert ops_test.model.applications[TLS_NAME].status == "active"
    assert ops_test.model.applications[ZOOKEEPER].status == "active"
    assert ops_test.model.applications[KAFKA].status == "active"


@pytest.mark.abort_on_fail
async def test_karapace_tls(ops_test: OpsTest):
    """Tests TLS on Karapace."""
    # Relate Kafka[TLS] to Karapace[Non-TLS]
    await ops_test.model.add_relation(KAFKA, APP_NAME)
    await ops_test.model.wait_for_idle(
        apps=[KAFKA], idle_period=15, timeout=1000, status="active"
    )
    await ops_test.model.wait_for_idle(
        apps=[KAFKA], idle_period=15, timeout=1000, status="blocked"
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

#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

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
from jubilant_adapters import JujuFixture, gather

from literals import PORT

logger = logging.getLogger(__name__)

TLS_NAME = "self-signed-certificates"
TLS_CHANNEL = "1/stable"


def test_deploy_tls(juju: JujuFixture, karapace_charm):
    tls_config = {"ca-common-name": "kafka"}

    gather(
        juju.ext.model.deploy(karapace_charm, application_name=APP_NAME, series=SERIES),
        juju.ext.model.deploy(TLS_NAME, channel=TLS_CHANNEL, config=tls_config),
        juju.ext.model.deploy(ZOOKEEPER, channel="3/stable", application_name=ZOOKEEPER),
        juju.ext.model.deploy(KAFKA, channel="3/stable", application_name=KAFKA),
    )
    juju.ext.model.wait_for_idle(
        apps=[APP_NAME, ZOOKEEPER, KAFKA, TLS_NAME], idle_period=20, timeout=1800
    )

    assert juju.ext.model.applications[APP_NAME].status == "blocked"
    assert juju.ext.model.applications[KAFKA].status == "blocked"
    assert juju.ext.model.applications[ZOOKEEPER].status == "active"
    assert juju.ext.model.applications[TLS_NAME].status == "active"

    # Relate Zookeeper & Kafka to TLS
    juju.ext.model.add_relation(KAFKA, ZOOKEEPER)
    juju.ext.model.add_relation(TLS_NAME, ZOOKEEPER)
    juju.ext.model.add_relation(TLS_NAME, f"{KAFKA}:certificates")

    with juju.ext.fast_forward(fast_interval="60s"):
        juju.ext.model.wait_for_idle(
            apps=[TLS_NAME, ZOOKEEPER, KAFKA], idle_period=25, timeout=1800, status="active"
        )

    assert juju.ext.model.applications[TLS_NAME].status == "active"
    assert juju.ext.model.applications[ZOOKEEPER].status == "active"
    assert juju.ext.model.applications[KAFKA].status == "active"


def test_karapace_tls(juju: JujuFixture):
    """Tests TLS on Karapace."""
    # Relate Kafka[TLS] to Karapace[Non-TLS]
    juju.ext.model.add_relation(KAFKA, APP_NAME)
    juju.ext.model.wait_for_idle(apps=[KAFKA], idle_period=15, timeout=1000, status="active")
    juju.ext.model.wait_for_idle(apps=[APP_NAME], idle_period=15, timeout=1000, status="blocked")

    # Unit is on 'blocked' but whole app is on 'waiting'
    assert juju.ext.model.applications[APP_NAME].status == "blocked"

    # Set a custom private key, by running set-tls-private-key action with no parameters,
    # as this will generate a random one
    set_tls_private_key(juju)

    logger.info("Relate Karapace to TLS")
    juju.ext.model.add_relation(APP_NAME, TLS_NAME)
    juju.ext.model.wait_for_idle(
        apps=[APP_NAME, KAFKA, TLS_NAME], idle_period=30, timeout=1200, status="active"
    )

    assert juju.ext.model.applications[APP_NAME].status == "active"
    assert juju.ext.model.applications[KAFKA].status == "active"


def test_schema_creation(juju: JujuFixture):
    """Check that a schema can be registered using internal credentials."""
    # Store the CA cert for requests
    action = juju.ext.model.units.get(f"{TLS_NAME}/0").run_action("get-ca-certificate")
    ca = action.wait()
    ca = ca.results.get("ca-certificate")
    open(CA_FILE, "w").write(ca)

    schema_name = "test-key"
    operator_password = get_admin_credentials(juju)
    address = get_address(juju=juju)
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

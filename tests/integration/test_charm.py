#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from subprocess import PIPE, check_output

import pytest
from helpers import (
    APP_NAME,
    KAFKA,
    SERIES,
    ZOOKEEPER,
    assert_list_schemas,
    check_socket,
    get_address,
    get_admin_credentials,
)
from jubilant_adapters import JujuFixture, gather

from literals import PORT

logger = logging.getLogger(__name__)


def test_build_and_deploy(juju: JujuFixture, karapace_charm):
    """Build the charm-under-test and deploy it together with related charms.

    Assert on the unit status before any relations/configurations take place.
    """
    juju.ext.model.deploy(
        karapace_charm,
        application_name=APP_NAME,
        num_units=1,
        series=SERIES,
    )
    juju.ext.model.wait_for_idle(apps=[APP_NAME], idle_period=30, timeout=3600)
    assert juju.ext.model.applications[APP_NAME].status == "blocked"


def test_integrate_kafka(juju: JujuFixture):
    """Integrate charm with Kafka."""
    gather(
        juju.ext.model.deploy(
            ZOOKEEPER, channel="3/stable", application_name=ZOOKEEPER, series="jammy"
        ),
        juju.ext.model.deploy(KAFKA, channel="3/stable", application_name=KAFKA, series="jammy"),
    )
    juju.ext.model.wait_for_idle(apps=[ZOOKEEPER, KAFKA], idle_period=30, timeout=3600)

    juju.ext.model.add_relation(KAFKA, ZOOKEEPER)
    juju.ext.model.wait_for_idle(apps=[KAFKA, ZOOKEEPER])

    assert juju.ext.model.applications[KAFKA].status == "active"
    assert juju.ext.model.applications[ZOOKEEPER].status == "active"

    juju.ext.model.add_relation(KAFKA, APP_NAME)
    juju.ext.model.wait_for_idle(apps=[KAFKA, APP_NAME])

    juju.ext.model.wait_for_idle(apps=[APP_NAME, KAFKA])
    assert juju.ext.model.applications[APP_NAME].status == "active"


def test_service(juju: JujuFixture):
    """Check that port is open."""
    address = get_address(juju=juju)
    assert check_socket(address, PORT)


def test_schema_creation(juju: JujuFixture):
    """Check that a schema can be registered using internal credentials."""
    operator_password = get_admin_credentials(juju)
    address = get_address(juju=juju)
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

    assert_list_schemas(juju, expected_schemas='["test-key"]')


@pytest.mark.skip
def test_scale_up_kafka(juju: JujuFixture):
    """Scale up Kafka charm."""
    juju.ext.model.applications[KAFKA].add_units(count=2)
    juju.ext.model.wait_for_idle(apps=[ZOOKEEPER, KAFKA, APP_NAME])

    assert juju.ext.model.applications[APP_NAME].status == "active"

    # Schema added on the previous test, checks that karapace is still working
    assert_list_schemas(juju, expected_schemas='["test-key"]')


def test_scale_up(juju: JujuFixture):
    """Scale up Karapace charm."""
    juju.ext.model.applications[APP_NAME].add_units(count=2)
    juju.ext.model.wait_for_idle(apps=[KAFKA, APP_NAME], status="active")

    assert juju.ext.model.applications[APP_NAME].status == "active"

    # Schema added on the previous test, checks that karapace is still working
    assert_list_schemas(juju, expected_schemas='["test-key"]', units=3)


def test_scale_down(juju: JujuFixture):
    """Scale down Karapace charm."""
    juju.ext.model.applications[APP_NAME].destroy_units(f"{APP_NAME}/1")
    juju.ext.model.applications[APP_NAME].destroy_units(f"{APP_NAME}/2")
    juju.ext.model.wait_for_idle(apps=[KAFKA, APP_NAME], wait_for_exact_units=2)

    assert juju.ext.model.applications[APP_NAME].status == "active"

    # Schema added on the previous test, checks that karapace is still working
    assert_list_schemas(juju, expected_schemas='["test-key"]')

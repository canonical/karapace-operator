#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import logging
from subprocess import PIPE, check_output

from helpers import (
    APP_NAME,
    DUMMY_NAME,
    KAFKA,
    SERIES,
    ZOOKEEPER,
    assert_list_schemas,
    get_address,
    get_application_credentials,
)
from jubilant_adapters import JujuFixture, gather

from literals import PORT

logger = logging.getLogger(__name__)


def test_build_and_deploy(juju: JujuFixture, karapace_charm, app_charm):
    gather(
        juju.ext.model.deploy(
            karapace_charm,
            application_name=APP_NAME,
            num_units=1,
            series=SERIES,
        ),
        juju.ext.model.deploy(
            ZOOKEEPER, channel="3/stable", application_name=ZOOKEEPER, series="jammy"
        ),
        juju.ext.model.deploy(KAFKA, channel="3/stable", application_name=KAFKA, series="jammy"),
        juju.ext.model.deploy(app_charm, application_name=DUMMY_NAME, num_units=1, series="jammy"),
    )

    juju.ext.model.add_relation(KAFKA, ZOOKEEPER)
    juju.ext.model.wait_for_idle(
        apps=[KAFKA, ZOOKEEPER], status="active", idle_period=60, timeout=1000
    )

    assert juju.ext.model.applications[KAFKA].status == "active"
    assert juju.ext.model.applications[ZOOKEEPER].status == "active"

    juju.ext.model.add_relation(KAFKA, APP_NAME)
    juju.ext.model.wait_for_idle(
        apps=[KAFKA, APP_NAME, DUMMY_NAME], status="active", idle_period=60, timeout=1000
    )

    assert juju.ext.model.applications[APP_NAME].status == "active"


def test_relate_requirer(juju: JujuFixture):
    juju.ext.model.add_relation(APP_NAME, f"{DUMMY_NAME}:karapace-client-admin")
    juju.ext.model.wait_for_idle(apps=[APP_NAME, DUMMY_NAME])

    assert juju.ext.model.applications[APP_NAME].status == "active"
    assert juju.ext.model.applications[DUMMY_NAME].status == "active"

    admin_username, admin_password = get_application_credentials(juju, role="admin")
    address = get_address(juju=juju)
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

    assert_list_schemas(juju, expected_schemas='["other-key"]')


def test_scaling_karapace_with_requirer(juju: JujuFixture):
    juju.ext.model.applications[APP_NAME].add_units(count=2)
    juju.ext.model.wait_for_idle(apps=[KAFKA, APP_NAME])

    assert juju.ext.model.applications[APP_NAME].status == "active"

    # Add a second schema using the API on a different unit from the scaled app
    admin_username, admin_password = get_application_credentials(juju, role="admin")
    address = get_address(juju=juju, unit_num=2)
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

    assert_list_schemas(juju, expected_schemas='["other-key","second-key"]', units=3)

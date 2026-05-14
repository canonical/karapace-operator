#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

from helpers import APP_NAME, KAFKA, SERIES, ZOOKEEPER, get_admin_credentials, set_password
from jubilant_adapters import JujuFixture, gather

logger = logging.getLogger(__name__)


def test_build_and_deploy(juju: JujuFixture, karapace_charm):
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
    )

    juju.ext.model.add_relation(KAFKA, ZOOKEEPER)
    juju.ext.model.wait_for_idle(
        apps=[KAFKA, ZOOKEEPER],
        idle_period=60,
        timeout=1000,
        status="active",
        raise_on_error=False,
    )

    assert juju.ext.model.applications[KAFKA].status == "active"
    assert juju.ext.model.applications[ZOOKEEPER].status == "active"

    juju.ext.model.add_relation(KAFKA, APP_NAME)
    juju.ext.model.wait_for_idle(
        apps=[KAFKA, APP_NAME], status="active", idle_period=60, timeout=1000
    )

    assert juju.ext.model.applications[APP_NAME].status == "active"


def test_password_rotation(juju: JujuFixture):
    """Check that password stored on Karapace has changed after a password rotation."""
    initial_operator_password = get_admin_credentials(juju)

    result = set_password(juju, username="operator", num_unit=0)
    assert "operator-password" in result.keys()

    juju.ext.model.wait_for_idle(apps=[APP_NAME])

    new_operator_user = get_admin_credentials(juju)

    assert initial_operator_password != new_operator_user

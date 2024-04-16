#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

import logging

import pytest
from pytest_operator.plugin import OpsTest

from .helpers import APP_NAME, get_admin_credentials, set_password

logger = logging.getLogger(__name__)


@pytest.mark.abort_on_fail
@pytest.mark.skip_if_deployed
async def test_build_and_deploy(ops_test: OpsTest, karapace_charm):
    await ops_test.model.deploy(
        karapace_charm, application_name=APP_NAME, num_units=1, series="jammy"
    )

    await ops_test.model.wait_for_idle(apps=[APP_NAME])
    assert ops_test.model.applications[APP_NAME].status == "waiting"


async def test_password_rotation(ops_test: OpsTest):
    """Check that password stored on Karapace has changed after a password rotation."""
    initial_operator_password = await get_admin_credentials(ops_test)

    result = await set_password(ops_test, username="operator", num_unit=0)
    assert "operator-password" in result.keys()

    await ops_test.model.wait_for_idle(apps=[APP_NAME])

    new_operator_user = await get_admin_credentials(ops_test)

    assert initial_operator_password != new_operator_user
